import hashlib
import importlib
import subprocess
import sys
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse


def ensure_package(module_name: str, package_name: str | None = None) -> None:
    try:
        importlib.import_module(module_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name or module_name])


ensure_package("duckduckgo_search")
ensure_package("ddgs")
ensure_package("requests")
ensure_package("PIL", "pillow")

import requests
from duckduckgo_search import DDGS
from ddgs import DDGS as RenamedDDGS
from PIL import Image, ImageFile


ImageFile.LOAD_TRUNCATED_IMAGES = True

BASE_DIR = Path(r"C:/State-Secrets/Projects/INFT/SB Project - clone 2/Dataset")
TARGET_PER_CLASS = 100
TIMEOUT = 15
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

CLASS_QUERIES = {
    "mobile": [
        "smartphone real photo",
        "phone in hand",
        "cracked phone",
        "mobile on table",
    ],
    "laptop": [
        "laptop on desk",
        "open laptop",
        "broken laptop screen",
        "laptop keyboard",
    ],
    "tablet": [
        "tablet real photo",
        "ipad on table",
        "cracked tablet",
    ],
    "powerbank": [
        "powerbank real",
        "portable charger",
        "battery pack",
    ],
    "other": [
        "usb cable close up",
        "pcb board close up",
        "charger adapter",
        "wires bundle",
    ],
}


def class_dir(class_name: str) -> Path:
    folder = BASE_DIR / class_name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def existing_hashes(folder: Path) -> set[str]:
    hashes = set()
    for file in folder.iterdir():
        if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS:
            try:
                hashes.add(hashlib.sha256(file.read_bytes()).hexdigest())
            except Exception:
                continue
    return hashes


def next_image_path(folder: Path, extension: str) -> Path:
    index = 1
    while True:
        candidate = folder / f"{index:04d}{extension}"
        if not candidate.exists():
            return candidate
        index += 1


def detect_extension(url: str, content_type: str) -> str | None:
    content_type = (content_type or "").lower()
    if "jpeg" in content_type or "jpg" in content_type:
        return ".jpg"
    if "png" in content_type:
        return ".png"

    path = urlparse(url).path.lower()
    for ext in IMAGE_EXTENSIONS:
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return None


def is_valid_image(image_bytes: bytes) -> bool:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
        return True
    except Exception:
        return False


def download_image(url: str) -> tuple[bytes | None, str | None]:
    try:
        response = requests.get(
            url,
            timeout=TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
    except Exception:
        return None, None

    extension = detect_extension(url, response.headers.get("Content-Type", ""))
    if extension is None:
        return None, None

    image_bytes = response.content
    if not is_valid_image(image_bytes):
        return None, None

    return image_bytes, extension


def download_class_images(class_name: str, queries: list[str]) -> int:
    folder = class_dir(class_name)
    hashes = existing_hashes(folder)
    downloaded = 0
    seen_urls = set()

    search_clients = [("duckduckgo_search", DDGS), ("ddgs", RenamedDDGS)]

    for query in queries:
        if downloaded >= TARGET_PER_CLASS:
            break

        print(f"[{class_name}] {query}")
        results = []

        for client_name, client_cls in search_clients:
            try:
                with client_cls() as ddgs:
                    results = ddgs.images(query, max_results=80)
                if results:
                    break
            except Exception as error:
                print(f"[{class_name}] {client_name} search failed: {error}")
                time.sleep(2)

        for result in results:
            if downloaded >= TARGET_PER_CLASS:
                break

            url = result.get("image")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            image_bytes, extension = download_image(url)
            if image_bytes is None or extension is None:
                continue

            content_hash = hashlib.sha256(image_bytes).hexdigest()
            if content_hash in hashes:
                continue

            output_path = next_image_path(folder, extension)
            output_path.write_bytes(image_bytes)
            hashes.add(content_hash)
            downloaded += 1

    return downloaded


def main() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    for class_name, queries in CLASS_QUERIES.items():
        downloaded = download_class_images(class_name, queries)
        print(f"total downloaded {class_name}: {downloaded}")


if __name__ == "__main__":
    main()
