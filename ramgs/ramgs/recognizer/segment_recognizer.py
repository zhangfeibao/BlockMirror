"""
Segment Recognizer - Seven-segment display digit recognition

Uses pattern matching to recognize digits displayed on seven-segment displays.
"""

from typing import Tuple, List, Optional
import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from .image_processor import (
    extract_region, to_grayscale, calculate_brightness, threshold_image
)


# Seven-segment encoding table
# Segments: a=top, b=top-right, c=bottom-right, d=bottom, e=bottom-left, f=top-left, g=middle
#
#    aaa
#   f   b
#    ggg
#   e   c
#    ddd
#
# Each entry: (character, [a, b, c, d, e, f, g])
SEGMENT_PATTERNS = {
    '0': [1, 1, 1, 1, 1, 1, 0],
    '1': [0, 1, 1, 0, 0, 0, 0],
    '2': [1, 1, 0, 1, 1, 0, 1],
    '3': [1, 1, 1, 1, 0, 0, 1],
    '4': [0, 1, 1, 0, 0, 1, 1],
    '5': [1, 0, 1, 1, 0, 1, 1],
    '6': [1, 0, 1, 1, 1, 1, 1],
    '7': [1, 1, 1, 0, 0, 0, 0],
    '8': [1, 1, 1, 1, 1, 1, 1],
    '9': [1, 1, 1, 1, 0, 1, 1],
    'A': [1, 1, 1, 0, 1, 1, 1],
    'b': [0, 0, 1, 1, 1, 1, 1],
    'C': [1, 0, 0, 1, 1, 1, 0],
    'd': [0, 1, 1, 1, 1, 0, 1],
    'E': [1, 0, 0, 1, 1, 1, 1],
    'F': [1, 0, 0, 0, 1, 1, 1],
    '-': [0, 0, 0, 0, 0, 0, 1],
    ' ': [0, 0, 0, 0, 0, 0, 0],
}

# Normalized segment positions (relative to digit bounding box)
# Each segment: (x_start, y_start, x_end, y_end) as fractions of width/height
# Optimized positions with tighter bounds to avoid edge interference
SEGMENT_POSITIONS = {
    'a': (0.20, 0.02, 0.80, 0.18),  # Top horizontal
    'b': (0.72, 0.10, 0.98, 0.48),  # Top-right vertical
    'c': (0.72, 0.52, 0.98, 0.90),  # Bottom-right vertical
    'd': (0.20, 0.82, 0.80, 0.98),  # Bottom horizontal
    'e': (0.02, 0.52, 0.28, 0.90),  # Bottom-left vertical
    'f': (0.02, 0.10, 0.28, 0.48),  # Top-left vertical
    'g': (0.20, 0.44, 0.80, 0.56),  # Middle horizontal
}


