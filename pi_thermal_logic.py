"""
PyroSense - MLX90640 Thermal Sensor Logic
All thermal detection algorithms and fire size calculation
Based on logic from: logic_testyolo_camera.py, logic_dashboard.py
"""

import numpy as np
import time
try:
    import board
    import busio
    import adafruit_mlx90640
except ImportError:
    print("⚠️  MLX90640 library not found - running in simulation mode")
    board = None

# ========== THERMAL THRESHOLDS (from logic_testyolo_camera.py) ==========

THERMAL_BASELINE = 25.0           # °C - room temperature
THERMAL_THRESHOLD_WARM = 40.0     # °C - warm object
THERMAL_THRESHOLD_HOT = 70.0      # °C - hot object (triggers RGB check)
THERMAL_THRESHOLD_FIRE = 90.0     # °C - likely fire
THERMAL_THRESHOLD_CRITICAL = 120.0  # °C - definite fire

# Fire size thresholds (percentage of frame)
FIRE_SIZE_NORMAL = 15.0      # < 15% = normal cooking flame
FIRE_SIZE_CAUTION = 25.0     # 15-25% = fire growing
FIRE_SIZE_WARNING = 40.0     # 25-40% = abnormal fire
# > 40% = critical uncontrolled fire

# ADDED: Track thermal history for dynamic heat detection
_thermal_history = {
    'frames': [],       # Last N thermal frames
    'max_frames': 10    # Keep last 10 frames (5 seconds at 2 Hz)
}

# ADDED: Thermal temperature ranges for each object class
THERMAL_RANGES = {
    'person': (33.0, 38.0),        # Body heat: 33-38°C
    'fire': (90.0, 500.0),          # Fire: 90°C+
    'stove': (60.0, 150.0),         # Stove/cooking: 60-150°C
    'candle': (50.0, 100.0),        # Candle flame: 50-100°C
    'hot_cup': (50.0, 90.0),        # Hot beverages: 50-90°C
    'ambient': (20.0, 30.0)         # Room temperature
}

class ThermalSensor:
    """MLX90640 Thermal Camera Interface"""
    
    def __init__(self, refresh_rate=2):  # 2 Hz refresh rate
        """Initialize MLX90640 sensor"""
        print("🌡️  Initializing MLX90640 thermal sensor...")
        
        self.simulation_mode = board is None
        self.frame_shape = (24, 32)  # MLX90640 resolution
        self.refresh_rate = refresh_rate
        
        if not self.simulation_mode:
            try:
                i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)
                self.mlx = adafruit_mlx90640.MLX90640(i2c)
                self.mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ
                print("✅ MLX90640 initialized successfully")
            except Exception as e:
                print(f"❌ MLX90640 init failed: {e}")
                print("⚠️  Switching to simulation mode")
                self.simulation_mode = True
        else:
            print("⚠️  Running in SIMULATION mode")
        
        # Frame buffer
        self.frame_buffer = np.zeros(self.frame_shape, dtype=float)
    
    def read_frame(self):
        """Read thermal frame from MLX90640"""
        if self.simulation_mode:
            return self._simulate_thermal_frame()
        
        try:
            # Read into buffer
            self.mlx.getFrame(self.frame_buffer.flatten())
            return self.frame_buffer.copy()
        except Exception as e:
            print(f"❌ Thermal read error: {e}")
            return self._simulate_thermal_frame()
    
    def _simulate_thermal_frame(self):
        """Simulate thermal data for testing"""
        # Base temperature with some noise
        frame = np.random.normal(25.0, 2.0, self.frame_shape)
        
        # Occasionally simulate hot spot
        if np.random.random() < 0.05:  # 5% chance
            hot_x = np.random.randint(5, 27)
            hot_y = np.random.randint(5, 19)
            hot_temp = np.random.uniform(70, 120)
            
            # Create hot region
            frame[hot_y-2:hot_y+3, hot_x-2:hot_x+3] = hot_temp
        
        return frame
    
    def close(self):
        """Clean up resources"""
        print("🌡️  Thermal sensor closed")

