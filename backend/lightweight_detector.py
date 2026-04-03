"""
Lightweight Image Feature Detector
Fast heuristic-based damage detection without heavy ML
CPU-friendly, <50ms per image
"""

import logging
from dataclasses import dataclass
from typing import Optional
import cv2
import numpy as np
from PIL import Image
import io

logger = logging.getLogger(__name__)


@dataclass
class FeatureDetectionResult:
    """Result of feature-based damage detection"""
    has_cracks: bool = False
    has_corrosion: bool = False
    has_burn_marks: bool = False
    has_swelling: bool = False
    has_major_scratches: bool = False
    has_deformation: bool = False
    has_missing_parts: bool = False
    confidence_level: str = "low"  # "low", "medium", "high"
    detectable_features: list[str] = None  # Features actually visible in image

    def __post_init__(self):
        if self.detectable_features is None:
            self.detectable_features = []


class LightweightFeatureDetector:
    """
    Fast damage detection using computer vision heuristics.
    Does NOT claim damage unless there's strong visual evidence.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def analyze_image(self, image_bytes: bytes) -> FeatureDetectionResult:
        """
        Analyze image for damage signals using lightweight heuristics.

        Returns only what can be confidently detected from the image.
        Conservative: prefers false negatives over false positives.
        """
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            img_array = np.array(image)

            result = FeatureDetectionResult()

            # Only use features we can detect reliably
            result = self._detect_cracks(img_array, result)
            result = self._detect_corrosion(img_array, result)
            result = self._detect_burn_marks(img_array, result)
            result = self._detect_major_scratches(img_array, result)
            result = self._detect_screen_damage(img_array, result)

            # Set confidence based on what we could actually detect
            if result.detectable_features:
                if len(result.detectable_features) >= 2:
                    result.confidence_level = "high"
                else:
                    result.confidence_level = "medium"
            else:
                result.confidence_level = "low"

            return result

        except Exception as e:
            self.logger.error(f"Feature detection failed: {e}")
            return FeatureDetectionResult(confidence_level="low")

    def _detect_cracks(self, img_array: np.ndarray, result: FeatureDetectionResult) -> FeatureDetectionResult:
        """
        Detect cracks using edge detection and line finding.
        Only reports cracks if VERY confident.
        """
        try:
            img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

            # Use Canny edge detection
            edges = cv2.Canny(gray, 50, 150)

            # Look for long straight lines (typical of cracks)
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, 50, minLineLength=100, maxLineGap=10)

            if lines is not None and len(lines) > 10:
                # Many long lines might indicate cracks
                line_angles = []
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
                    line_angles.append(angle % 180)

                # Cracks often form vertical or horizontal patterns
                vertical_lines = sum(1 for a in line_angles if abs(a) < 30 or abs(a - 180) < 30)
                if vertical_lines > 5:
                    result.has_cracks = True
                    result.detectable_features.append("cracks")
                    self.logger.info("Cracks detected with high confidence")

        except Exception as e:
            self.logger.debug(f"Crack detection error: {e}")

        return result

    def _detect_corrosion(self, img_array: np.ndarray, result: FeatureDetectionResult) -> FeatureDetectionResult:
        """
        Detect corrosion via color analysis (green/blue discoloration on metal).
        Only reports if clear color anomalies found.
        """
        try:
            # Convert to HSV for better color detection
            img_hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)

            # Green-blue corrosion (copper oxide)
            lower_green = np.array([40, 40, 40])
            upper_green = np.array([100, 255, 255])

            mask = cv2.inRange(img_hsv, lower_green, upper_green)
            corrosion_pixels = cv2.countNonZero(mask)

            total_pixels = img_array.shape[0] * img_array.shape[1]
            corrosion_ratio = corrosion_pixels / total_pixels

            # Only flag if significant green/blue area (>5% suggests corrosion)
            if corrosion_ratio > 0.05:
                result.has_corrosion = True
                result.detectable_features.append("corrosion")
                self.logger.info(f"Corrosion detected: {corrosion_ratio:.2%} of image")

        except Exception as e:
            self.logger.debug(f"Corrosion detection error: {e}")

        return result

    def _detect_burn_marks(self, img_array: np.ndarray, result: FeatureDetectionResult) -> FeatureDetectionResult:
        """
        Detect burn marks via dark spots and abnormal black regions.
        """
        try:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

            # Look for very dark regions (char/burn marks)
            very_dark = np.sum(gray < 30)
            dark_ratio = very_dark / gray.size

            # Also look for localized dark spots (not uniform darkness)
            if dark_ratio > 0.02 and dark_ratio < 0.4:
                # Some dark areas present, check if they're localized (burns)
                blurred = cv2.GaussianBlur(gray, (21, 21), 0)
                difference = cv2.absdiff(gray, blurred)
                burn_indicator = np.sum(difference > 50)

                if burn_indicator > gray.size * 0.01:
                    result.has_burn_marks = True
                    result.detectable_features.append("burn_marks")
                    self.logger.info("Burn marks detected")

        except Exception as e:
            self.logger.debug(f"Burn mark detection error: {e}")

        return result

    def _detect_major_scratches(self, img_array: np.ndarray, result: FeatureDetectionResult) -> FeatureDetectionResult:
        """
        Detect major/deep scratches (not minor surface scratches).
        Only reports very obvious scratches.
        """
        try:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

            # Use morphological operations to find linear features
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 1))
            horizontal = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 20))
            vertical = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)

            scratches = cv2.bitwise_or(horizontal, vertical)
            scratch_pixels = cv2.countNonZero(scratches)

            total = scratches.shape[0] * scratches.shape[1]
            scratch_ratio = scratch_pixels / total

            # Only flag if very prominent scratches
            if scratch_ratio > 0.08:
                result.has_major_scratches = True
                result.detectable_features.append("major_scratches")
                self.logger.info(f"Major scratches detected: {scratch_ratio:.2%}")

        except Exception as e:
            self.logger.debug(f"Scratch detection error: {e}")

        return result

    def _detect_screen_damage(self, img_array: np.ndarray, result: FeatureDetectionResult) -> FeatureDetectionResult:
        """
        Detect specific screen damage: cracks, black spots, dead pixels.
        """
        try:
            # For phone/screen detection, look for:
            # 1. Large dark regions on otherwise bright areas (dead pixels/areas)
            # 2. Shattered glass patterns

            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

            # Detect high-contrast anomalies
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            anomaly_score = np.std(laplacian)

            # Shattered glass has very high edge density
            edges = cv2.Canny(gray, 30, 100)
            edge_density = np.sum(edges > 0) / edges.size

            if edge_density > 0.3 and anomaly_score > 500:
                result.has_cracks = True
                result.detectable_features.append("screen_damage")
                self.logger.info("Screen damage detected")

        except Exception as e:
            self.logger.debug(f"Screen damage detection error: {e}")

        return result


def image_quality_score(image_bytes: bytes) -> int:
    """
    Score image quality for analysis (0-100).
    Higher = better quality for visual inspection.

    Factors:
    - Brightness (not too dark, not washed out)
    - Contrast (can see details)
    - Focus (not blurry)
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        img_array = np.array(image.convert('RGB'))

        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        # Brightness score: optimal 80-180
        mean_brightness = np.mean(gray)
        brightness_score = 100 if 80 <= mean_brightness <= 180 else max(0, 100 - abs(mean_brightness - 130) // 2)

        # Contrast score: std dev of pixel values
        contrast = np.std(gray)
        contrast_score = min(100, int(contrast))

        # Sharpness (blur detection): Laplacian variance
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        sharpness_score = min(100, max(0, int(laplacian_var / 10)))

        # Weighted average
        quality = int(0.3 * brightness_score + 0.3 * contrast_score + 0.4 * sharpness_score)
        return max(0, min(100, quality))

    except Exception as e:
        logger.warning(f"Quality score calculation failed: {e}")
        return 50  # Default neutral score
