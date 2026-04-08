from __future__ import annotations

import importlib
import logging
import subprocess
import sys
from pathlib import Path


def ensure_package(module_name: str, package_name: str | None = None) -> None:
    try:
        importlib.import_module(module_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name or module_name])


ensure_package("icrawler")
ensure_package("PIL", "pillow")

from icrawler.builtin import BingImageCrawler
from PIL import Image, UnidentifiedImageError


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("scrape_images")

PROJECT_ROOT = Path(__file__).resolve().parent
DATASET_DIR = PROJECT_ROOT / "dataset"
IMAGES_DIR = DATASET_DIR / "images"
MIN_IMAGES_PER_CLASS = 200
MIN_WIDTH = 224
MIN_HEIGHT = 224

CLASS_QUERIES: dict[str, list[str]] = {
    "mobile": [
        "mobile phone device photo",
        "smartphone on table real photo",
        "used mobile phone close up",
        "broken mobile phone screen",
    ],
    "laptop": [
        "laptop computer on desk real photo",
        "used laptop close up",
        "open laptop keyboard photo",
        "damaged laptop screen",
    ],
    "tablet": [
        "tablet device real photo",
        "android tablet on desk",
        "ipad tablet close up",
        "broken tablet screen",
    ],
}

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def image_count(folder: Path) -> int:
    return sum(1 for path in folder.glob("*") if path.is_file() and path.suffix.lower() in VALID_EXTENSIONS)


def is_valid_image(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            w, h = rgb.size
            return w >= MIN_WIDTH and h >= MIN_HEIGHT
    except (UnidentifiedImageError, OSError, ValueError):
        return False


def clean_invalid_images(folder: Path) -> int:
    removed = 0
    for path in folder.glob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in VALID_EXTENSIONS or not is_valid_image(path):
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def download_for_class(class_name: str) -> dict[str, int]:
    class_dir = IMAGES_DIR / class_name
    class_dir.mkdir(parents=True, exist_ok=True)

    before = image_count(class_dir)
    logger.info("[%s] images before download: %d", class_name, before)

    query_index = 0
    while image_count(class_dir) < MIN_IMAGES_PER_CLASS:
        query = CLASS_QUERIES[class_name][query_index % len(CLASS_QUERIES[class_name])]
        remaining = MIN_IMAGES_PER_CLASS - image_count(class_dir)
        batch = min(80, max(20, remaining))
        logger.info("[%s] scraping query='%s' target_batch=%d", class_name, query, batch)

        crawler = BingImageCrawler(
            downloader_threads=8,
            parser_threads=4,
            storage={"root_dir": str(class_dir)},
        )
        crawler.crawl(keyword=query, max_num=batch)
        query_index += 1

        if query_index > 12 and image_count(class_dir) < MIN_IMAGES_PER_CLASS:
            logger.warning("[%s] stopping early after repeated attempts", class_name)
            break

    removed = clean_invalid_images(class_dir)
    final = image_count(class_dir)
    logger.info("[%s] removed invalid images: %d", class_name, removed)
    logger.info("[%s] final valid images: %d", class_name, final)
    return {"before": before, "removed": removed, "final": final}


def main() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    summary: dict[str, dict[str, int]] = {}
    for class_name in ("mobile", "laptop", "tablet"):
        summary[class_name] = download_for_class(class_name)

    logger.info("Dataset image scraping complete.")
    for class_name, stats in summary.items():
        logger.info(
            "[%s] before=%d removed=%d final=%d",
            class_name,
            stats["before"],
            stats["removed"],
            stats["final"],
        )


if __name__ == "__main__":
    main()
