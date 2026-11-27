"""Prepare a human-review manifest from Quotex screenshot ZIP archives.

This does NOT assign pattern labels or train a model. Every image starts as
UNCLASSIFIED so the user can annotate it before supervised training.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import zipfile
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/screenshot_zips", help="Folder containing screenshot ZIP files")
    parser.add_argument("--images", default="data/quotex_images", help="Where extracted images are stored")
    parser.add_argument("--manifest", default="data/annotations.csv")
    args = parser.parse_args()

    input_dir = Path(args.input)
    image_dir = Path(args.images)
    image_dir.mkdir(parents=True, exist_ok=True)
    archives = sorted(input_dir.glob("*.zip"))
    if not archives:
        raise SystemExit(f"No ZIP archives found in {input_dir}")

    rows = []
    seen = set()
    for archive in archives:
        batch = archive.stem
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                source = Path(member.filename)
                if member.is_dir() or source.suffix.lower() not in IMAGE_EXTS:
                    continue
                data = zf.read(member)
                digest = hashlib.sha256(data).hexdigest()
                if digest in seen:
                    continue
                seen.add(digest)
                safe_name = f"{digest[:12]}_{source.name}"
                destination = image_dir / batch / safe_name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                rows.append({
                    "image_path": destination.as_posix(),
                    "source_batch": batch,
                    "timeframe": "M1",
                    "session_type": "unknown",
                    "asset": "unknown",
                    "market_structure": "UNCLASSIFIED",
                    "candle_pattern": "UNCLASSIFIED",
                    "next_candle_outcome": "UNKNOWN",
                    "review_status": "needs_human_review",
                })

    manifest = Path(args.manifest)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Extracted {len(rows)} unique images from {len(archives)} ZIP files.")
    print(f"Manifest: {manifest}")
    print("All labels are UNCLASSIFIED/UNKNOWN. Review and label before training.")


if __name__ == "__main__":
    main()
