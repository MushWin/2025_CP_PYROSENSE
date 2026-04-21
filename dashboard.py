# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
PyroSense Dashboard - Python Flask Application
Advanced Fire Detection System Dashboard
"""

from flask import Flask, render_template_string, jsonify, request, redirect, session, Response, stream_with_context, flash, url_for, make_response
from datetime import datetime
import random
import time
import threading
import json
import cv2  # ADDED: OpenCV for webcam streaming
import numpy as np  # ADDED: NumPy for image processing
import os  # ADDED: missing os import used by model file helpers
import glob
import pathlib
import sys            # <-- NEW
import socket         # <-- NEW
import requests
import subprocess
CONFIG_FILE = "threshold_config.json"
LOGS_DB_PATH = "/home/admin/pyrosense/2025_CP_PYROSENSE/pyrosense_logs.db"

from logic_dashboard import (
    FIRE_SIZE_NORMAL, FIRE_SIZE_CAUTION, FIRE_SIZE_WARNING,
    ALERT_ACTIVE, ALERT_CAUTION, ALERT_WARNING, ALERT_CRITICAL, ALERT_COLORS_RGB,
    calculate_fire_size_percentage, generate_combined_alert, simulate_temperature_variation
)

app = Flask(__name__)
# Add the same secret key as login.py for shared sessions
app.secret_key = 'pyrosense_shared_secret_key'

# Configuration: Login service base URL and camera control endpoint
LOGIN_BASE = os.environ.get('PYROSENSE_LOGIN_BASE', 'http://192.168.1.110:5000')
CAMERA_CONTROL_URL = os.environ.get('CAMERA_CONTROL_URL', '')
DETECTION_STATUS_URL = "http://192.168.1.110:8060/fire_status"

# Global variables for dashboard state
dashboard_state = {
    'current_temperature': 34.6,
    'threshold': 70,
    'is_recording': False,
    'night_vision': False,
    'alerts_active': True,
    'auto_mode': True,
    'fire_status': 'No fire detected',
    'fire_event_id': 0,
    'last_fire_trigger_at': None,
    'last_live_status': 'NORMAL',
    'system_status': {
        'camera': 'Online',
        'thermal': 'Offline',
        'edge': 'Running',
        'internet': 'Connected'
    },
    'log_entries': [
        f"[{datetime.now().strftime('%m/%d/%Y %H:%M:%S')}] System initialized",
        f"[{datetime.now().strftime('%m/%d/%Y %H:%M:%S')}] Sensors online",
        f"[{datetime.now().strftime('%m/%d/%Y %H:%M:%S')}] No fire detected"
    ],
    # calibration baseline so "calibrate" takes effect
    'baseline_temp': 34.6
}

# Add global video and fire-model flags
video_capture = None
video_lock = threading.Lock()
fire_model_enabled = False  # Controlled from the web UI
# Add the camera enabled flag
camera_enabled = True  # when False, generator will serve "camera off" image and capture is released

# --- ADDED: Fire model globals ---
net_fire = None
fire_classes = []
fire_output_layers = []
fire_model_loaded = False
fire_confidence_threshold = 0.25  # default; may be adjusted based on model class count

# NEW: inference tuning to reduce lag
inference_interval = 3      # run DNN once every N frames (increase to lower CPU)
jpeg_quality = 80           # JPEG encode quality (reduce bandwidth / CPU)

# Add detection bookkeeping and simple rate-limits
last_detection_summary = {
    'labels': [],          # last labels seen (list of strings)
    'timestamp': 0         # last inference time (epoch)
}
detection_lock = threading.Lock()
# Minimum seconds between logging identical detection summaries
_detection_log_min_interval = 5.0

# --- NEW: synthetic thermal influence from RGB fire detections ---
last_fire_detection_time = 0.0            # epoch of last 'fire' label seen
fire_temp_increase = 15.0                 # degrees above threshold to push when fire seen
fire_temp_persist_seconds = 8.0           # how long the elevated temp is held/ramped
fire_temp_rise_rate = 1.5                 # deg per tick rise while ramping
fire_temp_decay_rate = 0.8                # deg per tick decay after persist window

# --- NEW: persistence folders and recording state ---
recordings_dir = os.path.join(os.getcwd(), "recordings")
snapshots_dir = os.path.join(os.getcwd(), "snapshots")
os.makedirs(recordings_dir, exist_ok=True)
os.makedirs(snapshots_dir, exist_ok=True)

# Recording control globals
recording_flag = False
recording_thread = None
recording_lock = threading.Lock()
recording_filename = None
recording_writer = None

# Manual alert (set by Test Alert) Ã‚â€” displayed separately from model detections
dashboard_state.setdefault('manual_alert', None)

# Helper: locate model files in common locations (returns dict with keys 'cfg','weights','names' or {} if none)
def find_fire_model_files(model_dirs=None):
    try:
        # default search locations (include your YoloV4 path used by test_yolo_camera.py)
        if model_dirs is None:
            model_dirs = [
                os.path.join(os.getcwd(), "YoloV4-Tiny_Model", "fire_extracted_files"),
                os.path.join(os.getcwd(), "YoloV4-Tiny_Model"),
                os.path.join(os.getcwd(), 'models', 'fire'),
                os.path.join(os.getcwd(), 'models'),
                os.path.join(os.getcwd(), 'model'),
            ]

        # scan each directory recursively for best candidates
        for d in model_dirs:
            try:
                if not d or not os.path.isdir(d):
                    continue

                cfgs = glob.glob(os.path.join(d, "**", "*.cfg"), recursive=True)
                weights = glob.glob(os.path.join(d, "**", "*.weights"), recursive=True) + glob.glob(os.path.join(d, "**", "*.pt"), recursive=True) + glob.glob(os.path.join(d, "**", "*.onnx"), recursive=True)
                names = glob.glob(os.path.join(d, "**", "*.names"), recursive=True) + glob.glob(os.path.join(d, "**", "*.txt"), recursive=True)

                # prefer yolov4-tiny-ish configs first
                chosen_cfg = None
                for candidate in cfgs:
                    bn = os.path.basename(candidate).lower()
                    if "yolov4" in bn or "yolov4-tiny" in bn or "tiny" in bn:
                        chosen_cfg = candidate
                        break
                if not chosen_cfg and cfgs:
                    chosen_cfg = cfgs[0]

                # prefer weights with "best" or largest file
                chosen_weights = None
                if weights:
                    for w in weights:
                        if "best" in os.path.basename(w).lower() or "final" in os.path.basename(w).lower():
                            chosen_weights = w
                            break
                    if not chosen_weights:
                        # fallback to largest weights file (likely the trained darknet .weights)
                        chosen_weights = max(weights, key=lambda x: os.path.getsize(x))

                # prefer obj.names or any .names
                chosen_names = None
                for n in names:
                    bn = os.path.basename(n).lower()
                    if bn in ("obj.names", "classes.names", "obj.names.txt") or "obj" in bn:
                        chosen_names = n
                        break
                if not chosen_names and names:
                    chosen_names = names[0]

                files = {}
                if chosen_cfg:
                    files['cfg'] = chosen_cfg
                if chosen_weights:
                    files['weights'] = chosen_weights
                if chosen_names:
                    files['names'] = chosen_names

                if files:
                    # log selection for debugging in UI
                    add_log_entry(f"Model discovery: cfg={os.path.basename(files.get('cfg','None'))} weights={os.path.basename(files.get('weights','None'))} names={os.path.basename(files.get('names','None'))} (from {d})")
                    return files
            except Exception:
                continue

        # final fallback to cwd files
        cfgs = glob.glob('*.cfg')
        weights = glob.glob('*.weights') + glob.glob('*.pt') + glob.glob('*.onnx')
        names = glob.glob('*.names') + glob.glob('*.txt')
        files = {}
        if cfgs:
            files['cfg'] = cfgs[0]
        if weights:
            # pick largest in cwd
            files['weights'] = max(weights, key=lambda x: os.path.getsize(x))
        if names:
            files['names'] = names[0]
        if files:
            add_log_entry(f"Model discovery (cwd): cfg={files.get('cfg')} weights={files.get('weights')} names={files.get('names')}")
        return files
    except Exception as e:
        add_log_entry(f"Model discovery error: {e}")
        return {}

# Helper: read class names from the .names/.txt file
def load_fire_classes(names_path):
    try:
        if not names_path:
            return None
        with open(names_path, 'r', encoding='utf-8', errors='ignore') as fh:
            lines = [ln.strip() for ln in fh.readlines() if ln.strip()]
            return lines if lines else None
    except Exception:
        return None

# Helper: compute output layer names for older OpenCV dnn APIs
def get_output_layers(net):
    try:
        # net.getUnconnectedOutLayers can return array-like of indices (1-based)
        layer_names = net.getLayerNames()
        outs = net.getUnconnectedOutLayers()
        # normalize to list of ints
        if isinstance(outs, np.ndarray):
            ids = outs.flatten().tolist()
        else:
            try:
                ids = np.array(outs).flatten().tolist()
            except Exception:
                ids = []
        names = []
        for i in ids:
            try:
                idx = int(i) - 1
                if 0 <= idx < len(layer_names):
                    names.append(layer_names[idx])
            except Exception:
                continue
        return names
    except Exception:
        return []

def get_video_capture():
	"""Singleton video capture (lazy init). Attempts multiple backends to open camera for faster availability."""
	global video_capture
	with video_lock:
		if not camera_enabled:
			# If camera turned off, ensure capture released
			if video_capture is not None:
				try:
					video_capture.release()
				except:
					pass
				video_capture = None
			return None

		# If already created and opened return it
		if video_capture is not None and getattr(video_capture, "isOpened", lambda: False)():
			return video_capture

		# Otherwise attempt to open using helper
		video_capture = open_capture_with_backends(0)
		# set helpful properties if opened
		try:
			if video_capture is not None and video_capture.isOpened():
				video_capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
				video_capture.set(cv2.CAP_PROP_FPS, 30)
				video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
				video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
		except:
			pass
		return video_capture

# --- ADDED: dedicated opener used by get_video_capture and the toggle API ---
def open_capture_with_backends(index=0, warmup_reads=2):
	"""Try multiple backends to open camera quickly and perform a small warm-up read sequence."""
	backends = []
	try:
		# prefer platform-friendly backends when available
		backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
	except Exception:
		backends = [cv2.CAP_ANY]

	for backend in backends:
		try:
			cap = cv2.VideoCapture(index, backend)
			if cap is not None and cap.isOpened():
				# set reasonable defaults
				try:
					cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
					cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
					cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
					cap.set(cv2.CAP_PROP_FPS, 30)
				except:
					pass
				# quick warm-up reads to ensure camera actually returns frames fast
				for _ in range(warmup_reads):
					try:
						ret, _ = cap.read()
						if not ret:
							time.sleep(0.05)
					except:
						time.sleep(0.05)
				return cap
			else:
				try:
					if cap is not None:
						cap.release()
				except:
					pass
		except Exception:
			pass

	# Final fallback without backend hint
	try:
		cap = cv2.VideoCapture(index)
		if cap is not None and cap.isOpened():
			try:
				cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
				cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
			except:
				pass
			for _ in range(warmup_reads):
				try:
					ret, _ = cap.read()
					if not ret:
						time.sleep(0.05)
				except:
					time.sleep(0.05)
			return cap
		else:
			try:
				if cap is not None:
					cap.release()
			except:
				pass
	except Exception:
		pass

	return None

# --- UPDATED: more robust output-layer name getter used when loading model ---
def load_fire_model():
	"""Attempt to locate and load the fire model. Returns True on success."""
	global net_fire, fire_classes, fire_output_layers, fire_model_loaded, fire_confidence_threshold, fire_model_enabled
	fire_model_loaded = False
	files = find_fire_model_files()
	if not files:
		add_log_entry("Fire model: model folder not found (no cfg/weights/names discovered)")
		# update thermal sensor status
		dashboard_state['system_status']['thermal'] = 'Unavailable'
		return False
	cfg = files.get('cfg')
	weights = files.get('weights')
	names = files.get('names')

	if not (cfg and weights and names):
		add_log_entry(f"Fire model: incomplete model files (cfg={bool(cfg)}, weights={bool(weights)}, names={bool(names)})")
		return False

	try:
		# readNet supports (weights, cfg)
		net = cv2.dnn.readNet(weights, cfg)
		# Prefer CPU for compatibility
		try:
			net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
			net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
		except Exception:
			pass

		classes = load_fire_classes(names)
		if not classes:
			add_log_entry("Fire model: loaded but failed to read classes file")
			return False

		net_fire = net
		fire_classes = classes

		# Prefer the modern OpenCV convenience method if available
		try:
			if hasattr(net_fire, "getUnconnectedOutLayersNames"):
				fire_output_layers = net_fire.getUnconnectedOutLayersNames() or []
			else:
				fire_output_layers = get_output_layers(net_fire) or []
		except Exception:
			fire_output_layers = get_output_layers(net_fire) or []

		fire_model_loaded = True

		# adjust confidence threshold heuristically
		if len(classes) == 44:
			fire_confidence_threshold = 0.15
		elif len(classes) == 1:
			fire_confidence_threshold = 0.3
		else:
			fire_confidence_threshold = 0.2

		add_log_entry(f"Fire model loaded: {os.path.basename(weights)} ({len(classes)} classes) - names:{os.path.basename(names)}")
		# Enable overlay automatically when the model successfully loads (so boxes appear without extra toggle)
		fire_model_enabled = True

		# Update thermal sensor status to indicate model-backed sensor available
		dashboard_state['system_status']['thermal'] = 'OK'
		return True
	except Exception as e:
		add_log_entry(f"Fire model load failed: {e}")
		fire_model_loaded = False
		# Reflect thermal sensor problem in status panel
		dashboard_state['system_status']['thermal'] = 'Unavailable'
		return False

# --- UPDATED: remove automatic model load at definition-time ---
# Attempt to load at startup (non-blocking attempt) and enable overlay if successful
# try:
# 	_ok = load_fire_model()
# 	# load_fire_model sets fire_model_enabled True on success; ensure it's set here as well for clarity
# 	if _ok:
# 		fire_model_enabled = True
# except Exception:
# 	pass

# --- ADDED: safe startup attempt to load model (after logging and background thread exist) ---
# REMOVE automatic model load here as well so thermal stays Offline until explicitly loaded.
# (delete or comment out the block below if present)
# try:
#     loaded = load_fire_model()
#     if loaded:
#         fire_model_enabled = True
# except Exception:
#     pass

# --- NEW: recording loop used when recording is toggled ON ---
def _recording_loop(filename, stop_flag_ref):
    """Background loop that writes frames to a video file until stop flag set."""
    global recording_writer
    try:
        cap = get_video_capture()
        if cap is None or not getattr(cap, "isOpened", lambda: False)():
            # try to open a temporary capture
            cap = open_capture_with_backends(0, warmup_reads=2)
            if cap is None or not getattr(cap, "isOpened", lambda: False)():
                add_log_entry("Recording: camera not available to record")
                return

        # determine frame size
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(filename, fourcc, 20.0, (w, h))
        with recording_lock:
            recording_writer = writer

        add_log_entry(f"Recording started -> {os.path.basename(filename)}")
        while not stop_flag_ref():
            try:
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.05)
                    continue
                # mirror to match stream and write
                frame = cv2.flip(frame, 1)
                writer.write(frame)
                time.sleep(0.05)
            except Exception:
                time.sleep(0.05)
        try:
            writer.release()
        except:
            pass
        add_log_entry(f"Recording stopped -> {os.path.basename(filename)}")
    except Exception as e:
        add_log_entry(f"Recording error: {e}")
    finally:
        with recording_lock:
            recording_writer = None

def generate_mjpeg():
	"""Generator that yields MJPEG frames. Shows placeholder if camera disabled, and re-checks when enabled."""
	frame_idx = 0
	# store last detections to re-draw while skipping inference
	last_boxes = []
	last_class_ids = []
	last_confidences = []
	last_labels = []
	last_colors = []
	# ensure we can update the global fire timestamp here
	global last_fire_detection_time

	while True:
		cap = get_video_capture()
		# If camera disabled or not available, yield placeholder but keep re-checking
		if cap is None or not getattr(cap, "isOpened", lambda: False)():
			placeholder = np.zeros((360,640,3), dtype=np.uint8)
			# Centered title + subtitle
			title = "Camera is OFF"
			sub = "Click 'Camera' to enable feed"
			font = cv2.FONT_HERSHEY_SIMPLEX
			scale_title = 1.4
			scale_sub = 0.7
			thick = 3
			# compute centered positions
			(tw, th), _ = cv2.getTextSize(title, font, scale_title, thick)
			(sw, sh), _ = cv2.getTextSize(sub, font, scale_sub, 2)
			center_x = placeholder.shape[1] // 2
			center_y = placeholder.shape[0] // 2
			title_org = (center_x - tw // 2, center_y - 10)
			sub_org = (center_x - sw // 2, center_y + 30)
			cv2.putText(placeholder, title, title_org, font, scale_title, (255,255,255), thick, cv2.LINE_AA)
			cv2.putText(placeholder, sub, sub_org, font, scale_sub, (200,200,200), 2, cv2.LINE_AA)
			ret, jpeg = cv2.imencode('.jpg', placeholder)
			frame = jpeg.tobytes()
			# yield placeholder and re-check camera state on next loop iteration
			yield (b'--frame\r\n'
				   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
			time.sleep(0.25)
			continue

		# Camera is available Ã‚â€” stream frames
		ret, frame = cap.read()
		if not ret or frame is None:
			# If read failed, give the device a moment and re-check
			time.sleep(0.05)
			continue

		frame = cv2.flip(frame, 1)

		# Display manual alert or model fire alert only if alerts_active is True
		try:
			if dashboard_state.get('alerts_active'):
				manual_msg = dashboard_state.get('manual_alert')
				if manual_msg:
					# top bar for manual alerts
					cv2.rectangle(frame, (0,0), (frame.shape[1], 40), (50,50,220), -1)
					cv2.putText(frame, manual_msg[:80], (10,28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
				elif dashboard_state.get('fire_status') and 'FIRE' in dashboard_state.get('fire_status'):
					cv2.rectangle(frame, (0,0), (frame.shape[1], 40), (0,0,255), -1)
					cv2.putText(frame, "ALERT: FIRE DETECTED", (10,28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
		except Exception:
			pass

		# --- ADDED: Run lightweight YOLO fire-model inference and overlay boxes when enabled ---
		try:
			frame_idx += 1
			# Only run inference every N frames to reduce CPU usage
			do_infer = (fire_model_enabled and fire_model_loaded and net_fire is not None and (frame_idx % inference_interval == 0))
			if do_infer:
				# run on smaller input to save CPU (blobFromImage will resize)
				blob = cv2.dnn.blobFromImage(frame, 0.00392, (320, 320), (0,0,0), True, crop=False)
				net_fire.setInput(blob)
				try:
					if fire_output_layers:
						outs = net_fire.forward(fire_output_layers)
					else:
						outs = net_fire.forward()
				except Exception:
					try:
						outs = net_fire.forward()
					except Exception:
						outs = []

				if isinstance(outs, np.ndarray):
					outs = [outs]
				elif not isinstance(outs, (list, tuple)):
					outs = []

				height, width = frame.shape[:2]
				boxes = []
				confidences = []
				class_ids = []
				labels = []
				colors = []

				for out in outs:
					for detection in out:
						if detection.shape[0] <= 5:
							continue
						scores = detection[5:]
						if scores.size == 0:
							continue
						class_id = int(np.argmax(scores))
						class_score = float(scores[class_id])
						try:
							obj_conf = float(detection[4])
						except Exception:
							obj_conf = 1.0
						combined = obj_conf * class_score
						confidence = max(class_score, combined)
						if confidence > fire_confidence_threshold:
							cx = int(detection[0] * width)
							cy = int(detection[1] * height)
							w_box = int(detection[2] * width)
							h_box = int(detection[3] * height)
							x = int(cx - w_box / 2)
							y = int(cy - h_box / 2)
							boxes.append([x, y, w_box, h_box])
							confidences.append(confidence)
							class_ids.append(class_id)
							# label and color mapping
							label = fire_classes[class_id] if class_id < len(fire_classes) else f"ID:{class_id}"
							labels.append(label)
							if 'person' in label.lower():
								colors.append((0,255,0))   # green for person
							elif 'fire' in label.lower():
								colors.append((0,0,255))   # red for fire
								dashboard_state['fire_status'] = 'FIRE DETECTED!'
							else:
								colors.append((0,140,255)) # orange for others

				# NMS and store final detections to redraw on skipped frames
				last_boxes = []
				last_class_ids = []
				last_confidences = []
				last_labels = []
				last_colors = []
				if boxes:
					try:
						idxs = cv2.dnn.NMSBoxes(boxes, confidences, fire_confidence_threshold, 0.4)
					except Exception:
						idxs = []
					idx_list = idxs.flatten().tolist() if hasattr(idxs, 'flatten') and len(idxs) > 0 else (list(idxs) if isinstance(idxs, (list,tuple)) else [])
					for i in idx_list:
						try:
							ii = int(i)
							last_boxes.append(boxes[ii])
							last_class_ids.append(class_ids[ii])
							last_confidences.append(confidences[ii])
							last_labels.append(labels[ii])
							last_colors.append(colors[ii])
						except Exception:
							continue

				# Update shared detection summary and create logs for NEW detection changes (rate-limited)
				try:
					now = time.time()
					with detection_lock:
						# snapshot previous summary for comparison / rate-limit check
						prev_labels = list(last_detection_summary.get('labels', []))
						prev_timestamp = float(last_detection_summary.get('timestamp', 0) or 0)

						new_labels = list(last_labels)  # labels observed by this inference

						# expose a human-friendly short summary for acknowledgement UI
						if new_labels:
							dashboard_state['last_detected'] = ', '.join(new_labels[:4])
						else:
							dashboard_state['last_detected'] = ''

						# ALWAYS update fire timestamp when any 'fire' label is present
						if any('fire' in l.lower() for l in new_labels):
							# update global timestamp so simulate_temperature_variation sees it
							last_fire_detection_time = now
							# immediate temperature nudge so UI reacts quickly; further ramping handled by background simulator
							try:
								curr = float(dashboard_state.get('current_temperature', 34.6) or 34.6)
								target_now = dashboard_state['threshold'] + fire_temp_increase
								dashboard_state['current_temperature'] = max(curr, min(target_now, curr + random.uniform(3.0, 8.0)))
							except Exception:
								pass

						# Rate-limited logging when label set actually changed (compare to previous snapshot)
						prev_set = set(prev_labels)
						new_set = set(new_labels)
						if new_set and new_set != prev_set and (now - prev_timestamp > _detection_log_min_interval):
							for i, lbl in enumerate(new_labels):
								conf = last_confidences[i] if i < len(last_confidences) else 0.0
								add_log_entry(f"Camera detection: {lbl} (conf={conf:.2f})")
							# keep the UI alert/logging behavior
							if any('fire' in l.lower() for l in new_labels):
								dashboard_state['fire_status'] = 'FIRE DETECTED!'
								add_log_entry('?? FIRE ALERT: Camera detected fire!')

						# Now update the shared detection summary (after checks/logging)
						last_detection_summary['labels'] = new_labels
						last_detection_summary['timestamp'] = now
				except Exception:
					# don't break the stream on logging/errors
					pass

			# Re-draw last detections (fresh or from previous inference)
			for i in range(len(last_boxes)):
				try:
					x, y, w_box, h_box = last_boxes[i]
					label = last_labels[i] if i < len(last_labels) else (fire_classes[last_class_ids[i]] if last_class_ids and last_class_ids[i] < len(fire_classes) else f"ID:{last_class_ids[i] if last_class_ids else '?'}")
					conf = last_confidences[i] if i < len(last_confidences) else 0.0
					color = last_colors[i] if i < len(last_colors) else (0,140,255)
					thickness = 4 if (('fire' in label.lower()) or ('person' not in label.lower() and 'fire' in label.lower())) else 2
					cv2.rectangle(frame, (x, y), (x + w_box, y + h_box), color, thickness)
					cv2.putText(frame, f"{label} {conf:.2f}", (max(5, x), max(20, y-6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
				except Exception:
					continue
		except Exception:
			# Don't break streaming on any model error; log and continue
			pass

		# Encode as JPEG (slightly lower quality for less bandwidth/latency)
		encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
		ret2, jpeg = cv2.imencode('.jpg', frame, encode_params)
		if not ret2:
			# skip this frame if JPEG encoding failed
			continue
		frame_bytes = jpeg.tobytes()
		yield (b'--frame\r\n'
			   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
		# small sleep to avoid pegging CPU while allowing ~30fps
		time.sleep(0.02)

# New route: MJPEG stream of webcam (session-protected)
@app.route('/video_feed')
def video_feed():
    if not session.get('user'):
        return jsonify({'error':'Authentication required'}), 401
    return Response(stream_with_context(generate_mjpeg()), mimetype='multipart/x-mixed-replace; boundary=frame')

# API to toggle fire overlay on the video feed
@app.route('/api/toggle_fire_model', methods=['POST'])
def api_toggle_fire_model():
    if not session.get('user'):
        return jsonify({'error':'Authentication required'}), 401
    global fire_model_enabled, fire_model_loaded
    fire_model_enabled = not fire_model_enabled
    message = ''
    if fire_model_enabled:
        # Try to load model if not already loaded
        if not fire_model_loaded:
            ok = load_fire_model()
            if ok:
                message = 'Fire overlay enabled (model loaded)'
            else:
                message = 'Fire overlay requested but model failed to load'
                # Keep flag true to allow retry later, but mark not loaded
                fire_model_loaded = False
        else:
            message = 'Fire overlay enabled'
    else:
        message = 'Fire overlay disabled'
    add_log_entry(f"UI: {message}")
    return jsonify({'success': True, 'fire_model_enabled': fire_model_enabled, 'message': message, 'model_loaded': fire_model_loaded})

# API to get current fire-model status
@app.route('/api/fire_model_status')
def api_fire_model_status():
    if not session.get('user'):
        return jsonify({'error':'Authentication required'}), 401
    return jsonify({'fire_model_enabled': fire_model_enabled})

# API to toggle camera feed on/off
@app.route('/api/toggle_camera_feed', methods=['POST'])
def api_toggle_camera_feed():
	"""Toggle camera feed on/off. When enabling, open capture immediately for fast availability."""
	if not session.get('user'):
		return jsonify({'error':'Authentication required'}), 401
	global camera_enabled, video_capture
	camera_enabled = not camera_enabled

	stream_ready = False
	if camera_enabled:
		# Attempt to initialize/open the capture immediately so stream becomes available
		with video_lock:
			try:
				# Release any stale capture first
				if video_capture is not None:
					try:
						video_capture.release()
					except:
						pass
					video_capture = None

				# Use the robust opener that tries multiple backends and warms up the camera
				video_capture = open_capture_with_backends(0, warmup_reads=3)
				# if capture opened, ensure properties
				if video_capture is not None and video_capture.isOpened():
					try:
						video_capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
						video_capture.set(cv2.CAP_PROP_FPS, 30)
						video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
						video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
					except:
						pass
					# quick prime read
					try:
						ret, _ = video_capture.read()
						if ret:
							stream_ready = True
						else:
							stream_ready = bool(video_capture.isOpened())
					except:
						stream_ready = bool(video_capture.isOpened())
				else:
					stream_ready = False
			except Exception:
				stream_ready = False
	else:
		# disable: release capture immediately
		with video_lock:
			try:
				if video_capture is not None:
					try:
						video_capture.release()
					except:
						pass
				video_capture = None
			except:
				pass
		stream_ready = False

	# Update dashboard system status for camera
	dashboard_state['system_status']['camera'] = 'Online' if camera_enabled else 'Offline'

	message = 'Camera feed enabled' if camera_enabled else 'Camera feed disabled'
	add_log_entry(f"UI: {message} (ready={stream_ready})")
	return jsonify({'success': True, 'camera_enabled': camera_enabled, 'stream_ready': stream_ready, 'message': message})


#-----REFRESH RGB AND THERMAL CAMERA-----

@app.route("/api/restart_cameras", methods=["POST"])
def restart_cameras():
    if not session.get('user'):
        return jsonify({'error': 'Authentication required'}), 401

    try:
        subprocess.run(
            ["sudo", "/usr/bin/systemctl", "restart", "detection.service", "thermal.service"],
            capture_output=True,
            text=True,
            timeout=25,
            check=True
        )

        detection_check = subprocess.run(
            ["sudo", "/usr/bin/systemctl", "is-active", "detection.service"],
            capture_output=True,
            text=True,
            timeout=10
        )

        thermal_check = subprocess.run(
            ["sudo", "/usr/bin/systemctl", "is-active", "thermal.service"],
            capture_output=True,
            text=True,
            timeout=10
        )

        detection_status = detection_check.stdout.strip()
        thermal_status = thermal_check.stdout.strip()

        dashboard_state['system_status']['camera'] = 'Online' if detection_status == 'active' else 'Offline'
        dashboard_state['system_status']['thermal'] = 'Online' if thermal_status == 'active' else 'Offline'

        add_log_entry(f"Camera services restarted: detection={detection_status}, thermal={thermal_status}")

        return jsonify({
            "status": "success",
            "message": "Both cameras restarted successfully.",
            "detection_status": detection_status,
            "thermal_status": thermal_status
        })

    except subprocess.CalledProcessError as e:
        add_log_entry(f"Camera restart failed: {e.stderr.strip() if e.stderr else str(e)}")
        return jsonify({
            "status": "error",
            "message": e.stderr.strip() if e.stderr else str(e)
        }), 500

    except subprocess.TimeoutExpired:
        add_log_entry("Camera restart failed: timeout")
        return jsonify({
            "status": "error",
            "message": "Restart timed out."
        }), 500

    except Exception as e:
        add_log_entry(f"Camera restart exception: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

#--------CONFIGURATION------
@app.route("/api/get_thresholds")
def get_thresholds():

    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE,"r") as f:
                cfg=json.load(f)
        else:
            cfg={
                "level1_max":35,
                "level3_min":50
            }

    except:
        cfg={
            "level1_max":35,
            "level3_min":50
        }

    return jsonify(cfg)


@app.route("/api/save_thresholds", methods=["POST"])
def save_thresholds():
    if not session.get('user'):
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.json or {}

        level1 = int(data.get("level1_max", 35))
        level3 = int(data.get("level3_min", 50))

        cfg = {
            "level1_max": level1,
            "level3_min": level3
        }

        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f)

        add_log_entry(f"Threshold updated: L1={level1} L3={level3}")

        subprocess.run(
            ["sudo", "/usr/bin/systemctl", "restart", "detection.service", "thermal.service"],
            capture_output=True,
            text=True,
            timeout=25,
            check=True
        )

        detection_check = subprocess.run(
            ["sudo", "/usr/bin/systemctl", "is-active", "detection.service"],
            capture_output=True,
            text=True,
            timeout=10
        )

        thermal_check = subprocess.run(
            ["sudo", "/usr/bin/systemctl", "is-active", "thermal.service"],
            capture_output=True,
            text=True,
            timeout=10
        )

        detection_status = detection_check.stdout.strip()
        thermal_status = thermal_check.stdout.strip()

        dashboard_state['system_status']['camera'] = 'Online' if detection_status == 'active' else 'Offline'
        dashboard_state['system_status']['thermal'] = 'Online' if thermal_status == 'active' else 'Offline'

        add_log_entry(f"Threshold applied and cameras restarted: detection={detection_status}, thermal={thermal_status}")

        return jsonify({
            "status": "saved",
            "message": "Threshold saved and both cameras restarted.",
            "detection_status": detection_status,
            "thermal_status": thermal_status
        })

    except subprocess.CalledProcessError as e:
        add_log_entry(f"Threshold saved but restart failed: {e.stderr.strip() if e.stderr else str(e)}")
        return jsonify({
            "status": "error",
            "message": e.stderr.strip() if e.stderr else "Threshold saved, but restart failed."
        }), 500

    except Exception as e:
        add_log_entry(f"Save thresholds error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# --- NEW: form-action to toggle camera via POST (used by dashboard form) ---
@app.route('/action/toggle_camera', methods=['POST'])
def action_toggle_camera():
	"""Toggle camera feed on/off via form (redirect back to dashboard)."""
	if not session.get('user'):
		flash('Authentication required', 'error')
		return redirect(url_for('index'))

	global camera_enabled, video_capture
	camera_enabled = not camera_enabled
	stream_ready = False

	if camera_enabled:
		# Try to open capture immediately for a responsive UI
		with video_lock:
			try:
				# Release any stale capture first
				if video_capture is not None:
					try:
						video_capture.release()
					except:
						pass
					video_capture = None

				# Use the robust opener that tries multiple backends and warms up the camera
				video_capture = open_capture_with_backends(0, warmup_reads=3)
				if video_capture is not None and video_capture.isOpened():
					try:
						video_capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
						video_capture.set(cv2.CAP_PROP_FPS, 30)
						video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
						video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
					except:
						pass
					# quick prime read
					try:
						ret, _ = video_capture.read()
						if ret:
							stream_ready = True
						else:
							stream_ready = bool(video_capture.isOpened())
					except:
						stream_ready = bool(video_capture.isOpened())
				else:
					stream_ready = False
			except Exception:
				stream_ready = False
	else:
		# disable: release capture immediately
		with video_lock:
			try:
				if video_capture is not None:
					try:
						video_capture.release()
					except:
						pass
				video_capture = None
			except:
				pass
		stream_ready = False

	# Update dashboard system status for camera
	dashboard_state['system_status']['camera'] = 'Online' if camera_enabled else 'Offline'

	message = 'Camera feed enabled' if camera_enabled else 'Camera feed disabled'
	add_log_entry(f"User: {message} (ready={stream_ready})")
	flash(message, 'success')
	return redirect(url_for('index'))

# --- NEW: form-action to toggle night vision via POST (used by dashboard form) ---
@app.route('/action/toggle_night_vision', methods=['POST'])
def action_toggle_night_vision():
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))

    global video_capture
    # Toggle the night vision setting
    dashboard_state['night_vision'] = not dashboard_state['night_vision']

    # Update the fire model if it was enabled (re-load to apply to next stream)
    if fire_model_enabled:
        load_fire_model()

    message = 'Night vision enabled' if dashboard_state['night_vision'] else 'Night vision disabled'
    add_log_entry(f"User: {message}")
    flash(message, 'success')
    return redirect(url_for('index'))

# --- NEW: form-action to start/stop recording via POST (used by dashboard form) ---
@app.route('/action/toggle_recording', methods=['POST'])
def action_toggle_recording():
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))

    global recording_flag, recording_thread, recording_filename
    # Toggle UI state
    recording_flag = not recording_flag
    dashboard_state['is_recording'] = recording_flag
    dashboard_state['system_status']['edge'] = 'Recording' if recording_flag else 'Running'

    if recording_flag:
        # start recording thread
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(recordings_dir, f"recording_{ts}.mp4")
        recording_filename = filename
        try:
            t = threading.Thread(target=_recording_loop, args=(filename, (lambda: not recording_flag)), daemon=True)
            recording_thread = t
            t.start()
            add_log_entry(f'User started recording: {os.path.basename(filename)}')
            flash(f'Recording started: {os.path.basename(filename)}', 'success')
        except Exception as e:
            add_log_entry(f'Recording start error: {e}')
            recording_flag = False
            dashboard_state['is_recording'] = False
            flash('Failed to start recording', 'error')
    else:
        # stop: the recording thread checks recording_flag via stop lambda and will exit
        add_log_entry('User stopped recording')
        flash('Recording stopped', 'success')

    return redirect(url_for('index'))

# --- NEW: form-action to take a snapshot via POST (used by dashboard form) ---
@app.route('/action/snapshot', methods=['POST'])
def action_snapshot():
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    fname = os.path.join(snapshots_dir, f"snapshot_{ts}.jpg")
    cap = None
    try:
        cap = get_video_capture()
        if cap is None or not getattr(cap, "isOpened", lambda: False)():
            # try a short-lived capture
            cap = open_capture_with_backends(0, warmup_reads=2)
        if cap is None or not getattr(cap, "isOpened", lambda: False)():
            add_log_entry('Snapshot failed: camera unavailable')
            flash('Snapshot failed: camera unavailable', 'error')
            return redirect(url_for('index'))

        ret, frame = cap.read()
        if not ret or frame is None:
            add_log_entry('Snapshot failed: no frame')
            flash('Snapshot failed: no frame', 'error')
            return redirect(url_for('index'))

        # mirror to match stream
        frame = cv2.flip(frame, 1)
        cv2.imwrite(fname, frame)
        add_log_entry(f'User snapshot saved: {os.path.basename(fname)}')
        flash(f'Snapshot saved: {os.path.basename(fname)}', 'success')
    except Exception as e:
        add_log_entry(f'Snapshot error: {e}')
        flash('Snapshot error', 'error')
    finally:
        # do NOT release global capture here; open_capture_with_backends returns a new temporary cap which we should release
        try:
            if cap is not None and cap is not get_video_capture():
                try:
                    cap.release()
                except:
                    pass
        except Exception:
            pass

    return redirect(url_for('index'))

# --- NEW: clear log (form) ---
@app.route('/action/clear_log', methods=['POST'])
def action_clear_log():
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))
    dashboard_state['log_entries'] = []
    add_log_entry('User cleared the log')
    flash('Log cleared', 'success')
    return redirect(url_for('index'))

# --- NEW: export log (API returns downloadable text) ---
@app.route('/api/export_log')
def api_export_log():
    if not session.get('user'):
        return jsonify({'error': 'Authentication required'}), 401
    try:
        content = "\n".join(reversed(dashboard_state.get('log_entries', [])))  # oldest first
        resp = make_response(content)
        resp.headers['Content-Type'] = 'text/plain; charset=utf-8'
        resp.headers['Content-Disposition'] = 'attachment; filename=pyrosense_log.txt'
        return resp
    except Exception as e:
        add_log_entry(f'Export log error: {e}')
        return jsonify({'error': 'Export failed'}), 500

# --- NEW: simulate alert (form) ---
@app.route('/action/simulate_alert', methods=['POST'])
def action_simulate_alert():
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))
    dashboard_state['manual_alert'] = 'TEST ALERT: Manual simulation'
    dashboard_state['alerts_active'] = True
    register_fire_event('manual simulation')
    add_log_entry('User triggered test alert')
    flash('Test alert triggered', 'success')
    return redirect(url_for('index'))

# --- NEW: acknowledge alert (form) ---
@app.route('/action/acknowledge_alert', methods=['POST'])
def action_acknowledge_alert():
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))
    dashboard_state['manual_alert'] = None
    dashboard_state['fire_status'] = 'No fire detected'
    dashboard_state['last_live_status'] = 'NORMAL'
    add_log_entry('User acknowledged alert')
    flash('Alert acknowledged', 'notice')
    return redirect(url_for('index'))

# --- NEW: mute alerts for 5 minutes (form) ---
@app.route('/action/mute_alerts', methods=['POST'])
def action_mute_alerts():
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))
    try:
        dashboard_state['alerts_active'] = False
        add_log_entry('User muted alerts for 5 minutes')
        flash('Alerts muted for 5 minutes', 'success')
        # schedule unmute after 5 minutes
        def _unmute():
            dashboard_state['alerts_active'] = True
            add_log_entry('Alerts auto-unmuted after 5 minutes')
        t = threading.Timer(300.0, _unmute)
        t.daemon = True
        t.start()
    except Exception as e:
        add_log_entry(f'Mute alerts error: {e}')
        flash('Failed to mute alerts', 'error')
    return redirect(url_for('index'))

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PyroSense Dashboard - Python Edition</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/dashboard.css') }}">
  <style>
    .status-indicator {
      display: inline-block;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      margin-right: 8px;
    }
    .status-indicator.green {
      background-color: #28a745;
    }
    .status-indicator.red {
      background-color: #dc3545;
    }
    .status-indicator.blue {
      background-color: #007bff;
    }
        .thermal-feed {
            width: 100%;
            height: 260px;
            border-radius: 16px;
            background: linear-gradient(135deg, #151515, #242424);
            border: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #c9c9c9;
            font-weight: 600;
            letter-spacing: 0.4px;

}


/* =========================
   THERMAL FULLSCREEN FIX
   ========================= */

/* Make the fullscreen backdrop black */
#thermalPlayer::backdrop {
  background: #000;
}

/* Standard fullscreen */
#thermalPlayer:fullscreen {
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100vw;
  height: 100vh;
}

/* Safari fullscreen */
#thermalPlayer:-webkit-full-screen {
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100vw;
  height: 100vh;
}

/* IMPORTANT: target the image INSIDE thermalPlayer */
#thermalPlayer:fullscreen #thermalStream {
  width: 100vw !important;
  height: 100vh !important;
  object-fit: contain !important;  /* change to cover if you want it to fill */
  border-radius: 0 !important;
}

#thermalPlayer:-webkit-full-screen #thermalStream {
  width: 100vw !important;
  height: 100vh !important;
  object-fit: contain !important;
  border-radius: 0 !important;
}

  </style>
  <!-- SweetAlert2 -->
  <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
</head>
<body>
    <svg class="icon-sprite" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false" style="position:absolute;width:0;height:0;overflow:hidden;">
        <symbol id="icon-brand" viewBox="0 0 24 24">
            <path d="M12 3c2.5 2.2 4 4.7 4 7.2 0 2.8-1.9 5.2-4 6.3-2.1-1.1-4-3.5-4-6.3 0-2.5 1.5-5 4-7.2z" />
            <path d="M9 19c1 .9 2.1 1.4 3 1.4s2-.5 3-1.4" />
        </symbol>
        <symbol id="icon-logout" viewBox="0 0 24 24">
            <rect x="3" y="4" width="9" height="16" rx="2" />
            <line x1="13" y1="12" x2="21" y2="12" />
            <polyline points="18 9 21 12 18 15" />
        </symbol>
        <symbol id="icon-camera" viewBox="0 0 24 24">
            <rect x="3" y="7" width="18" height="12" rx="2" />
            <rect x="7" y="4" width="4" height="3" rx="1" />
            <circle cx="12" cy="13" r="3" />
        </symbol>
        <symbol id="icon-thermal" viewBox="0 0 24 24">
            <rect x="10" y="3" width="4" height="12" rx="2" />
            <circle cx="12" cy="19" r="4" />
            <line x1="12" y1="7" x2="12" y2="15" />
        </symbol>
        <symbol id="icon-log" viewBox="0 0 24 24">
            <rect x="5" y="4" width="14" height="16" rx="2" />
            <line x1="8" y1="8" x2="16" y2="8" />
            <line x1="8" y1="12" x2="16" y2="12" />
            <line x1="8" y1="16" x2="14" y2="16" />
        </symbol>
        <symbol id="icon-alert" viewBox="0 0 24 24">
            <polygon points="12 3 22 19 2 19" />
            <line x1="12" y1="8" x2="12" y2="13" />
            <circle cx="12" cy="16" r="1" />
        </symbol>
        <symbol id="icon-system" viewBox="0 0 24 24">
            <rect x="3" y="5" width="18" height="12" rx="2" />
            <line x1="8" y1="21" x2="16" y2="21" />
            <line x1="12" y1="17" x2="12" y2="21" />
        </symbol>
    </svg>
  <div class="dashboard-overlay">
    <!-- REMOVED: small top title bar -->
    <!-- <div class="dashboard-title">DASHBOARD</div> -->

    <header>
      <div class="header-container">
        <div class="header-left">
          <div class="header-logo"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-brand" /></svg></div>
          <div class="header-title-section">
            <h1 class="header-title">PYROSENSE</h1>
            <p class="header-subtitle" style="font-weight:700;font-size:1rem;opacity:1;">Welcome, {{ username }}!</p>
          </div>
          {% if user_role == 'admin' %}
          <a href="{{ admin_url }}" class="logout-button" style="margin-left:12px;background:linear-gradient(135deg,#7C0000,#3E0000);border:1px solid rgba(255,255,255,0.15);" title="Admin Panel">
            <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a5 5 0 1 1 0 10A5 5 0 0 1 12 2zm0 12c-5.33 0-8 2.67-8 4v2h16v-2c0-1.33-2.67-4-8-4z"/></svg>
            Admin Panel
          </a>
          {% endif %}
        </div>

        <div class="header-center">
          <nav class="main-nav">
            <a href="/" class="nav-link active" id="navDashboard">Dashboard</a>
            <span class="nav-sep" aria-hidden="true"></span>
            <a href="http://192.168.1.110:5001/history" class="nav-link" id="navHistory">History</a>
          </nav>
        </div>

        <div class="header-right">
          <span class="badge system-badge">System Online</span>
          <!-- REMOVED: history button from right side -->
          <!-- <a href="http://192.168.1.110:5001/history" class="history-button">?? HISTORY</a> -->
          
       <a href="/logout" class="logout-button" id="logoutBtn">
<svg class="icon" viewBox="0 0 24 24">
<use href="#icon-logout" />
</svg>
LOGOUT
</a>

<button id="reloadCamBtn" class="logout-button">
<svg class="icon" viewBox="0 0 24 24">
<path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6a6 6 0 01-6 6 6 6 0 01-5.65-4H4.26A8 8 0 0012 20a8 8 0 000-16z"/>
</svg>
Reload
</button>

<button id="settingsBtn" class="logout-button">
<svg class="icon" viewBox="0 0 24 24">
<path d="M12 8a4 4 0 100 8 4 4 0 000-8zm9 4a7.8 7.8 0 00-.2-1.7l2.1-1.6-2-3.4-2.5 1a8 8 0 00-1.5-.9l-.4-2.6h-4l-.4 2.6a8 8 0 00-1.5.9l-2.5-1-2 3.4 2.1 1.6A7.8 7.8 0 003 12c0 .6.1 1.2.2 1.7l-2.1 1.6 2 3.4 2.5-1c.5.4 1 .7 1.5.9l.4 2.6h4l.4-2.6c.5-.2 1-.5 1.5-.9l2.5 1 2-3.4-2.1-1.6c.1-.5.2-1.1.2-1.7z"/>
</svg>
</button>
    
        </div>
      </div>
    </header>

    <main>
      <!-- Live Camera Feed -->
      <div class="card">
        <div class="card-header">
          <div class="card-icon"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-camera" /></svg></div>
          <h2 class="card-title">Live Camera Feed</h2>
        </div>
        <div class="card-content">
          <!-- Replaced static box with live MJPEG stream + controls -->
          <div class="video-player" id="videoPlayer">
            <div class="video-topbar">
            </div>
            <img id="cameraStream"
     class="stream"
     src="http://192.168.1.110:8060/fire_stream"
     alt="RGB Fire Stream">
            <div class="video-controls">
              <!-- Removed Toggle Fire button and Minimize button per request -->
                            <button class="video-control-btn" id="fullscreenBtn" onclick="toggleFullscreen()" aria-label="Fullscreen">
                                <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
                                    <path d="M4 9V4h5" />
                                    <path d="M20 9V4h-5" />
                                    <path d="M4 15v5h5" />
                                    <path d="M20 15v5h-5" />
                                </svg>
                            </button>
                            <button class="video-control-btn" id="exitFullscreenBtn" onclick="exitFullscreen()" style="display:none;" aria-label="Exit Fullscreen">
                                <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
                                    <path d="M9 4H4v5" />
                                    <path d="M15 4h5v5" />
                                    <path d="M9 20H4v-5" />
                                    <path d="M15 20h5v-5" />
                                </svg>
                            </button>
            </div>
          </div>

                

          <div class="button-group">
            <!-- NEW: Camera toggle button placed left of Start Recording -->
            <form action="/action/toggle_camera" method="POST" style="display:inline;">
                           
            </form>

            <form action="/action/toggle_recording" method="POST" style="display:inline;">
              
            </form>
            <form action="/action/snapshot" method="POST" style="display:inline;">
              
            </form>
          </div>
        </div>
      </div>
      
      <!-- Thermal Reading -->
      <div class="card">
        <div class="card-header">
          <div class="card-icon"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-thermal" /></svg></div>
          <h2 class="card-title">Thermal Reading</h2>
        </div>
        <div class="card-content">
                    <div class="video-player" id="thermalPlayer">
                        <div class="video-topbar">
                        </div>
                        <img id="thermalStream"

     class="stream"
     src="http://192.168.1.110:8055/thermal_stream.mjpg"
     alt="Thermal Stream"
     style="width:100%; height:360px; object-fit:cover;">
                        <div class="video-controls">
                            <button class="video-control-btn" id="thermalFullscreenBtn" onclick="toggleThermalFullscreen()" aria-label="Fullscreen">
                                <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
                                    <path d="M4 9V4h5" />
                                    <path d="M20 9V4h-5" />
                                    <path d="M4 15v5h5" />
                                    <path d="M20 15v5h-5" />
                                </svg>
                            </button>
                            <button class="video-control-btn" id="thermalExitFullscreenBtn" onclick="exitFullscreen()" style="display:none;" aria-label="Exit Fullscreen">
                                <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
                                    <path d="M9 4H4v5" />
                                    <path d="M15 4h5v5" />
                                    <path d="M9 20H4v-5" />
                                    <path d="M15 20h5v-5" />
                                </svg>
                            </button>
                        </div>
                    </div>

                   <div id="thermalTemps" style="margin-top:8px; font-size:24px; display:flex; justify-content:center; gap:18px;">
  <div>MAX: <span id="thermalMax">--</span>&deg;C</div>
  <div>MIN: <span id="thermalMin">--</span>&deg;C</div>
</div>

                    <div class="status-line" style="margin-top:16px; text-align:center;">
                        <span class="status-label"></span>
                                            </div>



                    
          <div class="button-group">
            <!-- Calibrate now POSTS to server to set baseline -->
            <form action="/action/calibrate_sensor" method="POST" style="display:inline;">
              
            </form>
            <!-- Reset threshold to default -->
            <form action="/action/reset_threshold" method="POST" style="display:inline;">
             
            </form>
          </div>
        </div>
      </div>
      
    </main>
    
    <footer>
      PyroSense 2025 Ã‚Â© All rights reserved - Python Flask Edition
    </footer>
  </div>

  <!-- Tiny script: poll status to update temperature and slider -->
  <script>

let lastSeenFireEventId = 0;

    async function refreshStatus(){
      try {
        const res = await fetch('/api/status');
        if(!res.ok) return;
        const j = await res.json();

        const temp = (Math.round((j.temperature || 0) * 10) / 10).toFixed(1);

const currentTempEl = document.getElementById('currentTemp');
if (currentTempEl) {
    currentTempEl.innerHTML = '+' + temp + '&deg;C';
}

const slider = document.getElementById('tempSlider');
if (slider) {
    slider.value = Math.max(parseFloat(slider.min), Math.min(parseFloat(slider.max), j.temperature));
}

const thresholdEl = document.getElementById('thresholdValue');
if (thresholdEl && typeof j.threshold !== 'undefined') {
    thresholdEl.innerHTML = j.threshold + '&deg;C';
    const dial = document.querySelector('.threshold-dial');
    if (dial) {
        dial.style.setProperty('--threshold', j.threshold);
    }
}

const statusText = j.fire_status || '';
const lower = statusText.toLowerCase();
const isFire = lower.includes('fire detected') || lower.includes('alert: fire');
const fireEventId = Number(j.fire_event_id || 0);

const fireEl = document.getElementById('fireStatus');
if (fireEl) {
    fireEl.textContent = statusText;
    fireEl.classList.toggle('alert', isFire);
    fireEl.classList.toggle('ok', !isFire);
}

if (fireEventId > lastSeenFireEventId) {
    lastSeenFireEventId = fireEventId;

    Swal.fire({
        icon: 'warning',
        title: 'Fire Detected!',
        text: 'PyroSense detected a possible fire event. Please check immediately.',
        confirmButtonColor: '#ff3c00',
        background: '#161616',
        color: '#ffffff'
    });
}

      } catch(e) {
        // silent
      }
    }
    setInterval(refreshStatus, 2000);
    window.addEventListener('load', refreshStatus);

        // Preserve scroll position across reloads and form submits
        (function(){
            const key = 'pyrosense_scroll_y';
            const saved = sessionStorage.getItem(key);
            if (saved !== null) {
                window.scrollTo(0, parseInt(saved, 10));
                sessionStorage.removeItem(key);
            }
            window.addEventListener('beforeunload', () => {
                sessionStorage.setItem(key, String(window.scrollY || 0));
            });
            document.querySelectorAll('form').forEach(form => {
                form.addEventListener('submit', () => {
                    sessionStorage.setItem(key, String(window.scrollY || 0));
                });
            });
        })();

    // Show server-side flashed messages using SweetAlert2
    (function(){
      const msgs = [
        {% for category, msg in get_flashed_messages(with_categories=true) %}
          {cat: "{{ category }}", text: "{{ msg|escape }}"},
        {% endfor %}
      ];
      if(msgs.length){
        msgs.forEach(m => {
          // map categories to icons
          let icon = 'info';
          if(m.cat === 'success') icon = 'success';
          else if(m.cat === 'error') icon = 'error';
          else if(m.cat === 'notice' || m.cat === 'warning') icon = 'warning';
          Swal.fire({title: m.text, icon: icon, timer: 3000, toast: true, position: 'top-end', showConfirmButton: false});
        });
      }
    })();

   
    // Handle fullscreen button (if needed)
    function toggleFullscreen() {
            const panel = document.getElementById('videoPlayer');
            if (panel) {
        if (document.fullscreenElement) {
          document.exitFullscreen();
        } else {
                    panel.requestFullscreen().catch(err => {
            console.log('Fullscreen error:', err);
          });
        }
      }
    }

        function exitFullscreen() {
            if (document.fullscreenElement) {
                document.exitFullscreen();
            }
        }

        function toggleThermalFullscreen() {
    const thermal = document.getElementById("thermalPlayer");

    if (!document.fullscreenElement) {
        if (thermal.requestFullscreen) {
            thermal.requestFullscreen();
        } else if (thermal.webkitRequestFullscreen) {
            thermal.webkitRequestFullscreen();
        } else if (thermal.msRequestFullscreen) {
            thermal.msRequestFullscreen();
        }
    } else {
        document.exitFullscreen();
    }
}
        function updateFullscreenButtons() {
            const fsEl = document.fullscreenElement;
            const liveExit = document.getElementById('exitFullscreenBtn');
            const thermalExit = document.getElementById('thermalExitFullscreenBtn');
            const liveFs = document.getElementById('fullscreenBtn');
            const thermalFs = document.getElementById('thermalFullscreenBtn');
            const liveTarget = document.getElementById('videoPlayer');
            const thermalTarget = document.getElementById('thermalPlayer');

            if (liveExit && liveFs) {
                const isLive = fsEl === liveTarget;
                liveExit.style.display = isLive ? 'inline-flex' : 'none';
                liveFs.style.display = isLive ? 'none' : 'inline-flex';
            }
            if (thermalExit && thermalFs) {
                const isThermal = fsEl === thermalTarget;
                thermalExit.style.display = isThermal ? 'inline-flex' : 'none';
                thermalFs.style.display = isThermal ? 'none' : 'inline-flex';
            }
        }

        document.addEventListener('fullscreenchange', updateFullscreenButtons);
        window.addEventListener('load', updateFullscreenButtons);

    // Handle restart system button (if needed)
    function restartSystem() {
      Swal.fire({
        title: 'Restart System?',
        text: 'This will restart the PyroSense system.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Yes, restart',
        cancelButtonText: 'Cancel'
      }).then((result) => {
        if (result.isConfirmed) {
          Swal.fire('Restarting...', 'System restart initiated', 'info');
        }
      });
    }

document.getElementById("settingsBtn").addEventListener("click", function(){

document.getElementById("settingsModal").style.display="flex"

loadThresholds()

})

function closeSettings(){

document.getElementById("settingsModal").style.display="none"

}

async function saveThresholds() {
  const l1 = document.getElementById("level1").value;
  const l3 = document.getElementById("level3").value;

  try {
    const res = await fetch("/api/save_thresholds", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        level1_max: l1,
        level3_min: l3
      })
    });

    const data = await res.json();

    if (res.ok && (data.status === "saved" || data.status === "success")) {
      Swal.fire({
        icon: "success",
        title: "Threshold Updated",
        text: "Settings saved and both cameras restarted.",
        timer: 1800,
        showConfirmButton: false
      });

      const rgb = document.getElementById("cameraStream");
      const thermal = document.getElementById("thermalStream");
      const ts = new Date().getTime();

      if (rgb) rgb.src = `http://192.168.1.110:8060/fire_stream?t=${ts}`;
      if (thermal) thermal.src = `http://192.168.1.110:8055/thermal_stream.mjpg?t=${ts}`;

      closeSettings();
    } else {
      Swal.fire({
        icon: "error",
        title: "Save Failed",
        text: data.message || "Could not save settings."
      });
    }
  } catch (err) {
    Swal.fire({
      icon: "error",
      title: "Request Failed",
      text: err.message || "Something went wrong."
    });
  }
}

async function loadThresholds(){

const res=await fetch("/api/get_thresholds")
const data=await res.json()

document.getElementById("level1").value=data.level1_max
document.getElementById("level3").value=data.level3_min

}

document.getElementById("reloadCamBtn").addEventListener("click", async () => {
  const btn = document.getElementById("reloadCamBtn");
  btn.disabled = true;

  try {
    const res = await fetch("/api/restart_cameras", {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });

    const data = await res.json();

    if (res.ok && data.status === "success") {
      Swal.fire({
        icon: "success",
        title: "Cameras Reloaded",
        text: `RGB: ${data.detection_status} | Thermal: ${data.thermal_status}`,
        timer: 1800,
        showConfirmButton: false
      });

      const rgb = document.getElementById("cameraStream");
      const thermal = document.getElementById("thermalStream");
      const ts = new Date().getTime();

      if (rgb) rgb.src = `http://192.168.1.110:8060/fire_stream?t=${ts}`;
      if (thermal) thermal.src = `http://192.168.1.110:8055/thermal_stream.mjpg?t=${ts}`;
    } else {
      Swal.fire({
        icon: "error",
        title: "Reload Failed",
        text: data.message || "Could not restart cameras."
      });
    }
  } catch (err) {
    Swal.fire({
      icon: "error",
      title: "Request Failed",
      text: err.message || "Could not contact server."
    });
  } finally {
    btn.disabled = false;
  }
});

const THERMAL_API_URL = "http://192.168.1.110:8055/api/temperature";

async function updateThermalMinMax() {
  try {
    const res = await fetch(THERMAL_API_URL, { cache: "no-store" });
    const data = await res.json();

    document.getElementById("thermalMax").textContent =
      (data.max_temp ?? 0).toFixed(1);

    document.getElementById("thermalMin").textContent =
      (data.min_temp ?? 0).toFixed(1);

  } catch (err) {
    // optional: keep last value
  }
}

setInterval(updateThermalMinMax, 500); // every 0.5s
updateThermalMinMax();


document.addEventListener("DOMContentLoaded", () => {
  const host = window.location.hostname; // ex: 192.168.1.110
  const THERMAL_API_URL = `http://${host}:8055/api/temperature`;

  async function updateThermalMinMax() {
    try {
      const res = await fetch(THERMAL_API_URL, { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);

      const data = await res.json();

      const maxEl = document.getElementById("thermalMax");
      const minEl = document.getElementById("thermalMin");

      if (!maxEl || !minEl) return;

      maxEl.textContent = Number(data.max_temp).toFixed(1);
      minEl.textContent = Number(data.min_temp).toFixed(1);

    } catch (err) {
      // For debugging, uncomment:
      // console.log("Thermal fetch failed:", err);
    }
  }

  updateThermalMinMax();
  setInterval(updateThermalMinMax, 500);
});

document.getElementById("logoutBtn").addEventListener("click", function(e){

e.preventDefault()

Swal.fire({
title: "Logout?",
text: "Are you sure you want to logout?",
icon: "warning",
showCancelButton: true,
confirmButtonColor: "#ff3c00",
cancelButtonColor: "#6c757d",
confirmButtonText: "Yes, Logout",
cancelButtonText: "Cancel"
}).then((result) => {

if(result.isConfirmed){

window.location.href="/logout"

}

})

})




  </script>

<!-- SETTINGS MODAL -->
<div id="settingsModal" style="
display:none;
position:fixed;
top:0;
left:0;
width:100%;
height:100%;
background:rgba(0,0,0,0.55);
backdrop-filter: blur(6px);
z-index:9999;
align-items:center;
justify-content:center;
font-family: 'Segoe UI', sans-serif;
">

<div style="
background: linear-gradient(145deg,#0f0f0f,#1b1b1b);
border-radius:20px;
width:420px;
padding:30px;
border:1px solid rgba(255,255,255,0.06);
box-shadow:0 20px 60px rgba(0,0,0,0.85);
color:#e8e8e8;
font-family:Segoe UI, sans-serif;
">

<h2 style="
margin-bottom:6px;
font-weight:600;
font-size:20px;
color:white;
display:flex;
align-items:center;
gap:8px;
">
 Fire Threshold Settings
</h2>

<p style="
font-size:13px;
color:#9ca3af;
margin-bottom:22px;
">
Configure temperature thresholds used for fire detection.
</p>


<label style="font-size:13px;color:#cfcfcf;">Level 1 Max Temperature</label>

<div style="position:relative;margin-top:6px;margin-bottom:18px;">
<input type="number" id="level1" style="
width:100%;
padding:12px;
border-radius:10px;
border:1px solid rgba(255,255,255,0.08);
background:#0d0d0d;
color:white;
font-size:14px;
outline:none;
">
<span style="
position:absolute;
right:12px;
top:50%;
transform:translateY(-50%);
color:#9ca3af;
font-size:12px;
">&deg;C</span>
</div>


<label style="font-size:13px;color:#cfcfcf;">Level 3 Minimum Temperature</label>

<div style="position:relative;margin-top:6px;margin-bottom:20px;">
<input type="number" id="level3" style="
width:100%;
padding:12px;
border-radius:10px;
border:1px solid rgba(255,255,255,0.08);
background:#0d0d0d;
color:white;
font-size:14px;
outline:none;
">
<span style="
position:absolute;
right:12px;
top:50%;
transform:translateY(-50%);
color:#9ca3af;
font-size:12px;
">&deg;C</span>
</div>


<div style="
background:rgba(255,255,255,0.04);
border-radius:14px;
padding:16px;
margin-bottom:24px;
font-size:12px;
line-height:1.7;
">

<b style="color:white;">Detection Logic</b>

<div style="margin-top:8px;display:flex;flex-direction:column;gap:4px;">

<span style="color:#34d399;"> NORMAL</span>
Temperature &lt; Level 1

<span style="color:#fbbf24;"> WARNING</span>
Between Level 1 and Level 3

<span style="color:#ef4444;"> FIRE DETECTED</span>
Temperature = Level 3

</div>

</div>


<div style="
display:flex;
justify-content:flex-end;
gap:12px;
">

<button onclick="closeSettings()" style="
background:#2a2a2a;
color:#d6d6d6;
border:none;
padding:10px 18px;
border-radius:10px;
cursor:pointer;
font-size:13px;
">
Close
</button>

<button onclick="saveThresholds()" style="
background:linear-gradient(135deg,#ff7a00,#ff3c00);
color:white;
border:none;
padding:10px 20px;
border-radius:10px;
cursor:pointer;
font-weight:600;
font-size:13px;
box-shadow:0 8px 20px rgba(255,90,0,0.35);
transition:0.2s;
">
Save Settings
</button>

</div>

</div>
</body>
</html>
"""

