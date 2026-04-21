import sqlite3
from datetime import datetime

DB = "pyrosense.db"

def get_alert_level(temp):
    if temp >= 60:
        return "Critical"
    elif temp >= 45:
        return "Warning"
    elif temp >= 35:
        return "Caution"
    else:
        return "Active"

def log_event(temp, fire_detected):
    alert_level = get_alert_level(temp)

    status = "Fire Detected" if fire_detected else "Normal"

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute(
        "INSERT INTO logs (timestamp, temperature, alert_level, fire_detected, status) VALUES (?, ?, ?, ?, ?)",
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            temp,
            alert_level,
            int(fire_detected),
            status
        )
    )

    conn.commit()
    conn.close()