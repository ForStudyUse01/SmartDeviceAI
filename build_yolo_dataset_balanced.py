import importlib
import subprocess
import sys
from pathlib import Path
from shutil import move


def ensure_package(module_name: str, package_name: str | None = None) -> None:
    try:
        importlib.import_module(module_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name or module_name])


ensure_package("icrawler")
ensure_package("PIL", "pillow")
ensure_package("imagehash")

from icrawler.builtin import BingImageCrawler
import imagehash
from PIL import Image, ImageFile, ImageOps


ImageFile.LOAD_TRUNCATED_IMAGES = True

BASE_DIR = Path(r"C:/State-Secrets/Projects/INFT/SB Project - clone 2/Dataset")
FILTERED_DIR = BASE_DIR / "filtered_out"
CLASS_NAMES = ["mobile", "laptop", "tablet", "powerbank", "other"]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
TARGET_PER_CLASS = 120
DOWNLOADER_THREADS = 4
PHASH_DISTANCE_THRESHOLD = 6
MINIMUM_KEEP_COUNT = 70
MAX_DOWNLOAD_ROUNDS = 4

CLASS_QUERIES = {
    "mobile": [
        "smartphone real photo",
        "phone in hand",
        "mobile on table",
        "cracked phone",
        "broken smartphone",
        "phone in pocket",
        "android phone real",
        "iphone real",
        "person using smartphone",
        "smartphone indoor lighting",
    ],
    "laptop": [
        "laptop on desk",
        "open laptop",
        "broken laptop screen",
        "laptop keyboard",
        "old laptop",
        "laptop in office",
        "laptop side view",
        "open laptop workspace",
        "person using laptop",
        "laptop indoor lighting",
    ],
    "tablet": [
        "tablet real photo",
        "ipad on table",
        "tablet in hand",
        "cracked tablet",
        "tablet on bed",
        "android tablet",
        "tablet on table",
        "tablet usage real",
        "tablet indoor scene",
        "person using tablet",
    ],
    "powerbank": [
        "powerbank real",
        "portable charger",
        "powerbank charging phone",
        "battery pack",
        "damaged powerbank",
        "powerbank real photo",
        "portable charger in hand",
        "battery pack real",
        "power bank on table",
        "powerbank close up",
    ],
    "other": [
        "usb cable close up",
        "wires bundle",
        "pcb board close up",
        "circuit board",
        "charger adapter",
        "power adapter",
        "cables on desk",
        "charger adapter plug",
        "electronic wires bundle",
        "power adapter real",
    ],
}

CLASS_KEYWORDS = {
    "mobile": {"mobile", "phone", "smartphone", "iphone", "android", "cellphone"},
    "laptop": {"laptop", "notebook", "macbook", "computer", "workspace"},
    "tablet": {"tablet", "ipad", "tab"},
    "powerbank": {"powerbank", "power-bank", "portable-charger", "battery-pack", "charger"},
    "other": {"usb", "cable", "pcb", "board", "adapter", "wire", "charger", "plug", "power"},
}

BAD_FILENAME_KEYWORDS = {
    "cartoon",
    "anime",
    "illustration",
    "infographic",
    "poster",
}


def count_images(folder: Path) -> int:
    if not folder.exists():
        return 0
    return sum(1 for file in folder.iterdir() if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS)


def class_dir(class_name: str) -> Path:
    folder = BASE_DIR / class_name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def filtered_dir(class_name: str) -> Path:
    folder = FILTERED_DIR / class_name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def move_filtered_image(image_path: Path, class_name: str) -> None:
    target_path = filtered_dir(class_name) / image_path.name
    counter = 1
    while target_path.exists():
        target_path = filtered_dir(class_name) / f"{image_path.stem}_{counter}{image_path.suffix}"
        counter += 1
    move(str(image_path), str(target_path))


def split_target(total: int, parts: int) -> list[int]:
    if total <= 0:
        return [0] * parts
    base = total // parts
    remainder = total % parts
    return [base + (1 if i < remainder else 0) for i in range(parts)]


def download_missing_images() -> dict[str, int]:
    downloaded_per_class = {}
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    for class_name in CLASS_NAMES:
        folder = class_dir(class_name)
        before = count_images(folder)
        round_number = 0

        while count_images(folder) < TARGET_PER_CLASS and round_number < MAX_DOWNLOAD_ROUNDS:
            missing = TARGET_PER_CLASS - count_images(folder)
            targets = split_target(missing, len(CLASS_QUERIES[class_name]))
            progress_this_round = 0

            for query, target in zip(CLASS_QUERIES[class_name], targets):
                if target <= 0:
                    continue

                current_missing = TARGET_PER_CLASS - count_images(folder)
                if current_missing <= 0:
                    break

                query_target = min(max(3, target), current_missing)
                before_query = count_images(folder)
                print(f"[download] {class_name}: {query}")

                crawler = BingImageCrawler(
                    downloader_threads=DOWNLOADER_THREADS,
                    storage={"root_dir": str(folder)},
                )
                crawler.crawl(keyword=query, max_num=query_target)
                after_query = count_images(folder)
                progress_this_round += max(0, after_query - before_query)

            round_number += 1
            if progress_this_round == 0 and count_images(folder) >= MINIMUM_KEEP_COUNT:
                break
            if progress_this_round == 0:
                break

        after = count_images(folder)
        downloaded_per_class[class_name] = max(0, after - before)

    return downloaded_per_class


