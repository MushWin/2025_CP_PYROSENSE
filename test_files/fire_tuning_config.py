"""
Fire Detection Tuning Configuration
Adjust these settings to improve fire detection accuracy
"""

# Fire Detection Tuning Settings
FIRE_DETECTION_CONFIG = {
    # Confidence thresholds
    'fire_confidence_min': 0.15,    # Very sensitive (may detect pillows as fire)
    'fire_confidence_balanced': 0.35,  # Balanced (recommended for real fire)
    'fire_confidence_strict': 0.55,   # Strict (only very confident fire detections)
    
    # Color-based filtering (to reduce pillow false positives)
    'enable_color_filtering': True,
    'fire_hue_range': (0, 25),       # Red-orange hue range for fire
    'fire_saturation_min': 100,      # Minimum saturation for fire
    'fire_brightness_min': 80,       # Minimum brightness for fire
    
    # Size filtering
    'min_fire_area': 500,            # Minimum pixel area for fire detection
    'max_fire_area': 50000,          # Maximum pixel area (to exclude large colored objects)
    
    # Motion detection (fire usually has movement/flickering)
    'enable_motion_check': False,    # Set to True for advanced filtering
    'motion_threshold': 10,          # Minimum motion for fire confirmation
}

# COCO Detection Settings
COCO_DETECTION_CONFIG = {
    'person_confidence': 0.5,        # Standard confidence for person detection
    'object_confidence': 0.5,        # Standard confidence for other objects
    
    # Bounding box size limits
    'max_person_width_ratio': 0.8,   # Max person width as ratio of frame width
    'max_person_height_ratio': 0.9,  # Max person height as ratio of frame height
}

def apply_fire_filtering(detections, frame, config=FIRE_DETECTION_CONFIG):
    """
    Apply additional filtering to reduce fire false positives
    """
    import cv2
    import numpy as np
    
    filtered_detections = []
    
    for detection in detections:
        if detection['model'] == 'fire':
            x, y, w, h = detection['box']
            
            # Extract region of interest
            roi = frame[y:y+h, x:x+w]
            if roi.size == 0:
                continue
            
            # Size filtering
            area = w * h
            if area < config['min_fire_area'] or area > config['max_fire_area']:
                print(f"🔍 Fire detection rejected: size {area} pixels (pillow?)")
                continue
            
            # Color filtering to reduce pillow false positives
            if config['enable_color_filtering']:
                # Convert to HSV for better color analysis
                hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                
                # Check if colors match fire characteristics
                hue = hsv_roi[:,:,0]
                sat = hsv_roi[:,:,1]
                val = hsv_roi[:,:,2]
                
                # Fire should have red-orange hues with high saturation
                fire_mask = (
                    ((hue >= config['fire_hue_range'][0]) & (hue <= config['fire_hue_range'][1])) &
                    (sat >= config['fire_saturation_min']) &
                    (val >= config['fire_brightness_min'])
                )
                
                fire_pixel_ratio = np.sum(fire_mask) / fire_mask.size
                
                if fire_pixel_ratio < 0.1:  # Less than 10% fire-colored pixels
                    print(f"🔍 Fire detection rejected: low fire-color ratio {fire_pixel_ratio:.2f} (pillow?)")
                    continue
            
            # If it passes all filters, keep the detection
            filtered_detections.append(detection)
        else:
            # Keep all non-fire detections as-is
            filtered_detections.append(detection)
    
    return filtered_detections

# Usage instructions
USAGE_INSTRUCTIONS = """
🔥 FIRE DETECTION TUNING GUIDE

Your fire model is detecting your red/orange pillow because:
1. It's trained on fire colors (red, orange, yellow)
2. The pillow has similar colors to fire
3. The confidence threshold might be too low

SOLUTIONS:

1. IMMEDIATE FIX - Raise confidence threshold:
   - Press '+' key several times to increase fire confidence to 0.4-0.5
   - This will reduce pillow false positives

2. ADVANCED FILTERING:
   - Use the fire_tuning_config.py settings
   - Enable color and size filtering
   - Add motion detection for real fire

3. TRAINING IMPROVEMENTS:
   - Add negative samples (pillows, red objects) to training data
   - Train for more iterations with diverse backgrounds
   - Use data augmentation with different lighting

4. BOUNDING BOX SIZE:
   - Large person boxes are normal for YOLO
   - YOLO tends to be generous with bounding boxes
   - You can adjust NMS threshold to make boxes tighter

RECOMMENDED SETTINGS FOR YOUR ENVIRONMENT:
- Fire confidence: 0.4-0.5 (to avoid pillow detection)
- COCO confidence: 0.5 (standard)
- Enable color filtering for fire
- Use size limits to reject large colored objects
"""

if __name__ == "__main__":
    print(USAGE_INSTRUCTIONS)
