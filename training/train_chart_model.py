"""Train a chart-image classifier and export one ONNX model for browser + backend inference.

Dataset layout:
  data/chart_images/
    bullish_engulfing/*.jpg
    bearish_engulfing/*.jpg
    hammer/*.jpg
    shooting_star/*.jpg
    doji/*.jpg
    morning_star/*.jpg
    evening_star/*.jpg
    three_white_soldiers/*.jpg
    three_black_crows/*.jpg
    bullish_trend/*.jpg
    bearish_trend/*.jpg
    range/*.jpg
    breakout_up/*.jpg
    breakout_down/*.jpg

Only use chart screenshots you are allowed to use. Keep near-duplicate screenshots from
the same session in the same split; random image splits can leak information.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, models, transforms

IMAGE_SIZE = 224


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/chart_images")
    parser.add_argument("--out", default="models")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    random.seed(args.seed)
    torch.manual_seed(args.seed)

    root = Path(args.data)
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    if not root.exists():
        raise SystemExit(f"Dataset folder not found: {root}")
    train_tf = transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.RandomHorizontalFlip(p=0.15),
        transforms.ColorJitter(brightness=0.12, contrast=0.12, saturation=0.08),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    eval_tf = transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    base = datasets.ImageFolder(root, transform=train_tf)
    if len(base.classes) < 3 or len(base) < 90:
        raise SystemExit("Need at least 3 classes and 90 labelled images; aim for 100+ per class.")
    counts = {name: 0 for name in base.classes}
    for _, label in base.samples:
        counts[base.classes[label]] += 1
    if min(counts.values()) < 20:
        raise SystemExit("Every class needs at least 20 images; 100+ per class is recommended.")

    n_val = max(1, int(len(base) * 0.2))
    train_set, val_set = random_split(
        base, [len(base) - n_val, n_val],
        generator=torch.Generator().manual_seed(args.seed)
    )
    val_set.dataset = datasets.ImageFolder(root, transform=eval_tf)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    train_loader = DataLoader(train_set, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_set, batch_size=args.batch_size, shuffle=False, num_workers=0)

    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    model.fc = nn.Linear(model.fc.in_features, len(base.classes))
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=1e-4)
    loss_fn = nn.CrossEntropyLoss()
    best = 0.0
    for epoch in range(args.epochs):
        model.train()
        train_loss = 0.0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = loss_fn(model(images), labels)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(labels)
        model.eval()
        correct = total = 0
        with torch.no_grad():
            for images, labels in val_loader:
                logits = model(images.to(device))
                correct += (logits.argmax(1).cpu() == labels).sum().item()
                total += len(labels)
        accuracy = correct / max(1, total)
        print(f"epoch={epoch+1}/{args.epochs} train_loss={train_loss/len(train_set):.4f} val_accuracy={accuracy:.3f}")
        if accuracy > best:
            best = accuracy
            torch.save({"state_dict": model.cpu().state_dict(), "classes": base.classes}, output / "best_checkpoint.pt")
            model.to(device)

    checkpoint = torch.load(output / "best_checkpoint.pt", map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    dummy = torch.zeros(1, 3, IMAGE_SIZE, IMAGE_SIZE)
    torch.onnx.export(
        model, dummy, output / "quotex-chart.onnx",
        input_names=["image"], output_names=["logits"],
        dynamic_axes={"image": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=17,
    )
    (output / "labels.json").write_text(
        json.dumps({"classes": checkpoint["classes"], "image_size": IMAGE_SIZE,
                    "validation_accuracy": best}, indent=2),
        encoding="utf-8"
    )
    print(f"Exported {output/'quotex-chart.onnx'}; validation accuracy={best:.3f}")
    print("Evaluate on a separate unseen chronological test set before using predictions.")
    

if __name__ == "__main__":
    main()
