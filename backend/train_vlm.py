#!/usr/bin/env python
"""
Fine-tune BLIP-2 for e-waste condition + damage classification text outputs.

Expected JSONL format (one sample per line):
{"image": "relative/or/absolute/path.jpg", "condition": "Good", "damage": "Not Broken", "device_type": "mobile"}

Training uses the same prompt + JSON label shape as runtime inference (`vlm_model.VLMAnalyzer`).

Optional quality gate (multi-pass decode must match labels):
  python bootstrap_vlm_golden.py
  python train_vlm.py --train-jsonl data/vlm_train.jsonl --val-jsonl data/vlm_val.jsonl --image-root .. ^
    --gate-jsonl data/vlm_golden.jsonl --gate-repeats 4 --gate-max-samples 12 --epochs 8 ^
    --require-final-gate-pass
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from torch.utils.data import Dataset
from transformers import (
    Blip2ForConditionalGeneration,
    Blip2Processor,
    Trainer,
    TrainerCallback,
    TrainingArguments,
)

from vlm_gate_eval import run_vlm_label_gate
from vlm_prompts import E_WASTE_PROMPT, training_target_json


def _norm_condition(value: str) -> str:
    v = str(value or "").strip().lower()
    if v in {"good", "excellent"}:
        return "Good"
    if v in {"average", "fair", "medium"}:
        return "Average"
    if v in {"bad", "poor"}:
        return "Bad"
    return "Average"


def _norm_damage(value: str) -> str:
    v = str(value or "").strip().lower()
    if v in {"broken", "yes", "damaged"}:
        return "Broken"
    return "Not Broken"


class VlmJsonlDataset(Dataset):
    def __init__(self, jsonl_path: Path, image_root: Path):
        self.samples: list[dict[str, Any]] = []
        with jsonl_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if "image" not in row:
                    continue
                self.samples.append(row)
        self.image_root = image_root

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        row = self.samples[idx]
        image_path = Path(row["image"])
        if not image_path.is_absolute():
            image_path = self.image_root / image_path
        image = Image.open(image_path).convert("RGB")
        condition = _norm_condition(row.get("condition", "Average"))
        damage = _norm_damage(row.get("damage", "Not Broken"))
        target_text = training_target_json(row, condition=condition, damage=damage)
        return {"image": image, "prompt": E_WASTE_PROMPT, "target_text": target_text}


@dataclass
class VlmCollator:
    processor: Blip2Processor
    max_target_len: int = 128

    def __call__(self, features: list[dict[str, Any]]) -> dict[str, torch.Tensor]:
        images = [f["image"] for f in features]
        prompts = [f["prompt"] for f in features]
        targets = [f["target_text"] for f in features]

        model_inputs = self.processor(images=images, text=prompts, return_tensors="pt", padding=True)
        label_tokens = self.processor.tokenizer(
            targets,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self.max_target_len,
        )
        labels = label_tokens["input_ids"]
        labels[labels == self.processor.tokenizer.pad_token_id] = -100
        model_inputs["labels"] = labels
        return model_inputs


class GoldenGateCallback(TrainerCallback):
    """After each epoch, require multi-pass generation to match gate JSONL labels."""

    def __init__(
        self,
        *,
        processor: Blip2Processor,
        jsonl_path: Path,
        image_root: Path,
        repeats: int,
        max_samples: int,
        device: str,
    ) -> None:
        self.processor = processor
        self.jsonl_path = jsonl_path
        self.image_root = image_root
        self.repeats = repeats
        self.max_samples = max_samples
        self.device = device

    def on_epoch_end(self, args, state, control, **kwargs):
        model = kwargs.get("model")
        if model is None:
            return control
        ok, msg = run_vlm_label_gate(
            model,
            self.processor,
            device=self.device,
            jsonl_path=self.jsonl_path,
            image_root=self.image_root,
            repeats=self.repeats,
            max_samples=self.max_samples,
        )
        print(f"[vlm-gate] end of epoch {state.epoch:.0f}: {msg}")
        if ok:
            control.should_training_stop = True
        return control


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune BLIP-2 for device condition/damage outputs.")
    parser.add_argument("--train-jsonl", required=True, help="Path to train jsonl")
    parser.add_argument("--val-jsonl", required=False, help="Optional path to val jsonl")
    parser.add_argument("--image-root", required=True, help="Root folder for relative image paths")
    parser.add_argument("--model-name", default="Salesforce/blip2-opt-2.7b")
    parser.add_argument("--output-dir", default="artifacts/vlm-finetuned")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-samples", type=int, default=0, help="Use first N samples for smoke run")
    parser.add_argument(
        "--gate-jsonl",
        default="",
        help="Optional JSONL (same schema as train) used to stop early when generation matches labels.",
    )
    parser.add_argument(
        "--gate-image-root",
        default="",
        help="Root for resolving relative image paths in gate JSONL (defaults to --image-root).",
    )
    parser.add_argument("--gate-repeats", type=int, default=4, help="Consecutive identical passes required per image.")
    parser.add_argument("--gate-max-samples", type=int, default=12, help="Max gate JSONL rows to evaluate each epoch.")
    parser.add_argument(
        "--require-final-gate-pass",
        action="store_true",
        help="Exit with code 2 if the gate still fails after the last training epoch.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    if device != "cuda":
        raise RuntimeError("CUDA GPU is required for BLIP-2 fine-tuning.")

    train_jsonl = Path(args.train_jsonl).resolve()
    val_jsonl = Path(args.val_jsonl).resolve() if args.val_jsonl else None
    image_root = Path(args.image_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    processor = Blip2Processor.from_pretrained(args.model_name)
    model = Blip2ForConditionalGeneration.from_pretrained(
        args.model_name,
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
    )
    model.to(device)

    # Freeze heavy submodules to keep training stable on single GPU.
    if hasattr(model, "vision_model"):
        for p in model.vision_model.parameters():
            p.requires_grad = False
    if hasattr(model, "language_model"):
        for p in model.language_model.parameters():
            p.requires_grad = False

    # Ensure at least the Q-Former / projection stack can adapt (safe with frozen ViT + LM).
    if hasattr(model, "qformer"):
        for p in model.qformer.parameters():
            p.requires_grad = True
    if hasattr(model, "language_projection"):
        for p in model.language_projection.parameters():
            p.requires_grad = True

    train_ds = VlmJsonlDataset(train_jsonl, image_root)
    val_ds = VlmJsonlDataset(val_jsonl, image_root) if val_jsonl else None

    if args.max_samples > 0:
        train_ds.samples = train_ds.samples[: args.max_samples]
        if val_ds:
            val_ds.samples = val_ds.samples[: args.max_samples]

    if len(train_ds) == 0:
        raise RuntimeError("Training dataset is empty.")

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"Train samples: {len(train_ds)}")
    print(f"Val samples: {len(val_ds) if val_ds else 0}")
    print(f"Trainable params: {trainable:,} / {total:,}")

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.lr,
        fp16=False,
        logging_steps=10,
        save_strategy="epoch",
        eval_strategy="epoch" if val_ds else "no",
        report_to=[],
        remove_unused_columns=False,
    )

    gate_jsonl: Path | None = None
    if args.gate_jsonl and str(args.gate_jsonl).strip():
        gate_jsonl = Path(args.gate_jsonl).expanduser().resolve()
        if not gate_jsonl.is_file():
            raise RuntimeError(f"Gate JSONL not found: {gate_jsonl}")

    gate_image_root = (
        Path(args.gate_image_root).expanduser().resolve()
        if args.gate_image_root and str(args.gate_image_root).strip()
        else image_root
    )
    callbacks: list[TrainerCallback] = []
    if gate_jsonl is not None:
        callbacks.append(
            GoldenGateCallback(
                processor=processor,
                jsonl_path=gate_jsonl,
                image_root=gate_image_root,
                repeats=int(args.gate_repeats),
                max_samples=int(args.gate_max_samples),
                device=device,
            )
        )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=VlmCollator(processor=processor),
        callbacks=callbacks,
    )

    trainer.train()
    trainer.save_model(str(output_dir))
    processor.save_pretrained(str(output_dir))
    print(f"Saved fine-tuned model to: {output_dir}")

    if gate_jsonl is not None:
        ok, msg = run_vlm_label_gate(
            model,
            processor,
            device=device,
            jsonl_path=gate_jsonl,
            image_root=gate_image_root,
            repeats=int(args.gate_repeats),
            max_samples=int(args.gate_max_samples),
        )
        print(f"[vlm-gate] final: {msg}")
        if args.require_final_gate_pass and not ok:
            raise SystemExit(2)


if __name__ == "__main__":
    main()