class SegmentRecognizer:
    """Recognizes digits on seven-segment displays"""

    def __init__(self, segment_threshold: float = 0.4):
        """
        Initialize segment recognizer.

        Args:
            segment_threshold: Brightness threshold for segment on/off
        """
        self.segment_threshold = segment_threshold

    def recognize_digit(self, image: np.ndarray, x: int, y: int,
                       width: int, height: int) -> Tuple[str, float]:
        """
        Recognize a single digit from a seven-segment display.

        Args:
            image: Full panel image (BGR)
            x: Digit region left coordinate
            y: Digit region top coordinate
            width: Digit region width
            height: Digit region height

        Returns:
            Tuple of (recognized character, confidence)
        """
        region = extract_region(image, x, y, width, height)

        if region.size == 0:
            return (' ', 0.0)

        # Detect segment states
        segment_states = self._detect_segments(region)

        # Match against patterns
        return self._match_pattern(segment_states)

    def recognize_multi_digit(self, image: np.ndarray, x: int, y: int,
                             width: int, height: int,
                             digit_count: int = None) -> Tuple[str, float]:
        """
        Recognize multiple digits from a seven-segment display area.

        Args:
            image: Full panel image (BGR)
            x: Display area left coordinate
            y: Display area top coordinate
            width: Display area width
            height: Display area height
            digit_count: Number of digits (auto-detect if None)

        Returns:
            Tuple of (recognized string, average confidence)
        """
        region = extract_region(image, x, y, width, height)

        if region.size == 0:
            return ('', 0.0)

        # Auto-detect digit count based on aspect ratio
        if digit_count is None:
            aspect = width / height if height > 0 else 1
            digit_count = max(1, int(aspect / 0.6))  # Typical digit aspect ~0.6

        # Split region into individual digits
        digit_width = width // digit_count

        result = ''
        total_confidence = 0.0

        for i in range(digit_count):
            digit_x = x + i * digit_width
            char, conf = self.recognize_digit(image, digit_x, y, digit_width, height)
            result += char
            total_confidence += conf

        avg_confidence = total_confidence / digit_count if digit_count > 0 else 0.0

        # Strip leading/trailing spaces
        result = result.strip()

        return (result, avg_confidence)

    def _detect_segments(self, region: np.ndarray) -> List[float]:
        """
        Detect brightness of each segment in a digit region.

        Args:
            region: Digit image region

        Returns:
            List of 7 brightness values [a, b, c, d, e, f, g]
        """
        h, w = region.shape[:2]
        gray = to_grayscale(region)

        # Apply preprocessing for better segment detection
        gray = self._preprocess_digit(gray)

        segment_values = []
        segment_order = ['a', 'b', 'c', 'd', 'e', 'f', 'g']

        for seg_name in segment_order:
            pos = SEGMENT_POSITIONS[seg_name]

            # Calculate pixel coordinates
            x1 = int(pos[0] * w)
            y1 = int(pos[1] * h)
            x2 = int(pos[2] * w)
            y2 = int(pos[3] * h)

            # Ensure valid region
            x1, x2 = max(0, x1), min(w, x2)
            y1, y2 = max(0, y1), min(h, y2)

            if x2 > x1 and y2 > y1:
                seg_region = gray[y1:y2, x1:x2]
                # Use percentile-based brightness (top 30% pixels)
                # This is more robust than mean for detecting lit segments
                brightness = self._calculate_segment_brightness(seg_region)
            else:
                brightness = 0.0

            segment_values.append(brightness)

        return segment_values

    def _preprocess_digit(self, gray: np.ndarray) -> np.ndarray:
        """
        Preprocess digit region for better segment detection.

        Args:
            gray: Grayscale digit image

        Returns:
            Preprocessed grayscale image
        """
        if not CV2_AVAILABLE or gray.size == 0:
            return gray

        # Apply CLAHE for local contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
        enhanced = clahe.apply(gray)

        # Light Gaussian blur to reduce noise
        if enhanced.shape[0] >= 5 and enhanced.shape[1] >= 5:
            enhanced = cv2.GaussianBlur(enhanced, (3, 3), 0)

        return enhanced

    def _calculate_segment_brightness(self, seg_region: np.ndarray) -> float:
        """
        Calculate brightness of a segment region using robust statistics.

        Uses top percentile of pixels rather than mean, which better captures
        the brightness of lit LED segments.

        Args:
            seg_region: Grayscale segment region

        Returns:
            Brightness value (0.0 to 1.0)
        """
        if seg_region.size == 0:
            return 0.0

        # Use 70th percentile - captures lit pixels while ignoring dark edges
        percentile_val = np.percentile(seg_region, 70)

        return float(percentile_val) / 255.0

    def _calculate_adaptive_threshold(self, segment_values: List[float]) -> float:
        """
        Calculate adaptive threshold based on segment value distribution.

        Args:
            segment_values: List of 7 brightness values

        Returns:
            Adaptive threshold value
        """
        if not segment_values:
            return self.segment_threshold

        min_val = min(segment_values)
        max_val = max(segment_values)

        # If there's good contrast, use midpoint
        if max_val - min_val > 0.15:
            # Use weighted midpoint, slightly biased toward lower values
            return min_val + (max_val - min_val) * 0.4
        else:
            # Fall back to default threshold
            return self.segment_threshold

    def _match_pattern(self, segment_values: List[float]) -> Tuple[str, float]:
        """
        Match detected segment values against known patterns.

        Args:
            segment_values: List of 7 brightness values

        Returns:
            Tuple of (best matching character, confidence)
        """
        # Calculate adaptive threshold based on value distribution
        adaptive_threshold = self._calculate_adaptive_threshold(segment_values)

        # Convert to binary based on adaptive threshold
        binary_segments = [1 if v >= adaptive_threshold else 0
                         for v in segment_values]

        best_match = ' '
        best_score = -1
        best_pattern = [0] * 7

        for char, pattern in SEGMENT_PATTERNS.items():
            # Calculate match score
            matches = sum(1 for a, b in zip(binary_segments, pattern) if a == b)
            score = matches / 7.0

            if score > best_score:
                best_score = score
                best_match = char
                best_pattern = pattern

        # Separate ON and OFF segment values based on best pattern
        on_vals = [v for v, p in zip(segment_values, best_pattern) if p == 1]
        off_vals = [v for v, p in zip(segment_values, best_pattern) if p == 0]

        # Calculate confidence using multiple factors

        # Factor 1: Pattern match score (how many segments match)
        pattern_score = best_score

        # Factor 2: Segment clarity score (how clearly ON vs OFF)
        clarity_score = 0.0
        for v, p in zip(segment_values, best_pattern):
            if p == 1:
                # ON segment: higher brightness = better
                clarity_score += min(v / 0.6, 1.0)  # Normalize to expected ON brightness
            else:
                # OFF segment: lower brightness = better
                clarity_score += min((1.0 - v) / 0.7, 1.0)  # Normalize to expected OFF darkness
        clarity_score /= 7.0

        # Factor 3: Contrast bonus (separation between ON and OFF)
        contrast_bonus = 0.0
        if on_vals and off_vals:
            on_mean = np.mean(on_vals)
            off_mean = np.mean(off_vals)
            contrast = on_mean - off_mean
            # Strong bonus for good contrast (0.2-0.5 is typical good range)
            if contrast > 0.1:
                contrast_bonus = min(contrast * 0.5, 0.15)

        # Combine factors with weights
        # Pattern match is most important, then clarity, then contrast
        confidence = (pattern_score * 0.4 +
                     clarity_score * 0.45 +
                     contrast_bonus)

        # Ensure confidence is in valid range
        confidence = max(0.0, min(confidence, 1.0))

        return (best_match, confidence)
