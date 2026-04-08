import importlib
import os
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
ensure_package("torch")
ensure_package("ftfy")
ensure_package("regex")


def ensure_openai_clip() -> None:
    try:
        clip_module = importlib.import_module("clip")
        if hasattr(clip_module, "load") and hasattr(clip_module, "tokenize"):
            return
    except ImportError:
        pass

    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "clip"], check=False)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "git+https://github.com/openai/CLIP.git"])
    importlib.invalidate_caches()
    sys.modules.pop("clip", None)


ensure_openai_clip()

import clip
import torch
from icrawler.builtin import BingImageCrawler
from PIL import Image, ImageFile


ImageFile.LOAD_TRUNCATED_IMAGES = True

BASE_DIR = Path(r"C:/State-Secrets/Projects/INFT/SB Project - clone 2/Dataset")
FILTERED_DIR = BASE_DIR / "filtered_out"
CLASS_NAMES = ["mobile", "laptop", "tablet", "powerbank", "other"]
IMAGES_PER_CLASS = 80
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

CLASS_QUERIES = {
    "mobile": [
        "smartphone real photo",
        "phone in hand",
        "cracked phone screen",
    ],
    "laptop": [
        "laptop on desk",
        "open laptop real",
        "broken laptop screen",
    ],
    "tablet": [
        "tablet on table",
        "ipad in hand",
        "cracked tablet",
    ],
    "powerbank": [
        "powerbank real photo",
        "portable charger",
        "damaged powerbank",
    ],
    "other": [
        "usb cable close up",
        "pcb board close up",
        "charger adapter",
        "wires bundle",
    ],
}

REAL_PHOTO_PROMPTS = [
    "a real photo of an object",
    "a camera photo of a real product",
    "a close-up product photo",
]

BAD_CONTENT_PROMPTS = [
    "a cartoon",
    "an anime illustration",
    "an infographic",
    "a diagram",
    "a poster with lots of text",
    "a presentation slide",
    "a screenshot full of text",
    "multiple unrelated objects",
]

CLASS_PROMPTS = {
    "mobile": ["a real photo of a smartphone", "a real photo of a phone"],
    "laptop": ["a real photo of a laptop", "a real photo of an open laptop"],
    "tablet": ["a real photo of a tablet", "a real photo of an ipad"],
    "powerbank": ["a real photo of a powerbank", "a real photo of a portable charger"],
    "other": [
        "a real photo of a usb cable",
        "a real photo of a pcb board",
        "a real photo of a charger adapter",
        "a real photo of wires",
    ],
}


def image_count(folder: Path) -> int:
    if not folder.exists():
        return 0
    return sum(1 for file in folder.iterdir() if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS)


def download_images() -> int:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    total_downloaded = 0

    for class_name in CLASS_NAMES:
        class_dir = BASE_DIR / class_name
        class_dir.mkdir(parents=True, exist_ok=True)

        before_count = image_count(class_dir)
        per_query = max(1, IMAGES_PER_CLASS // len(CLASS_QUERIES[class_name]))

        for query in CLASS_QUERIES[class_name]:
            remaining = IMAGES_PER_CLASS - image_count(class_dir)
            if remaining <= 0:
                break

            target = min(per_query, remaining)
            print(f"[download] {class_name}: {query}")

            crawler = BingImageCrawler(
                downloader_threads=4,
                storage={"root_dir": str(class_dir)},
            )
            crawler.crawl(keyword=query, max_num=target)

        after_count = image_count(class_dir)
        total_downloaded += max(0, after_count - before_count)

    return total_downloaded


def load_clip_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)
    return model, preprocess, device


def clip_scores(image: Image.Image, prompts: list[str], model, preprocess, device):
    image_input = preprocess(image).unsqueeze(0).to(device)
    text_input = clip.tokenize(prompts).to(device)

    with torch.no_grad():
        logits_per_image, _ = model(image_input, text_input)
        probs = logits_per_image.softmax(dim=-1).cpu().numpy()[0]

    return probs.tolist()


def should_filter_image(image_path: Path, class_name: str, model, preprocess, device) -> bool:
    try:
        with Image.open(image_path) as img:
            image = img.convert("RGB")
            width, height = image.size
    except Exception:
        return True

    if width < 200 or height < 200:
        return True

    photo_score = max(clip_scores(image, REAL_PHOTO_PROMPTS, model, preprocess, device))
    bad_score = max(clip_scores(image, BAD_CONTENT_PROMPTS, model, preprocess, device))
    class_score = max(clip_scores(image, CLASS_PROMPTS[class_name], model, preprocess, device))

    if bad_score >= photo_score:
        return True

    if class_score < 0.45:
        return True

    return False


def move_filtered_image(image_path: Path, class_name: str) -> None:
    target_dir = FILTERED_DIR / class_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / image_path.name

    counter = 1
    while target_path.exists():
        target_path = target_dir / f"{image_path.stem}_{counter}{image_path.suffix}"
        counter += 1

    move(str(image_path), str(target_path))


def clean_dataset():
    model, preprocess, device = load_clip_model()
    removed = 0
    remaining_per_class = {}

    for class_name in CLASS_NAMES:
        class_dir = BASE_DIR / class_name
        if not class_dir.exists():
            remaining_per_class[class_name] = 0
            continue

        for image_path in list(class_dir.iterdir()):
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            if should_filter_image(image_path, class_name, model, preprocess, device):
                move_filtered_image(image_path, class_name)
                removed += 1

        remaining_per_class[class_name] = image_count(class_dir)

    return removed, remaining_per_class


def main() -> None:
    total_downloaded = download_images()
    removed, remaining_per_class = clean_dataset()

    print(f"total downloaded: {total_downloaded}")
    print(f"removed: {removed}")
    for class_name in CLASS_NAMES:
        print(f"remaining {class_name}: {remaining_per_class[class_name]}")


if __name__ == "__main__":
    main()
