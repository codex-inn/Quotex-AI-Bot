"""Extract Quotex screenshot ZIPs and create a human-review annotation manifest.

This does NOT invent chart labels or train a model. Review annotations.csv first,
then move reviewed images into class folders for the existing training script.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import zipfile
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--zip-dir", default="data/incoming_zips")
    p.add_argument("--images-dir", default="data/raw_screenshots")
    p.add_argument("--manifest", default="data/annotations.csv")
    args = p.parse_args()

    zip_dir = Path(args.zip_dir)
    images_dir = Path(args.images_dir)
    manifest = Path(args.manifest)
    images_dir.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    seen = set()
    archives = sorted(zip_dir.glob("*.zip"))
    if not archives:
        raise SystemExit(f"No ZIP files found in {zip_dir}")

    for archive in archives:
        source = "demo" if "demo" in archive.name.lower() else "live" if "live" in archive.name.lower() else "unknown"
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                src = Path(member.filename)
                if member.is_dir() or src.suffix.lower() not in IMAGE_EXTS:
                    continue
                digest = hashlib.sha256(zf.read(member)).hexdigest()
                if digest in seen:
                    continue
                seen.add(digest)
                batch = archive.stem.replace(" ", "_")
                dest_dir = images_dir / source / batch
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / src.name
                if not dest.exists():
                    dest.write_bytes(zf.read(member))
                rows.append({
                    "image_path": dest.as_posix(),
                    "sha256": digest,
                    "source": source,
                    "timeframe": "M1",
                    "asset": "unknown",
                    "session_group": batch,
                    "scene_label": "",
                    "pattern_label": "",
                    "next_candle_outcome": "",
                    "review_status": "unreviewed",
                    "notes": "",
                })

    fields = ["image_path", "sha256", "source", "timeframe", "asset",
              "session_group", "scene_label", "pattern_label",
              "next_candle_outcome", "review_status", "notes"]
    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Extracted/registered {len(rows)} unique images from {len(archives)} ZIP archives.")
    print(f"Manifest: {manifest}")
    print("Labels are intentionally blank. Review each image before training.")


if __name__ == "__main__":
    main()
