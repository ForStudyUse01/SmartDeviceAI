from __future__ import annotations

import importlib
import logging
import random
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


def ensure_package(module_name: str, package_name: str | None = None) -> None:
    try:
        importlib.import_module(module_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name or module_name])


ensure_package("ultralytics")
ensure_package("yaml", "pyyaml")
ensure_package("PIL", "pillow")
ensure_package("torch")

import torch
import yaml
from PIL import Image
from ultralytics import YOLO


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("auto_label")

PROJECT_ROOT = Path(__file__).resolve().parent
DATASET_DIR = PROJECT_ROOT / "dataset"
RAW_IMAGES_DIR = DATASET_DIR / "images"
RAW_LABELS_DIR = DATASET_DIR / "labels"
TRAIN_IMAGES_DIR = DATASET_DIR / "images" / "train"
VAL_IMAGES_DIR = DATASET_DIR / "images" / "val"
TRAIN_LABELS_DIR = DATASET_DIR / "labels" / "train"
VAL_LABELS_DIR = DATASET_DIR / "labels" / "val"
DATA_YAML_PATH = DATASET_DIR / "data.yaml"

CLASS_TO_ID = {"mobile": 0, "laptop": 1, "tablet": 2}
YOLO_TARGET_ALIASES = {
    "mobile": {"cell phone", "mobile phone", "phone"},
    "laptop": {"laptop"},
    "tablet": {"tablet"},
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
SPLIT_RATIO = 0.8
RANDOM_SEED = 42


@dataclass
class LabelResult:
    image_path: Path
    label_path: Path
    class_name: str
    detections_written: int


def clean_output_dirs() -> None:
    for folder in [RAW_LABELS_DIR, TRAIN_IMAGES_DIR, VAL_IMAGES_DIR, TRAIN_LABELS_DIR, VAL_LABELS_DIR]:
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True, exist_ok=True)


def list_raw_images(class_name: str) -> list[Path]:
    class_dir = RAW_IMAGES_DIR / class_name
    if not class_dir.exists():
        return []
    return sorted([p for p in class_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS])


def yolo_line(class_id: int, xyxy: list[float], width: int, height: int) -> str:
    x1, y1, x2, y2 = xyxy
    x_center = ((x1 + x2) / 2.0) / width
    y_center = ((y1 + y2) / 2.0) / height
    box_w = (x2 - x1) / width
    box_h = (y2 - y1) / height
    return f"{class_id} {x_center:.6f} {y_center:.6f} {box_w:.6f} {box_h:.6f}"


def label_single_image(model: YOLO, class_name: str, image_path: Path, device: int | str) -> LabelResult | None:
    class_label_dir = RAW_LABELS_DIR / class_name
    class_label_dir.mkdir(parents=True, exist_ok=True)
    label_path = class_label_dir / f"{image_path.stem}.txt"

    with Image.open(image_path) as img:
        width, height = img.size

    results = model.predict(
        source=str(image_path),
        conf=0.25,
        device=device,
        verbose=False,
    )
    result = results[0]
    names = {int(k): str(v).lower() for k, v in result.names.items()}

    allowed_names = YOLO_TARGET_ALIASES[class_name]
    lines: list[str] = []
    for box in result.boxes:
        cls_id = int(box.cls.item())
        label_name = names.get(cls_id, "")
        if label_name not in allowed_names:
            continue
        xyxy = [float(v) for v in box.xyxy[0].tolist()]
        lines.append(yolo_line(CLASS_TO_ID[class_name], xyxy, width, height))

    if not lines:
        return None

    label_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return LabelResult(
        image_path=image_path,
        label_path=label_path,
        class_name=class_name,
        detections_written=len(lines),
    )


def auto_label_dataset() -> list[LabelResult]:
    model = YOLO("yolov8n.pt")
    device: int | str = 0 if torch.cuda.is_available() else "cpu"
    logger.info("Auto-label inference device: %s", "cuda:0" if device == 0 else "cpu")
    if not RAW_IMAGES_DIR.exists():
        raise FileNotFoundError(f"Dataset images not found: {RAW_IMAGES_DIR}")

    labeled: list[LabelResult] = []
    skipped = 0
    total = 0
    for class_name in CLASS_TO_ID:
        images = list_raw_images(class_name)
        logger.info("[%s] raw images: %d", class_name, len(images))
        for image_path in images:
            total += 1
            item = label_single_image(model, class_name, image_path, device=device)
            if item is None:
                skipped += 1
                continue
            labeled.append(item)

    logger.info("Auto-labeling complete. total=%d labeled=%d skipped_no_detection=%d", total, len(labeled), skipped)
    return labeled


def split_and_copy(labeled: list[LabelResult]) -> None:
    random.seed(RANDOM_SEED)
    by_class: dict[str, list[LabelResult]] = {c: [] for c in CLASS_TO_ID}
    for item in labeled:
        by_class[item.class_name].append(item)

    total_train = 0
    total_val = 0

    for class_name, items in by_class.items():
        random.shuffle(items)
        split_idx = int(len(items) * SPLIT_RATIO)
        train_items = items[:split_idx]
        val_items = items[split_idx:]

        for split_name, split_items in (("train", train_items), ("val", val_items)):
            for index, item in enumerate(split_items):
                safe_name = f"{class_name}_{item.image_path.stem}_{index}{item.image_path.suffix.lower()}"
                target_image = (TRAIN_IMAGES_DIR if split_name == "train" else VAL_IMAGES_DIR) / safe_name
                target_label = (TRAIN_LABELS_DIR if split_name == "train" else VAL_LABELS_DIR) / f"{target_image.stem}.txt"

                shutil.copy2(item.image_path, target_image)
                shutil.copy2(item.label_path, target_label)

        total_train += len(train_items)
        total_val += len(val_items)
        logger.info("[%s] train=%d val=%d", class_name, len(train_items), len(val_items))

    logger.info("Split complete. train=%d val=%d", total_train, total_val)


def write_data_yaml() -> None:
    data = {
        "path": str(DATASET_DIR.resolve()),
        "train": "images/train",
        "val": "images/val",
        "names": CLASS_TO_ID,
    }
    DATA_YAML_PATH.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    logger.info("Wrote data.yaml: %s", DATA_YAML_PATH)


def main() -> None:
    clean_output_dirs()
    labeled = auto_label_dataset()
    if not labeled:
        raise RuntimeError("No labels were generated. Training cannot continue with empty labels.")
    split_and_copy(labeled)
    write_data_yaml()


if __name__ == "__main__":
    main()
