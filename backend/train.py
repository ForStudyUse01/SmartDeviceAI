#!/usr/bin/env python
"""
E-waste YOLO Fine-tuning Script
Trains YOLO v8 on custom e-waste dataset
"""

import argparse
import sys
from pathlib import Path

from yolo_model import TrainingConfig, YoloDetector
from utils import validate_data_yaml

def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune YOLO for e-waste detection"
    )
    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Path to data.yaml"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=50,
        help="Number of training epochs (default: 50)"
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="Image size (default: 640)"
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=8,
        help="Batch size (default: 8)"
    )
    parser.add_argument(
        "--device",
        type=int,
        default=0,
        help="GPU device ID (-1 for CPU, default: 0)"
    )
    parser.add_argument(
        "--name",
        type=str,
        default="e-waste-detector",
        help="Training run name"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate after training"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("E-waste YOLO Fine-tuning")
    print("=" * 70)

    # Validate data.yaml
    print(f"\n📋 Validating data.yaml: {args.data}")
    is_valid, errors = validate_data_yaml(args.data)

    if not is_valid:
        print("❌ Validation failed:")
        for error in errors:
            print(f"  ❌ {error}")
        sys.exit(1)

    print("✅ data.yaml is valid")

    # Initialize detector
    print("\n🔧 Loading YOLO model...")
    detector = YoloDetector("yolov8n.pt")

    if detector.model is None:
        print("❌ Failed to load YOLO model")
        sys.exit(1)

    print("✅ YOLO model loaded")

    # Create training config
    config = TrainingConfig(
        data_yaml=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch_size=args.batch,
        device=args.device,
        name=args.name,
    )

    print("\n⚙️  Training Configuration:")
    print(f"  • Data: {config.data_yaml}")
    print(f"  • Epochs: {config.epochs}")
    print(f"  • Image Size: {config.imgsz}")
    print(f"  • Batch Size: {config.batch_size}")
    print(f"  • Device: {'CPU' if config.device == -1 else f'GPU {config.device}'}")
    print(f"  • Run Name: {config.name}")

    # Start training
    print("\n🚀 Starting fine-tuning...")
    print("-" * 70)

    result = detector.fine_tune(config)

    print("-" * 70)

    if result["status"] == "success":
        print("\n✅ Fine-tuning completed successfully!")
        print(f"\n📁 Best model: {result['best_model_path']}")

        if args.validate:
            print("\n📊 Validating model...")
            val_result = detector.validate(data_yaml=args.data)

            if val_result["status"] == "success":
                metrics = val_result.get("metrics", {})
                print(f"  • mAP50: {metrics.get('map50', 'N/A')}")
                print(f"  • mAP: {metrics.get('map', 'N/A')}")
            else:
                print(f"  ⚠️  Validation failed: {val_result.get('error')}")

        print("\n" + "=" * 70)
        print("Next steps:")
        print(f"  1. Load model: curl -X POST 'http://127.0.0.1:5000/load-model?model_path={result['best_model_path']}'")
        print("  2. Test with images: python -m pytest tests/")
        print("  3. Deploy: docker build -t ewaste-api . && docker run -p 5000:5000 ewaste-api")
        print("=" * 70)

    else:
        print(f"\n❌ Fine-tuning failed: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
