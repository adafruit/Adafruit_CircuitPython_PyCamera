import json
import os
import struct
import sys
import time

import adafruit_pycamera
import bitmaptools
import board
import displayio
import espcamera
import gifio
import socketpool
import ulab.numpy as np
import wifi
from adafruit_httpserver import (BAD_REQUEST_400, GET, NOT_FOUND_404, POST, FileResponse,
                                 JSONResponse, Request, Response, Server)

pycam = adafruit_pycamera.PyCamera()
pycam.autofocus_init()

if wifi.radio.ipv4_address:
    # use alt port if web workflow enabled
    port = 8080
else:
    # connect to wifi and use standard http port otherwise
    wifi.radio.connect(os.getenv("WIFI_SSID"), os.getenv("WIFI_PASSWORD"))
    port = 80

print(wifi.radio.ipv4_address)

pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=True, root_path='/htdocs')

@server.route("/metadata.json", [GET])
def property(request: Request) -> Response:
    return FileResponse(request, "/metadata.json")

@server.route("/", [GET])
def property(request: Request) -> Response:
    return FileResponse(request, "/index.html")

@server.route("/index.js", [GET])
def property(request: Request) -> Response:
    return FileResponse(request, "/index.js")


@server.route("/lcd", [GET, POST])
def property(request: Request) -> Response:
    pycam.blit(pycam.continuous_capture())
    return Response(request, "")


@server.route("/jpeg", [GET, POST])
def property(request: Request) -> Response:
    pycam.camera.reconfigure(
        pixel_format=espcamera.PixelFormat.JPEG,
        frame_size=pycam.resolution_to_frame_size[pycam._resolution],
    )
    try:
        jpeg = pycam.camera.take(1)
        if jpeg is not None:
            return Response(request, bytes(jpeg), content_type="image/jpeg")
        else:
            return Response(
                request, "", content_type="text/plain", status=INTERNAL_SERVER_ERROR_500
            )
    finally:
        pycam.live_preview_mode()

@server.route("/focus", [GET])
def focus(request: Request) -> Response:
    return JSONResponse(request, pycam.autofocus())

@server.route("/property", [GET, POST])
def property(request: Request) -> Response:
    return property_common(pycam, request)


@server.route("/property2", [GET, POST])
def property2(request: Request) -> Response:
    return property_common(pycam.camera, request)


def property_common(obj, request):
    try:
        params = request.query_params or request.form_data
        key = params["k"]
        value = params.get("v", None)

        if value is None:
            try:
                current_value = getattr(obj, key, None)
                return JSONResponse(request, current_value)
            except Exception as e:
                return Response(request, {'error': str(e)}, status=BAD_REQUEST_400)
        else:
            new_value = json.loads(value)
            setattr(obj, key, new_value)
            return JSONResponse(request, {'status': 'OK'})
    except Exception as e:
        return JSONResponse(request, {'error': str(e)}, status=BAD_REQUEST_400)


server.serve_forever(str(wifi.radio.ipv4_address), port)


server = Server(pool, debug=True)

