import os
import sys
import time
import struct
import board
import keypad
from digitalio import DigitalInOut, Direction, Pull
from adafruit_debouncer import Debouncer
import busio
import adafruit_lis3dh
from adafruit_seesaw.seesaw import Seesaw
import adafruit_seesaw.digitalio as ss_dio
import neopixel
from rainbowio import colorwheel
import sdcardio
import storage
import displayio
import adafruit_ov5640
from adafruit_st7789 import ST7789
import terminalio
from adafruit_display_text import label

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_PyCamera.git"

from micropython import const

SNAPSHOT_MODE = 0

class PyCamera:
    resolutions = (None, "160x120", "176x144", "240x176", "240x240", "320x240", "400x296", "480x320", "640x480",
                   "800x600", "1024x768", "1280x720", "1280x1024", "1600x1200", "2560x1440",
                   "2560x1600", "1088x1920", "2560x1920")
    
    _SS_DOWN = const(16) # PC4
    _SS_LEFT =  const(2) # PA6
    _SS_UP =  const(3) # PA7
    _SS_RIGHT =   const(6) # PB5
    _SS_BATTMON =  const(18) # PA1
    _SS_CAMRST  =  const(19) # PA2
    _SS_CAMPWDN =  const(20) # PA3
    _SS_CARDDET =   const(4) # PB7

    _INIT_SEQUENCE = (
        b"\x01\x80\x78"  # _SWRESET and Delay 120ms
        b"\x11\x80\x05"  # _SLPOUT and Delay 5ms
        b"\x3A\x01\x55"  # _COLMOD
        b"\x21\x00"      # _INVON Hack
        b"\x13\x00"      # _NORON
        b"\x36\x01\xA0"  # _MADCTL
        b"\x29\x80\x05"  # _DISPON and Delay 5ms
        )


    def __init__(self) -> None:
        self.t = time.monotonic()
        self._i2c = board.I2C()
        self._spi = board.SPI()
        self.deinit_display()

        self.splash = displayio.Group()
        self._sd_label = label.Label(terminalio.FONT, text="SD ??", color=0x0, x=180, y=10, scale=2)

        # seesaw GPIO expander
        self._ss = Seesaw(self._i2c, 0x44, reset=False)
        self._ss.sw_reset(0.01)
        print("seesaw done @", time.monotonic()-self.t)
        carddet = ss_dio.DigitalIO(self._ss, _SS_CARDDET)
        carddet.switch_to_input(Pull.UP)
        self.card_detect = Debouncer(carddet)
        self._card_power = DigitalInOut(board.CARD_POWER)
        self._card_power.switch_to_output(True)
        
        self.sdcard = None
        try:
            self.mount_sd_card()
        except RuntimeError:
            pass # no card found, its ok!
        print("sdcard done @", time.monotonic()-self.t)
        
        # lis3dh accelerometer
        self.accel = adafruit_lis3dh.LIS3DH_I2C(self._i2c, address=0x19)
        self.accel.range = adafruit_lis3dh.RANGE_2_G

        # lights!
        # built in red LED
        led = DigitalInOut(board.LED)
        led.switch_to_output(False)
        # built in neopixels
        neopixels = neopixel.NeoPixel(board.NEOPIXEL, 4, brightness=0.1)
        neopixels.fill(0)
        
        # camera!
        self._cam_pwdn = ss_dio.DigitalIO(self._ss, _SS_CAMPWDN)
        self._cam_pwdn.switch_to_output(True)
        self._cam_reset = ss_dio.DigitalIO(self._ss, _SS_CAMRST)
        self._cam_reset.switch_to_output(False)

        print("pre cam @", time.monotonic()-self.t)

        self.camera = adafruit_ov5640.OV5640(
            self._i2c,
            data_pins=board.CAMERA_DATA,
            clock=board.CAMERA_PCLK,
            vsync=board.CAMERA_VSYNC,
            href=board.CAMERA_HREF,
            mclk=board.CAMERA_XCLK,
            mclk_frequency=20_000_000,
            size=adafruit_ov5640.OV5640_SIZE_HQVGA,
            shutdown=self._cam_pwdn,
            reset=self._cam_reset
            )
        print("Found camera ID %04x" % self.camera.chip_id)
        print("camera done @", time.monotonic()-self.t)
        self.camera.flip_x = True
        self.camera.flip_y = False
        #self.camera.test_pattern = True
        self.camera.effect = adafruit_ov5640.OV5640_SPECIAL_EFFECT_NONE
        self.camera.saturation = 3

        # action!
        if not self.display:
            self.init_display()
        
        shut = DigitalInOut(board.BUTTON)
        shut.switch_to_input(Pull.UP)
        self.shutter = Debouncer(shut)

        up = ss_dio.DigitalIO(self._ss, _SS_UP)
        up.switch_to_input(Pull.UP)
        self.up = Debouncer(up)
        down = ss_dio.DigitalIO(self._ss, _SS_DOWN)
        down.switch_to_input(Pull.UP)
        self.down = Debouncer(down)
        left = ss_dio.DigitalIO(self._ss, _SS_LEFT)
        left.switch_to_input(Pull.UP)
        self.left = Debouncer(left)
        right = ss_dio.DigitalIO(self._ss, _SS_RIGHT)
        right.switch_to_input(Pull.UP)
        self.right = Debouncer(right)

        self._bigbuf = None
        self._bitmap = displayio.Bitmap(240, 176, 65536)

        self._topbar = displayio.Group()
        self._res_label = label.Label(terminalio.FONT, text="", color=0xFFFFFF, x=0, y=10, scale=2)
        self._topbar.append(self._res_label)
        self._topbar.append(self._sd_label)

        self._botbar = displayio.Group(x=0, y=210)
        self._mode_label = label.Label(terminalio.FONT, text="", color=0xFFFFFF, x=0, y=10, scale=2)
        self._botbar.append(self._mode_label)

        self.splash.append(self._topbar)
        self.splash.append(self._botbar)
        self.display.show(self.splash)
        self.display.refresh()
        
        print("init done @", time.monotonic()-self.t)

    def set_mode(self, mode):
        if mode == SNAPSHOT_MODE:
            self._mode_label.text = "JPEG Camera"
        self.display.refresh()
                      
    def set_resolution(self, res):
        if not res in self.resolutions:
            raise RuntimeError("Invalid resolution")
        self._resolution = self.resolutions.index(res)
        self._res_label.text = res
        self.display.refresh()

    def get_resolution(self):
        return self._resolution

    def init_display(self):
        # construct displayio by hand
        displayio.release_displays()        
        self._display_bus = displayio.FourWire(self._spi, command=board.TFT_DC,
                                               chip_select=board.TFT_CS,
                                               reset=board.TFT_RESET,
                                               baudrate=60_000_000)
        self.display = board.DISPLAY
        # init specially since we are going to write directly below
        self.display = displayio.Display(self._display_bus, self._INIT_SEQUENCE,
                                         width=240, height=240, colstart=80,
                                         auto_refresh=False)
        self.display.show(self.splash)
        self.display.refresh()
        
    def deinit_display(self):
        # construct displayio by hand
        displayio.release_displays()
        self._display_bus = None
        self.display = None

    def display_message(self, message, color=0xFF0000):
        text_area = label.Label(terminalio.FONT, text=message, color=color, scale=3)
        text_area.anchor_point = (0.5, 0.5)
        text_area.anchored_position = (self.display.width / 2, self.display.height / 2)
        
        # Show it
        self.splash.append(text_area)
        self.display.refresh()
        self.splash.pop()

    def mount_sd_card(self):
        self._sd_label.text = "NO SD"
        self._sd_label.color = 0xFF0000
        if not self.card_detect.value:
            raise RuntimeError("SD card detection failed")
        if self.sdcard:
            self.sdcard.deinit()
        # depower SD card
        self._card_power.value = True
        card_cs = DigitalInOut(board.CARD_CS)
        card_cs.switch_to_output(False)
        # deinit display and SPI
        self.deinit_display()
        self._spi.deinit()
        sckpin = DigitalInOut(board.SCK)
        sckpin.switch_to_output(False)
        mosipin = DigitalInOut(board.MOSI)
        mosipin.switch_to_output(False)
        misopin = DigitalInOut(board.MISO)
        misopin.switch_to_output(False)

        time.sleep(0.05)

        sckpin.deinit()
        mosipin.deinit()
        misopin.deinit()
        self._spi = board.SPI()
        # power SD card
        self._card_power.value = False
        card_cs.deinit()
        print("sdcard init @", time.monotonic()-self.t)
        self.sdcard = sdcardio.SDCard(self._spi, board.CARD_CS, baudrate=60000000)
        vfs = storage.VfsFat(self.sdcard)
        print("mount vfs @", time.monotonic()-self.t)
        storage.mount(vfs, "/sd")
        self.init_display()
        self._image_counter = 0
        self._sd_label.text = "SD OK"
        self._sd_label.color = 0x00FF00
        

    def unmount_sd_card(self):
        try:
            storage.umount("/sd")
        except OSError:
            pass
        self._sd_label.text = "NO SD"
        self._sd_label.color = 0xFF0000


    def keys_debounce(self):
        self.card_detect.update()
        self.shutter.update()
        self.up.update()
        self.down.update()
        self.left.update()
        self.right.update()

    def live_preview_mode(self):
        self.camera._write_list(adafruit_ov5640._sensor_default_regs)
        self.camera.size = adafruit_ov5640.OV5640_SIZE_HQVGA 
        self.camera.colorspace = adafruit_ov5640.OV5640_COLOR_RGB

    def open_next_image(self):
        while True:
            filename = "/sd/img%04d.jpg" % self._image_counter
            self._image_counter += 1
            try:
                os.stat(filename)
            except OSError:
                break
        print("Writing to", filename)
        return open(filename, "wb")

    def capture_jpeg(self):
        try:
            os.stat("/sd")
        except OSError:            # no SD card!
            raise RuntimeError("No SD card mounted")
        self.camera.colorspace = adafruit_ov5640.OV5640_COLOR_JPEG
        self.camera.size = self._resolution
        self.camera.quality = 4
        b = bytearray(self.camera.capture_buffer_size)
        jpeg = self.camera.capture(b)
        print("Captured %d bytes of jpeg data (had allocated %d bytes" % (len(jpeg), self.camera.capture_buffer_size))
        print("Resolution %d x %d" % (self.camera.width, self.camera.height))

        with self.open_next_image() as f:
            f.write(jpeg)
        print("# Wrote image")
            
    def capture_and_blit(self):
        self._display_bus.send(42, struct.pack(">hh", 80,
                                               80 + self._bitmap.width - 1))
        self._display_bus.send(43, struct.pack(">hh", 32,
                                               32 + self._bitmap.height - 1))
        t = time.monotonic()
        self.camera.capture(self._bitmap)
        capture_time = time.monotonic()-t
        self._display_bus.send(44, self._bitmap)
        blit_time = time.monotonic()-capture_time-t
        return (capture_time, blit_time)
