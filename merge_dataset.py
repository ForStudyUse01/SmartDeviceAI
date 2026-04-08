from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path

import yaml


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("merge_dataset")

PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT / "roboflow_downloads"
OUT_ROOT = PROJECT_ROOT / "dataset"

TARGET_CLASSES = ["mobile", "laptop", "tablet", "powerbank"]
TARGET_ID = {name: index for index, name in enumerate(TARGET_CLASSES)}
SYNONYMS = {
    "mobile": "mobile",
    "phone": "mobile",
    "cellphone": "mobile",
    "cell phone": "mobile",
    "smartphone": "mobile",
    "laptop": "laptop",
    "notebook": "laptop",
    "tablet": "tablet",
    "powerbank": "powerbank",
    "power bank": "powerbank",
}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLIT_MAP = {"train": "train", "valid": "val", "val": "val"}


def clean_out_dir() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    for rel in ("images/train", "images/val", "labels/train", "labels/val"):
        (OUT_ROOT / rel).mkdir(parents=True, exist_ok=True)


def normalize_name(name: str) -> str | None:
    key = str(name).strip().lower().replace("-", " ").replace("_", " ")
    key = " ".join(key.split())
    return SYNONYMS.get(key)


def read_names(data_yaml: Path) -> dict[int, str]:
    content = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    names = content.get("names", {})
    if isinstance(names, list):
        return {i: str(v) for i, v in enumerate(names)}
    if isinstance(names, dict):
        mapped: dict[int, str] = {}
        for k, v in names.items():
            mapped[int(k)] = str(v)
        return mapped
    return {}


def valid_box(parts: list[str]) -> bool:
    if len(parts) != 5:
        return False
    try:
        _, x, y, w, h = map(float, parts)
    except ValueError:
        return False
    if w <= 0 or h <= 0:
        return False
    return 0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1


def hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    hasher.update(path.read_bytes())
    return hasher.hexdigest()


def merge_one_dataset(
    dataset_dir: Path,
    seen_hashes: set[str],
    class_counts: dict[str, int],
    image_counts: dict[str, int],
    image_class_counts: dict[str, int],
) -> None:
    data_yaml = dataset_dir / "data.yaml"
    if not data_yaml.exists():
        logger.warning("Skipping dataset without data.yaml: %s", dataset_dir)
        return
    names = read_names(data_yaml)
    dataset_name = dataset_dir.name

    for src_split, out_split in SPLIT_MAP.items():
        img_dir = dataset_dir / src_split / "images"
        lbl_dir = dataset_dir / src_split / "labels"
        if not img_dir.exists() or not lbl_dir.exists():
            continue

        for img_path in img_dir.iterdir():
            if not img_path.is_file() or img_path.suffix.lower() not in IMAGE_EXT:
                continue
            lbl_path = lbl_dir / f"{img_path.stem}.txt"
            if not lbl_path.exists():
                continue

            raw_lines = [line.strip() for line in lbl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            mapped_lines: list[str] = []
            classes_in_image: set[str] = set()
            for raw in raw_lines:
                parts = raw.split()
                if not valid_box(parts):
                    continue
                cls_idx = int(float(parts[0]))
                original_name = names.get(cls_idx, "")
                normalized = normalize_name(original_name)
                if normalized is None:
                    continue
                mapped_cls = TARGET_ID[normalized]
                mapped_lines.append(f"{mapped_cls} {parts[1]} {parts[2]} {parts[3]} {parts[4]}")
                class_counts[normalized] += 1
                classes_in_image.add(normalized)

            if not mapped_lines:
                continue

            digest = hash_file(img_path)
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)

            base = f"{dataset_name}_{img_path.stem}_{digest[:8]}"
            out_img = OUT_ROOT / "images" / out_split / f"{base}{img_path.suffix.lower()}"
            out_lbl = OUT_ROOT / "labels" / out_split / f"{base}.txt"
            shutil.copy2(img_path, out_img)
            out_lbl.write_text("\n".join(mapped_lines) + "\n", encoding="utf-8")
            image_counts[out_split] += 1
            for normalized in classes_in_image:
                image_class_counts[normalized] += 1


def write_data_yaml() -> None:
    content = {
        "path": str(OUT_ROOT.resolve()),
        "train": "images/train",
        "val": "images/val",
        "names": {i: name for i, name in enumerate(TARGET_CLASSES)},
    }
    (OUT_ROOT / "data.yaml").write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")


def main() -> None:
    if not SOURCE_ROOT.exists():
        raise FileNotFoundError(f"Source datasets folder not found: {SOURCE_ROOT}")

    clean_out_dir()
    seen_hashes: set[str] = set()
    class_counts = {name: 0 for name in TARGET_CLASSES}
    image_class_counts = {name: 0 for name in TARGET_CLASSES}
    image_counts = {"train": 0, "val": 0}

    for dataset_dir in sorted([p for p in SOURCE_ROOT.iterdir() if p.is_dir()]):
        merge_one_dataset(dataset_dir, seen_hashes, class_counts, image_counts, image_class_counts)

    write_data_yaml()

    logger.info("Merged dataset complete.")
    logger.info("Image counts: train=%d val=%d", image_counts["train"], image_counts["val"])
    for name in TARGET_CLASSES:
        logger.info("Dataset size [%s]: images=%d boxes=%d", name, image_class_counts[name], class_counts[name])


if __name__ == "__main__":
    main()
