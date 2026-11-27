"""Review chart screenshots and sort them into labelled class folders.

Usage:
  py training/label_images.py --input data/quotex_images --output data/chart_images

Keys: 1-9 choose a class, A-E choose classes 10-14, 0 skip, Backspace undo,
Left/Right navigate. Labels describe visible chart structure/pattern only;
they do NOT mean the next candle will move that way.
"""
from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageOps

CLASSES = [
    "bullish_engulfing", "bearish_engulfing", "hammer", "shooting_star",
    "doji", "morning_star", "evening_star", "three_white_soldiers",
    "three_black_crows", "bullish_trend", "bearish_trend", "range",
    "breakout_up", "breakout_down",
]
KEYS = list("123456789abcde")
EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


class Reviewer:
    def __init__(self, root: tk.Tk, files: list[Path], output: Path):
        self.root, self.files, self.output = root, files, output
        self.index = 0
        self.photo = None
        self.history: list[tuple[Path, Path]] = []
        self.csv_path = output / "labels.csv"
        output.mkdir(parents=True, exist_ok=True)
        if not self.csv_path.exists():
            with self.csv_path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(["source_path", "label", "copied_path"])
        root.title("Quotex chart screenshot labeller")
        root.geometry("1100x760")
        root.configure(bg="#101827")
        self.title = tk.Label(root, fg="white", bg="#101827", font=("Segoe UI", 14, "bold"))
        self.title.pack(pady=8)
        self.canvas = tk.Label(root, bg="#0b1220")
        self.canvas.pack(fill="both", expand=True, padx=12, pady=8)
        self.help = tk.Label(root, fg="#cbd5e1", bg="#101827", justify="left",
            text="1-9: choose class  |  A-E: classes 10-14  |  0: skip  |  Backspace: undo  |  ←/→: navigate\n"
                 "Choose only what is visibly clear. If uncertain, skip. These are visual labels, not future-price outcomes.")
        self.help.pack(pady=8)
        self.status = tk.Label(root, fg="#93c5fd", bg="#101827")
        self.status.pack(pady=6)
        root.bind("<Key>", self.key)
        root.bind("<Left>", lambda _e: self.move(-1))
        root.bind("<Right>", lambda _e: self.move(1))
        self.show()

    def show(self):
        if not self.files:
            self.title.config(text="No images found.")
            return
        path = self.files[self.index]
        try:
            image = Image.open(path).convert("RGB")
            image.thumbnail((1020, 570))
            self.photo = ImageTk.PhotoImage(image)
            self.canvas.config(image=self.photo, text="")
        except Exception as exc:
            self.canvas.config(image="", text=f"Cannot open image: {exc}", fg="white")
        self.title.config(text=f"Image {self.index + 1}/{len(self.files)}  ·  {path.name}")
        self.status.config(text=f"Labelled: {len(self.history)} this session  ·  Output: {self.output}")

    def key(self, event):
        key = event.keysym.lower()
        if key in KEYS:
            self.label(CLASSES[KEYS.index(key)])
        elif key == "0":
            self.move(1)
        elif key == "backspace":
            self.undo()
        elif key == "left":
            self.move(-1)
        elif key == "right":
            self.move(1)

    def label(self, name: str):
        source = self.files[self.index]
        folder = self.output / name
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / source.name
        if destination.exists():
            destination = folder / f"{source.stem}_{self.index}{source.suffix}"
        shutil.copy2(source, destination)
        with self.csv_path.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([str(source), name, str(destination)])
        self.history.append((source, destination))
        self.move(1)

    def move(self, amount: int):
        if not self.files:
            return
        self.index = max(0, min(len(self.files) - 1, self.index + amount))
        self.show()

    def undo(self):
        if not self.history:
            return
        source, destination = self.history.pop()
        try:
            destination.unlink(missing_ok=True)
            # Remove the most recent matching CSV row by rewriting the log.
            rows = list(csv.reader(self.csv_path.open(encoding="utf-8")))
            for i in range(len(rows) - 1, 0, -1):
                if len(rows[i]) >= 3 and rows[i][2] == str(destination):
                    rows.pop(i)
                    break
            with self.csv_path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows(rows)
            self.index = self.files.index(source)
        except Exception as exc:
            messagebox.showerror("Undo failed", str(exc))
        self.show()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/quotex_images")
    parser.add_argument("--output", default="data/chart_images")
    args = parser.parse_args()
    source = Path(args.input)
    files = sorted(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in EXTS)
    if not files:
        raise SystemExit(f"No images found under {source}")
    root = tk.Tk()
    Reviewer(root, files, Path(args.output))
    root.mainloop()


if __name__ == "__main__":
    main()
