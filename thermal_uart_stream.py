#!/usr/bin/env python3
import serial
import time
import numpy as np
import cv2
import requests
from flask import Flask, Response, jsonify
import threading

# =====================================================
# CONFIG
# =====================================================
SERIAL_PORT = "/dev/serial0"
BAUDRATE = 115200

TEMP_THRESHOLD = 70.0
RGB_CHECK_URL = "http://127.0.0.1:8060/rgb_check"

RGB_COOLDOWN = 2.0
JPEG_QUALITY = 85

# Stability settings
WARMUP_FRAMES = 3
MAX_VALID_TEMP = 120.0
SPIKE_LIMIT = 100.0
SERIAL_RETRY_DELAY = 2.0

# Output size
OUTPUT_W, OUTPUT_H = 640, 360

# Rotation (landscape)
ROTATE_MODE = cv2.ROTATE_180
# Grid config
GRID_COLS = 6
GRID_ROWS = 6
GRID_COLOR = (255, 255, 255)
GRID_THICKNESS = 1
GRID_ALPHA = 0.35  # transparency

# Crosshair config
CROSS_SIZE = 10
CROSS_THICK = 2
TEXT_SCALE = 0.7
TEXT_THICK = 2

app = Flask(__name__)

latest_temp = 0.0
latest_min_temp = 0.0
latest_max_temp = 0.0
latest_frame = None
last_rgb_check = 0.0

valid_frame_count = 0
last_good_temp = 30.0

frame_lock = threading.Lock()


# =====================================================
# CORS FIX (so dashboard fetch() works across ports)
# =====================================================
@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Cache-Control"] = "no-store"
    return resp

# =====================================================
# SERIAL CONNECTOR (AUTO RECONNECT)
# =====================================================
def connect_serial():
    while True:
        try:
            print("Opening thermal serial...")
            ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)

            # Init MLX90640 (based on your module protocol)
            ser.write(bytes([0xA5, 0x25, 0x01, 0xCB]))
            time.sleep(0.1)
            ser.write(bytes([0xA5, 0x35, 0x02, 0xDC]))

            print("Thermal UART connected")
            return ser

        except Exception as e:
            print("Serial connect failed:", e)
            time.sleep(SERIAL_RETRY_DELAY)


# =====================================================
# PARSE FRAME
# =====================================================
def parse_frame(data):
    raw = data[4:1540]
    temp = np.frombuffer(raw, dtype=np.int16).reshape((24, 32))
    return temp / 100.0


# =====================================================
# RGB VALIDATION
# =====================================================
def check_rgb_fire():
    try:
        r = requests.get(RGB_CHECK_URL, timeout=0.25)
        if r.ok and r.json().get("fire"):
            print("CONFIRMED FIRE (THERMAL + RGB)")
        else:
            print("High temp but RGB sees NO fire")
    except:
        print("RGB check failed")