def is_small_image(width: int, height: int) -> bool:
    return width < 200 or height < 200


def has_bad_filename_signal(path: Path) -> bool:
    name = path.stem.lower().replace("_", " ").replace("-", " ")
    return any(keyword in name for keyword in BAD_FILENAME_KEYWORDS)


def looks_unrelated_by_filename(path: Path, class_name: str) -> bool:
    name = path.stem.lower().replace("_", " ").replace("-", " ")
    if any(keyword in name for keyword in CLASS_KEYWORDS[class_name]):
        return False

    unrelated = {"dog", "cat", "car", "food", "flower", "building", "landscape", "shoe", "dress", "face"}
    return any(keyword in name for keyword in unrelated)


def grayscale_complexity(image: Image.Image) -> float:
    grayscale = ImageOps.grayscale(image).resize((128, 128))
    histogram = grayscale.histogram()
    total = sum(histogram)
    if total == 0:
        return 0.0
    used_bins = sum(1 for count in histogram if count > 0)
    return used_bins / 256.0


def edge_density(image: Image.Image) -> float:
    grayscale = ImageOps.grayscale(image).resize((128, 128))
    pixels = list(grayscale.getdata())
    width, height = grayscale.size
    strong_edges = 0
    comparisons = 0

    for y in range(height - 1):
        for x in range(width - 1):
            idx = y * width + x
            right_diff = abs(pixels[idx] - pixels[idx + 1])
            down_diff = abs(pixels[idx] - pixels[idx + width])
            if right_diff > 40:
                strong_edges += 1
            if down_diff > 40:
                strong_edges += 1
            comparisons += 2

    return strong_edges / comparisons if comparisons else 0.0


def block_uniformity(image: Image.Image) -> float:
    small = image.resize((24, 24)).convert("RGB")
    pixels = list(small.getdata())
    unique_colors = len(set(pixels))
    return unique_colors / len(pixels)


def looks_like_graphic(image: Image.Image) -> bool:
    complexity = grayscale_complexity(image)
    edges = edge_density(image)
    uniformity = block_uniformity(image)

    low_detail_flat = complexity < 0.07 and uniformity < 0.12
    poster_like = complexity < 0.12 and edges > 0.22 and uniformity < 0.18
    extreme_flat = uniformity < 0.10

    return low_detail_flat or poster_like or extreme_flat


def clean_class_folder(class_name: str) -> int:
    folder = class_dir(class_name)
    removed = 0
    seen_hashes: list[imagehash.ImageHash] = []

    for image_path in list(folder.iterdir()):
        if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        remove_reason = False

        if has_bad_filename_signal(image_path) or looks_unrelated_by_filename(image_path, class_name):
            remove_reason = True
        else:
            try:
                with Image.open(image_path) as raw_img:
                    image = raw_img.convert("RGB")
                    width, height = image.size
                    if is_small_image(width, height):
                        remove_reason = True
                    else:
                        current_hash = imagehash.phash(image)
                        if any(abs(current_hash - existing_hash) <= PHASH_DISTANCE_THRESHOLD for existing_hash in seen_hashes):
                            remove_reason = True
                        elif has_bad_filename_signal(image_path) or looks_like_graphic(image):
                            remove_reason = True
                        else:
                            seen_hashes.append(current_hash)
            except Exception:
                remove_reason = True

        if remove_reason:
            move_filtered_image(image_path, class_name)
            removed += 1

    return removed


def clean_dataset() -> tuple[dict[str, int], dict[str, int]]:
    removed_per_class = {}
    final_per_class = {}

    for class_name in CLASS_NAMES:
        removed_per_class[class_name] = clean_class_folder(class_name)
        final_per_class[class_name] = count_images(class_dir(class_name))

    return removed_per_class, final_per_class


def main() -> None:
    downloaded_per_class = download_missing_images()
    removed_per_class, final_per_class = clean_dataset()

    for class_name in CLASS_NAMES:
        if final_per_class[class_name] < MINIMUM_KEEP_COUNT:
            folder = class_dir(class_name)
            round_number = 0
            while final_per_class[class_name] < MINIMUM_KEEP_COUNT and round_number < MAX_DOWNLOAD_ROUNDS:
                needed = MINIMUM_KEEP_COUNT - final_per_class[class_name]
                progress = 0
                for query, target in zip(CLASS_QUERIES[class_name], split_target(needed, len(CLASS_QUERIES[class_name]))):
                    if target <= 0:
                        continue
                    before_query = count_images(folder)
                    print(f"[retry] {class_name}: {query}")
                    crawler = BingImageCrawler(
                        downloader_threads=DOWNLOADER_THREADS,
                        storage={"root_dir": str(folder)},
                    )
                    crawler.crawl(keyword=query, max_num=max(3, target))
                    progress += max(0, count_images(folder) - before_query)

                extra_removed, extra_final = clean_dataset()
                removed_per_class[class_name] += extra_removed[class_name]
                final_per_class[class_name] = extra_final[class_name]
                downloaded_per_class[class_name] += progress
                round_number += 1
                if progress == 0:
                    break

    for class_name in CLASS_NAMES:
        print(f"downloaded {class_name}: {downloaded_per_class[class_name]}")
    for class_name in CLASS_NAMES:
        print(f"removed {class_name}: {removed_per_class[class_name]}")
    for class_name in CLASS_NAMES:
        print(f"final {class_name}: {final_per_class[class_name]}")


if __name__ == "__main__":
    main()
