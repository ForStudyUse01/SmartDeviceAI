"""
E-waste Detection API - Usage Examples
Demonstrates how to use the API programmatically
"""

import asyncio
import json
import time
from pathlib import Path

import requests
from PIL import Image

API_URL = "http://127.0.0.1:5000"


def check_api_health():
    """Check if API is running and healthy"""
    print("🔍 Checking API health...")
    try:
        response = requests.get(f"{API_URL}/health")
        response.raise_for_status()
        health = response.json()

        print(f"✅ API Health:")
        print(f"  • Status: {health['status']}")
        print(f"  • YOLO Ready: {health['yolo_ready']}")
        print(f"  • VLM Ready: {health['vlm_ready']}")
        return True
    except Exception as e:
        print(f"❌ API not available: {e}")
        return False


def analyze_single_image(image_path: str, conf_threshold: float = 0.25):
    """Analyze a single image"""
    print(f"\n📸 Analyzing single image: {image_path}")

    path = Path(image_path)
    if not path.exists():
        print(f"❌ File not found: {image_path}")
        return None

    try:
        with open(path, "rb") as f:
            files = {"file": f}
            params = {"conf_threshold": conf_threshold}
            response = requests.post(f"{API_URL}/analyze", files=files, params=params)

        response.raise_for_status()
        result = response.json()

        print(f"✅ Analysis complete!")
        print(f"  • Status: {result['status']}")
        print(f"  • Objects detected: {result['num_detections']}")

        if result["detected_objects"]:
            print(f"\n  Objects:")
            for i, obj in enumerate(result["detected_objects"], 1):
                print(f"    {i}. {obj['vlm_object']}")
                print(f"       • Condition: {obj['condition']}")
                print(f"       • Eco Score: {obj['eco_score']}/100")
                print(f"       • Suggestion: {obj['suggestion']}")

        return result

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return None


def analyze_batch(image_paths: list[str], conf_threshold: float = 0.25):
    """Analyze multiple images"""
    print(f"\n📦 Analyzing batch of {len(image_paths)} images")

    files = []
    for image_path in image_paths:
        path = Path(image_path)
        if path.exists():
            files.append(("files", open(path, "rb")))
        else:
            print(f"⚠️  Skipping missing file: {image_path}")

    if not files:
        print("❌ No valid files to analyze")
        return None

    try:
        params = {"conf_threshold": conf_threshold}
        response = requests.post(f"{API_URL}/analyze-batch", files=files, params=params)

        # Close files
        for _, f in files:
            f.close()

        response.raise_for_status()
        result = response.json()

        print(f"✅ Batch analysis complete!")
        print(f"  • Total images: {result['total_images']}")
        print(f"  • Successful: {result['successful']}")
        print(f"  • Failed: {result['failed']}")
        print(f"  • Total objects: {result['total_objects_detected']}")

        # Summary statistics
        all_objects = []
        for image_result in result["results"]:
            all_objects.extend(image_result["detected_objects"])

        if all_objects:
            eco_scores = [obj["eco_score"] for obj in all_objects]
            avg_eco = sum(eco_scores) / len(eco_scores)
            print(f"\n  Statistics:")
            print(f"    • Average eco score: {avg_eco:.1f}/100")
            print(f"    • Min eco score: {min(eco_scores)}")
            print(f"    • Max eco score: {max(eco_scores)}")

        return result

    except Exception as e:
        print(f"❌ Batch analysis failed: {e}")
        return None
    finally:
        # Ensure files are closed
        for _, f in files:
            if not f.closed:
                f.close()


