# pi_rgb_logic.py

import cv2
import numpy as np
import os

try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except ImportError:
    print("picamera2 not found - using USB fallback")
    PICAMERA_AVAILABLE = False


CLASS_FIRE = 0
CLASS_PERSON = 1
CLASS_STOVE = 2
CLASS_CANDLE = 3

CLASS_CONF_THRESH = {
    CLASS_FIRE: 0.25,
    CLASS_PERSON: 0.18,
    CLASS_STOVE: 0.20,
    CLASS_CANDLE: 0.30
}

CLASS_COLORS = {
    CLASS_FIRE: (0, 0, 255),
    CLASS_PERSON: (0, 255, 0),
    CLASS_STOVE: (255, 100, 0),
    CLASS_CANDLE: (0, 255, 255)
}


class FireDetectionRGB:

    def __init__(self, model_path='models', resolution=(640, 480), use_camera=True):

        self.resolution = resolution
        self.use_camera = use_camera and PICAMERA_AVAILABLE

        # =============================
        # CAMERA ONLY IF REQUESTED
        # =============================
        if self.use_camera:
            print("Initializing Pi Camera...")
            self.camera = Picamera2()

            # Preview configuration (wide FOV)
            config = self.camera.create_preview_configuration(
                main={"size": (1288, 720), "format": "RGB888"}
            )
            self.camera.configure(config)

            # Start camera first, then apply controls
            self.camera.start()

            # Normal auto settings (NO "filter look")
            try:
                self.camera.set_controls({
                    "AeEnable": True,
                    "AwbEnable": True,
                    # 0=Off, 1=Fast, 2=HighQuality (depends on pipeline)
                    "NoiseReductionMode": 1,
                    "Sharpness": 1.0,
                    "Contrast": 1.0,
                    "Saturation": 1.0
                })
            except Exception as e:
                print("Warning: some camera controls not supported:", e)

            print("Pi Camera initialized")
        else:
            self.camera = None

        self._load_yolo_model(model_path)

    # =============================
    # YOLO LOADER
    # =============================
    def _load_yolo_model(self, model_path):

        print(f"Loading YOLO model from {model_path}...")

        cfg_file = os.path.join(model_path, 'fire.cfg')
        weights_file = os.path.join(model_path, 'fire.weights')
        names_file = os.path.join(model_path, 'fire.names')

        if not (os.path.exists(cfg_file)
                and os.path.exists(weights_file)
                and os.path.exists(names_file)):
            raise FileNotFoundError(
                f"Model files missing in {model_path}"
            )

        self.net = cv2.dnn.readNetFromDarknet(cfg_file, weights_file)
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

        with open(names_file, 'r') as f:
            self.classes = [line.strip() for line in f]

        layer_names = self.net.getLayerNames()
        unconnected = self.net.getUnconnectedOutLayers()

        if isinstance(unconnected, np.ndarray) and unconnected.ndim == 2:
            self.output_layers = [layer_names[i[0]-1] for i in unconnected]
        else:
            self.output_layers = [layer_names[i-1] for i in unconnected]

        print(f"YOLO loaded ({len(self.classes)} classes)")

    # =============================
    # CAPTURE
    # =============================
    def capture_frame(self):
        if not self.use_camera:
            return None

        # IMPORTANT FIX:
        # Picamera2 returns frames that are already correct for OpenCV usage here.
        # DO NOT convert RGB->BGR again (that causes weird colors).
        frame = self.camera.capture_array()
        return frame

    def close(self):
        if self.use_camera and self.camera:
            self.camera.stop()
            print("Camera closed")