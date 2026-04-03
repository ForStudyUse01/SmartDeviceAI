#!/usr/bin/env python
"""
Test script for improved device detection with fallback mechanism
This tests the pipeline with a sample phone image
"""

import json
from pathlib import Path

import requests
from PIL import Image

# Configuration
API_URL = "http://127.0.0.1:5000"


def test_phone_detection():
    """Test detection of a phone"""
    print("=" * 70)
    print("E-waste Detection - Phone Detection Test")
    print("=" * 70)

    # Create a test image (you should replace with your actual phone image)
    # For now, we'll create a simple test pattern that looks somewhat like a phone
    print("\n📸 Creating test phone image...")

    width, height = 300, 600  # Phone-like aspect ratio
    image = Image.new("RGB", (width, height), color=(50, 50, 50))

    # Add some features that look like a phone
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)

    # Draw screen (dark area)
    draw.rectangle([20, 50, 280, 550], fill=(30, 30, 30), outline=(100, 100, 100))

    # Draw camera area at top
    draw.ellipse([140, 20, 160, 40], fill=(20, 20, 20), outline=(50, 50, 50))

    # Draw speaker
    draw.rectangle([120, 15, 180, 18], fill=(15, 15, 15))

    # Save test image
    test_image_path = "/tmp/test_phone.jpg"
    image.save(test_image_path)
    print(f"✅ Test image created: {test_image_path}")

    # Test with API
    print("\n🔍 Testing device detection with fallback...")

    try:
        with open(test_image_path, "rb") as f:
            files = {"file": f}
            response = requests.post(
                f"{API_URL}/analyze",
                files=files,
                params={"conf_threshold": 0.25},
                timeout=30,
            )

        response.raise_for_status()
        result = response.json()

        print(f"\n✅ Detection successful!")
        print(f"\nResponse:")
        print(json.dumps(result, indent=2))

        # Check results
        if result.get("status") == "success":
            objects = result.get("detected_objects", [])
            if objects:
                for i, obj in enumerate(objects, 1):
                    print(f"\n📱 Object {i}:")
                    print(f"  • Detected as: {obj['vlm_object']}")
                    print(f"  • YOLO Label: {obj['yolo_label']} ({obj['yolo_confidence']:.1f}%)")
                    print(f"  • Condition: {obj['condition']}")
                    print(f"  • Eco Score: {obj['eco_score']}/100")
                    print(f"  • Suggestion: {obj['suggestion']}")
            else:
                print("⚠️  No objects detected")
        else:
            print(f"❌ Detection failed: {result.get('error_message')}")

    except requests.exceptions.ConnectionError:
        print("❌ API not running! Start it with: python app.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    print("\n" + "=" * 70)
    return True


def test_with_real_image(image_path: str):
    """Test with a real image file"""
    print("=" * 70)
    print(f"Testing with real image: {image_path}")
    print("=" * 70)

    if not Path(image_path).exists():
        print(f"❌ Image not found: {image_path}")
        return False

    try:
        with open(image_path, "rb") as f:
            files = {"file": f}
            response = requests.post(
                f"{API_URL}/analyze",
                files=files,
                params={"conf_threshold": 0.10},  # Lower threshold for better detection
                timeout=30,
            )

        response.raise_for_status()
        result = response.json()

        print(f"\n✅ Analysis successful!")
        print(f"\nDetected Objects: {result.get('num_detections', 0)}")

        for i, obj in enumerate(result.get("detected_objects", []), 1):
            print(f"\n📱 Object {i}:")
            print(f"  • Device: {obj['vlm_object']}")
            print(f"  • YOLO: {obj['yolo_label']} ({obj['yolo_confidence']:.1f}%)")
            print(f"  • Condition: {obj['condition']}")
            print(f"  • Score: {obj['eco_score']}/100")
            print(f"  • Advice: {obj['suggestion'][:60]}...")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    import sys

    print("\n🤖 E-waste Detection - Improved Accuracy Test Suite\n")

    # Test with the test image
    test_phone_detection()

    # If a real image path is provided, test with that too
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        print("\n" + "=" * 70)
        test_with_real_image(image_path)

    print(
        "\n💡 Tip: Run with your own image:"
        "\n   python test_detection.py /path/to/your/image.jpg\n"
    )
