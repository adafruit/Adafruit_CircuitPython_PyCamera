import sys
import struct
import displayio

try:
    import numpy as np
except:
    import ulab.numpy as np


def _bytes_per_row(source_width: int) -> int:
    pixel_bytes = 3 * source_width
    padding_bytes = (4 - (pixel_bytes % 4)) % 4
    return pixel_bytes + padding_bytes


def _write_bmp_header(output_file: BufferedWriter, filesize: int) -> None:
    output_file.write(bytes("BM", "ascii"))
    output_file.write(struct.pack("<I", filesize))
    output_file.write(b"\00\x00")
    output_file.write(b"\00\x00")
    output_file.write(struct.pack("<I", 54))


def _write_dib_header(output_file: BufferedWriter, width: int, height: int) -> None:
    output_file.write(struct.pack("<I", 40))
    output_file.write(struct.pack("<I", width))
    output_file.write(struct.pack("<I", height))
    output_file.write(struct.pack("<H", 1))
    output_file.write(struct.pack("<H", 24))
    for _ in range(24):
        output_file.write(b"\x00")


def components_to_file_rgb565(output_file, r, g, b):
    height, width = r.shape
    pixel_bytes = 3 * width
    padding_bytes = (4 - (pixel_bytes % 4)) % 4
    filesize = 54 + height * (pixel_bytes + padding_bytes)
    _write_bmp_header(output_file, filesize)
    _write_dib_header(output_file, width, height)
    p = b"\0" * padding_bytes
    m = memoryview(buffer_from_components_rgb888(r, g, b))
    for i in range(0, len(m), pixel_bytes)[::-1]:
        output_file.write(m[i : i + pixel_bytes])
        output_file.write(p)


def np_convolve_same(a, v):
    """Perform the np.convolve(mode=same) operation

    This is not directly supported on ulab, so we have to slice the "full" mode result
    """
    if len(a) < len(v):
        a, v = v, a
    tmp = np.convolve(a, v)
    n = len(a)
    c = (len(v) - 1) // 2
    result = tmp[c : c + n]
    return result


FIVE_BITS = 0b11111
SIX_BITS = 0b111111
EIGHT_BITS = 0b11111111


def bitmap_as_array(bitmap):
    ### XXX todo: work on blinka
    if bitmap.width % 2:
        raise ValueError("Can only work on even-width bitmaps")
    return (
        np.frombuffer(bitmap, dtype=np.uint16)
        .reshape((bitmap.height, bitmap.width))
        .byteswap()
    )


def bitmap_to_components_rgb565(bitmap):
    """Convert a RGB65_BYTESWAPPED image to float32 components in the [0,1] inclusive range"""
    arr = bitmap_as_array(bitmap)

    r = np.right_shift(arr, 11) * (1.0 / FIVE_BITS)
    g = (np.right_shift(arr, 5) & SIX_BITS) * (1.0 / SIX_BITS)
    b = (arr & FIVE_BITS) * (1.0 / FIVE_BITS)
    return r, g, b


def bitmap_from_components_rgb565(r, g, b):
    """Convert the float32 components to a bitmap"""
    h, w = r.shape
    result = displayio.Bitmap(w, h, 65535)
    return bitmap_from_components_inplace_rgb565(result, r, g, b)


def bitmap_from_components_inplace_rgb565(bitmap, r, g, b):
    arr = bitmap_as_array(bitmap)
    r = np.array(np.maximum(np.minimum(r, 1.0), 0.0) * FIVE_BITS, dtype=np.uint16)
    g = np.array(np.maximum(np.minimum(g, 1.0), 0.0) * SIX_BITS, dtype=np.uint16)
    b = np.array(np.maximum(np.minimum(b, 1.0), 0.0) * FIVE_BITS, dtype=np.uint16)
    arr = np.left_shift(r, 11)
    arr[:] |= np.left_shift(g, 5)
    arr[:] |= b
    arr = arr.byteswap().flatten()
    dest = np.frombuffer(bitmap, dtype=np.uint16)
    dest[:] = arr
    return bitmap


def buffer_from_components_rgb888(r, g, b):
    """Convert the float32 components to a RGB888 buffer in memory"""
    r = np.array(
        np.maximum(np.minimum(r, 1.0), 0.0) * EIGHT_BITS, dtype=np.uint8
    ).flatten()
    g = np.array(
        np.maximum(np.minimum(g, 1.0), 0.0) * EIGHT_BITS, dtype=np.uint8
    ).flatten()
    b = np.array(
        np.maximum(np.minimum(b, 1.0), 0.0) * EIGHT_BITS, dtype=np.uint8
    ).flatten()
    result = np.zeros(3 * len(r), dtype=np.uint8)
    result[2::3] = r
    result[1::3] = g
    result[0::3] = b
    return result


