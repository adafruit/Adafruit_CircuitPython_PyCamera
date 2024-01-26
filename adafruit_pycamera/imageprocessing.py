# SPDX-FileCopyrightText: 2024 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""Routines for performing image manipulation"""

import bitmapfilter

from adafruit_pycamera.ironbow import ironbow_palette

sepia_weights = bitmapfilter.ChannelMixer(
    0.393, 0.769, 0.189, 0.349, 0.686, 0.168, 0.272, 0.534, 0.131
)


def sepia(bitmap, mask=None):
    """Apply a sepia filter to an image in place"""
    bitmapfilter.mix(bitmap, sepia_weights, mask=mask)
    return bitmap


negative_weights = bitmapfilter.ChannelScaleOffset(-1, 1, -1, 1, -1, 1)


def negative(bitmap, mask=None):
    """Invert an image"""
    bitmapfilter.mix(bitmap, negative_weights, mask=mask)
    return bitmap


greyscale_weights = bitmapfilter.ChannelMixer(
    0.299, 0.587, 0.114, 0.299, 0.587, 0.114, 0.299, 0.587, 0.114
)


def greyscale(bitmap, mask=None):
    """Convert an image to greyscale"""
    bitmapfilter.mix(bitmap, greyscale_weights, mask=mask)
    return bitmap


def red_cast(bitmap, mask=None):
    """Give an image a red cast by dividing G and B channels in half"""
    bitmapfilter.mix(bitmap, bitmapfilter.ChannelScale(1, 0.5, 0.5), mask=mask)
    return bitmap


def green_cast(bitmap, mask=None):
    """Give an image a green cast by dividing R and B channels in half"""
    bitmapfilter.mix(bitmap, bitmapfilter.ChannelScale(0.5, 1, 0.5), mask=mask)
    return bitmap


def blue_cast(bitmap, mask=None):
    """Give an image a blue cast by dividing R and G channels in half"""
    bitmapfilter.mix(bitmap, bitmapfilter.ChannelScale(0.5, 0.5, 1), mask=mask)
    return bitmap


def blur(bitmap, mask=None):
    """Blur a bitmap"""
    bitmapfilter.morph(bitmap, (1, 2, 1, 2, 4, 2, 1, 2, 1), mask=mask)
    return bitmap


def sharpen(bitmap, mask=None):
    """Sharpen a bitmap"""
    bitmapfilter.morph(bitmap, (-1, -2, -1, -2, 13, -2, -1, -2, -1), mask=mask)
    return bitmap


def emboss(bitmap, mask=None):
    """Run an emboss filter on the bitmap"""
    bitmapfilter.morph(bitmap, (-2, -1, 0, -1, 0, 1, 0, 1, 2), add=0.5, mask=mask)


def emboss_greyscale(bitmap, mask=None):
    """Run an emboss filter on the bitmap in greyscale"""
    greyscale(bitmap, mask=mask)
    return emboss(bitmap, mask=mask)


def ironbow(bitmap, mask=None):
    """Convert an image to false color using the 'ironbow palette'"""
    return bitmapfilter.false_color(bitmap, ironbow_palette, mask=mask)
