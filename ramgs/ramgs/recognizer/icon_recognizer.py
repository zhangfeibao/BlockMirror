"""
Icon Recognizer - Detect on/off state of indicator icons

Uses brightness and color matching to determine if an icon is lit.
"""

from typing import Tuple
import numpy as np

from .image_processor import (
    extract_region, extract_circle_region, calculate_brightness,
    calculate_color_match, calculate_color_match_hsv, hex_to_bgr, to_grayscale
)
from .recognition_result import IconState


# Weights for multi-feature fusion
BRIGHTNESS_WEIGHT = 0.4
COLOR_WEIGHT = 0.3
GLOW_WEIGHT = 0.3


class IconRecognizer:
    """Recognizes on/off state of indicator icons"""

    def __init__(self, brightness_threshold: float = 0.4):
        """
        Initialize icon recognizer.

        Args:
            brightness_threshold: Threshold for on/off decision (0.0 to 1.0)
        """
        self.brightness_threshold = brightness_threshold

    def recognize_rectangle(self, image: np.ndarray, x: int, y: int,
                           width: int, height: int,
                           active_color: str = None) -> Tuple[IconState, float]:
        """
        Recognize state of a rectangular icon.

        Args:
            image: Full panel image (BGR)
            x: Icon left coordinate
            y: Icon top coordinate
            width: Icon width
            height: Icon height
            active_color: Expected color when active (hex string)

        Returns:
            Tuple of (state, confidence)
        """
        region = extract_region(image, x, y, width, height)
        return self._analyze_region(region, active_color)

    def recognize_circle(self, image: np.ndarray, center_x: int, center_y: int,
                        radius: int, active_color: str = None) -> Tuple[IconState, float]:
        """
        Recognize state of a circular icon.

        Args:
            image: Full panel image (BGR)
            center_x: Circle center X
            center_y: Circle center Y
            radius: Circle radius
            active_color: Expected color when active (hex string)

        Returns:
            Tuple of (state, confidence)
        """
        region = extract_circle_region(image, center_x, center_y, radius)
        return self._analyze_region(region, active_color, use_mask=True)

    def recognize_ellipse(self, image: np.ndarray, center_x: int, center_y: int,
                         radius_x: int, radius_y: int,
                         active_color: str = None) -> Tuple[IconState, float]:
        """
        Recognize state of an elliptical icon.

        Args:
            image: Full panel image (BGR)
            center_x: Ellipse center X
            center_y: Ellipse center Y
            radius_x: Horizontal radius
            radius_y: Vertical radius
            active_color: Expected color when active (hex string)

        Returns:
            Tuple of (state, confidence)
        """
        # Extract bounding rectangle
        x = center_x - radius_x
        y = center_y - radius_y
        width = radius_x * 2
        height = radius_y * 2

        region = extract_region(image, x, y, width, height)
        return self._analyze_region(region, active_color)

    def _detect_led_glow(self, region: np.ndarray) -> float:
        """
        Detect LED glow characteristic: center is brighter than edges.

        Args:
            region: Image region to analyze

        Returns:
            Glow score (0.0 to 1.0), higher means stronger center glow
        """
        if region.size == 0:
            return 0.0

        gray = to_grayscale(region)
        h, w = gray.shape

        if h < 4 or w < 4:
            return 0.0

        # Define center region (inner 50%)
        center_y, center_x = h // 2, w // 2
        r = min(h, w) // 4

        # Create center mask
        y_coords, x_coords = np.ogrid[:h, :w]
        center_mask = ((x_coords - center_x)**2 + (y_coords - center_y)**2) <= r**2

        if np.sum(center_mask) == 0 or np.sum(~center_mask) == 0:
            return 0.0

        center_brightness = np.mean(gray[center_mask]) / 255.0
        edge_brightness = np.mean(gray[~center_mask]) / 255.0

        # Glow score: how much brighter is center vs edges
        glow = max(0.0, center_brightness - edge_brightness)

        # Normalize to 0-1 range (typical LED glow difference is 0.1-0.3)
        return min(glow * 3.0, 1.0)

    def _analyze_region(self, region: np.ndarray, active_color: str = None,
                       use_mask: bool = False) -> Tuple[IconState, float]:
        """
        Analyze a region to determine on/off state using multi-feature fusion.

        Args:
            region: Image region to analyze
            active_color: Expected active color (hex string)
            use_mask: Whether to ignore black pixels

        Returns:
            Tuple of (state, confidence)
        """
        if region.size == 0:
            return (IconState.UNKNOWN, 0.0)

        # Calculate brightness score
        brightness = calculate_brightness(region, use_mask=use_mask)

        # Calculate LED glow score
        glow_score = self._detect_led_glow(region)

        # Calculate color match score if active color is provided
        if active_color:
            target_bgr = hex_to_bgr(active_color)
            # Use HSV color matching for better robustness
            color_match = calculate_color_match_hsv(region, target_bgr)

            # Multi-feature weighted combination
            score = (brightness * BRIGHTNESS_WEIGHT +
                    color_match * COLOR_WEIGHT +
                    glow_score * GLOW_WEIGHT)
        else:
            # Use brightness and glow only
            score = brightness * 0.6 + glow_score * 0.4

        # Determine state based on threshold
        if score >= self.brightness_threshold:
            state = IconState.ON
            # Base confidence + feature consistency bonus
            base_conf = 0.6 + (score - self.brightness_threshold) / (1.0 - self.brightness_threshold) * 0.3
            # Consistency bonus: if glow is detected, it confirms LED is on
            consistency_bonus = 0.1 if glow_score > 0.1 else 0.0
            confidence = min(base_conf + consistency_bonus, 1.0)
        else:
            state = IconState.OFF
            # Higher confidence when clearly off (low score)
            confidence = 0.6 + (self.brightness_threshold - score) / self.brightness_threshold * 0.4

        return (state, min(confidence, 1.0))
