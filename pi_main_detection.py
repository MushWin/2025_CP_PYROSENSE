# -*- coding: utf-8 -*-
#!/usr/bin/env python3


import json
import os
import cv2
import numpy as np
import time
import requests
import sqlite3
import smtplib
import ssl
import threading
import queue
import RPi.GPIO as GPIO
import atexit
from datetime import datetime
from email.message import EmailMessage
from flask import Flask, Response, jsonify

from pi_rgb_logic import FireDetectionRGB, CLASS_COLORS

# ================= CONFIG =================

DB_PATH = "/home/admin/pyrosense/2025_CP_PYROSENSE/pyrosense_logs.db"
USERS_DB_PATH = "/home/admin/pyrosense/2025_CP_PYROSENSE/pyrosense_db.db"
MODEL_PATH = "/home/admin/pyrosense/2025_CP_PYROSENSE/FIRE_MODEL"
THERMAL_JSON_URL = "http://127.0.0.1:8055/thermal1.json"


CONFIG_FILE = "threshold_config.json"

def load_thresholds():

    default_l1 = 35
    default_l3 = 50

    try:

        if os.path.exists(CONFIG_FILE):

            with open(CONFIG_FILE,"r") as f:
                cfg = json.load(f)

            l1 = int(cfg.get("level1_max", default_l1))
            l3 = int(cfg.get("level3_min", default_l3))

            return l1, l3

    except Exception as e:
        print("Threshold config error:", e)

    return default_l1, default_l3


RGB_CONF_THRESHOLD = 0.25
DETECTION_INTERVAL = 3

LEVEL1_MAX, LEVEL3_MIN = load_thresholds()

LEVEL2_MIN = LEVEL1_MAX
LEVEL2_MAX = LEVEL3_MIN - 1

LED_PIN = 22
BUZZER_PIN = 17

EMAIL_USER = "pyrosense260@gmail.com"
EMAIL_PASS = "tejoeivuecxcgxhf"


LOG_INTERVAL = 3
EMAIL_COOLDOWN = 30
RGB_FIRE_HOLD = 2.0

OUTPUT_WIDTH = 640
OUTPUT_HEIGHT = 360

app = Flask(__name__)

print("PyroSense Detection System Started")



# ================= GRID =================

def draw_grid(frame, rows=6, cols=6):

    h, w = frame.shape[:2]

    for c in range(1, cols):
        x = int(round(c * w / cols))
        cv2.line(frame, (x, 0), (x, h), (200,200,200), 1)

    for r in range(1, rows):
        y = int(round(r * h / rows))
        cv2.line(frame, (0, y), (w, y), (200,200,200), 1)

# ================= DATABASE =================

def level_to_status(level):

    if level == 1:
        return "NORMAL"
    if level == 2:
        return "WARNING"
    return "FIRE DETECTED"

def log_fire_event(temp, level):

    try:

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        temperature REAL,
        level INTEGER,
        status TEXT
        )
        """)

        c.execute("""
        INSERT INTO logs (timestamp, temperature, level, status)
        VALUES (?, ?, ?, ?)
        """,(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        round(float(temp),2),
        int(level),
        level_to_status(level)
        ))

        conn.commit()
        conn.close()

    except Exception as e:
        print("DB ERROR:",e)


#==========EMAIL ALERT==========

def get_alert_emails():
    try:
        conn = sqlite3.connect(USERS_DB_PATH)
        c = conn.cursor()

        c.execute("""
            SELECT Email
            FROM Users
            WHERE Email IS NOT NULL
              AND TRIM(Email) != ''
        """)

        rows = c.fetchall()
        conn.close()

        emails = [row[0].strip() for row in rows if row[0] and row[0].strip()]
        return list(set(emails))

    except Exception as e:
        print("USER DB EMAIL ERROR:", e)
        return []

# ================= GPIO =================

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.setup(BUZZER_PIN, GPIO.OUT)

GPIO.output(LED_PIN, False)
GPIO.output(BUZZER_PIN, False)

atexit.register(GPIO.cleanup)

# ================= BUZZER PATTERN =================

buzzer_running = False

def buzzer_pattern():

    global buzzer_running

    while buzzer_running:

        GPIO.output(BUZZER_PIN, True)
        time.sleep(0.15)

        GPIO.output(BUZZER_PIN, False)
        time.sleep(0.15)

        GPIO.output(BUZZER_PIN, True)
        time.sleep(0.15)

        GPIO.output(BUZZER_PIN, False)
        time.sleep(0.15)

        GPIO.output(BUZZER_PIN, True)
        time.sleep(0.15)

        GPIO.output(BUZZER_PIN, False)
        time.sleep(0.6)

buzzer_thread = None

# ================= EMAIL THREAD =================

alert_queue = queue.Queue()

def email_worker():
    while True:
        data = alert_queue.get()

        if data is None:
            break

        snapshot_path, temp, level = data

        try:
            recipients = get_alert_emails()

            if not recipients:
                print("No recipient emails found in user database")
                alert_queue.task_done()
                continue

            msg = EmailMessage()
            msg["Subject"] = f"FIRE ALERT LEVEL {level}"
            msg["From"] = EMAIL_USER
            msg["To"] = ", ".join(recipients)

            plain_text = f"""
