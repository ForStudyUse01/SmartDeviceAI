from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from pathlib import Path


def ensure_package(module_name: str, package_name: str | None = None) -> None:
    try:
        __import__(module_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name or module_name])


ensure_package("roboflow")
from roboflow import Roboflow


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = PROJECT_ROOT / "Dataset VLM" / "roboflow_sources.json"
DATASET_ROOT = PROJECT_ROOT / "Dataset VLM"
RAW_ROOT = DATASET_ROOT / "raw"
TRAIN_JSONL = PROJECT_ROOT / "backend" / "data" / "vlm_train.jsonl"
VAL_JSONL = PROJECT_ROOT / "backend" / "data" / "vlm_val.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Roboflow datasets and build VLM JSONL labels.")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-per-source", type=int, default=0, help="0 = no cap")
    return parser.parse_args()


def load_sources() -> list[dict]:
    if not SOURCES_PATH.exists():
        raise FileNotFoundError(f"Missing source config: {SOURCES_PATH}")
    return json.loads(SOURCES_PATH.read_text(encoding="utf-8"))


def detect_latest_version(workspace: str, project: str, api_key: str) -> int:
    import urllib.request

    # Roboflow project endpoint returns available versions.
    url = f"https://api.roboflow.com/{workspace}/{project}?api_key={api_key}"
    with urllib.request.urlopen(url, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    versions = payload.get("project", {}).get("versions", [])
    if isinstance(versions, int):
        return max(1, int(versions))
    if not isinstance(versions, list) or not versions:
        return 1
    ids = []
    for v in versions:
        if isinstance(v, dict) and v.get("id") is not None:
            try:
                ids.append(int(v.get("id")))
            except (TypeError, ValueError):
                continue
        elif isinstance(v, int):
            ids.append(int(v))
    return max(ids) if ids else 1


def collect_images(dataset_dir: Path) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    paths: list[Path] = []
    for split in ("train", "valid", "test"):
        root = dataset_dir / split / "images"
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.suffix.lower() in exts:
                paths.append(p)
    return paths


def build_labels(images: list[Path], source: dict, seed: int) -> list[dict]:
    random.seed(seed)
    labels: list[dict] = []
    for img in images:
        condition = source["default_condition"]
        damage = source["default_damage"]
        # Add some average examples for non-broken data to improve label diversity.
        if damage == "Not Broken" and random.random() < 0.35:
            condition = "Average"
        labels.append(
            {
                "image": str(img.resolve()),
                "condition": condition,
                "damage": damage,
                "device_type": source.get("device_type", "unknown"),
                "source": source.get("name", "unknown"),
            }
        )
    return labels


def main() -> None:
    args = parse_args()
    api_key = os.getenv("ROBOFLOW_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ROBOFLOW_API_KEY is required to download datasets from Roboflow.")

    sources = load_sources()
    RAW_ROOT.mkdir(parents=True, exist_ok=True)

    rf = Roboflow(api_key=api_key)
    all_rows: list[dict] = []

    for source in sources:
        name = source["name"]
        workspace = source["workspace"]
        project = source["project"]
        latest_version = detect_latest_version(workspace, project, api_key)

        target = RAW_ROOT / name
        target.mkdir(parents=True, exist_ok=True)
        print(f"[{name}] downloading workspace={workspace} project={project} version={latest_version}")
        version = rf.workspace(workspace).project(project).version(latest_version)
        dataset = version.download("yolov8", location=str(target))
        dataset_dir = Path(dataset.location)
        images = collect_images(dataset_dir)
        if args.max_per_source > 0:
            images = images[: args.max_per_source]
        print(f"[{name}] images={len(images)}")
        all_rows.extend(build_labels(images, source, args.seed))

    if not all_rows:
        raise RuntimeError("No images found after download.")

    random.Random(args.seed).shuffle(all_rows)
    split_idx = int(len(all_rows) * (1 - args.val_ratio))
    train_rows = all_rows[:split_idx]
    val_rows = all_rows[split_idx:]

    TRAIN_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with TRAIN_JSONL.open("w", encoding="utf-8") as f:
        for row in train_rows:
            f.write(json.dumps(row) + "\n")
    with VAL_JSONL.open("w", encoding="utf-8") as f:
        for row in val_rows:
            f.write(json.dumps(row) + "\n")

    print(f"Total rows: {len(all_rows)}")
    print(f"Train rows: {len(train_rows)} -> {TRAIN_JSONL}")
    print(f"Val rows: {len(val_rows)} -> {VAL_JSONL}")
    print("Tablet dataset note: no public source configured; current build uses mobile/laptop only.")


if __name__ == "__main__":
    main()
