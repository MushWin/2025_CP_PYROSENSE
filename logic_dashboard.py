"""
PyroSense - Dashboard Logic
All algorithms and utility functions for dashboard fire detection and thermal simulation
"""

import random
import time
from datetime import datetime

# ========== THERMAL FIRE SIZE DETECTION ==========

FIRE_SIZE_NORMAL = 15.0
FIRE_SIZE_CAUTION = 25.0
FIRE_SIZE_WARNING = 40.0

ALERT_ACTIVE = "Active"
ALERT_CAUTION = "Caution"
ALERT_WARNING = "Warning"
ALERT_CRITICAL = "Critical"

ALERT_COLORS_RGB = {
    ALERT_ACTIVE: (0, 255, 0),
    ALERT_CAUTION: (0, 255, 255),
    ALERT_WARNING: (0, 165, 255),
    ALERT_CRITICAL: (0, 0, 255)
}

# ADDED: Sustained fire duration thresholds (in seconds)
DURATION_ACTIVE = 5
DURATION_CAUTION = 15
DURATION_WARNING = 25
DURATION_CRITICAL = 30

# ADDED: Fire tracking state for dashboard
_dashboard_fire_tracking = {
    'fire_start_time': None,
    'fire_duration': 0.0,
    'last_update': None
}

def calculate_fire_size_percentage(boxes, frame_width, frame_height):
    """Calculate total fire area as percentage of frame"""
    if not boxes:
        return 0.0
    
    total_area = 0
    frame_area = frame_width * frame_height
    
    for box in boxes:
        x, y, w, h = box
        total_area += w * h
    
    percentage = (total_area / frame_area) * 100
    return round(percentage, 2)

def calculate_fire_duration_dashboard(fire_detected, fire_size_pct):
    """Calculate sustained fire duration for dashboard"""
    import time
    
    current_time = time.time()
    
    if fire_detected and fire_size_pct > 5:
        if _dashboard_fire_tracking['fire_start_time'] is None:
            _dashboard_fire_tracking['fire_start_time'] = current_time
        
        _dashboard_fire_tracking['last_update'] = current_time
        duration = current_time - _dashboard_fire_tracking['fire_start_time']
        _dashboard_fire_tracking['fire_duration'] = duration
        
        return duration, duration >= DURATION_ACTIVE
    else:
        if _dashboard_fire_tracking['fire_start_time'] is not None:
            time_since_last = current_time - _dashboard_fire_tracking['last_update']
            
            if time_since_last < 2.0:
                return _dashboard_fire_tracking['fire_duration'], True
            else:
                _dashboard_fire_tracking['fire_start_time'] = None
                _dashboard_fire_tracking['fire_duration'] = 0.0
        
        return 0.0, False

def is_smoke_not_fire(box, frame):
    """
    Distinguish smoke from fire based on visual characteristics
    Returns True if box appears to be smoke, False if it's likely fire
    """
    import cv2
    import numpy as np
    
    x, y, w, h = box
    
    # Extract region of interest
    roi = frame[max(0, y):min(frame.shape[0], y+h), max(0, x):min(frame.shape[1], x+w)]
    
    if roi.size == 0:
        return False
    
    # Convert to HSV to analyze color
    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    
    # Get average saturation and value
    avg_saturation = np.mean(hsv_roi[:, :, 1])
    avg_value = np.mean(hsv_roi[:, :, 2])
    
    # Smoke has low saturation (gray/white)
    if avg_saturation < 60:
        return True
    
    # Bright but not colorful = white smoke
    if avg_value > 180 and avg_saturation < 80:
        return True
    
    # Check color distribution
    hue_hist = cv2.calcHist([hsv_roi], [0], None, [180], [0, 180])
    fire_hue_pixels = np.sum(hue_hist[0:36])
    total_pixels = roi.shape[0] * roi.shape[1]
    fire_hue_ratio = fire_hue_pixels / (total_pixels + 1e-6)
    
    if fire_hue_ratio < 0.3:
        return True
    
    return False