def is_high_temperature_detected(thermal_frame, threshold=THERMAL_THRESHOLD_HOT):
    """
    Detect high temperature regions that require RGB validation
    
    IMPROVED: Rejects static hot objects (cups, kettles, plates)
    Only triggers for DYNAMIC heat (flames, spreading fire)
    
    Returns: List of (x, y, w, h, max_temp) for hot regions
    """
    # Find pixels above threshold
    hot_mask = thermal_frame > threshold
    
    if not np.any(hot_mask):
        return []
    
    # ADDED: Check if heat is dynamic (fire) or static (hot object)
    if not _is_heat_dynamic(thermal_frame):
        # Static hot object detected - REJECT
        return []
    
    # Find contiguous regions
    from scipy import ndimage
    labeled, num_features = ndimage.label(hot_mask)
    
    hot_regions = []
    
    for region_id in range(1, num_features + 1):
        region_mask = labeled == region_id
        coords = np.argwhere(region_mask)
        
        if len(coords) < 3:  # Filter tiny regions
            continue
        
        # Get bounding box
        y_min, x_min = coords.min(axis=0)
        y_max, x_max = coords.max(axis=0)
        
        w = x_max - x_min + 1
        h = y_max - y_min + 1
        
        # Get max temperature in this region
        region_temps = thermal_frame[region_mask]
        max_temp = np.max(region_temps)
        avg_temp = np.mean(region_temps)
        
        # ADDED: Additional validation - fire spreads, hot cups don't
        if _is_region_fire_like(region_mask, thermal_frame):
            hot_regions.append({
                'x': int(x_min),
                'y': int(y_min),
                'w': int(w),
                'h': int(h),
                'max_temp': float(max_temp),
                'avg_temp': float(avg_temp)
            })
    
    return hot_regions

def _is_heat_dynamic(thermal_frame):
    """
    Check if heat pattern is dynamic (fire) or static (hot object)
    
    Fire characteristics:
    - Temperature changes over time (flickering)
    - Heat spreads to new areas
    - Irregular, growing pattern
    
    Hot object characteristics:
    - Constant temperature over time
    - Heat stays in same location
    - Uniform, stable pattern
    """
    # Store current frame in history
    _thermal_history['frames'].append(thermal_frame.copy())
    
    # Keep only last N frames
    if len(_thermal_history['frames']) > _thermal_history['max_frames']:
        _thermal_history['frames'].pop(0)
    
    # Need at least 3 frames to detect dynamics
    if len(_thermal_history['frames']) < 3:
        return True  # Not enough history, allow detection
    
    # Calculate temperature variance over time
    frames = np.array(_thermal_history['frames'])
    
    # Get standard deviation across time for each pixel
    temporal_variance = np.std(frames, axis=0)
    
    # Fire flickers - high temporal variance
    # Hot cup stays constant - low temporal variance
    avg_variance = np.mean(temporal_variance)
    
    # THRESHOLD: Fire flickers at least 2-3°C, hot cups < 1°C variance
    if avg_variance < 1.0:
        print(f"⚠️  Static hot object detected (variance: {avg_variance:.2f}°C) - REJECTED")
        return False  # Static object (hot cup/kettle)
    
    return True  # Dynamic heat (likely fire)

def _is_region_fire_like(region_mask, thermal_frame):
    """
    Additional validation: Check if hot region has fire-like characteristics
    
    Fire: Irregular shape, high temperature gradient, asymmetric
    Hot cup: Circular/rectangular, uniform temperature, symmetric
    """
    # Get region shape
    coords = np.argwhere(region_mask)
    
    if len(coords) < 5:
        return True  # Too small to analyze
    
    # Calculate bounding box aspect ratio
    y_coords, x_coords = coords[:, 0], coords[:, 1]
    width = x_coords.max() - x_coords.min()
    height = y_coords.max() - y_coords.min()
    
    aspect_ratio = height / (width + 1e-6)
    
    # Hot cups/plates are usually circular (aspect ~1:1)
    # Fire is irregular and tends to be taller (aspect > 1.2)
    if 0.8 < aspect_ratio < 1.2:
        # Check if shape is too regular (circular = hot cup)
        filled_ratio = len(coords) / ((width + 1) * (height + 1))
        
        if filled_ratio > 0.7:  # Very filled = circular/rectangular
            print(f"⚠️  Circular hot object detected (aspect: {aspect_ratio:.2f}) - Likely cup/plate")
            return False
    
    # Check temperature gradient (fire has sharp gradients at edges)
    region_temps = thermal_frame[region_mask]
    temp_std = np.std(region_temps)
    
    # Hot cup has uniform temperature, fire has varying temps
    if temp_std < 3.0:  # Very uniform
        print(f"⚠️  Uniform temperature detected (std: {temp_std:.2f}°C) - Likely solid object")
        return False
    
    return True