# Add the forgot password template
FORGOT_PASSWORD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PyroSense - Forgot Password</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
            background-color: #121212;
            color: #f0f0f0;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .login-container {
            display: flex;
            flex: 1;
            overflow: hidden;
        }
        
        .graphic-section {
            flex: 1;
            background-color: #f2f2e6;
            overflow: hidden;
            position: relative;
        }
        
        .flames-graphic {
            height: 100%;
            width: 100%;
            background: linear-gradient(to bottom right, #f77f00, #d62828, #fcbf49);
            position: relative;
            overflow: hidden;
        }
        
        .flame-shape {
            position: absolute;
            background: #2b2d2f;
            clip-path: polygon(30% 0%, 70% 0%, 100% 30%, 100% 70%, 70% 100%, 30% 100%, 0% 70%, 0% 30%);
        }
        
        .flame-1 {
            width: 300px;
            height: 600px;
            top: -100px;
            left: 50px;
            transform: rotate(45deg);
        }
        
        .flame-2 {
            width: 400px;
            height: 400px;
            bottom: -100px;
            left: -100px;
            transform: rotate(25deg);
        }
        
        .flame-3 {
            width: 200px;
            height: 600px;
            bottom: 50px;
            right: 100px;
            transform: rotate(-15deg);
        }
        
        .login-form-section {
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .login-form {
            width: 100%;
            max-width: 400px;
            padding: 20px;
        }
        
        .login-title {
            font-size: 3rem;
            font-weight: bold;
            margin-bottom: 40px;
            color: #f0f0f0;
        }
        
        .form-group {
            margin-bottom: 25px;
        }
        
        label {
            display: block;
            margin-bottom: 10px;
            font-weight: 500;
        }
        
        input[type="email"] {
            width: 100%;
            padding: 12px;
            border-radius: 5px;
            border: 1px solid #555;
            background-color: #1e1e1e;
            color: #f0f0f0;
            font-size: 16px;
            box-sizing: border-box;
        }
        
        .login-button {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 5px;
            background-color: #f77f00;
            color: white;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        
        .login-button:hover {
            background-color: #d62828;
        }
        
        .login-header {
            position: absolute;
            top: 10px;
            left: 10px;
            font-size: 14px;
            color: #888;
        }
        
        .flash-message {
            padding: 10px 15px;
            margin-bottom: 20px;
            border-radius: 5px;
            background-color: #d62828;
            color: white;
            font-weight: 500;
        }
        
        .success-message {
            padding: 10px 15px;
            margin-bottom: 20px;
            border-radius: 5px;
            background-color: #2e7d32;
            color: white;
            font-weight: 500;
        }
        
        .back-link {
            margin-top: 15px;
            text-align: center;
        }
        
        .back-link a {
            color: #888;
            text-decoration: none;
        }
        
        .back-link a:hover {
            color: #f77f00;
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="login-header">FORGOT PASSWORD</div>
    
    <div class="login-container">
        <div class="graphic-section">
            <div class="flames-graphic">
                <div class="flame-shape flame-1"></div>
                <div class="flame-shape flame-2"></div>
                <div class="flame-shape flame-3"></div>
            </div>
        </div>
        
        <div class="login-form-section">
            <div class="login-form">
                <h1 class="login-title">Pyrosense</h1>
                <p>Enter your admin email to reset your password.</p>
                
                {% if error %}
                <div class="flash-message">{{ error }}</div>
                {% endif %}
                
                {% if success %}
                <div class="success-message">{{ success }}</div>
                {% endif %}
                
                <form action="/forgot-password" method="post">
                    <div class="form-group">
                        <label for="email">Admin Email:</label>
                        <input type="email" id="email" name="email" required>
                    </div>
                    
                    <button type="submit" class="login-button">Reset Password</button>
                </form>
                
                <div class="back-link">
                    <a href="/login">Back to login</a>
                </div>
            </div>
        </div>
    </div>


</div>
</div>

</body>
</html>
"""

# ========== NEW: THERMAL FIRE SIZE DETECTION ==========

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

def detect_thermal_fire_region(frame, temp_threshold=70):
    """Detect thermal fire regions using color-based detection"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    lower_fire = np.array([0, 100, 100])
    upper_fire = np.array([35, 255, 255])
    
    mask = cv2.inRange(hsv, lower_fire, upper_fire)
    
    kernel = np.ones((5,5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    thermal_boxes = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 500:
            x, y, w, h = cv2.boundingRect(contour)
            thermal_boxes.append([x, y, w, h])
    
    return thermal_boxes, mask

def generate_combined_alert(fire_boxes, class_ids, classes, frame_width, frame_height, thermal_boxes=None):
    """Generate combined alert level based on thermal + RGB detection"""
    all_fire_boxes = []
    
    if thermal_boxes:
        all_fire_boxes.extend(thermal_boxes)
    
    for i, class_id in enumerate(class_ids):
        if class_id < len(classes) and 'fire' in classes[class_id].lower():
            all_fire_boxes.append(fire_boxes[i])
    
    fire_size_pct = calculate_fire_size_percentage(all_fire_boxes, frame_width, frame_height)
    
    CLASS_STOVE = 0
    CLASS_CANDLE = 4
    CLASS_PERSON = 3
    CLASS_FIRE = 2
    
    has_stove = CLASS_STOVE in class_ids
    has_candle = CLASS_CANDLE in class_ids
    has_person = CLASS_PERSON in class_ids
    has_fire = CLASS_FIRE in class_ids or len(all_fire_boxes) > 0
    
    if not has_fire and fire_size_pct < 5:
        return ALERT_ACTIVE, ALERT_COLORS_RGB[ALERT_ACTIVE], fire_size_pct, "No fire detected"
    
    if fire_size_pct > FIRE_SIZE_WARNING:
        if has_person:
            return ALERT_CRITICAL, ALERT_COLORS_RGB[ALERT_CRITICAL], fire_size_pct, "CRITICAL: Large fire with person!"
        else:
            return ALERT_CRITICAL, ALERT_COLORS_RGB[ALERT_CRITICAL], fire_size_pct, "CRITICAL: Uncontrolled fire!"
    
    if fire_size_pct > FIRE_SIZE_CAUTION or (has_person and has_fire):
        if has_person:
            return ALERT_WARNING, ALERT_COLORS_RGB[ALERT_WARNING], fire_size_pct, "WARNING: Person near fire!"
        elif not has_stove and not has_candle:
            return ALERT_WARNING, ALERT_COLORS_RGB[ALERT_WARNING], fire_size_pct, "WARNING: Fire without context!"
        else:
            return ALERT_WARNING, ALERT_COLORS_RGB[ALERT_WARNING], fire_size_pct, "WARNING: Large fire"
    
    if fire_size_pct > FIRE_SIZE_NORMAL:
        if has_stove:
            return ALERT_CAUTION, ALERT_COLORS_RGB[ALERT_CAUTION], fire_size_pct, "CAUTION: Fire larger than normal"
        else:
            return ALERT_CAUTION, ALERT_COLORS_RGB[ALERT_CAUTION], fire_size_pct, "CAUTION: Medium fire"
    
    if has_stove or has_candle:
        return ALERT_ACTIVE, ALERT_COLORS_RGB[ALERT_ACTIVE], fire_size_pct, "ACTIVE: Normal cooking"
    elif has_fire:
        return ALERT_ACTIVE, ALERT_COLORS_RGB[ALERT_ACTIVE], fire_size_pct, "ACTIVE: Small fire"
    
    return ALERT_ACTIVE, ALERT_COLORS_RGB[ALERT_ACTIVE], fire_size_pct, "Monitoring"

def add_log_entry(message):
    """Add a new log entry to the system"""
    timestamp = datetime.now().strftime('[%m/%d/%Y %H:%M:%S]')
    new_entry = f"{timestamp} {message}"
    dashboard_state['log_entries'].insert(0, new_entry)
    
    # Keep only last 20 entries
    if len(dashboard_state['log_entries']) > 20:
        dashboard_state['log_entries'] = dashboard_state['log_entries'][:20]

def register_fire_event(source='device'):
    """Create a new fire event so the dashboard popup appears only for new detections."""
    dashboard_state['fire_event_id'] = dashboard_state.get('fire_event_id', 0) + 1
    dashboard_state['last_fire_trigger_at'] = datetime.now().isoformat()
    dashboard_state['fire_status'] = 'FIRE DETECTED!'
    add_log_entry(f'FIRE ALERT: Fire detected from {source}')


def read_thermal_temperature():
    try:
        response = requests.get("http://192.168.1.110:8055/api/temperature", timeout=2)
        if response.status_code == 200:
            data = response.json()
            return float(data.get("max_temp", 0))
        return None
    except Exception as e:
        print("Thermal API error:", e)
        return None
    
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Get hottest pixel value
        max_pixel = np.max(gray)

        # ?? Convert pixel (0-255) to temperature
        # Adjust mapping depending on your thermal sensor
        min_temp = 20
        max_temp = 120

        temperature = min_temp + (max_pixel / 255.0) * (max_temp - min_temp)

        return round(float(temperature), 1)

    except Exception as e:
        print("Thermal read error:", e)
        return None

def thermal_monitor():
    while True:
        temp = read_thermal_temperature()
        if temp is not None:
            dashboard_state['current_temperature'] = temp
        time.sleep(2)  # every 2 seconds

thermal_thread = threading.Thread(target=thermal_monitor, daemon=True)
thermal_thread.start()

# --- ADDED: safe startup attempt to load model (after logging and background thread exist) ---
try:
    loaded = load_fire_model()
    if loaded:
        fire_model_enabled = True
except Exception:
    # don't fail startup if model can't be loaded
    pass

def dashboard():
    """Main dashboard page"""
    # Check if user is authenticated
    if not session.get('user'):
        # If no user in session, redirect to login page
        return redirect('http://localhost:5000/login')
    
    # Force thermal sensor status to "Offline" for now
  
    # Compute indicator CSS classes based on current system_status values
    def _indicator(status):
        s = (status or '').lower()
        if any(x in s for x in ['online', 'ok', 'connected']):
            return 'green'
        if any(x in s for x in ['running']):
            return 'blue'
        return 'red'

    def _value_class(status):
        s = (status or '').lower()
        if 'offline' in s or 'unavailable' in s:
            return 'offline'
        if 'connected' in s:
            return 'connected'
        if 'online' in s or 'ok' in s:
            return 'ok'
        if 'running' in s:
            return 'running'
        return ''

    camera_stat = dashboard_state['system_status'].get('camera', 'Offline')
    thermal_stat = dashboard_state['system_status'].get('thermal', 'Offline')
    edge_stat = dashboard_state['system_status'].get('edge', 'Running')
    internet_stat = dashboard_state['system_status'].get('internet', 'Disconnected')

    template_data = {
        'current_temperature': round(dashboard_state['current_temperature'], 1),
        'threshold': dashboard_state['threshold'],
        'is_recording': dashboard_state['is_recording'],
        'night_vision': dashboard_state['night_vision'],
        'alerts_active': dashboard_state['alerts_active'],
        'auto_mode': dashboard_state['auto_mode'],
        'fire_status': dashboard_state['fire_status'],
        'system_status': dashboard_state['system_status'],
        'log_entries': dashboard_state['log_entries'][:10],  # Show only recent 10
        'last_update': datetime.now().strftime('%m/%d/%Y %H:%M:%S'),
        'username': session.get('name', 'User'),
        'user_role': session.get('role', 'user'),
        'admin_url': f"http://{request.host.split(':')[0]}:5003/admin",
        # indicator classes sent to template
        'camera_indicator': _indicator(camera_stat),
        'thermal_indicator': _indicator(thermal_stat),
        'edge_indicator': _indicator(edge_stat),
        'internet_indicator': _indicator(internet_stat),
        'camera_enabled': camera_enabled,
        # value pill classes for consistent styling (used in template)
        'camera_value_class': _value_class(camera_stat),
        'thermal_value_class': _value_class(thermal_stat),
        'edge_value_class': _value_class(edge_stat),
        'internet_value_class': _value_class(internet_stat),
    }
    return render_template_string(HTML_TEMPLATE, **template_data)

@app.route('/')
def index():
    return dashboard()


def get_latest_fire_status_from_logs():
    try:
        conn = sqlite3.connect(LOGS_DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("""
            SELECT temperature, level, status, timestamp
            FROM logs
            ORDER BY id DESC
            LIMIT 1
        """)
        row = c.fetchone()
        conn.close()

        if not row:
            return None

        return {
            'temperature': row['temperature'],
            'level': row['level'],
            'status': row['status'],
            'timestamp': row['timestamp']
        }

    except Exception as e:
        print("LOG STATUS READ ERROR:", e)
        return None

def get_live_detection_status():
    try:
        r = requests.get(DETECTION_STATUS_URL, timeout=1.0)
        if not r.ok:
            return None
        data = r.json()
        return {
            "fire_level": data.get("fire_level"),
            "fire_status": data.get("fire_status"),
            "temperature": data.get("temperature"),
            "timestamp": data.get("timestamp")
        }
    except Exception as e:
        print("LIVE DETECTION STATUS ERROR:", e)
        return None

@app.route('/api/status')
def get_status():
    """Get current system status"""
    if not session.get('user'):
        return jsonify({'error': 'Authentication required'}), 401

    live = get_live_detection_status()

    fire_status = dashboard_state.get('fire_status', 'No fire detected')
    temperature = round(dashboard_state.get('current_temperature', 34.6), 1)

    previous_live_status = (dashboard_state.get('last_live_status') or 'NORMAL').upper()
    current_live_status = previous_live_status

    if live:
        current_live_status = (live.get('fire_status') or '').upper()
        live_temp = live.get('temperature')

        if live_temp is not None:
            try:
                temperature = round(float(live_temp), 1)
            except Exception:
                pass

        if current_live_status == 'FIRE DETECTED':
            fire_status = 'FIRE DETECTED!'
        elif current_live_status == 'WARNING':
            fire_status = 'WARNING'
        elif current_live_status == 'NORMAL':
            fire_status = 'No fire detected'

    # Detect only NEW fire events
    if current_live_status == 'FIRE DETECTED' and previous_live_status != 'FIRE DETECTED':
        register_fire_event('live detection service')

    # Detect when fire is cleared
    if current_live_status != 'FIRE DETECTED' and previous_live_status == 'FIRE DETECTED':
        add_log_entry('Fire cleared')
        dashboard_state['fire_status'] = 'No fire detected'

    dashboard_state['last_live_status'] = current_live_status
    dashboard_state['fire_status'] = fire_status
    dashboard_state['current_temperature'] = temperature

    return jsonify({
        'temperature': temperature,
        'threshold': dashboard_state['threshold'],
        'fire_status': dashboard_state['fire_status'],
        'alert_level': dashboard_state.get('alert_level', 'Active'),
        'fire_size_pct': dashboard_state.get('fire_size_pct', 0.0),
        'system_status': dashboard_state['system_status'],
        'fire_event_id': dashboard_state.get('fire_event_id', 0),
        'last_fire_trigger_at': dashboard_state.get('last_fire_trigger_at'),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/toggle_recording', methods=['POST'])
def toggle_recording():
    """Toggle recording state"""
    dashboard_state['is_recording'] = not dashboard_state['is_recording']
    # reflect on edge system status
    dashboard_state['system_status']['edge'] = 'Recording' if dashboard_state['is_recording'] else 'Running'
    message = 'Python recording started' if dashboard_state['is_recording'] else 'Python recording stopped'
    add_log_entry(message)
    
    return jsonify({
        'success': True,
        'is_recording': dashboard_state['is_recording'],
        'message': message
    })

@app.route('/api/snapshot', methods=['POST'])
def take_snapshot():
    """Take a snapshot"""
    add_log_entry('Python snapshot captured')
   
    return jsonify({
        'success': True,
        'message': 'Snapshot saved to Python gallery!'
    })

@app.route('/api/toggle_night_vision', methods=['POST'])
def toggle_night_vision():
    """Toggle night vision mode"""
    dashboard_state['night_vision'] = not dashboard_state['night_vision']
    message = 'Python night vision enabled' if dashboard_state['night_vision'] else 'Python day vision enabled'
    add_log_entry(message)
    
    return jsonify({
        'success': True,
        'night_vision': dashboard_state['night_vision'],
        'message': message
    })

@app.route('/api/update_threshold', methods=['POST'])
def update_threshold():
    """Update temperature threshold"""
    data = request.get_json()
    threshold = data.get('threshold', 70)
    dashboard_state['threshold'] = threshold
    message = f'Python threshold updated to {threshold}°C'
    add_log_entry(message)
    
    return jsonify({
        'success': True,
        'threshold': threshold,
        'message': message
    })

@app.route('/api/calibrate_sensor', methods=['POST'])
def calibrate_sensor():
    """Start sensor calibration"""
    add_log_entry('Python sensor calibration started...')
    return jsonify({
        'success': True,
        'message': 'Python sensor calibration started...'
    })

@app.route('/api/reset_threshold', methods=['POST'])
def reset_threshold():
    """Reset threshold to default"""
    dashboard_state['threshold'] = 70
    message = 'Python threshold reset to default (70Ã‚Â°C)'
    add_log_entry(message)
    
    return jsonify({
        'success': True,
        'threshold': 70,
        'message': message
    })

# --- NEW: server-side form-action endpoints for calibration and reset ---
@app.route('/action/calibrate_sensor', methods=['POST'])
def action_calibrate_sensor():
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))
    # Set the baseline to the current temperature (user pressed Calibrate)
    try:
        baseline = float(dashboard_state.get('current_temperature', 34.6))
        dashboard_state['baseline_temp'] = baseline
        add_log_entry(f'User calibrated baseline to {baseline:.1f}Ã‚Â°C')
        flash(f'Calibration saved: baseline {baseline:.1f}Ã‚Â°C', 'success')
    except Exception as e:
        add_log_entry(f'Calibration error: {e}')
        flash('Calibration failed', 'error')
    return redirect(url_for('index'))

@app.route('/action/reset_threshold', methods=['POST'])
def action_reset_threshold():
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))
    dashboard_state['threshold'] = 70
    add_log_entry('User reset threshold to default (70Ã‚Â°C)')
    flash('Threshold reset to 70Ã‚Â°C', 'success')
    return redirect(url_for('index'))

# --- NEW: logout route (clears session and returns to central login) ---
@app.route('/logout')
def logout_dashboard():
    user_id = session.get('user')
    session.clear()
    # best-effort: tell camera control to stop streaming
    if CAMERA_CONTROL_URL:
        try:
            requests.post(CAMERA_CONTROL_URL, json={"action": "stop", "user_id": user_id}, timeout=5)
        except Exception as e:
            print("Camera stop request failed during dashboard logout:", e, file=sys.stderr)
    # Redirect back to central login. Prefer PYROSENSE_LOGIN_BASE if set, otherwise use the host the dashboard was served on.
    try:
        login_base = LOGIN_BASE or f"http://{request.host.split(':')[0]}:5000"
    except Exception:
        login_base = LOGIN_BASE or "http://127.0.0.1:5000"
    return redirect(login_base.rstrip('/') + '/login')

# Lightweight internet connectivity monitor to update system_status.internet
def internet_monitor():
    while True:
        try:
            sock = socket.create_connection(("8.8.8.8", 53), timeout=1.0)
            sock.close()
            dashboard_state['system_status']['internet'] = 'Connected'
        except Exception:
            dashboard_state['system_status']['internet'] = 'Disconnected'
        time.sleep(10)

# Start internet monitor thread if not already running
try:
    internet_thread = threading.Thread(target=internet_monitor, daemon=True)
    internet_thread.start()
except Exception:
    pass

# Ensure the app can be started directly
if __name__ == '__main__':
    print("?? Starting PyroSense Python Flask Dashboard...")
    print("?? Fire Detection System - Python Edition")
    print("=" * 50)
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print(f"Host: {hostname}  IP: {local_ip}")
    except Exception:
        pass
    print("Dashboard URL: http://localhost:5002")
    print("To stop server: Press Ctrl+C")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5002)
