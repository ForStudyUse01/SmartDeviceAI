"""
Conservative Image Analysis - Condition Detection
Evidence-based analysis without hallucinating damage
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class VisibleCondition(str, Enum):
    """Observable physical state only"""
    PRISTINE = "pristine"           # No visible damage
    MINOR_COSMETIC = "minor_cosmetic"  # Light scratches, dust
    MODERATE_DAMAGE = "moderate_damage"  # Visible scratches, dents
    SEVERE_DAMAGE = "severe_damage"   # Cracks, missing parts, corrosion
    UNKNOWN = "unknown"              # Cannot determine


class FunctionalStatus(str, Enum):
    """Inferred operational capability - explicitly uncertain"""
    LIKELY_WORKING = "likely_working"      # No visible damage to suggest otherwise
    POSSIBLY_WORKING = "possibly_working"  # Some damage but not critical
    LIKELY_DAMAGED = "likely_damaged"      # Significant damage visible
    UNKNOWN = "unknown"                    # Cannot be determined from images


class MissingView(str, Enum):
    """Views that would improve confidence"""
    SCREEN_POWERED_ON = "screen_powered_on"
    FRONT_DISPLAY = "front_display"
    BACK = "back"
    SIDES = "sides"
    INTERNAL = "internal"


@dataclass
class DamageSignal:
    """Concrete observable damage"""
    category: str  # "cracks", "corrosion", "deformation", "burn_marks", "swelling", "missing_parts", "major_scratches"
    severity: str  # "minor", "moderate", "severe"
    location: str  # Where on device
    confidence: int  # 0-100, how certain we are about this


@dataclass
class AnalysisResult:
    """Evidence-based analysis result"""
    device_type: str
    visible_condition: VisibleCondition
    functional_status: FunctionalStatus
    confidence: int  # Overall confidence in this assessment (0-100)
    damage_signals: list[DamageSignal]  # Concrete observable damage
    missing_views: list[MissingView]  # Views that would improve confidence
    recommendation: str  # Conservative, evidence-based
    justification: str  # Explain the reasoning
    analysis_type: str  # "fast_fallback" | "evidence_based"
    num_images_analyzed: int


class ConservativeConditionAnalyzer:
    """
    Analyzes device condition conservatively.
    Never claims damage without evidence.
    Distinguishes visible vs functional vs confidence.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def analyze_phone(
        self,
        image_count: int,
        has_front: bool,
        has_back: bool,
        has_side: bool,
        has_powered_on: bool,
        visible_cracks: bool = False,
        visible_corrosion: bool = False,
        visible_deformation: bool = False,
        visible_burn_marks: bool = False,
        visible_swelling: bool = False,
        visible_missing_parts: bool = False,
        major_scratches_only: bool = False,
    ) -> AnalysisResult:
        """
        Analyze phone condition conservatively.

        Args:
            image_count: Number of images provided
            has_front: We have front/screen image
            has_back: We have back image
            has_side: We have side images
            has_powered_on: Screen is powered on in image
            visible_*: Concrete visual damage observations (MUST be confident)

        Returns:
            Conservative analysis result
        """

        damage_signals = []
        missing_views = []
        justification_parts = []

        # Detect concrete damage
        if visible_cracks:
            damage_signals.append(DamageSignal(
                category="cracks",
                severity="severe",
                location="display/body",
                confidence=95
            ))
            justification_parts.append("Cracks visible on screen or frame (confirmed)")

        if visible_corrosion:
            damage_signals.append(DamageSignal(
                category="corrosion",
                severity="moderate",
                location="connectors/body",
                confidence=85
            ))
            justification_parts.append("Corrosion observed on metal components")

        if visible_swelling:
            damage_signals.append(DamageSignal(
                category="swelling",
                severity="severe",
                location="battery/body",
                confidence=90
            ))
            justification_parts.append("Battery or internal swelling detected")

        if visible_burn_marks:
            damage_signals.append(DamageSignal(
                category="burn_marks",
                severity="severe",
                location="various",
                confidence=90
            ))
            justification_parts.append("Burn marks visible on components")

        if visible_missing_parts:
            damage_signals.append(DamageSignal(
                category="missing_parts",
                severity="severe",
                location="various",
                confidence=95
            ))
            justification_parts.append("Parts missing from device")

        if visible_deformation:
            damage_signals.append(DamageSignal(
                category="deformation",
                severity="moderate",
                location="frame/body",
                confidence=85
            ))
            justification_parts.append("Device body is bent or deformed")

        if major_scratches_only:
            damage_signals.append(DamageSignal(
                category="major_scratches",
                severity="moderate",
                location="screen/body",
                confidence=80
            ))
            justification_parts.append("Major/deep scratches visible")

        # Determine visible condition based on damage
        if visible_cracks or visible_burn_marks or visible_swelling or visible_missing_parts:
            visible_condition = VisibleCondition.SEVERE_DAMAGE
        elif visible_deformation or visible_corrosion or major_scratches_only:
            visible_condition = VisibleCondition.MODERATE_DAMAGE
        else:
            visible_condition = VisibleCondition.PRISTINE
            justification_parts.append("No visible damage observed")

        # Determine functional status conservatively
        if damage_signals:
            # Has concrete damage - but can't be sure if functional
            if visible_cracks or visible_swelling or visible_burn_marks:
                functional_status = FunctionalStatus.LIKELY_DAMAGED
            else:
                functional_status = FunctionalStatus.POSSIBLY_WORKING
        else:
            # No visible damage = likely working
            functional_status = FunctionalStatus.LIKELY_WORKING

        # Identify missing views
        if not has_front:
            missing_views.append(MissingView.FRONT_DISPLAY)
        if not has_powered_on and not has_front:
            missing_views.append(MissingView.SCREEN_POWERED_ON)
        if not has_back:
            missing_views.append(MissingView.BACK)
        if not has_side:
            missing_views.append(MissingView.SIDES)

        # Calculate confidence
        base_confidence = 60
        if image_count == 1:
            base_confidence = 40
        elif image_count == 2:
            base_confidence = 60
        elif image_count >= 3:
            base_confidence = 75

        if has_powered_on:
            base_confidence += 15
        if has_front and has_back:
            base_confidence += 10

        confidence = min(100, base_confidence)

        # Generate evidence-based recommendation
        if visible_cracks or visible_burn_marks or visible_missing_parts:
            recommendation = "Device shows severe damage. Not suitable for resale. Components may be salvageable for parts recycling."
        elif visible_swelling:
            recommendation = "Battery swelling detected - serious safety hazard. Do not use. Recycle immediately."
        elif visible_deformation or visible_corrosion or major_scratches_only:
            recommendation = "Device shows cosmetic damage. May have reduced resale value. Functionality must be verified separately."
        else:
            if image_count == 1:
                recommendation = "No damage visible in provided image. Recommend additional images (front, powered-on display) to verify functionality and complete assessment."
            elif image_count >= 3:
                recommendation = "No visible damage detected. Device appears suitable for resale or reuse if functionality is verified."
            else:
                recommendation = "No visible damage in current images. Additional views recommended for higher confidence."

        # Build justification
        if not justification_parts:
            justification_parts.append("Visual inspection clean - no damage indicators")

        if missing_views:
            missing_str = ", ".join([v.value for v in missing_views])
            justification_parts.append(f"Missing views for full assessment: {missing_str}")

        if image_count == 1:
            justification_parts.append("Only 1 image provided - confidence limited to visible surfaces only")

        justification = " | ".join(justification_parts)

        return AnalysisResult(
            device_type="phone",
            visible_condition=visible_condition,
            functional_status=functional_status,
            confidence=confidence,
            damage_signals=damage_signals,
            missing_views=missing_views,
            recommendation=recommendation,
            justification=justification,
            analysis_type="evidence_based",
            num_images_analyzed=image_count,
        )

    def analyze_laptop(
        self,
        image_count: int,
        visible_screen_crack: bool = False,
        visible_hinge_damage: bool = False,
        visible_keyboard_damage: bool = False,
        visible_corrosion: bool = False,
        visible_deformation: bool = False,
    ) -> AnalysisResult:
        """Analyze laptop condition conservatively"""

        damage_signals = []
        missing_views = []

        if visible_screen_crack:
            damage_signals.append(DamageSignal(
                category="cracks",
                severity="severe",
                location="screen",
                confidence=95
            ))

        if visible_hinge_damage:
            damage_signals.append(DamageSignal(
                category="deformation",
                severity="moderate",
                location="hinge",
                confidence=85
            ))

        if visible_keyboard_damage:
            damage_signals.append(DamageSignal(
                category="damage",
                severity="moderate",
                location="keyboard",
                confidence=80
            ))

        if visible_corrosion:
            damage_signals.append(DamageSignal(
                category="corrosion",
                severity="moderate",
                location="ports/internals",
                confidence=85
            ))

        if visible_deformation:
            damage_signals.append(DamageSignal(
                category="deformation",
                severity="moderate",
                location="chassis",
                confidence=85
            ))

        # Determine condition
        if visible_screen_crack:
            visible_condition = VisibleCondition.SEVERE_DAMAGE
        elif damage_signals:
            visible_condition = VisibleCondition.MODERATE_DAMAGE
        else:
            visible_condition = VisibleCondition.PRISTINE

        # Functional status
        if visible_screen_crack or visible_corrosion:
            functional_status = FunctionalStatus.LIKELY_DAMAGED
        elif damage_signals:
            functional_status = FunctionalStatus.POSSIBLY_WORKING
        else:
            functional_status = FunctionalStatus.LIKELY_WORKING

        # Missing views
        if image_count < 2:
            missing_views.append(MissingView.INTERNAL)

        confidence = min(100, 60 + (image_count * 10))

        if visible_screen_crack:
            recommendation = "Screen cracked - repair cost may exceed value. Suitable for parts recycling."
        elif damage_signals:
            recommendation = "Device shows damage. Resale value reduced. Functionality should be verified."
        else:
            if image_count == 1:
                recommendation = "No visible damage detected. Powered-on test and internal inspection recommended."
            else:
                recommendation = "No visible damage. Appears suitable for resale if functionality verified."

        justification = f"Analyzed {image_count} image(s). "
        if damage_signals:
            justification += f"Found {len(damage_signals)} damage indicator(s). "
        else:
            justification += "No damage markers observed. "

        if missing_views:
            justification += f"Missing: {', '.join([v.value for v in missing_views])}"

        return AnalysisResult(
            device_type="laptop",
            visible_condition=visible_condition,
            functional_status=functional_status,
            confidence=confidence,
            damage_signals=damage_signals,
            missing_views=missing_views,
            recommendation=recommendation,
            justification=justification,
            analysis_type="evidence_based",
            num_images_analyzed=image_count,
        )

    def fallback_analysis(self, device_type: str, image_count: int) -> AnalysisResult:
        """
        Safe fallback when visual analysis is impossible.
        Explicitly honest about uncertainty.
        """
        return AnalysisResult(
            device_type=device_type,
            visible_condition=VisibleCondition.UNKNOWN,
            functional_status=FunctionalStatus.UNKNOWN,
            confidence=0,  # Be honest about confidence
            damage_signals=[],
            missing_views=[],
            recommendation="Cannot assess condition from provided images. Clear images of all surfaces required.",
            justification="Image quality or framing prevents reliable visual assessment.",
            analysis_type="fallback",
            num_images_analyzed=image_count,
        )