def calculate_thermal_fire_size_percentage(thermal_frame, threshold=THERMAL_THRESHOLD_FIRE):
    """
    Calculate fire size as percentage of thermal frame
    
    Algorithm from: logic_testyolo_camera.py - calculate_fire_size_percentage()
    """
    fire_mask = thermal_frame > threshold
    fire_pixels = np.sum(fire_mask)
    total_pixels = thermal_frame.size
    
    percentage = (fire_pixels / total_pixels) * 100.0
    return round(percentage, 2)

def map_thermal_to_rgb_coordinates(thermal_box, thermal_shape=(24, 32), rgb_shape=(480, 640)):
    """
    Map thermal sensor coordinates to RGB camera coordinates
    MLX90640: 24x32 pixels → Pi Camera: 640x480 pixels
    """
    scale_x = rgb_shape[1] / thermal_shape[1]  # 640 / 32 = 20
    scale_y = rgb_shape[0] / thermal_shape[0]  # 480 / 24 = 20
    
    rgb_box = {
        'x': int(thermal_box['x'] * scale_x),
        'y': int(thermal_box['y'] * scale_y),
        'w': int(thermal_box['w'] * scale_x),
        'h': int(thermal_box['h'] * scale_y)
    }
    
    return rgb_box

def is_thermal_fire_sustained(thermal_history, duration_threshold=5.0):
    """
    Check if high temperature has been sustained
    
    Algorithm from: logic_testyolo_camera.py - calculate_fire_duration()
    """
    if len(thermal_history) == 0:
        return False, 0.0
    
    # Check if temperatures consistently above threshold
    sustained_count = 0
    for temp_data in thermal_history:
        if temp_data['max_temp'] > THERMAL_THRESHOLD_FIRE:
            sustained_count += 1
        else:
            sustained_count = 0  # Reset if drops below
    
    # Assuming 2 Hz refresh rate
    duration = sustained_count * 0.5  # seconds
    
    is_sustained = duration >= duration_threshold
    
    return is_sustained, duration

