import os

CAPTURE_ROOT = os.getenv("IMAGE_CAPTURE_ROOT") or os.path.expanduser("~/captures")
THUMBNAIL_SIZE = (300, 200)
