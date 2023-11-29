# SPDX-FileCopyrightText: 2023 Jeff Epler for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2021 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

"""
This demo is designed for the Kaluga development kit version 1.3 with the
ILI9341 display.
"""

import time

import bitmaptools
import displayio
import espcamera
import qrio

from adafruit_pycamera import PyCamera

zoomed = displayio.Bitmap(240, 176, 65535)
pycam = PyCamera()
pycam.camera.reconfigure(
    pixel_format=espcamera.PixelFormat.RGB565,
    frame_size=espcamera.FrameSize.VGA,
)
pycam._mode_label.text = "QR SCAN"  # pylint: disable=protected-access
pycam._res_label.text = ""  # pylint: disable=protected-access
pycam.effect = 0
pycam.display.refresh()
qrdecoder = qrio.QRDecoder(zoomed.width, zoomed.height)

old_payload = None
while True:
    new_frame = pycam.continuous_capture()
    if new_frame is None:
        continue
    bitmaptools.blit(zoomed, new_frame, 0, 0, x1=(640 - 240) // 2, y1=(480 - 176) // 2)
    pycam.blit(zoomed)
    for row in qrdecoder.decode(zoomed, qrio.PixelPolicy.RGB565_SWAPPED):
        payload = row.payload
        try:
            payload = payload.decode("utf-8")
        except UnicodeError:
            payload = str(payload)
        if payload != old_payload:
            pycam.tone(200, 0.1)
            print(payload)
            pycam.display_message(payload, color=0xFFFFFF, scale=1)
            time.sleep(1)
            old_payload = payload
