from enum import Enum


class settings(str, Enum):
    FOCUS_DISTANCE = "d171"


class lenses(tuple, Enum):
    x35mm = ([0.3, 0.5, 1, 1.5, 2, 3, 5, 10], [1730, 983, 472, 327, 257, 197, 142, 103])