def separable_filter(data, vh, vv=None):
    """Apply a separable filter to a 2d array.

    If the vertical coefficients ``vv`` are none, the ``vh`` components are
    used for vertical too."""
    if vv is None:
        vv = vh

    result = data[:]

    # First run the filter across each row
    n_rows = result.shape[0]
    for i in range(n_rows):
        result[i, :] = np_convolve_same(result[i, :], vh)

    # Run the filter across each column
    n_cols = result.shape[1]
    for i in range(n_cols):
        result[:, i] = np_convolve_same(result[:, i], vv)

    return result


def bitmap_separable_filter(bitmap, vh, vv=None):
    """Apply a separable filter to an image, returning a new image"""
    r, g, b = bitmap_to_components_rgb565(bitmap)
    r = separable_filter(r, vh, vv)
    g = separable_filter(g, vh, vv)
    b = separable_filter(b, vh, vv)
    return bitmap_from_components_rgb565(r, g, b)


def bitmap_channel_filter3(
    bitmap, r_func=lambda r, g, b: r, g_func=lambda r, g, b: g, b_func=lambda r, g, b: b
):
    """Perform channel filtering where each function recieves all 3 channels"""
    r, g, b = bitmap_to_components_rgb565(bitmap)
    r = r_func(r, g, b)
    g = g_func(r, g, b)
    b = b_func(r, g, b)
    return bitmap_from_components_rgb565(r, g, b)


def bitmap_channel_filter1(
    bitmap, r_func=lambda r: r, g_func=lambda g: g, b_func=lambda b: b
):
    """Perform channel filtering where each function recieves just one channel"""
    return bitmap_channel_filter3(
        bitmap,
        lambda r, g, b: r_func(r),
        lambda r, g, b: g_func(g),
        lambda r, g, b: b_func(b),
    )


def solarize_channel(c, threshold=0.5):
    """Solarize an image channel.

    If the channel value is above a threshold, it is inverted. Otherwise, it is unchanged.
    """
    return (-1 * arr) * (arr > threshold) + arr * (arr <= threshold)


def solarize(bitmap, threshold=0.5):
    """Apply a solarize filter to an image"""
    return bitmap_channel_filter1(
        bitmap,
        lambda r: solarize_channel(r, threshold),
        lambda g: solarize_channel(r, threshold),
        lambda b: solarize_channel(b, threshold),
    )


def sepia(bitmap):
    """Apply a sepia filter to an image

    based on some coefficients I found on the internet"""
    return bitmap_channel_filter3(
        bitmap,
        lambda r, g, b: 0.393 * r + 0.769 * g + 0.189 * b,
        lambda r, g, b: 0.349 * r + 0.686 * g + 0.168 * b,
        lambda r, g, b: 0.272 * r + 0.534 * g + 0.131 * b,
    )


def greyscale(bitmap):
    """Convert an image to greyscale"""
    r, g, b = bitmap_to_components_rgb565(bitmap)
    l = 0.2989 * r + 0.5870 * g + 0.1140 * b
    return bitmap_from_components_rgb565(l, l, l)


def red_cast(bitmap):
    return bitmap_channel_filter1(
        bitmap, lambda r: r, lambda g: g * 0.5, lambda b: b * 0.5
    )


def green_cast(bitmap):
    return bitmap_channel_filter1(
        bitmap, lambda r: r * 0.5, lambda g: g, lambda b: b * 0.5
    )


def blue_cast(bitmap):
    return bitmap_channel_filter1(
        bitmap, lambda r: r * 0.5, lambda g: g * 0.5, lambda b: b
    )


def blur(bitmap):
    return bitmap_separable_filter(bitmap, np.array([0.25, 0.5, 0.25]))


def sharpen(bitmap):
    y = 1 / 5
    return bitmap_separable_filter(bitmap, np.array([-y, -y, 2 - y, -y, -y]))


def edgedetect(bitmap):
    coefficients = np.array([-1, 0, 1])
    r, g, b = bitmap_to_components_rgb565(bitmap)
    r = separable_filter(r, coefficients, coefficients) + 0.5
    g = separable_filter(g, coefficients, coefficients) + 0.5
    b = separable_filter(b, coefficients, coefficients) + 0.5
    return bitmap_from_components_rgb565(r, g, b)
