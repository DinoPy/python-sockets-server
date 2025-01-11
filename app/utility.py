import math


def duration_str_to_int(dur_str):
    """
    Converts the string duration format of 00:00:00 to nanosenconds

    params:
        dur_str: string

    returns: integer
    """
    duration_split = dur_str.split(":")
    duration_int = (int(duration_split[0]) * 60 * 60 +
                    int(duration_split[1]) * 60 +
                    int(duration_split[2])) * 1000
    return duration_int


def duration_int_to_str(dur_int):
    """
    Converts the duration from nanoseconds to readable form 00:00:00

    params:
        dur_int: int

    returns: string
    """
    minutes = math.floor((dur_int / 60) % 60)
    hours = math.floor(dur_int / 60 / 60)
    seconds = math.floor(dur_int % 60)
    return f"{'0' + str(hours) if hours < 10 else hours }:{'0' + str(minutes) if minutes < 10 else minutes }:{'0' + str(seconds) if seconds < 10 else seconds}"
