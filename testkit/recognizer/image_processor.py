"""
Image Processor - Image loading and preprocessing utilities

Provides functions for loading images, extracting regions, and color analysis.
"""

from typing import Tuple, Optional
import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


def check_opencv() -> bool:
    """Check if OpenCV is available"""
    return CV2_AVAILABLE


def load_image(path: str) -> Optional[np.ndarray]:
    """
    Load an image from file.

    Args:
        path: Path to image file

    Returns:
        Image as numpy array (BGR format) or None if failed
    """
    if not CV2_AVAILABLE:
        return None

    img = cv2.imread(path)
    return img


def extract_region(image: np.ndarray, x: int, y: int,
                   width: int, height: int) -> np.ndarray:
    """
    Extract a rectangular region from an image.

    Args:
        image: Source image (BGR)
        x: Left coordinate
        y: Top coordinate
        width: Region width
        height: Region height

    Returns:
        Extracted region as numpy array
    """
    # Clamp coordinates to image bounds
    h, w = image.shape[:2]
    x1 = max(0, int(x))
    y1 = max(0, int(y))
    x2 = min(w, int(x + width))
    y2 = min(h, int(y + height))

    return image[y1:y2, x1:x2].copy()


def extract_circle_region(image: np.ndarray, center_x: int, center_y: int,
                          radius: int) -> np.ndarray:
    """
    Extract a circular region from an image.

    Creates a masked region where pixels outside the circle are black.

    Args:
        image: Source image (BGR)
        center_x: Circle center X
        center_y: Circle center Y
        radius: Circle radius

    Returns:
        Extracted region with circular mask applied
    """
    # Extract bounding rectangle
    x = center_x - radius
    y = center_y - radius
    size = radius * 2

    region = extract_region(image, x, y, size, size)

    if region.size == 0:
        return region

    # Create circular mask
    h, w = region.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(mask, (w // 2, h // 2), min(w, h) // 2, 255, -1)

    # Apply mask
    result = cv2.bitwise_and(region, region, mask=mask)
    return result


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """
    Convert image to grayscale.

    Args:
        image: Source image (BGR or grayscale)

    Returns:
        Grayscale image
    """
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def calculate_brightness(image: np.ndarray, use_mask: bool = False) -> float:
    """
    Calculate average brightness of an image region.

    Args:
        image: Image region (BGR or grayscale)
        use_mask: If True, ignore black pixels (for masked regions)

    Returns:
        Average brightness (0.0 to 1.0)
    """
    if image.size == 0:
        return 0.0

    gray = to_grayscale(image)

    if use_mask:
        # Only consider non-zero pixels
        non_zero = gray[gray > 0]
        if non_zero.size == 0:
            return 0.0
        return float(np.mean(non_zero)) / 255.0
    else:
        return float(np.mean(gray)) / 255.0


def hex_to_bgr(hex_color: str) -> Tuple[int, int, int]:
    """
    Convert hex color string to BGR tuple.

    Args:
        hex_color: Color in format "#RRGGBB"

    Returns:
        Tuple of (B, G, R) values
    """
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return (0, 0, 0)

    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    return (b, g, r)


def calculate_color_match(image: np.ndarray, target_color: Tuple[int, int, int],
                          tolerance: int = 50) -> float:
    """
    Calculate how well an image region matches a target color.

    Args:
        image: Image region (BGR)
        target_color: Target color as (B, G, R)
        tolerance: Color tolerance for matching

    Returns:
        Match score (0.0 to 1.0)
    """
    if image.size == 0 or len(image.shape) < 3:
        return 0.0

    # Create color range
    lower = np.array([max(0, c - tolerance) for c in target_color], dtype=np.uint8)
    upper = np.array([min(255, c + tolerance) for c in target_color], dtype=np.uint8)

    # Create mask of matching pixels
    mask = cv2.inRange(image, lower, upper)

    # Calculate percentage of matching pixels
    total_pixels = mask.size
    matching_pixels = np.count_nonzero(mask)

    return matching_pixels / total_pixels if total_pixels > 0 else 0.0


def apply_perspective_transform(image: np.ndarray,
                                src_points: np.ndarray,
                                dst_size: Tuple[int, int]) -> np.ndarray:
    """
    Apply perspective transformation to correct camera angle.

    Args:
        image: Source image
        src_points: Four corner points in source image (4x2 array)
        dst_size: Output size (width, height)

    Returns:
        Transformed image
    """
    dst_points = np.array([
        [0, 0],
        [dst_size[0], 0],
        [dst_size[0], dst_size[1]],
        [0, dst_size[1]]
    ], dtype=np.float32)

    src_points = np.array(src_points, dtype=np.float32)

    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
    result = cv2.warpPerspective(image, matrix, dst_size)

    return result


def resize_image(image: np.ndarray, width: int, height: int) -> np.ndarray:
    """
    Resize image to specified dimensions.

    Args:
        image: Source image
        width: Target width
        height: Target height

    Returns:
        Resized image
    """
    return cv2.resize(image, (width, height), interpolation=cv2.INTER_LINEAR)


def threshold_image(image: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """
    Apply binary threshold to grayscale image.

    Args:
        image: Grayscale image
        threshold: Threshold value (0.0 to 1.0)

    Returns:
        Binary image (0 or 255)
    """
    gray = to_grayscale(image)
    thresh_val = int(threshold * 255)
    _, binary = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)
    return binary


def enhance_contrast(image: np.ndarray, clip_limit: float = 2.0,
                     tile_size: int = 8) -> np.ndarray:
    """
    Enhance local contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization).

    Args:
        image: Source image (BGR or grayscale)
        clip_limit: Threshold for contrast limiting
        tile_size: Size of grid for histogram equalization

    Returns:
        Contrast-enhanced image
    """
    if not CV2_AVAILABLE:
        return image

    if len(image.shape) == 3:
        # For color images, apply CLAHE to L channel in LAB space
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=clip_limit,
                                tileGridSize=(tile_size, tile_size))
        l_enhanced = clahe.apply(l)
        return cv2.cvtColor(cv2.merge([l_enhanced, a, b]), cv2.COLOR_LAB2BGR)
    else:
        # For grayscale images
        clahe = cv2.createCLAHE(clipLimit=clip_limit,
                                tileGridSize=(tile_size, tile_size))
        return clahe.apply(image)


def calculate_color_match_hsv(image: np.ndarray, target_bgr: Tuple[int, int, int],
                               h_tolerance: int = 15, s_min: int = 50) -> float:
    """
    Calculate color match using HSV color space (more robust to lighting changes).

    Args:
        image: Image region (BGR)
        target_bgr: Target color as (B, G, R)
        h_tolerance: Hue tolerance for matching (0-180)
        s_min: Minimum saturation to consider (filters out gray/white)

    Returns:
        Match score (0.0 to 1.0)
    """
    if image.size == 0 or len(image.shape) < 3:
        return 0.0

    # Convert image to HSV
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Convert target color to HSV
    target_pixel = np.uint8([[target_bgr]])
    target_hsv = cv2.cvtColor(target_pixel, cv2.COLOR_BGR2HSV)[0][0]
    target_h = int(target_hsv[0])

    # Calculate hue difference (handle wraparound at 180)
    h_channel = hsv[:, :, 0].astype(np.int32)
    h_diff = np.abs(h_channel - target_h)
    h_diff = np.minimum(h_diff, 180 - h_diff)

    # Saturation channel - filter out low saturation pixels
    s_channel = hsv[:, :, 1]

    # Match: hue within tolerance AND saturation above minimum
    match_mask = (h_diff <= h_tolerance) & (s_channel >= s_min)

    return float(np.sum(match_mask)) / match_mask.size if match_mask.size > 0 else 0.0