# =====================================================
# PLACEHOLDER FRAME
# =====================================================
def make_placeholder(text="WAITING FOR THERMAL FRAME..."):
    img = np.zeros((OUTPUT_H, OUTPUT_W, 3), dtype=np.uint8)
    cv2.putText(img, text, (35, OUTPUT_H // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    ok, jpeg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return jpeg.tobytes() if ok else None


# =====================================================
# GRID DRAW
# =====================================================
def draw_grid(img, cols=6, rows=6):
    overlay = img.copy()
    h, w = img.shape[:2]

    # vertical lines
    for c in range(1, cols):
        x = int(w * c / cols)
        cv2.line(overlay, (x, 0), (x, h), GRID_COLOR, GRID_THICKNESS)

    # horizontal lines
    for r in range(1, rows):
        y = int(h * r / rows)
        cv2.line(overlay, (0, y), (w, y), GRID_COLOR, GRID_THICKNESS)

    # blend overlay
    return cv2.addWeighted(overlay, GRID_ALPHA, img, 1 - GRID_ALPHA, 0)


# =====================================================
# POINT ROTATION + SCALING HELPERS
# =====================================================
def rotate_point(x, y, src_w, src_h, rotate_mode):
    if rotate_mode == cv2.ROTATE_90_COUNTERCLOCKWISE:
        new_w, new_h = src_h, src_w
        return (y, new_h - 1 - x), (new_w, new_h)

    if rotate_mode == cv2.ROTATE_90_CLOCKWISE:
        new_w, new_h = src_h, src_w
        return (new_w - 1 - y, x), (new_w, new_h)

    if rotate_mode == cv2.ROTATE_180:
        new_w, new_h = src_w, src_h
        return (new_w - 1 - x, new_h - 1 - y), (new_w, new_h)

    return (x, y), (src_w, src_h)


def scale_point(x, y, src_w, src_h, dst_w, dst_h):
    sx = dst_w / float(src_w)
    sy = dst_h / float(src_h)
    return int(round(x * sx)), int(round(y * sy))


def draw_crosshair(img, x, y, color):
    cv2.line(img, (x - CROSS_SIZE, y), (x + CROSS_SIZE, y), color, CROSS_THICK)
    cv2.line(img, (x, y - CROSS_SIZE), (x, y + CROSS_SIZE), color, CROSS_THICK)


def put_temp_label(img, x, y, temp_value, color):
    text = f"{temp_value:.1f}C"
    cv2.putText(img, text, (x + 12, y - 12),
                cv2.FONT_HERSHEY_SIMPLEX, TEXT_SCALE, color, TEXT_THICK, cv2.LINE_AA)


# =====================================================
# PROCESS FRAME
# =====================================================
def process_frame(temp_map):
    global latest_temp, latest_min_temp, latest_max_temp, last_rgb_check
    global valid_frame_count, last_good_temp

    max_temp = float(np.max(temp_map))
    min_temp = float(np.min(temp_map))

    # Invalid reading filter
    if max_temp < 0 or max_temp > MAX_VALID_TEMP:
        return None

    # Warmup counter
    if valid_frame_count < WARMUP_FRAMES:
        valid_frame_count += 1

    # Spike filter (after warmup only)
    if valid_frame_count >= WARMUP_FRAMES:
        if abs(max_temp - last_good_temp) > SPIKE_LIMIT:
            return None

    last_good_temp = max_temp
    latest_temp = max_temp
    latest_min_temp = min_temp
    latest_max_temp = max_temp

    now = time.time()

    # Cross validation with RGB
    if latest_max_temp >= TEMP_THRESHOLD:
        if now - last_rgb_check > RGB_COOLDOWN:
            last_rgb_check = now
            threading.Thread(target=check_rgb_fire, daemon=True).start()

    # =====================================================
    # VISUALIZATION
    # =====================================================
    norm = cv2.normalize(temp_map, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    norm = cv2.GaussianBlur(norm, (5, 5), 0)
    color = cv2.applyColorMap(norm, cv2.COLORMAP_INFERNO)

    # Find min/max in original map coords
    max_pos = np.unravel_index(np.argmax(temp_map), temp_map.shape)  # (row, col)
    min_pos = np.unravel_index(np.argmin(temp_map), temp_map.shape)

    src_h, src_w = temp_map.shape  # (24,32)
    max_x, max_y = int(max_pos[1]), int(max_pos[0])
    min_x, min_y = int(min_pos[1]), int(min_pos[0])

    # rotate image
    color = cv2.rotate(color, ROTATE_MODE)

    # rotate points
    (r_max_x, r_max_y), (rot_w, rot_h) = rotate_point(max_x, max_y, src_w, src_h, ROTATE_MODE)
    (r_min_x, r_min_y), _ = rotate_point(min_x, min_y, src_w, src_h, ROTATE_MODE)

    # resize
    color = cv2.resize(color, (OUTPUT_W, OUTPUT_H), interpolation=cv2.INTER_CUBIC)

    # scale points to output
    out_max_x, out_max_y = scale_point(r_max_x, r_max_y, rot_w, rot_h, OUTPUT_W, OUTPUT_H)
    out_min_x, out_min_y = scale_point(r_min_x, r_min_y, rot_w, rot_h, OUTPUT_W, OUTPUT_H)

    # draw grid 6x6 (after resize so it's clean)
    color = draw_grid(color, GRID_COLS, GRID_ROWS)

    # draw crosshairs (temp label only)
    draw_crosshair(color, out_max_x, out_max_y, (0, 0, 255))
    put_temp_label(color, out_max_x, out_max_y, latest_max_temp, (0, 0, 255))

    draw_crosshair(color, out_min_x, out_min_y, (255, 0, 0))
    put_temp_label(color, out_min_x, out_min_y, latest_min_temp, (255, 0, 0))

    return color


# =====================================================
# MAIN THERMAL LOOP
# =====================================================
def thermal_loop():
    global latest_frame
    ser = connect_serial()

    while True:
        try:
            data = ser.read(1544)
            if len(data) != 1544:
                raise RuntimeError("Incomplete frame")

            temp_map = parse_frame(data)
            frame = process_frame(temp_map)

            if frame is None:
                time.sleep(0.02)
                continue

            ok, jpeg = cv2.imencode(
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
            )

            if ok:
                with frame_lock:
                    latest_frame = jpeg.tobytes()

            time.sleep(0.03)

        except Exception as e:
            print("Thermal error:", e)
            try:
                ser.close()
            except:
                pass

            print("Reconnecting thermal sensor...")
            time.sleep(SERIAL_RETRY_DELAY)
            ser = connect_serial()


# =====================================================
# ROUTES
# =====================================================
@app.route("/thermal_stream.mjpg")
def thermal_stream():
    def gen():
        placeholder = make_placeholder()
        while True:
            with frame_lock:
                frame = latest_frame
            if frame is None:
                frame = placeholder

            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n"
                   b"Cache-Control: no-cache, no-store, must-revalidate\r\n"
                   b"Pragma: no-cache\r\n"
                   b"Expires: 0\r\n\r\n" + frame + b"\r\n")

            time.sleep(0.02)

    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/thermal1.json")
def thermal_json():
    return jsonify({
        "min": round(float(latest_min_temp), 2),
        "max": round(float(latest_max_temp), 2),
        "timestamp": time.time()
    })


@app.route("/api/temperature")
def api_temperature():
    return jsonify({
        "min_temp": round(float(latest_min_temp), 2),
        "max_temp": round(float(latest_max_temp), 2),
        "timestamp": time.time()
    })


@app.route("/thermal_check")
def thermal_check():
    return jsonify({"hazard": latest_max_temp >= TEMP_THRESHOLD})


# =====================================================
# START
# =====================================================
if __name__ == "__main__":
    print("Thermal UART Server running on :8055")
    threading.Thread(target=thermal_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8055, threaded=True)