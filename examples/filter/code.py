# SPDX-FileCopyrightText: 2024 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

"""Effects Demonstration

This will apply a nubmer of effects to a single image.

Press any of the directional buttons to immediately apply a new effect.

Otherwise, effects cycle every DISPLAY_INTERVAL milliseconds (default 2000 = 2 seconds)
"""

import displayio
from jpegio import JpegDecoder
from adafruit_display_text.label import Label
from adafruit_ticks import ticks_less, ticks_ms, ticks_add, ticks_diff
from font_free_mono_bold_24 import FONT
import bitmapfilter

from adafruit_pycamera import imageprocessing
from adafruit_pycamera import PyCameraBase

effects = [
    ("blue cast", imageprocessing.blue_cast),
    ("blur", imageprocessing.blur),
    ("bright", lambda b: bitmapfilter.mix(b, bitmapfilter.ChannelScale(2.0, 2.0, 2.0))),
    ("emboss", imageprocessing.emboss),
    ("green cast", imageprocessing.green_cast),
    ("greyscale", imageprocessing.greyscale),
    ("ironbow", imageprocessing.ironbow),
    (
        "low contrast",
        lambda b: bitmapfilter.mix(
            b, bitmapfilter.ChannelScaleOffset(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        ),
    ),
    ("negative", imageprocessing.negative),
    ("red cast", imageprocessing.red_cast),
    ("sepia", imageprocessing.sepia),
    ("sharpen", imageprocessing.sharpen),
    ("solarize", bitmapfilter.solarize),
    (
        "swap r/b",
        lambda b: bitmapfilter.mix(
            b, bitmapfilter.ChannelMixer(0, 0, 1, 0, 1, 0, 1, 0, 0)
        ),
    ),
]


def cycle(seq):
    while True:
        for s in seq:
            yield s


effects_cycle = iter(cycle(effects))


DISPLAY_INTERVAL = 2000  # milliseconds

decoder = JpegDecoder()

pycam = PyCameraBase()
pycam.init_display()


def main():
    filename = "/cornell_box_208x208.jpg"

    bitmap = displayio.Bitmap(208, 208, 65535)
    bitmap0 = displayio.Bitmap(208, 208, 65535)
    decoder.open(filename)
    decoder.decode(bitmap0)

    label = Label(font=FONT, x=0, y=8)
    pycam.display.root_group = label
    pycam.display.refresh()

    deadline = ticks_ms()
    while True:
        now = ticks_ms()
        if pycam.up.fell:
            deadline = now

        if pycam.down.fell:
            deadline = now

        if pycam.left.fell:
            deadline = now

        if pycam.right.fell:
            deadline = now

        if ticks_less(deadline, now):
            memoryview(bitmap)[:] = memoryview(bitmap0)
            deadline = ticks_add(deadline, DISPLAY_INTERVAL)

            effect_name, effect = next(effects_cycle)  # random.choice(effects)
            print(effect)
            print(f"applying {effect=}")
            t0 = ticks_ms()
            effect(bitmap)
            t1 = ticks_ms()
            dt = ticks_diff(t1, t0)
            print(f"{dt}ms to apply effect")
            pycam.blit(bitmap, x_offset=16)
            label.text = f"{dt:4}ms: {effect_name}"
            pycam.display.refresh()


main()
