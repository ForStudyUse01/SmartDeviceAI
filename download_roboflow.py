from __future__ import annotations

import importlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def ensure_package(module_name: str, package_name: str | None = None) -> None:
    try:
        importlib.import_module(module_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name or module_name])


ensure_package("roboflow")
ensure_package("yaml", "pyyaml")

import yaml
from roboflow import Roboflow


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("download_roboflow")

PROJECT_ROOT = Path(__file__).resolve().parent
DOWNLOAD_ROOT = PROJECT_ROOT / "roboflow_downloads"


def load_specs() -> list[dict[str, Any]]:
    """
    Reads dataset specs from env ROBOTFLOW_DATASETS_JSON.
    Example:
    [
      {"name":"mobile", "workspace":"my-ws", "project":"mobile-phone", "version":1},
      {"name":"laptop", "workspace":"my-ws", "project":"laptop-det", "version":3}
    ]
    """
    raw = os.getenv("ROBOFLOW_DATASETS_JSON", "").strip()
    if not raw:
        raise RuntimeError("ROBOFLOW_DATASETS_JSON is required.")
    data = json.loads(raw)
    if not isinstance(data, list) or not data:
        raise RuntimeError("ROBOFLOW_DATASETS_JSON must be a non-empty JSON list.")
    for item in data:
        for key in ("name", "workspace", "project", "version"):
            if key not in item:
                raise RuntimeError(f"Dataset spec missing key '{key}': {item}")
    return data


def download_one(rf: Roboflow, spec: dict[str, Any]) -> Path:
    target_dir = DOWNLOAD_ROOT / str(spec["name"])
    target_dir.mkdir(parents=True, exist_ok=True)

    ws = rf.workspace(str(spec["workspace"]))
    project = ws.project(str(spec["project"]))
    version = project.version(int(spec["version"]))
    dataset = version.download("yolov8", location=str(target_dir))
    dataset_dir = Path(dataset.location)

    data_yaml = dataset_dir / "data.yaml"
    if data_yaml.exists():
        content = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
        names = content.get("names", {})
        logger.info("[%s] downloaded -> %s | classes=%s", spec["name"], dataset_dir, names)
    else:
        logger.warning("[%s] data.yaml missing in %s", spec["name"], dataset_dir)

    return dataset_dir


def main() -> None:
    api_key = os.getenv("ROBOFLOW_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ROBOFLOW_API_KEY is required.")

    specs = load_specs()
    DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    rf = Roboflow(api_key=api_key)

    logger.info("Downloading %d Roboflow datasets...", len(specs))
    for spec in specs:
        download_one(rf, spec)
    logger.info("Download complete. Root: %s", DOWNLOAD_ROOT)


if __name__ == "__main__":
    main()
