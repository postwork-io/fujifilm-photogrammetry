import time
import math

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

        def cleanup():
            pass

    GPIO = mock_gpio()

# Class has functions to control stepper motors and normal DC Motors


class Stepper:

    def __init__(
        self,
        step_pin=13,
        max_speed=0.001,
        min_speed=0.05,
        total_steps=200,
        step_res=0.25,
        ease_length=40,
        cool_down=1.0,
    ):

        self.step_pin = step_pin  # Send pulses to the the coil
        self.max_speed = max_speed
        self.min_speed = min_speed
        self.total_steps = total_steps
        self.step_res = step_res
        self.ease_length = ease_length
        self.cool_down = cool_down

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, type, value, traceback):
        self.cleanup()

    def setup(self):
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.step_pin, GPIO.OUT)
        GPIO.output(self.step_pin, GPIO.LOW)

    def cleanup(self):
        GPIO.cleanup()

    def one_step(self, speed):

        GPIO.output(self.step_pin, GPIO.HIGH)
        time.sleep(speed)
        GPIO.output(self.step_pin, GPIO.LOW)

    def advance_degrees(self, degrees=6.0):
        print(f"Advancing Stepper {degrees} degrees")
        steps_per_degree = (self.total_steps / self.step_res) / 360.0
        steps = int(degrees * steps_per_degree)

        half_steps = steps / 2
        for step in range(steps):
            if step < half_steps:
                x = (step + 1) / self.ease_length
                step_time = exp_interp(self.max_speed, self.min_speed, x)
            else:
                x = (steps - step) / self.ease_length
                step_time = exp_interp(self.max_speed, self.min_speed, x)
            self.one_step(step_time)
        time.sleep(self.cool_down)


def advance_stepper(degree):
    with Stepper() as stepper:
        stepper.advance_degrees(degree)


def exp_interp(a, b, x, power=2, flip=True):
    if x <= 0:
        if flip:
            return b
        return a
    elif x >= 1.0:
        if flip:
            return a
        return b
    exp_x = math.pow(x, power)
    if flip:
        return ((1 - exp_x) * (b - a)) + a
    return (exp_x * (b - a)) + a
