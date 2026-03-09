"""
Camera - Camera capture functionality for snapshot command

Provides:
- Camera device enumeration
- Image capture from USB webcams, laptop cameras, etc.
- OpenCV availability check
"""

import os
from datetime import datetime
from typing import List, Tuple, Optional


def check_opencv() -> bool:
    """Check if OpenCV is available."""
    try:
        import cv2
        return True
    except ImportError:
        return False


def list_cameras(max_devices: int = 10) -> List[Tuple[int, str]]:
    """
    Enumerate available camera devices.

    Args:
        max_devices: Maximum number of devices to check

    Returns:
        List of (index, name) tuples for available cameras
    """
    import cv2

    cameras = []
    for i in range(max_devices):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            # Try to get device name (not always available)
            name = f"Camera {i}"
            if i == 0:
                name += " (default)"
            cameras.append((i, name))
            cap.release()
        else:
            # Stop checking after first failure (usually contiguous)
            if i > 0 and not cameras:
                continue
            elif cameras:
                break

    return cameras


def capture_snapshot(device_index: int = 0,
                     output_path: Optional[str] = None,
                     output_dir: str = "ramgs_tmp_imgs") -> Tuple[bool, str, str]:
    """
    Capture a single image from camera.

    Args:
        device_index: Camera device index
        output_path: Custom output filename (optional)
        output_dir: Output directory (default: ramgs_tmp_imgs)

    Returns:
        (success, image_path, error_message)
    """
    import cv2

    # Ensure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Open camera
    cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        return False, "", f"Failed to access camera device {device_index}. Device may be in use or not available."

    try:
        # Allow camera to warm up - read a few frames
        for _ in range(5):
            cap.read()

        # Capture frame
        ret, frame = cap.read()
        if not ret or frame is None:
            return False, "", f"Failed to capture image from camera device {device_index}"

        # Generate filename
        if output_path:
            filename = output_path
            if not filename.lower().endswith('.png'):
                filename += '.png'
        else:
            now = datetime.now()
            filename = f"snapshot_{now.strftime('%Y%m%d_%H%M%S')}_{now.microsecond // 1000:03d}.png"

        # Full path
        full_path = os.path.join(output_dir, filename)

        # Save image
        success = cv2.imwrite(full_path, frame)
        if not success:
            return False, "", f"Failed to save image to {full_path}"

        return True, full_path, ""

    finally:
        cap.release()


class CameraCapture:
    """
    Camera capture context manager for repeated captures.
    Keeps camera open between captures for better performance.
    """

    def __init__(self, device_index: int = 0, output_dir: str = "ramgs_tmp_imgs"):
        self.device_index = device_index
        self.output_dir = output_dir
        self.cap = None

    def __enter__(self):
        import cv2

        # Ensure output directory exists
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        # Open camera
        self.cap = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to access camera device {self.device_index}. Device may be in use or not available.")

        # Warm up camera
        for _ in range(5):
            self.cap.read()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cap:
            self.cap.release()
        return False

    def capture(self, output_path: Optional[str] = None) -> Tuple[bool, str, str]:
        """
        Capture a single frame.

        Args:
            output_path: Custom output filename (optional)

        Returns:
            (success, image_path, error_message)
        """
        import cv2

        if not self.cap or not self.cap.isOpened():
            return False, "", "Camera not opened"

        # Capture frame
        ret, frame = self.cap.read()
        if not ret or frame is None:
            return False, "", f"Failed to capture image from camera device {self.device_index}"

        # Generate filename
        if output_path:
            filename = output_path
            if not filename.lower().endswith('.png'):
                filename += '.png'
        else:
            now = datetime.now()
            filename = f"snapshot_{now.strftime('%Y%m%d_%H%M%S')}_{now.microsecond // 1000:03d}.png"

        # Full path
        full_path = os.path.join(self.output_dir, filename)

        # Save image
        success = cv2.imwrite(full_path, frame)
        if not success:
            return False, "", f"Failed to save image to {full_path}"

        return True, full_path, ""
