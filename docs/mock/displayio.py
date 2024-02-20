# SPDX-FileCopyrightText: 2024 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense


class Palette:
    def __init__(self, i):
        self._data = [0] * i

    def __setitem__(self, idx, value):
        self._data[idx] = value


class ColorConverter:
    def __init__(self, colorspace):
        self._colorspace = colorspace

    def convert(self, color_value) -> int:
        pass


class Bitmap:
    def __init__(self, width, height, color_count):
        pass


class Colorspace:
    pass


class Display:
    pass
