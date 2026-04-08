from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def collect_image_label_pairs(images_dir: Path, labels_dir: Path) -> list[tuple[Path, Path]]:
    if not images_dir.is_dir():
        raise FileNotFoundError(f"Images directory not found: {images_dir}")
    if not labels_dir.is_dir():
        raise FileNotFoundError(f"Labels directory not found: {labels_dir}")

    image_files = sorted(
        path for path in images_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not image_files:
        raise ValueError(f"No images found in: {images_dir}")

    pairs: list[tuple[Path, Path]] = []
    missing_labels: list[Path] = []

    for image_path in image_files:
        label_path = labels_dir / f"{image_path.stem}.txt"
        if not label_path.exists():
            missing_labels.append(label_path)
            continue
        pairs.append((image_path, label_path))

    if missing_labels:
        preview = "\n".join(str(path) for path in missing_labels[:10])
        raise ValueError(
            "Missing label files were found. Aborting without moving files.\n"
            f"Missing count: {len(missing_labels)}\n"
            f"Examples:\n{preview}"
        )

    return pairs


def prepare_output_dirs(output_root: Path) -> dict[str, Path]:
    directories = {
        "train_images": output_root / "train" / "images",
        "train_labels": output_root / "train" / "labels",
        "val_images": output_root / "val" / "images",
        "val_labels": output_root / "val" / "labels",
    }
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)
    return directories


def move_pairs(pairs: list[tuple[Path, Path]], image_target: Path, label_target: Path) -> None:
    for image_path, label_path in pairs:
        shutil.move(str(image_path), str(image_target / image_path.name))
        shutil.move(str(label_path), str(label_target / label_path.name))


def update_data_yaml(data_yaml: Path, dataset_root: Path) -> None:
    train_path = (dataset_root / "train" / "images").as_posix()
    val_path = (dataset_root / "val" / "images").as_posix()

    lines = data_yaml.read_text(encoding="utf-8").splitlines()
    updated_lines: list[str] = []
    train_written = False
    val_written = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("train:"):
            updated_lines.append(f"train: {train_path}")
            train_written = True
        elif stripped.startswith("val:"):
            updated_lines.append(f"val: {val_path}")
            val_written = True
        elif stripped.startswith("test:"):
            continue
        else:
            updated_lines.append(line)

    if not train_written:
        updated_lines.insert(0, f"train: {train_path}")
    if not val_written:
        insert_at = 1 if train_written or updated_lines and updated_lines[0].startswith("train:") else 0
        updated_lines.insert(insert_at, f"val: {val_path}")

    data_yaml.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8")


def split_dataset(
    source_root: Path,
    output_root: Path,
    data_yaml: Path,
    train_ratio: float,
    seed: int,
) -> None:
    images_dir = source_root / "train" / "images"
    labels_dir = source_root / "train" / "labels"

    pairs = collect_image_label_pairs(images_dir, labels_dir)
    rng = random.Random(seed)
    rng.shuffle(pairs)

    split_index = int(len(pairs) * train_ratio)
    if split_index <= 0 or split_index >= len(pairs):
        raise ValueError(
            f"Split would create an empty subset. Dataset size: {len(pairs)}, train ratio: {train_ratio}"
        )

    train_pairs = pairs[:split_index]
    val_pairs = pairs[split_index:]

    directories = prepare_output_dirs(output_root)
    move_pairs(train_pairs, directories["train_images"], directories["train_labels"])
    move_pairs(val_pairs, directories["val_images"], directories["val_labels"])
    update_data_yaml(data_yaml, output_root)

    print("Split complete.")
    print(f"Source dataset : {source_root}")
    print(f"Output dataset : {output_root}")
    print(f"data.yaml      : {data_yaml}")
    print(f"Total pairs    : {len(pairs)}")
    print(f"Train pairs    : {len(train_pairs)}")
    print(f"Val pairs      : {len(val_pairs)}")
    print(f"Seed           : {seed}")


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parent
    default_source_root = project_root / "Detection" / "SmartDeviceAI.yolov8"
    default_output_root = project_root / "dataset"
    default_data_yaml = default_source_root / "data.yaml"

    parser = argparse.ArgumentParser(
        description="Split a YOLOv8 dataset from train/images + train/labels into train/val folders."
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=default_source_root,
        help="Dataset root containing train/images and train/labels.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=default_output_root,
        help="Output dataset root to create train/ and val/ folders in.",
    )
    parser.add_argument(
        "--data-yaml",
        type=Path,
        default=default_data_yaml,
        help="Path to the YOLOv8 data.yaml file to update.",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.8,
        help="Train split ratio. Validation receives the remainder.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed used before splitting.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    split_dataset(
        source_root=args.source_root.resolve(),
        output_root=args.output_root.resolve(),
        data_yaml=args.data_yaml.resolve(),
        train_ratio=args.train_ratio,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