def generate_combined_alert(fire_boxes, class_ids, classes, frame_width, frame_height, thermal_boxes=None, frame=None):
    """Generate combined alert level based on thermal + RGB detection + sustained duration + smoke filtering"""
    all_fire_boxes = []
    
    # UPDATED: Only use thermal boxes if RGB model detected fire first
    has_rgb_fire = any(
        class_id < len(classes) and 'fire' in classes[class_id].lower() 
        for class_id in class_ids
    ) if classes else False
    
    # FIXED: Thermal boxes only counted when model confirms fire
    if thermal_boxes and has_rgb_fire:
        all_fire_boxes.extend(thermal_boxes)
    
    # ADDED: Filter out smoke from RGB fire detections
    for i, class_id in enumerate(class_ids):
        if class_id < len(classes) and 'fire' in classes[class_id].lower():
            # Validate this is actual fire, not smoke
            if frame is not None:
                if not is_smoke_not_fire(fire_boxes[i], frame):
                    all_fire_boxes.append(fire_boxes[i])
            else:
                all_fire_boxes.append(fire_boxes[i])
    
    fire_size_pct = calculate_fire_size_percentage(all_fire_boxes, frame_width, frame_height)
    
    # ADDED: Calculate sustained fire duration
    fire_duration, is_sustained = calculate_fire_duration_dashboard(has_rgb_fire and len(all_fire_boxes) > 0, fire_size_pct)
    
    CLASS_STOVE = 0
    CLASS_CANDLE = 4
    CLASS_PERSON = 3
    CLASS_FIRE = 2
    
    has_stove = CLASS_STOVE in class_ids
    has_candle = CLASS_CANDLE in class_ids
    has_person = CLASS_PERSON in class_ids
    has_fire = CLASS_FIRE in class_ids or len(all_fire_boxes) > 0
    
    # UPDATED: Return 0% when no actual fire detected
    if not has_rgb_fire and fire_size_pct < 5:
        return ALERT_ACTIVE, ALERT_COLORS_RGB[ALERT_ACTIVE], 0.0, "No fire detected"
    
    # UPDATED: Alert logic with sustained duration
    if fire_size_pct > FIRE_SIZE_WARNING and fire_duration >= DURATION_CRITICAL:
        if has_person:
            return ALERT_CRITICAL, ALERT_COLORS_RGB[ALERT_CRITICAL], fire_size_pct, f"CRITICAL: Large fire for {int(fire_duration)}s with person — EVACUATE!"
        else:
            return ALERT_CRITICAL, ALERT_COLORS_RGB[ALERT_CRITICAL], fire_size_pct, f"CRITICAL: Large fire sustained for {int(fire_duration)}s — EVACUATE!"
    
    if fire_size_pct > FIRE_SIZE_WARNING:
        if has_person:
            return ALERT_CRITICAL, ALERT_COLORS_RGB[ALERT_CRITICAL], fire_size_pct, "CRITICAL: Large fire with person!"
        else:
            return ALERT_WARNING, ALERT_COLORS_RGB[ALERT_WARNING], fire_size_pct, f"WARNING: Large fire for {int(fire_duration)}s — check now!"
    
    if fire_size_pct > FIRE_SIZE_CAUTION and fire_duration >= DURATION_WARNING:
        if has_person:
            return ALERT_WARNING, ALERT_COLORS_RGB[ALERT_WARNING], fire_size_pct, f"WARNING: Fire sustained for {int(fire_duration)}s — Person nearby!"
        elif not has_stove and not has_candle:
            return ALERT_WARNING, ALERT_COLORS_RGB[ALERT_WARNING], fire_size_pct, f"WARNING: Fire sustained for {int(fire_duration)}s — check now!"
        else:
            return ALERT_WARNING, ALERT_COLORS_RGB[ALERT_WARNING], fire_size_pct, f"WARNING: Large fire for {int(fire_duration)}s"
    
    if fire_size_pct > FIRE_SIZE_NORMAL and fire_duration >= DURATION_CAUTION:
        if has_stove:
            return ALERT_CAUTION, ALERT_COLORS_RGB[ALERT_CAUTION], fire_size_pct, f"CAUTION: Fire growing for {int(fire_duration)}s — keep watching"
        else:
            return ALERT_CAUTION, ALERT_COLORS_RGB[ALERT_CAUTION], fire_size_pct, f"CAUTION: Medium fire for {int(fire_duration)}s"
    
    if has_stove or has_candle:
        if fire_duration > 0:
            return ALERT_ACTIVE, ALERT_COLORS_RGB[ALERT_ACTIVE], fire_size_pct, f"ACTIVE: Normal cooking ({int(fire_duration)}s)"
        else:
            return ALERT_ACTIVE, ALERT_COLORS_RGB[ALERT_ACTIVE], fire_size_pct, "ACTIVE: Normal cooking"
    elif has_fire:
        if fire_duration > 0:
            return ALERT_ACTIVE, ALERT_COLORS_RGB[ALERT_ACTIVE], fire_size_pct, f"ACTIVE: Small fire ({int(fire_duration)}s)"
        else:
            return ALERT_ACTIVE, ALERT_COLORS_RGB[ALERT_ACTIVE], fire_size_pct, "ACTIVE: Small fire"
    
    return ALERT_ACTIVE, ALERT_COLORS_RGB[ALERT_ACTIVE], fire_size_pct, "Monitoring"

def simulate_temperature_variation(dashboard_state):
    """Simulate temperature variation with fire influence"""
    baseline = dashboard_state.get('baseline_temp', 34.6)
    threshold = dashboard_state.get('threshold', 70)
    
    # Natural variation around baseline
    natural_variation = random.uniform(-0.5, 0.5)
    new_temp = baseline + natural_variation
    
    # Simulate gradual drift
    if random.random() < 0.1:
        dashboard_state['baseline_temp'] += random.uniform(-0.2, 0.2)
    
    dashboard_state['current_temperature'] = round(new_temp, 1)
