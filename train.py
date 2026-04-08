from __future__ import annotations

import argparse
import importlib
import logging
import random
import shutil
import subprocess
import sys
from pathlib import Path


def ensure_package(module_name: str, package_name: str | None = None) -> None:
    try:
        importlib.import_module(module_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name or module_name])


ensure_package("ultralytics")
ensure_package("PIL", "pillow")
ensure_package("yaml", "pyyaml")

import yaml
from PIL import Image, ImageDraw


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("train")

PROJECT_ROOT = Path(__file__).resolve().parent
DATASET_DIR = PROJECT_ROOT / "dataset"
DATA_YAML_PATH = DATASET_DIR / "data.yaml"
REVIEW_DIR = DATASET_DIR / "review_samples"
RUNS_DIR = PROJECT_ROOT / "runs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train YOLOv8 with manual labeled-image verification.")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--review-count", type=int, default=20)
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Skip prompt and continue training automatically.",
    )
    return parser.parse_args()


def load_data_yaml() -> dict:
    if not DATA_YAML_PATH.exists():
        raise FileNotFoundError(f"Missing data.yaml: {DATA_YAML_PATH}")
    return yaml.safe_load(DATA_YAML_PATH.read_text(encoding="utf-8"))


def yolo_to_xyxy(line: str, width: int, height: int) -> tuple[float, float, float, float] | None:
    parts = line.strip().split()
    if len(parts) != 5:
        return None
    _, xc, yc, bw, bh = map(float, parts)
    x_center = xc * width
    y_center = yc * height
    box_w = bw * width
    box_h = bh * height
    x1 = x_center - box_w / 2
    y1 = y_center - box_h / 2
    x2 = x_center + box_w / 2
    y2 = y_center + box_h / 2
    return (x1, y1, x2, y2)


def collect_labeled_pairs() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for split in ("train", "val"):
        image_dir = DATASET_DIR / "images" / split
        label_dir = DATASET_DIR / "labels" / split
        if not image_dir.exists() or not label_dir.exists():
            continue
        for image_path in image_dir.glob("*"):
            if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
                continue
            label_path = label_dir / f"{image_path.stem}.txt"
            if not label_path.exists():
                continue
            content = label_path.read_text(encoding="utf-8").strip()
            if not content:
                continue
            pairs.append((image_path, label_path))
    return pairs


def build_review_samples(pairs: list[tuple[Path, Path]], review_count: int) -> Path:
    if REVIEW_DIR.exists():
        shutil.rmtree(REVIEW_DIR)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    sample_count = min(review_count, len(pairs))
    selected = random.sample(pairs, sample_count)
    rendered_paths: list[Path] = []

    for idx, (image_path, label_path) in enumerate(selected, start=1):
        with Image.open(image_path) as image:
            img = image.convert("RGB")
            draw = ImageDraw.Draw(img)
            width, height = img.size
            lines = label_path.read_text(encoding="utf-8").strip().splitlines()
            for line in lines:
                xyxy = yolo_to_xyxy(line, width, height)
                if xyxy is None:
                    continue
                draw.rectangle(xyxy, outline=(255, 64, 64), width=3)

            out_path = REVIEW_DIR / f"{idx:02d}_{image_path.name}"
            img.save(out_path)
            rendered_paths.append(out_path)

    # Build a single contact-sheet for quick human review.
    thumb_w, thumb_h = 320, 240
    cols = 5
    rows = max(1, (len(rendered_paths) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * thumb_w, rows * thumb_h), color=(20, 20, 20))
    for i, path in enumerate(rendered_paths):
        with Image.open(path) as item:
            thumb = item.copy()
            thumb.thumbnail((thumb_w, thumb_h))
            x = (i % cols) * thumb_w
            y = (i // cols) * thumb_h
            px = x + (thumb_w - thumb.width) // 2
            py = y + (thumb_h - thumb.height) // 2
            sheet.paste(thumb, (px, py))

    sheet_path = REVIEW_DIR / "review_grid.jpg"
    sheet.save(sheet_path)
    logger.info("Review images generated at: %s", REVIEW_DIR)
    logger.info("Review contact-sheet: %s", sheet_path)
    return sheet_path


def require_manual_review(sheet_path: Path, auto_approve: bool) -> None:
    if auto_approve:
        logger.info("Manual review gate bypassed via --auto-approve")
        return
    logger.info("Manual review required. Please inspect: %s", sheet_path)
    answer = input("Type YES to continue training: ").strip().upper()
    if answer != "YES":
        raise RuntimeError("Training cancelled. Manual review was not approved.")


def run_training(epochs: int, imgsz: int) -> None:
    command = [
        "yolo",
        "detect",
        "train",
        "model=yolov8n.pt",
        f"data={DATA_YAML_PATH}",
        f"epochs={epochs}",
        f"imgsz={imgsz}",
    ]
    logger.info("Running training command: %s", " ".join(command))
    subprocess.check_call(command, cwd=str(PROJECT_ROOT))


def resolve_best_pt() -> Path:
    candidates = sorted(
        PROJECT_ROOT.glob("runs/**/weights/best.pt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No best.pt found after training in runs/**/weights/")
    return candidates[0]


def integrate_model(best_path: Path) -> Path:
    target = PROJECT_ROOT / "best.pt"
    shutil.copy2(best_path, target)
    logger.info("Integrated trained model at: %s", target)
    return target


def main() -> None:
    args = parse_args()
    _ = load_data_yaml()
    pairs = collect_labeled_pairs()
    if not pairs:
        raise RuntimeError("No labeled images found in dataset/images + dataset/labels. Run auto_label.py first.")

    logger.info("Labeled pairs available for training: %d", len(pairs))
    sheet_path = build_review_samples(pairs, args.review_count)
    require_manual_review(sheet_path, args.auto_approve)
    run_training(args.epochs, args.imgsz)
    best_path = resolve_best_pt()
    integrate_model(best_path)
    logger.info("Training + integration complete. best.pt source: %s", best_path)


if __name__ == "__main__":
    main()
