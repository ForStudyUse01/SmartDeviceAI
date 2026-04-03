"""
Smart Device Detector - Identifies phones/tablets by visual characteristics
Used as fallback when YOLO detection fails
"""

import io
import logging
from typing import Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class SmartDeviceDetector:
    """
    Identifies electronic devices based on visual characteristics
    Detects: phones, tablets, laptops, screens, etc.
    """

    def __init__(self):
        """Initialize detector"""
        self.device_names = [
            "phone", "mobile", "smartphone",
            "tablet", "ipad", "e-reader",
            "laptop", "notebook", "screen", "monitor"
        ]

    def detect_device_from_image(self, image_bytes: bytes) -> tuple[str, float]:
        """
        Detect device type from image characteristics.

        Args:
            image_bytes: Image data

        Returns:
            (device_type, confidence) - e.g., ("phone", 0.85)
        """
        try:
            # Load image
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            img_array = np.array(image)

            # Convert to OpenCV format (BGR)
            img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

            # Analyze characteristics
            device = self._classify_device(img_cv, image)

            return device

        except Exception as e:
            logger.warning(f"Device detection failed: {e}")
            return ("unknown", 0.0)

    def _classify_device(self, img_cv, pil_image) -> tuple[str, float]:
        """Classify device based on visual features"""
        height, width = img_cv.shape[:2]
        aspect_ratio = width / height if height > 0 else 1.0

        # Get image characteristics
        edges = self._detect_edges(img_cv)
        colors = self._analyze_colors(img_cv)
        corners = self._find_corners(edges)

        features = {
            "aspect_ratio": aspect_ratio,
            "has_rounded_corners": len(corners) > 0 and all(
                self._is_rounded_corner(corners)
            ),
            "screen_dominance": self._get_screen_dominance(img_cv),
            "has_camera": self._detect_camera_area(img_cv),
            "color_variance": colors["variance"],
        }

        # Classify based on features
        return self._classify_from_features(features)

    def _detect_edges(self, img_cv) -> np.ndarray:
        """Detect edges in image"""
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        return edges

    def _analyze_colors(self, img_cv) -> dict:
        """Analyze color distribution"""
        # Convert to HSV for better color analysis
        hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)

        # Get unique colors
        pixels = hsv.reshape(-1, 3)
        unique_colors = len(np.unique(pixels, axis=0))

        # Calculate color variance
        variance = np.std(pixels, axis=0).mean()

        return {
            "unique_colors": unique_colors,
            "variance": variance,
        }

    def _find_corners(self, edges) -> list:
        """Find corner points in edge map"""
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return []

        # Get largest contour
        largest = max(contours, key=cv2.contourArea)
        corners = cv2.approxPolyDP(largest, 0.02 * cv2.arcLength(largest, True), True)

        return corners.reshape(-1, 2) if len(corners) > 0 else []

    def _is_rounded_corner(self, corners) -> bool:
        """Check if corners are rounded"""
        # Simplified check: if we detected corners without sharp angles
        return len(corners) >= 4

    def _get_screen_dominance(self, img_cv) -> float:
        """Calculate percentage of image that looks like a screen"""
        # Look for dark/uniform regions (typical of phone/tablet screens)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        # Find dark regions
        dark_pixels = np.sum(gray < 100)
        total_pixels = gray.shape[0] * gray.shape[1]

        return dark_pixels / total_pixels if total_pixels > 0 else 0.0

    def _detect_camera_area(self, img_cv) -> bool:
        """Detect if image has camera-like features"""
        # Look for circular/oval shapes (typical of cameras)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        # Detect circles using Hough transform
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=30,
            param1=50,
            param2=30,
            minRadius=5,
            maxRadius=100,
        )

        return circles is not None

    def _classify_from_features(self, features: dict) -> tuple[str, float]:
        """Classify device based on extracted features"""
        aspect = features["aspect_ratio"]
        rounded = features["has_rounded_corners"]
        screen = features["screen_dominance"]
        camera = features["has_camera"]
        color_var = features["color_variance"]

        # Heuristics for device classification
        scores = {
            "phone": 0.0,
            "tablet": 0.0,
            "laptop": 0.0,
            "monitor": 0.0,
        }

        # Phone detection (narrow aspect ratio, rounded corners, camera)
        if 0.45 < aspect < 0.6:  # Typical phone aspect ratio
            scores["phone"] += 0.5
            if rounded:
                scores["phone"] += 0.3
            if camera:
                scores["phone"] += 0.2

        # Tablet detection (wider than phone, less rounded)
        elif 0.6 < aspect < 0.9:
            scores["tablet"] += 0.5
            if screen > 0.3:
                scores["tablet"] += 0.3

        # Laptop/monitor detection (wide aspect ratio)
        elif aspect > 1.2:
            if screen > 0.4 and color_var < 30:
                scores["laptop"] += 0.4
                scores["monitor"] += 0.4
            else:
                scores["laptop"] += 0.5

        # Default to phone if narrower
        if max(scores.values()) == 0:
            if aspect < 0.8:
                scores["phone"] = 0.3
            else:
                scores["tablet"] = 0.3

        # Find best match
        best_device = max(scores, key=scores.get)
        best_score = scores[best_device]

        # Boosters
        if rounded and best_device == "phone":
            best_score = min(1.0, best_score + 0.2)
        if camera and best_device == "phone":
            best_score = min(1.0, best_score + 0.15)

        return (best_device, min(best_score, 1.0))
