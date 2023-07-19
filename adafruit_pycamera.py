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
import neopixel
from rainbowio import colorwheel
import sdcardio
import storage
import displayio
#import adafruit_ov5640
import espcamera
from adafruit_st7789 import ST7789
import terminalio
from adafruit_display_text import label
import pwmio
import microcontroller
import adafruit_aw9523
import espidf

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_PyCamera.git"

from micropython import const



class PyCamera:
    resolutions = ("160x120", "176x144", "240x176", "240x240", "320x240", "400x296",
                   "480x320", "640x480", "800x600", "1024x768", "1280x720", "1280x1024",
                   "1600x1200", "2560x1440", "2560x1600", "1088x1920", "2560x1920")

    effects = ("Normal", "Negative", "Grayscale", "Reddish", "Greenish", "Bluish", "Sepia", "Overexp", "Solarize")
    modes = ("JPEG", "GIF", "STOP")
    
    _AW_DOWN = const(15)
    _AW_LEFT =  const(14)
    _AW_UP =  const(13)
    _AW_RIGHT =   const(12)
    _AW_OK =   const(11)
    _AW_SELECT =   const(1)
    _AW_BACKLIGHT =   const(2)
    _AW_CARDDET =   const(8)
    _AW_MUTE =   const(0)
    _AW_SDPWR =   const(9)
    #_SS_ALL_BUTTONS_MASK = const(0b000010000000001011100)
    #_SS_DOWN_MASK = const(0x10000)
    #_SS_LEFT_MASK = const(0x00004)
    #_SS_UP_MASK = const(0x00008)
    #_SS_RIGHT_MASK = const(0x00040)
    #_SS_CARDDET_MASK = const(0x00010)
    _AW_CAMRST  =  const(10)
    _AW_CAMPWDN =  const(7)

    _NVM_RESOLUTION = const(1)
    _NVM_EFFECT = const(2)
    _NVM_MODE = const(3)
    
    _INIT_SEQUENCE = (
        b"\x01\x80\x78"  # _SWRESET and Delay 120ms
        b"\x11\x80\x05"  # _SLPOUT and Delay 5ms
        b"\x3A\x01\x55"  # _COLMOD
        b"\x21\x00"      # _INVON Hack
        b"\x13\x00"      # _NORON
        b"\x36\x01\xA0"  # _MADCTL
        b"\x29\x80\x05"  # _DISPON and Delay 5ms
        )

    def i2c_scan(self):
        while not self._i2c.try_lock():
            pass

        try:
            print("I2C addresses found:",
                    [hex(device_address) for device_address in self._i2c.scan()],
                )
        finally:  # unlock the i2c bus when ctrl-c'ing out of the loop
            self._i2c.unlock()
    

    def __init__(self) -> None:
        if espidf.get_reserved_psram() < 1024 * 512:
            raise RuntimeError("Please reserve at least 512kB of PSRAM!")
        
        self.t = time.monotonic()
        self._i2c = board.I2C()
        self._spi = board.SPI()
        self.deinit_display()

        self.splash = displayio.Group()
        self._sd_label = label.Label(terminalio.FONT, text="SD ??", color=0x0, x=180, y=10, scale=2)
        self._effect_label = label.Label(terminalio.FONT, text="", color=0xFFFFFF, x=4, y=10, scale=2)
        self._mode_label = label.Label(terminalio.FONT, text="MODE", color=0xFFFFFF, x=150, y=10, scale=2)

        # AW9523 GPIO expander
        self._aw = adafruit_aw9523.AW9523(self._i2c, address=0x5B)
        print("Found AW9523")
        self.backlight = self._aw.get_pin(_AW_BACKLIGHT)
        self.backlight.switch_to_output(False)
        
        self.carddet_pin = self._aw.get_pin(_AW_CARDDET)
        self.card_detect = Debouncer(self.carddet_pin)
        
        self._card_power = self._aw.get_pin(_AW_SDPWR)
        self._card_power.switch_to_output(True)

        self.mute = self._aw.get_pin(_AW_MUTE)
        self.mute.switch_to_output(False)

        self.sdcard = None
        try:
            self.mount_sd_card()
        except RuntimeError:
            pass # no card found, its ok!
        print("sdcard done @", time.monotonic()-self.t)
        
        # lis3dh accelerometer
        self.accel = adafruit_lis3dh.LIS3DH_I2C(self._i2c, address=0x19)
        self.accel.range = adafruit_lis3dh.RANGE_2_G

        # built in neopixels
        neopix = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.1)
        neopix.fill(0)
        
        # camera!
        self._cam_reset = self._aw.get_pin(_AW_CAMRST)
        self._cam_pwdn = self._aw.get_pin(_AW_CAMPWDN)

        self._cam_reset.switch_to_output(False)
        self._cam_pwdn.switch_to_output(True)
        time.sleep(0.01)
        self._cam_pwdn.switch_to_output(False)
        time.sleep(0.01)
        self._cam_reset.switch_to_output(True)
        time.sleep(0.01)
        
        print("pre cam @", time.monotonic()-self.t)
        #self.i2c_scan()

        print("Initializing camera")
        self.camera = espcamera.Camera(
            data_pins=board.CAMERA_DATA,
            external_clock_pin=board.CAMERA_XCLK,
            pixel_clock_pin=board.CAMERA_PCLK,
            vsync_pin=board.CAMERA_VSYNC,
            href_pin=board.CAMERA_HREF,
            pixel_format=espcamera.PixelFormat.RGB565,
            frame_size=espcamera.FrameSize.QVGA,
            i2c=board.I2C(),
            external_clock_frequency=20_000_000,
            framebuffer_count=2)
        
        print("Found camera %s (%d x %d)" % (self.camera.sensor_name, self.camera.width, self.camera.height))
        print("camera done @", time.monotonic()-self.t)
        print(dir(self.camera))

        #display.auto_refresh = False

        self.camera.hmirror = True
        self.camera.vflip = False

        # action!
        if not self.display:
            self.init_display()
        
        self.shutter_button = DigitalInOut(board.BUTTON)
        self.shutter_button.switch_to_input(Pull.UP)
        self.shutter = Debouncer(self.shutter_button)

        self.up_pin = self._aw.get_pin(_AW_UP)
        self.up_pin.switch_to_input()
        self.up = Debouncer(self.up_pin)
        self.down_pin = self._aw.get_pin(_AW_DOWN)
        self.down_pin.switch_to_input()
        self.down = Debouncer(self.down_pin)
        self.left_pin = self._aw.get_pin(_AW_LEFT)
        self.left_pin.switch_to_input()
        self.left = Debouncer(self.left_pin)
        self.right_pin = self._aw.get_pin(_AW_RIGHT)
        self.right_pin.switch_to_input()
        self.right = Debouncer(self.right_pin)

        self._bigbuf = None
        self._bitmap1 = displayio.Bitmap(240, 176, 65535)
        self._bitmap2 = displayio.Bitmap(240, 176, 65535)

        self._topbar = displayio.Group()
        self._res_label = label.Label(terminalio.FONT, text="", color=0xFFFFFF, x=0, y=10, scale=2)
        self._topbar.append(self._res_label)
        self._topbar.append(self._sd_label)

        self._botbar = displayio.Group(x=0, y=210)
        self._botbar.append(self._effect_label)
        self._botbar.append(self._mode_label)

        self.splash.append(self._topbar)
        self.splash.append(self._botbar)
        self.display.show(self.splash)
        self.display.refresh()

        #self.camera.colorbar = True
        #self.effect = microcontroller.nvm[_NVM_EFFECT]
        #self.camera.saturation = 3
        #self.resolution = microcontroller.nvm[_NVM_RESOLUTION]
        #self.mode = microcontroller.nvm[_NVM_MODE]
        print("init done @", time.monotonic()-self.t)

    def select_setting(self, setting_name):
        self._effect_label.color = 0xFFFFFF
        self._effect_label.background_color = 0x0
        self._res_label.color = 0xFFFFFF
        self._res_label.background_color = 0x0
        self._mode_label.color = 0xFFFFFF
        self._mode_label.background_color = 0x0
        if setting_name == "effect":
            self._effect_label.color = 0x0
            self._effect_label.background_color = 0xFFFFFF
        if setting_name == "resolution":
            self._res_label.color = 0x0
            self._res_label.background_color = 0xFFFFFF
        if setting_name == "mode":
            self._mode_label.color = 0x0
            self._mode_label.background_color = 0xFFFFFF

        self.display.refresh()

    @property
    def mode(self):
        return self._mode

    @property
    def mode_text(self):
        return self.modes[self._mode]
    
    @mode.setter
    def mode(self, setting):
        setting = (setting + len(self.modes)) % len(self.modes)
        self._mode = setting
        self._mode_label.text = self.modes[setting]
        if self.modes[setting] == "STOP":
            self.stop_motion_frame = 0
        if self.modes[setting] == "GIF":
            self._res_label.text = ""
        else:
            self.resolution = self.resolution # kick it to reset the display
        microcontroller.nvm[_NVM_MODE] = setting
        self.display.refresh()
    
    @property
    def effect(self):
        return self._effect
    
    @effect.setter
    def effect(self, setting):
        setting = (setting + len(self.effects)) % len(self.effects)
        self._effect = setting
        self._effect_label.text = self.effects[setting]
        self.camera.effect = setting
        microcontroller.nvm[_NVM_EFFECT] = setting
        self.display.refresh()

    @property
    def resolution(self):
        return self._resolution

    @resolution.setter
    def resolution(self, res):
        if isinstance(res, str):
            if not res in self.resolutions:
                raise RuntimeError("Invalid Resolution")
            res = self.resolutions.index(res)
        if isinstance(res, int):
            res = (res + len(self.resolutions)) % len(self.resolutions)
            microcontroller.nvm[_NVM_RESOLUTION] = res
            self._resolution = res
            self._res_label.text = self.resolutions[res]
        self.display.refresh()


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
        # shutter button is true GPIO so we debounce as normal
        self.shutter.update()
        self.card_detect.update(self.carddet_pin)
        self.up.update(self.up_pin.value)
        self.down.update(self.down_pin.value)
        self.left.update(self.left_pin.value)
        self.right.update(self.right_pin.value)

    def tone(self, frequency, duration=0.1):
        with pwmio.PWMOut(
            board.SPEAKER, frequency=int(frequency), variable_frequency=False
            ) as pwm:
            self.mute.value = True
            pwm.duty_cycle = 0x8000
            time.sleep(duration)
            self.mute.value = False

    def live_preview_mode(self):
        self.camera._write_list(adafruit_ov5640._sensor_default_regs)
        self.camera.size = adafruit_ov5640.OV5640_SIZE_HQVGA 
        self.camera.colorspace = adafruit_ov5640.OV5640_COLOR_RGB
        self.effect = self._effect
        self.continuous_capture_start()

    def open_next_image(self, extension="jpg"):
        try:
            os.stat("/sd")
        except OSError:            # no SD card!
            raise RuntimeError("No SD card mounted")
        while True:
            filename = "/sd/img%04d.%s" % (self._image_counter, extension)
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
        self.camera.size = self._resolution + 1  # starts at 1 not 0
        self.camera.quality = 4
        time.sleep(0.1)
        b = bytearray(self.camera.capture_buffer_size)
        jpeg = self.camera.capture(b)
        print("Captured %d bytes of jpeg data (had allocated %d bytes" % (len(jpeg), self.camera.capture_buffer_size))
        print("Resolution %d x %d" % (self.camera.width, self.camera.height))

        with self.open_next_image() as f:
            f.write(jpeg)
        print("# Wrote image")

    def continuous_capture_start(self):
        self._bitmap1 = self.camera.take(1)
        #self.camera._imagecapture.continuous_capture_start(self._bitmap1, self._bitmap2)

    def capture_into_bitmap(self, bitmap):
        self.camera.capture(bitmap)

    def continuous_capture(self):
        return self.camera.take(1)

    def blit(self, bitmap):
        self._display_bus.send(42, struct.pack(">hh", 80,
                                               80 + bitmap.width - 1))
        self._display_bus.send(43, struct.pack(">hh", 32,
                                               32 + bitmap.height - 1))
        self._display_bus.send(44, bitmap)

