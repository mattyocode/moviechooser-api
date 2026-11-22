"""argparse types shared by the movies management commands."""


def non_negative_float(value):
    number = float(value)
    if number < 0:
        raise ValueError("must be >= 0")
    return number
