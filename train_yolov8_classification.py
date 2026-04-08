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

from ultralytics import YOLO


DATASET_PATH = Path(r"C:/State-Secrets/Projects/INFT/SB Project - clone 2/Dataset")
CLASS_NAMES = ["mobile", "laptop", "tablet", "powerbank", "other"]
SAMPLE_COUNT = 5


def collect_sample_images() -> list[str]:
    sample_images = []
    for class_name in CLASS_NAMES:
        class_dir = DATASET_PATH / class_name
        if not class_dir.exists():
            continue

        for image_path in sorted(class_dir.iterdir()):
            if image_path.is_file() and image_path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                sample_images.append(str(image_path))
                if len(sample_images) >= SAMPLE_COUNT:
                    return sample_images
    return sample_images


def main() -> None:
    if not DATASET_PATH.exists():
        print(f"Dataset folder not found: {DATASET_PATH}")
        return

    model = YOLO("yolov8s-cls.pt")

    train_results = model.train(
        data=str(DATASET_PATH),
        epochs=50,
        imgsz=224,
        batch=16,
        augment=True,
    )

    metrics = train_results.results_dict
    top1 = metrics.get("metrics/accuracy_top1", "n/a")
    top5 = metrics.get("metrics/accuracy_top5", "n/a")

    print(f"top1 accuracy: {top1}")
    print(f"top5 accuracy: {top5}")
    print("Best model path: runs/classify/train/weights/best.pt")

    sample_images = collect_sample_images()
    if not sample_images:
        print("No sample images found for prediction.")
        return

    print("Running prediction on sample images...")
    prediction_results = model.predict(source=sample_images, imgsz=224, save=True)

    for image_path, result in zip(sample_images, prediction_results):
        top_class_index = int(result.probs.top1)
        top_class_name = result.names[top_class_index]
        confidence = float(result.probs.top1conf)
        print(f"{image_path} -> {top_class_name} ({confidence:.4f})")


if __name__ == "__main__":
    main()