def validate_class_with_thermal(class_name, thermal_region, thermal_frame):
    """
    Cross-validate RGB detection with thermal data
    
    Each object has expected thermal signature:
    - Person: 33-38°C (body temperature)
    - Fire: >90°C and spreading
    - Stove: 60-150°C and stationary
    - Candle: 50-100°C and small area
    - Hot cup: 50-90°C and static
    
    Returns: (is_valid: bool, confidence: float, reason: str)
    """
    max_temp = thermal_region.get('max_temp', 0)
    avg_temp = thermal_region.get('avg_temp', 0)
    
    class_lower = class_name.lower()
    
    # VALIDATION 1: PERSON
    if 'person' in class_lower:
        expected_min, expected_max = THERMAL_RANGES['person']
        
        # Check if thermal reading matches body temperature
        if expected_min <= max_temp <= expected_max:
            return True, 0.9, f"Thermal confirms person (body heat: {max_temp:.1f}°C)"
        elif max_temp < expected_min:
            return False, 0.2, f"Too cold for person ({max_temp:.1f}°C < 33°C)"
        else:
            return False, 0.3, f"Too hot for person ({max_temp:.1f}°C > 38°C)"
    
    # VALIDATION 2: FIRE
    elif 'fire' in class_lower:
        expected_min, expected_max = THERMAL_RANGES['fire']
        
        # Fire must be hot AND spreading
        if max_temp >= expected_min:
            # Check if fire is spreading (dynamic heat)
            if _is_heat_dynamic(thermal_frame):
                return True, 0.95, f"Thermal confirms fire ({max_temp:.1f}°C, spreading)"
            else:
                return False, 0.4, f"Hot but static ({max_temp:.1f}°C) - likely stove/kettle"
        else:
            return False, 0.1, f"Not hot enough for fire ({max_temp:.1f}°C < 90°C)"
    
    # VALIDATION 3: STOVE
    elif 'stove' in class_lower or 'oven' in class_lower:
        expected_min, expected_max = THERMAL_RANGES['stove']
        
        # Stove must be hot AND stationary
        if expected_min <= max_temp <= expected_max:
            # Check if heat is static (not spreading)
            if not _is_heat_dynamic(thermal_frame):
                return True, 0.85, f"Thermal confirms stove ({max_temp:.1f}°C, stationary)"
            else:
                return False, 0.5, f"Heat is spreading ({max_temp:.1f}°C) - possible fire"
        elif max_temp > expected_max:
            return False, 0.3, f"Too hot for stove ({max_temp:.1f}°C) - possible fire"
        else:
            return False, 0.2, f"Not hot enough for stove ({max_temp:.1f}°C)"
    
    # VALIDATION 4: CANDLE
    elif 'candle' in class_lower:
        expected_min, expected_max = THERMAL_RANGES['candle']
        
        # Candle: small hot region
        region_area = thermal_region.get('w', 0) * thermal_region.get('h', 0)
        
        if expected_min <= max_temp <= expected_max:
            if region_area < 500:  # Small area (< 500 pixels)
                return True, 0.8, f"Thermal confirms candle ({max_temp:.1f}°C, small)"
            else:
                return False, 0.4, f"Too large for candle ({region_area} px²)"
        else:
            return False, 0.2, f"Temperature mismatch for candle ({max_temp:.1f}°C)"
    
    # VALIDATION 5: HOT CUP/KETTLE (REJECT AS FIRE)
    elif max_temp >= 50 and max_temp < 90:
        # This is a hot object but NOT fire
        if not _is_heat_dynamic(thermal_frame):
            return False, 0.1, f"Hot static object ({max_temp:.1f}°C) - NOT fire"
    
    # Default: no thermal validation available
    return True, 0.5, "No thermal cross-validation available"

def get_thermal_region_for_rgb_box(rgb_box, thermal_frame, rgb_shape=(480, 640)):
    """
    Get thermal data for a specific RGB bounding box
    Maps RGB coordinates to thermal sensor coordinates
    
    Returns: thermal_region dict with max_temp, avg_temp, w, h
    """
    from pi_thermal_logic import map_thermal_to_rgb_coordinates
    
    # RGB box coordinates
    x, y, w, h = rgb_box
    
    # Convert to thermal coordinates (reverse mapping)
    thermal_shape = thermal_frame.shape  # (24, 32)
    
    scale_x = thermal_shape[1] / rgb_shape[1]  # 32 / 640
    scale_y = thermal_shape[0] / rgb_shape[0]  # 24 / 480
    
    thermal_x = int(x * scale_x)
    thermal_y = int(y * scale_y)
    thermal_w = max(1, int(w * scale_x))
    thermal_h = max(1, int(h * scale_y))
    
    # Extract thermal ROI
    thermal_roi = thermal_frame[
        max(0, thermal_y):min(thermal_shape[0], thermal_y + thermal_h),
        max(0, thermal_x):min(thermal_shape[1], thermal_x + thermal_w)
    ]
    
    if thermal_roi.size == 0:
        return {
            'max_temp': 0.0,
            'avg_temp': 0.0,
            'w': 0,
            'h': 0
        }
    
    return {
        'max_temp': float(np.max(thermal_roi)),
        'avg_temp': float(np.mean(thermal_roi)),
        'w': thermal_w,
        'h': thermal_h
    }
