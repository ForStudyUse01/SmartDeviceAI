import importlib
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


ensure_package("yaml", "pyyaml")
ensure_package("ultralytics")
ensure_package("torch")

import yaml
from ultralytics import YOLO
import torch


PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT / "Detection" / "SmartDeviceAI - 2.yolov8"
AUTOSPLIT_ROOT = PROJECT_ROOT / "Detection" / "autosplit_runtime"
DATA_YAML = AUTOSPLIT_ROOT / "data.yaml"
RUN_NAME = "rtx3050ti_smallset_auto"
EPOCHS = 80
IMGSZ = 640
BATCH = 16
TRAIN_RATIO = 0.85
SEED = 42
SAMPLE_PREDICT_COUNT = 8


def _image_files(images_dir: Path) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    return sorted(p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in exts)


def prepare_dataset_split() -> tuple[Path, list[Path]]:
    src_images = SOURCE_ROOT / "train" / "images"
    src_labels = SOURCE_ROOT / "train" / "labels"

    if not src_images.exists() or not src_labels.exists():
        raise FileNotFoundError(f"Expected dataset folders missing under: {SOURCE_ROOT}")

    images = _image_files(src_images)
    if not images:
        raise ValueError(f"No training images found in: {src_images}")

    pairs: list[tuple[Path, Path]] = []
    for image_path in images:
        label_path = src_labels / f"{image_path.stem}.txt"
        if not label_path.exists():
            raise ValueError(f"Missing label for image: {image_path}")
        pairs.append((image_path, label_path))

    random.seed(SEED)
    random.shuffle(pairs)
    split_idx = max(1, min(len(pairs) - 1, int(len(pairs) * TRAIN_RATIO)))
    train_pairs = pairs[:split_idx]
    val_pairs = pairs[split_idx:]

    if AUTOSPLIT_ROOT.exists():
        shutil.rmtree(AUTOSPLIT_ROOT)

    for split in ("train", "val"):
        (AUTOSPLIT_ROOT / split / "images").mkdir(parents=True, exist_ok=True)
        (AUTOSPLIT_ROOT / split / "labels").mkdir(parents=True, exist_ok=True)

    for image_path, label_path in train_pairs:
        shutil.copy2(image_path, AUTOSPLIT_ROOT / "train" / "images" / image_path.name)
        shutil.copy2(label_path, AUTOSPLIT_ROOT / "train" / "labels" / label_path.name)

    for image_path, label_path in val_pairs:
        shutil.copy2(image_path, AUTOSPLIT_ROOT / "val" / "images" / image_path.name)
        shutil.copy2(label_path, AUTOSPLIT_ROOT / "val" / "labels" / label_path.name)

    data = {
        "path": str(AUTOSPLIT_ROOT.resolve()),
        "train": "train/images",
        "val": "val/images",
        "names": ["laptop", "mobile", "powerbank", "tablet"],
        "nc": 4,
    }
    DATA_YAML.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    print(f"Prepared autosplit dataset at: {AUTOSPLIT_ROOT}")
    print(f"Total pairs: {len(pairs)} | Train: {len(train_pairs)} | Val: {len(val_pairs)}")
    return DATA_YAML, [p[0] for p in pairs]


def train_and_validate() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable. GPU training cannot proceed.")

    print(f"CUDA available: {torch.cuda.is_available()}")
    print(f"Using GPU: {torch.cuda.get_device_name(0)}")

    data_yaml_path, all_images = prepare_dataset_split()

    model = YOLO("yolov8n.pt")
    model.train(
        data=str(data_yaml_path),
        epochs=EPOCHS,
        imgsz=IMGSZ,
        batch=BATCH,
        device=0,
        workers=2,
        cache=True,
        patience=20,
        cos_lr=True,
        close_mosaic=10,
        degrees=5.0,
        scale=0.3,
        translate=0.08,
        fliplr=0.5,
        project="runs/detect",
        name=RUN_NAME,
        exist_ok=True,
        pretrained=True,
        optimizer="AdamW",
        lr0=0.002,
        lrf=0.02,
    )

    best_candidates = sorted(
        PROJECT_ROOT.glob(f"runs/**/{RUN_NAME}/weights/best.pt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not best_candidates:
        raise FileNotFoundError("best.pt not found in runs/** after training.")
    best_path = best_candidates[0]

    print(f"best.pt saved at: {best_path}")

    infer_model = YOLO(str(best_path))
    sample_images = all_images[:SAMPLE_PREDICT_COUNT]
    infer_model.predict(
        source=[str(p) for p in sample_images],
        save=True,
        imgsz=IMGSZ,
        conf=0.25,
        device=0,
        project="runs/predict",
        name=RUN_NAME,
        exist_ok=True,
    )

    pred_dir = PROJECT_ROOT / "runs" / "predict" / RUN_NAME
    generated = list(pred_dir.glob("*"))
    if not generated:
        raise RuntimeError(f"Prediction output folder is empty: {pred_dir}")

    print(f"Predictions verified. Output directory: {pred_dir}")
    print(f"Prediction files generated: {len(generated)}")


if __name__ == "__main__":
    train_and_validate()