last_frame = displayio.Bitmap(pycam.camera.width, pycam.camera.height, 65535)
onionskin = displayio.Bitmap(pycam.camera.width, pycam.camera.height, 65535)
while True:
    if pycam.mode_text == "STOP" and pycam.stop_motion_frame != 0:
        # alpha blend
        new_frame = pycam.continuous_capture()
        bitmaptools.alphablend(
            onionskin, last_frame, new_frame, displayio.Colorspace.RGB565_SWAPPED
        )
        pycam.blit(onionskin)
    else:
        pycam.blit(pycam.continuous_capture())
    # print("\t\t", capture_time, blit_time)

    pycam.keys_debounce()
    print(
        f"{pycam.shutter.released=} {pycam.shutter.long_press=} {pycam.shutter.short_count=}"
    )
    # test shutter button
    if pycam.shutter.long_press:
        print("FOCUS")
        print(pycam.autofocus_status)
        pycam.autofocus()
        print(pycam.autofocus_status)
    if pycam.shutter.short_count:
        print("Shutter released")
        if pycam.mode_text == "STOP":
            pycam.capture_into_bitmap(last_frame)
            pycam.stop_motion_frame += 1
            try:
                pycam.display_message("Snap!", color=0x0000FF)
                pycam.capture_jpeg()
            except TypeError as e:
                pycam.display_message("Failed", color=0xFF0000)
                time.sleep(0.5)
            except RuntimeError as e:
                pycam.display_message("Error\nNo SD Card", color=0xFF0000)
                time.sleep(0.5)
            pycam.live_preview_mode()

        if pycam.mode_text == "GIF":
            try:
                f = pycam.open_next_image("gif")
            except RuntimeError as e:
                pycam.display_message("Error\nNo SD Card", color=0xFF0000)
                time.sleep(0.5)
                continue
            i = 0
            ft = []
            pycam._mode_label.text = "RECORDING"

            pycam.display.refresh()
            with gifio.GifWriter(
                f,
                pycam.camera.width,
                pycam.camera.height,
                displayio.Colorspace.RGB565_SWAPPED,
                dither=True,
            ) as g:
                t00 = t0 = time.monotonic()
                while (i < 15) or (pycam.shutter_button.value == False):
                    i += 1
                    _gifframe = pycam.continuous_capture()
                    g.add_frame(_gifframe, 0.12)
                    pycam.blit(_gifframe)
                    t1 = time.monotonic()
                    ft.append(1 / (t1 - t0))
                    print(end=".")
                    t0 = t1
            pycam._mode_label.text = "GIF"
            print(f"\nfinal size {f.tell()} for {i} frames")
            print(f"average framerate {i/(t1-t00)}fps")
            print(f"best {max(ft)} worst {min(ft)} std. deviation {np.std(ft)}")
            f.close()
            pycam.display.refresh()

        if pycam.mode_text == "JPEG":
            pycam.tone(200, 0.1)
            try:
                pycam.display_message("Snap!", color=0x0000FF)
                pycam.capture_jpeg()
                pycam.live_preview_mode()
            except TypeError as e:
                pycam.display_message("Failed", color=0xFF0000)
                time.sleep(0.5)
                pycam.live_preview_mode()
            except RuntimeError as e:
                pycam.display_message("Error\nNo SD Card", color=0xFF0000)
                time.sleep(0.5)
    if pycam.card_detect.fell:
        print("SD card removed")
        pycam.unmount_sd_card()
        pycam.display.refresh()
    if pycam.card_detect.rose:
        print("SD card inserted")
        pycam.display_message("Mounting\nSD Card", color=0xFFFFFF)
        for _ in range(3):
            try:
                print("Mounting card")
                pycam.mount_sd_card()
                print("Success!")
                break
            except OSError as e:
                print("Retrying!", e)
                time.sleep(0.5)
        else:
            pycam.display_message("SD Card\nFailed!", color=0xFF0000)
            time.sleep(0.5)
        pycam.display.refresh()

    if pycam.up.fell:
        print("UP")
        key = settings[curr_setting]
        if key:
            setattr(pycam, key, getattr(pycam, key) + 1)
    if pycam.down.fell:
        print("DN")
        key = settings[curr_setting]
        if key:
            setattr(pycam, key, getattr(pycam, key) - 1)
    if pycam.left.fell:
        print("LF")
        curr_setting = (curr_setting + 1) % len(settings)
        print(settings[curr_setting])
        # new_res = min(len(pycam.resolutions)-1, pycam.get_resolution()+1)
        # pycam.set_resolution(pycam.resolutions[new_res])
        pycam.select_setting(settings[curr_setting])
    if pycam.right.fell:
        print("RT")
        curr_setting = (curr_setting - 1 + len(settings)) % len(settings)
        print(settings[curr_setting])
        pycam.select_setting(settings[curr_setting])
        # new_res = max(1, pycam.get_resolution()-1)
        # pycam.set_resolution(pycam.resolutions[new_res])
    if pycam.select.fell:
        print("SEL")
    if pycam.ok.fell:
        print("OK")
