"""
Multi-pass VLM label gate: same prompt/decoding as runtime `VLMAnalyzer.analyze_crop`.

Used after (or between) fine-tuning epochs to require condition + damage to match
JSONL labels for every checked sample, for `repeats` consecutive forward passes each.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

import torch
from PIL import Image

from vlm_prompts import E_WASTE_PROMPT

def _resolve_image_path(row: dict[str, Any], image_root: Path) -> Path:
    p = Path(str(row.get("image", "")))
    if p.is_absolute():
        return p
    return (image_root / p).resolve()


def _extract_json_object(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    return m.group(0).strip() if m else text


def _norm_condition_label(value: str) -> str:
    condition = str(value or "").lower().strip()
    mapping = {
        "good": "Good",
        "excellent": "Good",
        "average": "Average",
        "fair": "Average",
        "poor": "Bad",
        "bad": "Bad",
    }
    if condition in mapping:
        return mapping[condition]
    if "poor" in condition or "bad" in condition or "broken" in condition or "major" in condition:
        return "Bad"
    if "average" in condition or "minor" in condition or "wear" in condition:
        return "Average"
    if "good" in condition or "clean" in condition:
        return "Good"
    return "Average"


def _norm_damage(value: str) -> str:
    v = str(value or "").lower().strip()
    if v in {"broken", "yes", "damaged"}:
        return "Broken"
    if v in {"not broken", "no", "not_broken", "intact"}:
        return "Not Broken"
    if "broken" in v and "not" not in v:
        return "Broken"
    return "Not Broken"


def _labels_from_generation_text(response_text: str) -> tuple[str, str, bool]:
    """Return (condition_label, damage, parsed_ok)."""
    try:
        data = json.loads(_extract_json_object(response_text))
        return (
            _norm_condition_label(str(data.get("condition", "Average"))),
            _norm_damage(str(data.get("damage", "Not Broken"))),
            True,
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        return ("Average", "Not Broken", False)


def _maybe_resize(image: Image.Image, max_side: int = 1024) -> Image.Image:
    if max(image.size) > max_side:
        image = image.copy()
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return image


def load_gate_rows(jsonl_path: Path, *, max_samples: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if max_samples > 0 and len(rows) >= max_samples:
                break
    return rows


@torch.inference_mode()
def run_vlm_label_gate(
    model: torch.nn.Module,
    processor: Any,
    *,
    device: str,
    jsonl_path: Path,
    image_root: Path,
    repeats: int = 4,
    max_samples: int = 16,
) -> tuple[bool, str]:
    """
    For each sample (up to max_samples), require `repeats` identical decoded
    (condition_label, damage) pairs matching JSONL `condition` / `damage` after normalization.
    """
    rows = load_gate_rows(jsonl_path, max_samples=max_samples)
    if not rows:
        return False, "Gate JSONL is empty."

    model.eval()

    failures: list[str] = []
    used = 0

    for idx, row in enumerate(rows):
        img_path = _resolve_image_path(row, image_root)
        if not img_path.is_file():
            failures.append(f"[{idx}] missing image: {img_path}")
            continue

        exp_c = _norm_condition_label(str(row.get("condition", "Average")))
        exp_d = _norm_damage(str(row.get("damage", "Not Broken")))

        image = Image.open(img_path).convert("RGB")
        image = _maybe_resize(image)
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=92)
        image = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")

        first_pair: tuple[str, str] | None = None
        sample_failed = False
        for r in range(max(1, repeats)):
            inputs = processor(image, E_WASTE_PROMPT, return_tensors="pt")
            inputs = {k: (v.to(device) if hasattr(v, "to") else v) for k, v in inputs.items()}

            out = model.generate(
                **inputs,
                max_new_tokens=64,
                num_beams=1,
                do_sample=False,
            )
            input_len = int(inputs["input_ids"].shape[-1])
            gen_ids = out[0, input_len:] if out.shape[-1] > input_len else out[0]
            text = processor.decode(gen_ids, skip_special_tokens=True).strip()
            if not text:
                text = processor.decode(out[0], skip_special_tokens=True).strip()
            c_lab, dmg, ok = _labels_from_generation_text(text)
            if not ok:
                failures.append(f"[{idx}] parse_fail run={r+1} raw={text[:120]!r}")
                sample_failed = True
                break
            pair = (c_lab, dmg)
            if first_pair is None:
                first_pair = pair
            elif pair != first_pair:
                failures.append(f"[{idx}] unstable run={r+1} got={pair} first={first_pair}")
                sample_failed = True
                break
            if c_lab != exp_c or dmg != exp_d:
                failures.append(
                    f"[{idx}] mismatch run={r+1} pred=({c_lab},{dmg}) expected=({exp_c},{exp_d}) raw={text[:160]!r}"
                )
                sample_failed = True
                break

        if sample_failed:
            break
        used += 1

    if failures:
        report = "; ".join(failures[:6])
        if len(failures) > 6:
            report += f" … (+{len(failures) - 6} more)"
        return False, report

    if used == 0:
        return False, "No usable gate images (paths missing?)."

    return True, f"Gate OK on {used} sample(s), {repeats} repeat(s) each."


def _cli_main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run multi-pass VLM label gate on a JSONL of labeled images.")
    parser.add_argument("--model-path", required=True, help="HF model folder or base model id")
    parser.add_argument("--gate-jsonl", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, default=Path("."))
    parser.add_argument("--repeats", type=int, default=4)
    parser.add_argument("--max-samples", type=int, default=12)
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device != "cuda":
        raise SystemExit("CUDA is required for this gate script (BLIP-2).")

    from transformers import Blip2ForConditionalGeneration, Blip2Processor

    mp = str(args.model_path)
    processor = Blip2Processor.from_pretrained(mp)
    model = Blip2ForConditionalGeneration.from_pretrained(
        mp,
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
    )
    model.to(device)

    ok, msg = run_vlm_label_gate(
        model,
        processor,
        device=device,
        jsonl_path=args.gate_jsonl.resolve(),
        image_root=args.image_root.resolve(),
        repeats=int(args.repeats),
        max_samples=int(args.max_samples),
    )
    print(msg)
    raise SystemExit(0 if ok else 2)


if __name__ == "__main__":
    _cli_main()
