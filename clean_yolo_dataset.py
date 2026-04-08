from pathlib import Path
from shutil import move

import torch
from PIL import Image, ImageFile
from transformers import CLIPModel, CLIPProcessor


ImageFile.LOAD_TRUNCATED_IMAGES = True

BASE_DIR = Path(r"C:\State-Secrets\Projects\INFT\SB Project - clone 2\Dataset")
REMOVED_DIR = BASE_DIR / "_removed"
CLASS_FOLDERS = ["mobile", "laptop", "tablet", "powerbank", "other"]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

REAL_PHOTO_PROMPTS = [
    "a real photo of a physical object",
    "a real-world product photo",
    "a camera photo of an electronic device",
]

GRAPHIC_PROMPTS = [
    "a cartoon or illustration",
    "an anime drawing",
    "an infographic or diagram",
    "a poster with lots of text",
    "a presentation slide",
    "a screenshot with text",
]

CLASS_PROMPTS = {
    "mobile": [
        "a real photo of a mobile phone",
        "a real photo of a smartphone",
    ],
    "laptop": [
        "a real photo of a laptop",
        "a real photo of a notebook computer",
    ],
    "tablet": [
        "a real photo of a tablet",
        "a real photo of a touchscreen tablet device",
    ],
    "powerbank": [
        "a real photo of a power bank",
        "a real photo of a portable charger",
    ],
    "other": [
        "a real photo of charger wires",
        "a real photo of a circuit board",
        "a real photo of a pcb",
        "a real photo of a charger",
        "a real photo of electronic cables",
    ],
}

NEGATIVE_OBJECT_PROMPTS = [
    "a real photo of a person",
    "a real photo of food",
    "a real photo of furniture",
    "a real photo of a vehicle",
    "a real photo of a building",
]


def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
    model.eval()
    return processor, model, device


def score_image(image, prompts, processor, model, device):
    inputs = processor(text=prompts, images=image, return_tensors="pt", padding=True)
    inputs = {key: value.to(device) for key, value in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)
        image_embeds = outputs.image_embeds / outputs.image_embeds.norm(dim=-1, keepdim=True)
        text_embeds = outputs.text_embeds / outputs.text_embeds.norm(dim=-1, keepdim=True)
        scores = (image_embeds @ text_embeds.T).squeeze(0)

    return scores.detach().cpu().tolist()


def should_remove_image(image_path, class_name, processor, model, device):
    try:
        image = Image.open(image_path).convert("RGB")
    except Exception:
        return True

    photo_scores = score_image(image, REAL_PHOTO_PROMPTS, processor, model, device)
    graphic_scores = score_image(image, GRAPHIC_PROMPTS, processor, model, device)
    class_scores = score_image(image, CLASS_PROMPTS[class_name], processor, model, device)
    negative_scores = score_image(image, NEGATIVE_OBJECT_PROMPTS, processor, model, device)

    best_photo = max(photo_scores)
    best_graphic = max(graphic_scores)
    best_class = max(class_scores)
    best_negative = max(negative_scores)

    if best_graphic >= best_photo:
        return True

    if best_class < 0.20:
        return True

    if best_negative > best_class:
        return True

    return False


def move_to_removed(image_path, class_name):
    target_dir = REMOVED_DIR / class_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / image_path.name

    counter = 1
    while target_path.exists():
        target_path = target_dir / f"{image_path.stem}_{counter}{image_path.suffix}"
        counter += 1

    move(str(image_path), str(target_path))


def main():
    processor, model, device = load_model()

    total_checked = 0
    removed_count = 0

    for class_name in CLASS_FOLDERS:
        class_dir = BASE_DIR / class_name
        if not class_dir.exists():
            continue

        for image_path in class_dir.iterdir():
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            total_checked += 1

            if should_remove_image(image_path, class_name, processor, model, device):
                move_to_removed(image_path, class_name)
                removed_count += 1

    remaining_count = total_checked - removed_count

    print(f"total images checked: {total_checked}")
    print(f"removed count: {removed_count}")
    print(f"remaining count: {remaining_count}")


if __name__ == "__main__":
    main()
