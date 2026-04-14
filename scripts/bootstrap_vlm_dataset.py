from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAIN_JSONL = PROJECT_ROOT / "backend" / "data" / "vlm_train.jsonl"
VAL_JSONL = PROJECT_ROOT / "backend" / "data" / "vlm_val.jsonl"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build bootstrap VLM train/val JSONL from local image folders.")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--roots",
        nargs="+",
        default=["Dataset", "Detection"],
        help="Root folders to scan for images",
    )
    parser.add_argument("--max-samples", type=int, default=0, help="0 means all samples")
    parser.add_argument(
        "--target-broken-ratio",
        type=float,
        default=0.35,
        help="Oversample broken samples up to this ratio in the combined set.",
    )
    return parser.parse_args()


def _path_tokens(path: Path) -> set[str]:
    joined = " ".join(path.parts).lower().replace("-", " ").replace("_", " ")
    return {tok for tok in joined.split() if tok}


def _visual_scores(path: Path) -> tuple[float, float, float]:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 128.0, 32.0, 50.0
    brightness = float(np.mean(img))
    contrast = float(np.std(img))
    lap_var = float(cv2.Laplacian(img, cv2.CV_64F).var())
    return brightness, contrast, lap_var


def infer_labels(path: Path) -> tuple[str, str]:
    tokens = _path_tokens(path)

    if "broken" in tokens:
        return "Bad", "Broken"
    if "crack" in tokens or "cracked" in tokens or "damage" in tokens:
        return "Bad", "Broken"
    if "good" in tokens or "excellent" in tokens:
        return "Good", "Not Broken"
    if "average" in tokens or "fair" in tokens:
        return "Average", "Not Broken"
    if "poor" in tokens or "bad" in tokens:
        return "Bad", "Broken"

    brightness, contrast, lap_var = _visual_scores(path)
    # Heuristic fallback when folder labels are not present:
    # low sharpness and very low contrast tend to indicate poor/broken captures.
    if lap_var < 22 or (contrast < 28 and brightness < 90):
        return "Bad", "Broken"
    if lap_var < 45 or contrast < 38:
        return "Average", "Not Broken"
    return "Good", "Not Broken"


def infer_device_type(path: Path) -> str:
    text = str(path).lower()
    if "laptop" in text:
        return "laptop"
    if "tablet" in text:
        return "tablet"
    if "mobile" in text or "phone" in text:
        return "mobile"
    return "unknown"


def collect_rows(roots: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in IMAGE_EXTS:
                continue
            condition, damage = infer_labels(p)
            rows.append(
                {
                    "image": str(p.resolve()),
                    "condition": condition,
                    "damage": damage,
                    "device_type": infer_device_type(p),
                    "source": str(root),
                }
            )
    return rows


def main() -> None:
    args = parse_args()
    roots = [PROJECT_ROOT / r for r in args.roots]
    rows = collect_rows(roots)
    if not rows:
        raise RuntimeError("No images found in configured roots.")

    rng = random.Random(args.seed)
    broken = [r for r in rows if r.get("damage") == "Broken"]
    not_broken = [r for r in rows if r.get("damage") != "Broken"]
    if broken and not_broken:
        total = len(rows)
        current_ratio = len(broken) / total
        if current_ratio < args.target_broken_ratio:
            target_broken_count = int((args.target_broken_ratio * len(not_broken)) / (1 - args.target_broken_ratio))
            extra_needed = max(0, target_broken_count - len(broken))
            rows.extend(rng.choice(broken).copy() for _ in range(extra_needed))

    rng.shuffle(rows)
    if args.max_samples > 0:
        rows = rows[: args.max_samples]

    split_idx = int(len(rows) * (1 - args.val_ratio))
    train_rows = rows[:split_idx]
    val_rows = rows[split_idx:]

    TRAIN_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with TRAIN_JSONL.open("w", encoding="utf-8") as f:
        for row in train_rows:
            f.write(json.dumps(row) + "\n")
    with VAL_JSONL.open("w", encoding="utf-8") as f:
        for row in val_rows:
            f.write(json.dumps(row) + "\n")

    def count_by(rows_: list[dict], key: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in rows_:
            out[r[key]] = out.get(r[key], 0) + 1
        return out

    print(f"Total rows: {len(rows)}")
    print(f"Train rows: {len(train_rows)} -> {TRAIN_JSONL}")
    print(f"Val rows: {len(val_rows)} -> {VAL_JSONL}")
    print("Condition distribution:", count_by(rows, "condition"))
    print("Damage distribution:", count_by(rows, "damage"))


if __name__ == "__main__":
    main()
