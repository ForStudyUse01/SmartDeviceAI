import importlib
import subprocess
import sys
import uuid
from pathlib import Path
from shutil import move


def ensure_package(module_name: str, package_name: str | None = None) -> None:
    try:
        importlib.import_module(module_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name or module_name])


ensure_package("PIL", "pillow")
ensure_package("imagehash")
ensure_package("cv2", "opencv-python")

import cv2
import imagehash
import numpy as np
from PIL import Image, ImageFile


ImageFile.LOAD_TRUNCATED_IMAGES = True

BASE_DIR = Path(r"C:/State-Secrets/Projects/INFT/SB Project - clone 2/Dataset")
FILTERED_DIR = BASE_DIR / "filtered_out"
CLASS_NAMES = ["mobile", "laptop", "tablet", "powerbank", "other"]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
PHASH_THRESHOLD = 6

BAD_NAME_KEYWORDS = {
    "cartoon",
    "anime",
    "illustration",
    "infographic",
    "poster",
    "slide",
    "slides",
    "presentation",
    "render",
    "3d",
    "glow",
    "neon",
    "vector",
}


def class_dir(class_name: str) -> Path:
    return BASE_DIR / class_name


def filtered_dir(class_name: str) -> Path:
    folder = FILTERED_DIR / class_name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def move_removed(image_path: Path, class_name: str) -> None:
    target = filtered_dir(class_name) / image_path.name
    while target.exists():
        target = filtered_dir(class_name) / f"{target.stem}_{uuid.uuid4().hex[:6]}{target.suffix}"
    move(str(image_path), str(target))


def load_rgb_image(image_path: Path) -> Image.Image | None:
    try:
        with Image.open(image_path) as img:
            return img.convert("RGB")
    except Exception:
        return None


def too_small(image: Image.Image) -> bool:
    width, height = image.size
    return width < 200 or height < 200


def bad_extension(image_path: Path) -> bool:
    return image_path.suffix.lower() not in IMAGE_EXTENSIONS


def white_background_ratio(image: Image.Image) -> float:
    arr = np.array(image.resize((200, 200)))
    bright = np.all(arr > 245, axis=2)
    return float(bright.mean())


def saturation_mean(image: Image.Image) -> float:
    hsv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2HSV)
    return float(hsv[:, :, 1].mean())


def edge_density(image: Image.Image) -> float:
    gray = cv2.cvtColor(np.array(image.resize((256, 256))), cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    return float((edges > 0).mean())


def text_like_ratio(image: Image.Image) -> float:
    gray = cv2.cvtColor(np.array(image.resize((256, 256))), cv2.COLOR_RGB2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        21,
        15,
    )
    contours, _ = cv2.findContours(255 - thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    area = gray.shape[0] * gray.shape[1]
    text_area = 0
    small_boxes = 0
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        rect_area = w * h
        if 8 <= w <= 80 and 6 <= h <= 40 and rect_area < 2000:
            text_area += rect_area
            small_boxes += 1

    if small_boxes < 20:
        return 0.0
    return text_area / area


def looks_like_bad_graphic(image: Image.Image, image_path: Path) -> bool:
    name = image_path.stem.lower().replace("_", " ").replace("-", " ")
    if any(keyword in name for keyword in BAD_NAME_KEYWORDS):
        return True

    white_ratio = white_background_ratio(image)
    sat_mean = saturation_mean(image)
    edges = edge_density(image)
    text_ratio = text_like_ratio(image)

    text_heavy = text_ratio > 0.18
    glowing_graphic = sat_mean > 120 and edges < 0.05
    white_bg_product = white_ratio > 0.82 and edges < 0.10

    return text_heavy or glowing_graphic or white_bg_product


def unique_name(extension: str) -> str:
    ext = ".jpg" if extension.lower() == ".jpeg" else extension.lower()
    return f"{uuid.uuid4().hex}{ext}"


def process_class(class_name: str) -> tuple[int, int, int, int]:
    folder = class_dir(class_name)
    if not folder.exists():
        return 0, 0, 0, 0

    total_checked = 0
    duplicates_removed = 0
    bad_removed = 0
    seen_hashes: list[imagehash.ImageHash] = []
    kept_files: list[Path] = []

    for image_path in list(folder.iterdir()):
        if not image_path.is_file():
            continue

        total_checked += 1

        if bad_extension(image_path):
            move_removed(image_path, class_name)
            bad_removed += 1
            continue

        image = load_rgb_image(image_path)
        if image is None or too_small(image):
            move_removed(image_path, class_name)
            bad_removed += 1
            continue

        current_hash = imagehash.phash(image)
        if any(abs(current_hash - existing_hash) <= PHASH_THRESHOLD for existing_hash in seen_hashes):
            move_removed(image_path, class_name)
            duplicates_removed += 1
            continue

        if looks_like_bad_graphic(image, image_path):
            move_removed(image_path, class_name)
            bad_removed += 1
            continue

        seen_hashes.append(current_hash)
        kept_files.append(image_path)

    for image_path in kept_files:
        new_name = unique_name(image_path.suffix)
        target = folder / new_name
        while target.exists():
            target = folder / unique_name(image_path.suffix)
        image_path.rename(target)

    final_count = sum(1 for file in folder.iterdir() if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS)
    return total_checked, duplicates_removed, bad_removed, final_count


def main() -> None:
    for class_name in CLASS_NAMES:
        total_checked, duplicates_removed, bad_removed, final_count = process_class(class_name)
        print(f"class: {class_name}")
        print(f"total images checked: {total_checked}")
        print(f"duplicates removed: {duplicates_removed}")
        print(f"bad images removed: {bad_removed}")
        print(f"final count: {final_count}")


if __name__ == "__main__":
    main()