PYROSENSE FIRE ALERT

Fire Risk Level: {level}
Temperature: {temp:.1f}&deg;C
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please check the area immediately.
"""

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>PyroSense Fire Alert</title>
</head>
<body style="margin:0;padding:0;background-color:#0f1115;font-family:Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#0f1115;padding:30px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#171a21;border-radius:16px;overflow:hidden;border:1px solid #2a2f3a;">
          
          <tr>
            <td style="background:linear-gradient(135deg,#ff7a00,#ff3c00);padding:24px;text-align:center;">
              <h1 style="margin:0;color:white;font-size:28px;letter-spacing:1px;">PYROSENSE</h1>
              <p style="margin:8px 0 0;color:#ffe7dd;font-size:14px;">Fire Detection Alert Notification</p>
            </td>
          </tr>

          <tr>
            <td style="padding:30px;">
              <p style="margin:0 0 18px;color:#ffffff;font-size:20px;font-weight:bold;">
                Fire Alert Detected
              </p>

              <div style="margin-bottom:20px;">
                <span style="
                  display:inline-block;
                  padding:10px 16px;
                  border-radius:999px;
                  background:#ff3c00;
                  color:#ffffff;
                  font-size:13px;
                  font-weight:bold;
                  letter-spacing:0.5px;
                ">
                  ALERT LEVEL {level}
                </span>
              </div>

              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
                <tr>
                  <td style="padding:14px;background:#11141a;border:1px solid #252a34;border-radius:12px;">
                    <p style="margin:0 0 6px;color:#9da7b5;font-size:12px;">Temperature</p>
                    <p style="margin:0;color:#ffffff;font-size:24px;font-weight:bold;">{temp:.1f}&deg;C</p>
                  </td>
                </tr>
              </table>

              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
                <tr>
                  <td style="padding:14px;background:#11141a;border:1px solid #252a34;border-radius:12px;">
                    <p style="margin:0 0 6px;color:#9da7b5;font-size:12px;">Detected Time</p>
                    <p style="margin:0;color:#ffffff;font-size:16px;font-weight:bold;">
                      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    </p>
                  </td>
                </tr>
              </table>

              <div style="padding:16px;background:#2a120d;border:1px solid #5a2419;border-radius:12px;margin-bottom:20px;">
                <p style="margin:0;color:#ffd7cc;font-size:14px;line-height:1.6;">
                  A possible fire event has been detected by the PyroSense monitoring system.
                  Please verify the affected area immediately and follow your emergency response procedure.
                </p>
              </div>

              <p style="margin:0;color:#8d97a5;font-size:13px;line-height:1.7;">
                A snapshot image is attached to this email for reference.
              </p>
            </td>
          </tr>

          <tr>
            <td style="padding:18px 24px;background:#11141a;border-top:1px solid #252a34;text-align:center;">
              <p style="margin:0;color:#7e8794;font-size:12px;">
                PyroSense Automated Alert System
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

            msg.set_content(plain_text)
            msg.add_alternative(html_content, subtype="html")

            with open(snapshot_path, "rb") as f:
                msg.add_attachment(
                    f.read(),
                    maintype="image",
                    subtype="jpeg",
                    filename="snapshot.jpg"
                )

            context = ssl.create_default_context()

            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                server.login(EMAIL_USER, EMAIL_PASS)
                server.send_message(msg)

            print(f"Email alert sent to: {', '.join(recipients)}")

        except Exception as e:
            print("Email error:", e)

        alert_queue.task_done()

threading.Thread(target=email_worker,daemon=True).start()

# ================= DETECTOR =================

detector = FireDetectionRGB(model_path=MODEL_PATH)

current_temp = 0.0
fire_level = 1

frame_count = 0
last_email_time = 0
last_log_time = 0

last_boxes=[]
last_ids=[]
last_confs=[]

last_rgb_fire=False
last_rgb_fire_time=0

# ================= THERMAL =================

def read_temp():

    global current_temp

    try:

        r=requests.get(THERMAL_JSON_URL,timeout=0.5)

        if r.ok:
            current_temp=float(r.json().get("max",current_temp))

    except:
        pass

# ================= ALARM =================

def alarm(level):

    global buzzer_running
    global buzzer_thread

    if level == 3:

        GPIO.output(LED_PIN, True)

        if not buzzer_running:

            buzzer_running = True
            buzzer_thread = threading.Thread(target=buzzer_pattern, daemon=True)
            buzzer_thread.start()

    elif level == 2:

        GPIO.output(LED_PIN, True)

        buzzer_running = False
        GPIO.output(BUZZER_PIN, False)

    else:

        GPIO.output(LED_PIN, False)

        buzzer_running = False
        GPIO.output(BUZZER_PIN, False)

# ================= STREAM =================

def gen_frames():

    global frame_count
    global fire_level
    global last_email_time
    global last_log_time
    global last_rgb_fire
    global last_rgb_fire_time
    global last_boxes, last_ids, last_confs

    while True:

        frame = detector.capture_frame()

        if frame is None:
            continue

        frame = cv2.rotate(frame, cv2.ROTATE_180)
        frame = cv2.flip(frame, 1)

        frame = cv2.resize(frame, (OUTPUT_WIDTH, OUTPUT_HEIGHT))

        read_temp()

        h, w = frame.shape[:2]

        frame_count += 1
        fire_detected = False

        # default: keep last detections when not running YOLO this frame
        if frame_count % DETECTION_INTERVAL == 0:

            blob = cv2.dnn.blobFromImage(frame, 1/255.0, (256, 256), swapRB=True)
            detector.net.setInput(blob)

            outputs = detector.net.forward(detector.output_layers)

            boxes = []
            confs = []
            ids = []

            for out in outputs:
                for det in out:

                    scores = det[5:]
                    cid = int(np.argmax(scores))
                    conf = float(scores[cid])

                    if conf < RGB_CONF_THRESHOLD:
                        continue

                    label = detector.classes[cid].lower()

                    # ? REMOVE PERSON (skip it)
                    if "person" in label:
                        continue

                    # ? KEEP FIRE
                    if "fire" in label:
                        fire_detected = True
                        last_rgb_fire = True
                        last_rgb_fire_time = time.time()

                    cx = int(det[0] * w)
                    cy = int(det[1] * h)
                    bw = int(det[2] * w)
                    bh = int(det[3] * h)

                    x = int(cx - bw / 2)
                    y = int(cy - bh / 2)

                    boxes.append([x, y, bw, bh])
                    confs.append(conf)
                    ids.append(cid)

            idxs = cv2.dnn.NMSBoxes(boxes, confs, 0.3, 0.4)

            last_boxes, last_ids, last_confs = [], [], []
            if len(idxs) > 0:
                for i in idxs.flatten():
                    last_boxes.append(boxes[i])
                    last_ids.append(ids[i])
                    last_confs.append(confs[i])

        # hold logic for rgb fire
        if time.time() - last_rgb_fire_time > RGB_FIRE_HOLD:
            last_rgb_fire = False

        thermal_high = current_temp >= LEVEL3_MIN

        if thermal_high and last_rgb_fire:
            fire_level = 3
        elif (LEVEL2_MIN <= current_temp <= LEVEL2_MAX) or fire_detected:
            fire_level = 2
        else:
            fire_level = 1

        if fire_level == 3 and time.time() - last_email_time > EMAIL_COOLDOWN:

            snapshot = f"/home/admin/fire_{int(time.time())}.jpg"
            cv2.imwrite(snapshot, frame)
            alert_queue.put((snapshot, current_temp, 3))
            last_email_time = time.time()

        alarm(fire_level)

        if time.time() - last_log_time > LOG_INTERVAL:
            log_fire_event(current_temp, fire_level)
            last_log_time = time.time()

        # draw last detections (person is already filtered out)
        for (x, y, bw, bh), cid, conf in zip(last_boxes, last_ids, last_confs):
            color = CLASS_COLORS.get(cid, (255, 255, 255))
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), color, 2)

        if fire_level == 1:
            status = "NORMAL"
            color = (0, 255, 0)
        elif fire_level == 2:
            status = "WARNING"
            color = (0, 165, 255)
        else:
            status = "FIRE DETECTED"
            color = (0, 0, 255)

        cv2.rectangle(frame, (0, 0), (w, 40), (0, 0, 0), -1)
        cv2.putText(frame, status, (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        draw_grid(frame, 6, 6)

        ok, jpeg = cv2.imencode(".jpg", frame)

        if ok:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' +
                   jpeg.tobytes() + b'\r\n')

# ================= ROUTE =================

@app.route("/fire_stream")
def fire_stream():

    return Response(gen_frames(),
    mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/fire_status")
def fire_status_api():
    return jsonify({
        "fire_level": fire_level,
        "fire_status": level_to_status(fire_level),
        "temperature": round(float(current_temp), 1),
        "timestamp": datetime.now().isoformat()
    })

# ================= START =================

if __name__=="__main__":

    app.run(host="0.0.0.0",port=8060,threaded=True)