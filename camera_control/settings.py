import os

CAPTURE_ROOT = os.getenv("IMAGE_CAPTURE_ROOT") or os.path.expanduser("~/captures")
THUMBNAIL_SIZE = (300, 200)
TURNTABLE_STEPPER_PIN = int(os.getenv("TURNTABLE_STEPPER_PIN") or 16)
POLARIZER_STEPPER_PIN = int(os.getenv("POLARIZER_STEPPER_PIN") or 22)
POLARIZER_DIRECTION_PIN = int(os.getenv("POLARIZER_DIRECTION_PIN") or 32)
TURNTABLE_STEPS_PER_ROTATION = int(os.getenv("TURNTABLE_STEPS_PER_ROTATION") or 800)
POLARIZER_STEPS_PER_ROTATION = int(os.getenv("POLARIZER_STEPS_PER_ROTATION") or 1920)
"""
Current Stepper Belt Gear has 20 Teeth
Focus Ring has 96 teeth
That gives us a gear ratio of 5/24 or 1:4.8
Stepper steps is 400 for a total of 1920 steps for a total rotation
"""
POST_PROCESS_URL = os.getenv("POST_PROCESS_URL") or "http://192.168.1.183:5000/upload"
SETTLE_TIME = float(os.getenv("SETTLE_TIME", 3))
