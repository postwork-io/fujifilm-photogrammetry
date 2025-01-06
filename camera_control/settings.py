import os

CAPTURE_ROOT = os.getenv("IMAGE_CAPTURE_ROOT") or os.path.expanduser("~/captures")
THUMBNAIL_SIZE = (300, 200)
STEPEPR_PIN = int(os.getenv("STEPPER_PIN") or 16)
STEPS_PER_ROTATION = int(os.getenv("STEPS_PER_ROTATION") or 800)
