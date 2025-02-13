import time
import math
import atexit

# import RPi.GPIO as GPIO
try:
    import RPi.GPIO as GPIO
except ImportError:

    class mock_gpio:
        BOARD = ""
        OUT = 0
        IN = 1
        HIGH = 1
        LOW = 0

        def setmode(self, mode):
            pass

        def setup(self, pin: int, pin_mode: int):
            pass

        def output(self, pin: int, value: int):
            pass

        def cleanup(self):
            pass

    GPIO = mock_gpio()

GPIO.setmode(GPIO.BOARD)
atexit.register(GPIO.cleanup)


class Stepper:
    FORWARD = 0
    REVERSE = 1

    def __init__(
        self,
        step_pin=16,
        direction_pin=None,
        max_speed=0.005,
        min_speed=0.01,
        steps_per_rotation=800,
        ease_length=50,
        cool_down=1.0,
    ):

        self.step_pin = step_pin  # Send pulses to the the coil
        self.max_speed = max_speed
        self.min_speed = min_speed
        self.steps_per_rotation = steps_per_rotation
        self.ease_length = ease_length
        self.cool_down = cool_down
        self.direction_pin = direction_pin
        self._board = None

    def __enter__(self):
        self.setup()
        direction_enabled = "not enabled."
        if self.direction_pin:
            direction_enabled = f"enabled with pin {self.direction_pin}."
        print(
            f"Enabling Stepper on pin {self.step_pin}. Direction is {direction_enabled}"
        )
        return self

    def __exit__(self, type, value, traceback):
        self.cleanup()

    def setup(self):

        GPIO.setup(self.step_pin, GPIO.OUT)
        GPIO.output(self.step_pin, GPIO.LOW)

        if self.direction_pin is not None:
            GPIO.setup(self.direction_pin, GPIO.OUT)
            GPIO.output(self.direction_pin, self.FORWARD)

    def cleanup(self):
        pass

    def one_step(self, speed, direction=FORWARD):
        if self.direction_pin is not None:
            GPIO.output(self.direction_pin, direction)
        GPIO.output(self.step_pin, GPIO.HIGH)
        time.sleep(speed)
        GPIO.output(self.step_pin, GPIO.LOW)

    def advance_degrees(self, degrees=6.0, direction=FORWARD):
        print(f"Advancing Stepper {degrees} degrees")
        steps_per_degree = self.steps_per_rotation / 360.0
        steps = int(degrees * steps_per_degree)

        half_steps = steps / 2
        for step in range(steps):
            if step < half_steps:
                x = (step + 1) / self.ease_length
                step_time = exp_interp(self.max_speed, self.min_speed, x)
            else:
                x = (steps - step) / self.ease_length
                step_time = exp_interp(self.max_speed, self.min_speed, x)
            self.one_step(step_time, direction=direction)
        time.sleep(self.cool_down)


def advance_stepper(degree):
    with Stepper() as stepper:
        stepper.advance_degrees(degree)


def exp_interp(a, b, x, power=1, flip=True):
    if x <= 0:
        if flip:
            return b
        return a
    exp_x = math.pow(x, power)
    if exp_x >= 1.0:
        if flip:
            return a
        return b
    offset = a
    size = b - a
    if flip:
        return ((1 - exp_x) * size) + offset
    return (exp_x * size) + offset
