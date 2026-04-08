from __future__ import annotations

import logging
import random
import shutil
import subprocess
from pathlib import Path

import torch
from ultralytics import YOLO


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("train_model")

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_YAML = PROJECT_ROOT / "dataset" / "data.yaml"
VAL_IMAGES = PROJECT_ROOT / "dataset" / "images" / "val"
RUNS_ROOT = PROJECT_ROOT / "runs"
ROOT_BEST = PROJECT_ROOT / "best.pt"


def train() -> None:
    command = [
        "yolo",
        "detect",
        "train",
        "model=yolov8n.pt",
        f"data={DATA_YAML}",
        "epochs=100",
        "imgsz=640",
        "batch=16",
    ]
    logger.info("Running: %s", " ".join(command))
    subprocess.check_call(command, cwd=str(PROJECT_ROOT))


def resolve_best() -> Path:
    candidates = sorted(
        RUNS_ROOT.glob("**/weights/best.pt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("Training finished but no best.pt found in runs/**/weights/")
    return candidates[0]


def integrate_model(best_path: Path) -> None:
    shutil.copy2(best_path, ROOT_BEST)
    logger.info("Integrated trained model: %s", ROOT_BEST)


def run_validation_samples() -> None:
    images = [p for p in VAL_IMAGES.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}]
    if not images:
        logger.warning("No validation images found for sample inference.")
        return

    sample = random.sample(images, min(5, len(images)))
    model = YOLO(str(ROOT_BEST))
    device = 0 if torch.cuda.is_available() else "cpu"
    for image_path in sample:
        results = model.predict(source=str(image_path), conf=0.25, device=device, verbose=False)
        result = results[0]
        if len(result.boxes) == 0:
            logger.info("[sample] %s -> no detections", image_path.name)
            continue
        for box in result.boxes:
            cls_id = int(box.cls.item())
            label = result.names.get(cls_id, str(cls_id))
            conf = float(box.conf.item())
            logger.info("[sample] %s -> %s (%.3f)", image_path.name, label, conf)


def main() -> None:
    if not DATA_YAML.exists():
        raise FileNotFoundError(f"Missing data.yaml: {DATA_YAML}")
    train()
    best = resolve_best()
    integrate_model(best)
    run_validation_samples()


if __name__ == "__main__":
    main()
