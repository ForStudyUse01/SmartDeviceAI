import importlib
import subprocess
import sys
from pathlib import Path


def ensure_package(module_name: str, package_name: str | None = None) -> None:
    try:
        importlib.import_module(module_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name or module_name])


ensure_package("torch")
ensure_package("ultralytics")
ensure_package("yaml", "pyyaml")

import yaml
from ultralytics import YOLO


BASE_DIR = Path(r"C:/State-Secrets/Projects/INFT/SB Project - clone 2/Dataset")
CLASS_NAMES = ["mobile", "laptop", "tablet", "powerbank", "other"]
DATA_YAML_PATH = BASE_DIR / "data.yaml"
SAMPLE_PREDICTION_COUNT = 5


def find_images_and_labels():
    images = []
    labels_missing = []

    for class_name in CLASS_NAMES:
        class_dir = BASE_DIR / class_name
        if not class_dir.exists():
            continue

        for image_path in class_dir.iterdir():
            if image_path.is_file() and image_path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                images.append(image_path)
                label_path = image_path.with_suffix(".txt")
                if not label_path.exists():
                    labels_missing.append(image_path)

    return images, labels_missing


def create_data_yaml() -> None:
    data = {
        "path": str(BASE_DIR),
        "train": ".",
        "val": ".",
        "names": {index: name for index, name in enumerate(CLASS_NAMES)},
    }
    DATA_YAML_PATH.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def print_metrics(results) -> None:
    metrics = results.results_dict
    map50 = metrics.get("metrics/mAP50(B)", "n/a")
    map5095 = metrics.get("metrics/mAP50-95(B)", "n/a")
    precision = metrics.get("metrics/precision(B)", "n/a")
    recall = metrics.get("metrics/recall(B)", "n/a")

    print(f"mAP50: {map50}")
    print(f"mAP50-95: {map5095}")
    print(f"precision: {precision}")
    print(f"recall: {recall}")


def run_predictions(model: YOLO, images: list[Path]) -> None:
    sample_images = images[:SAMPLE_PREDICTION_COUNT]
    if not sample_images:
        print("No sample images available for prediction.")
        return

    print("Running prediction on sample images...")
    model.predict(source=[str(path) for path in sample_images], save=True, imgsz=640)


def main() -> None:
    if not BASE_DIR.exists():
        print(f"Dataset folder not found: {BASE_DIR}")
        return

    images, labels_missing = find_images_and_labels()

    if not images:
        print(f"No images found in dataset: {BASE_DIR}")
        return

    if labels_missing:
        print("YOLOv8 detection training requires annotation .txt files for every image.")
        print(f"Images found: {len(images)}")
        print(f"Images missing labels: {len(labels_missing)}")
        print("Example images missing labels:")
        for image_path in labels_missing[:10]:
            print(f"- {image_path}")
        print("Training was not started because the dataset is not in YOLO detection format yet.")
        return

    create_data_yaml()
    print(f"Created data.yaml at: {DATA_YAML_PATH}")

    model = YOLO("yolov8s.pt")
    results = model.train(
        data=str(DATA_YAML_PATH),
        epochs=50,
        imgsz=640,
        batch=8,
        patience=10,
        augment=True,
    )

    print_metrics(results)
    run_predictions(model, images)
    print("Best model path: runs/detect/train/weights/best.pt")


if __name__ == "__main__":
    main()
