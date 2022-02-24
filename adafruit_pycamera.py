import os
import sys
import time
import struct
import board
from digitalio import DigitalInOut, Direction, Pull
import microcontroller
import busio
import adafruit_lis3dh
from adafruit_seesaw.seesaw import Seesaw
import adafruit_seesaw.digitalio as ss_dio
import neopixel
from rainbowio import colorwheel
import adafruit_sdcard
import storage
import displayio
import adafruit_ov5640
from adafruit_st7789 import ST7789


__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_PyCamera.git"

from micropython import const

class PyCamera:
    _SS_BUTTONA = const(16) # PC4
    _SS_BUTTONB =  const(2) # PA6
    _SS_BUTTONC =  const(3) # PA7
    _SS_BUTTOND =   const(6) # PB5
    _SS_BATTMON =  const(18) # PA1
    _SS_CAMRST  =  const(19) # PA2
    _SS_CAMPWDN =  const(20) # PA3
    _SS_CARDDET =   const(4) # PB7

    _INIT_SEQUENCE = (
        b"\x01\x80\x96"  # _SWRESET and Delay 150ms
        b"\x11\x80\xFF"  # _SLPOUT and Delay 500ms
        b"\x3A\x81\x55\x0A"  # _COLMOD and Delay 10ms
        b"\x21\x80\x0A"  # _INVON Hack and Delay 10ms
        b"\x13\x80\x0A"  # _NORON and Delay 10ms
        b"\x36\x01\xA0"  # _MADCTL
        b"\x29\x80\xFF"  # _DISPON and Delay 500ms
        )


    def __init__(self) -> None:
        self._i2c = board.I2C()

        self._i2c.try_lock()
        print("I2C addr found:",
              [hex(device_address) for device_address in self._i2c.scan()])
        self._i2c.unlock()

        self._spi = board.SPI()
        # construct displayio by hand
        displayio.release_displays()
        self._display_bus = displayio.FourWire(self._spi, command=board.TFT_DC,
                                               chip_select=board.TFT_CS,
                                               reset=board.TFT_RESET,
                                               baudrate=60_000_000)
        self.display = board.DISPLAY
        # init specially since we are going to write directly below
        self.display = displayio.Display(self._display_bus, self._INIT_SEQUENCE,
                                         width=240, height=240, colstart=80)

        # seesaw GPIO expander
        self._ss = Seesaw(self._i2c, 0x44)
        # lis3dh accelerometer
        self.accel = adafruit_lis3dh.LIS3DH_I2C(self._i2c, address=0x19)
        self.accel.range = adafruit_lis3dh.RANGE_2_G

        # lights!
        # built in red LED
        led = DigitalInOut(board.LED)
        led.switch_to_output(False)
        # built in neopixels
        neopixels = neopixel.NeoPixel(board.NEOPIXEL, 4, brightness=0.1)

        # camera!
        self._cam_pwdn = ss_dio.DigitalIO(self._ss, _SS_CAMPWDN)
        self._cam_pwdn.switch_to_output(True)
        self._cam_reset = ss_dio.DigitalIO(self._ss, _SS_CAMRST)
        self._cam_reset.switch_to_output(False)

        self.camera = adafruit_ov5640.OV5640(
            self._i2c,
            data_pins=(board.CAMERA_DATA2, board.CAMERA_DATA3, board.CAMERA_DATA4,
                       board.CAMERA_DATA5, board.CAMERA_DATA6, board.CAMERA_DATA7,
                       board.CAMERA_DATA8, board.CAMERA_DATA9),
            clock=board.CAMERA_PCLK,
            vsync=board.CAMERA_VSYNC,
            href=board.CAMERA_HREF,
            mclk=board.CAMERA_XCLK,
            mclk_frequency=20_000_000,
            size=adafruit_ov5640.OV5640_SIZE_240X240,
            shutdown=self._cam_pwdn,
            reset=self._cam_reset
            )
        print("Found camera ID %04x" % self.camera.chip_id)
        self.camera.flip_x = True
        self.camera.flip_y = False
        self.camera.colorspace = adafruit_ov5640.OV5640_COLOR_RGB
        #self.camera.test_pattern = True
        self.camera.effect = adafruit_ov5640.OV5640_SPECIAL_EFFECT_NONE
        self.camera.saturation = 3

        # action!
        self.shutter = DigitalInOut(microcontroller.pin.GPIO0)
        self.shutter.direction = Direction.INPUT
        self.shutter.pull = Pull.UP
        self.carddetect = ss_dio.DigitalIO(self._ss, _SS_CARDDET)
        self.carddetect.direction = Direction.INPUT
        self.carddetect.pull = Pull.UP
        self._card_cs = DigitalInOut(board.CARD_CS)
        self.sdcard = None
        self._bitmap = None

    def capture_and_blit(self):
        if not self._bitmap:
            self._bitmap = displayio.Bitmap(self.camera.width,
                                            self.camera.height, 65536)
        # setup the window to be the full screen
        self.display.auto_refresh = False
        self._display_bus.send(42, struct.pack(">hh", 80,
                                               80 + self._bitmap.width - 1))
        self._display_bus.send(43, struct.pack(">hh", 0,
                                               self._bitmap.height - 1))

        t = time.monotonic()
        self.camera.capture(self._bitmap)
        capture_time = time.monotonic()-t
        self._display_bus.send(44, self._bitmap)
        blit_time = time.monotonic()-capture_time-t
        return (capture_time, blit_time)
