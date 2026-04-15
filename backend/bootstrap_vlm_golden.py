#!/usr/bin/env python
"""
Build a small `vlm_golden.jsonl` from an existing JSONL by keeping only rows whose
image files exist, with simple diversity on (condition, damage).
Run from repo root or `backend/` (paths are resolved against --image-root).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bootstrap vlm_golden.jsonl from val/train JSONL.")
    p.add_argument("--source-jsonl", type=Path, default=_BACKEND_DIR / "data/vlm_val.jsonl")
    p.add_argument("--out-jsonl", type=Path, default=_BACKEND_DIR / "data/vlm_golden.jsonl")
    p.add_argument(
        "--image-root",
        type=Path,
        default=_REPO_ROOT,
        help="Repo root (or folder) used to resolve relative image paths",
    )
    p.add_argument("--limit", type=int, default=12, help="Maximum rows to write")
    return p.parse_args()


def resolve_image(row: dict[str, Any], image_root: Path) -> Path:
    raw = Path(str(row.get("image", "")))
    if raw.is_absolute():
        return raw
    return (image_root / raw).resolve()


def main() -> None:
    args = parse_args()
    src = args.source_jsonl.resolve()
    out = args.out_jsonl.resolve()
    image_root = args.image_root.resolve()

    if not src.is_file():
        raise SystemExit(f"Source JSONL not found: {src}")

    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    with src.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "image" not in row:
                continue
            path = resolve_image(row, image_root)
            if not path.is_file():
                continue
            key = (str(row.get("condition", "Average")), str(row.get("damage", "Not Broken")))
            buckets[key].append(row)

    picked: list[dict[str, Any]] = []
    # Round-robin across buckets for spread, then fill remainder.
    keys = sorted(buckets.keys(), key=lambda k: (k[0], k[1]))
    while len(picked) < args.limit and keys:
        progressed = False
        for key in list(keys):
            rows = buckets.get(key) or []
            if not rows:
                keys.remove(key)
                continue
            picked.append(rows.pop(0))
            progressed = True
            if len(picked) >= args.limit:
                break
        if not progressed:
            break

    if not picked:
        raise SystemExit(
            f"No rows with existing image files (source={src}, image_root={image_root}). "
            "Fix paths or download datasets, then retry."
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in picked:
            rel = Path(row["image"])
            if rel.is_absolute():
                try:
                    rel = rel.relative_to(image_root)
                except ValueError:
                    rel = Path(row["image"])
            row_out = {**row, "image": str(rel).replace("\\", "/")}
            f.write(json.dumps(row_out, ensure_ascii=False) + "\n")

    print(f"Wrote {len(picked)} rows -> {out}")


if __name__ == "__main__":
    main()