def train_yolo(data_yaml_path: str, epochs: int = 50, batch_size: int = 8):
    """Fine-tune YOLO on custom dataset"""
    print(f"\n🤖 Starting YOLO fine-tuning")
    print(f"  • Dataset: {data_yaml_path}")
    print(f"  • Epochs: {epochs}")
    print(f"  • Batch size: {batch_size}")

    try:
        params = {
            "data_yaml_path": data_yaml_path,
            "epochs": epochs,
            "imgsz": 640,
            "batch_size": batch_size,
        }
        response = requests.post(f"{API_URL}/train-yolo", params=params)

        response.raise_for_status()
        result = response.json()

        if result["status"] == "success":
            print(f"✅ Training completed!")
            print(f"  • Best model: {result['best_model_path']}")
            return result
        else:
            print(f"❌ Training failed: {result.get('error')}")
            return None

    except Exception as e:
        print(f"❌ Training request failed: {e}")
        return None


def load_custom_model(model_path: str):
    """Load a fine-tuned model"""
    print(f"\n📂 Loading custom model: {model_path}")

    try:
        params = {"model_path": model_path}
        response = requests.post(f"{API_URL}/load-model", params=params)

        response.raise_for_status()
        result = response.json()

        if result.get("status") == "success":
            print(f"✅ Model loaded successfully!")
            return result
        else:
            print(f"❌ Failed to load model: {result.get('message')}")
            return None

    except Exception as e:
        print(f"❌ Load request failed: {e}")
        return None


def validate_model(data_yaml_path: str):
    """Validate model on validation set"""
    print(f"\n📊 Validating model")

    try:
        params = {"data_yaml_path": data_yaml_path}
        response = requests.get(f"{API_URL}/validate-yolo", params=params)

        response.raise_for_status()
        result = response.json()

        if result.get("status") == "success":
            metrics = result.get("metrics", {})
            print(f"✅ Validation complete!")
            print(f"  • mAP50: {metrics.get('map50', 'N/A')}")
            print(f"  • mAP: {metrics.get('map', 'N/A')}")
            return result
        else:
            print(f"❌ Validation failed: {result.get('error')}")
            return None

    except Exception as e:
        print(f"❌ Validation request failed: {e}")
        return None


def get_api_stats():
    """Get API statistics"""
    print(f"\n📈 API Statistics")

    try:
        response = requests.get(f"{API_URL}/stats")
        response.raise_for_status()
        stats = response.json()

        print(f"✅ Stats retrieved:")
        print(f"  • Status: {stats['status']}")
        print(f"  • YOLO Model: {stats['yolo_model']}")
        print(f"  • VLM Model: {stats['vlm_model']}")
        print(f"  • Device: {stats['device']}")
        return stats

    except Exception as e:
        print(f"❌ Failed to get stats: {e}")
        return None


# ============================================================================
# DEMO / MAIN
# ============================================================================

def demo():
    """Run demo analysis"""
    print("=" * 70)
    print("E-waste Detection API - Examples")
    print("=" * 70)

    # Check API health
    if not check_api_health():
        print("\n⚠️  Please start the API first:")
        print("   python app.py")
        return

    # Get stats
    get_api_stats()

    # Create a sample image for testing (small test image)
    print("\n📝 Creating sample test image...")
    test_image_path = "test_sample.png"

    # Create a simple colored image
    img = Image.new("RGB", (640, 480), color=(100, 150, 200))
    img.save(test_image_path)
    print(f"✅ Created test image: {test_image_path}")

    # Analyze single image
    result = analyze_single_image(test_image_path, conf_threshold=0.25)
    if result:
        print(f"\nRaw response: {json.dumps(result, indent=2)}")

    # Analyze batch (using same image twice)
    batch_result = analyze_batch([test_image_path, test_image_path], conf_threshold=0.25)
    if batch_result:
        print(f"\nBatch response: {json.dumps(batch_result, indent=2)}")

    # Clean up
    Path(test_image_path).unlink()
    print(f"\n✅ Cleaned up test image")

    print("\n" + "=" * 70)
    print("For more examples:")
    print("  • Single image: analyze_single_image('path/to/image.jpg')")
    print("  • Batch: analyze_batch(['img1.jpg', 'img2.jpg'])")
    print("  • Training: train_yolo('path/to/data.yaml', epochs=50)")
    print("=" * 70)


if __name__ == "__main__":
    demo()
