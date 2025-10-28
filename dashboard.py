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

app = Flask(__name__)
# Add the same secret key as login.py for shared sessions
app.secret_key = 'pyrosense_shared_secret_key'

# Global variables for dashboard state
dashboard_state = {
    'current_temperature': 34.6,
    'threshold': 70,
    'is_recording': False,
    'night_vision': False,
    'alerts_active': True,
    'auto_mode': True,
    'fire_status': 'No fire detected',
    'system_status': {
        'camera': 'Online',
        'thermal': 'Offline',   # always Offline unless you implement it
        'edge': 'Running',
        'internet': 'Connected'
    },
    'log_entries': [
        f"[{datetime.now().strftime('%m/%d/%Y %H:%M:%S')}] System initialized",
        f"[{datetime.now().strftime('%m/%d/%Y %H:%M:%S')}] Sensors online",
        f"[{datetime.now().strftime('%m/%d/%Y %H:%M:%S')}] No fire detected"
    ]
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

# Manual alert (set by Test Alert) — displayed separately from model detections
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

		# Camera is available — stream frames
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
						new_labels = [lbl for lbl in last_labels]  # list of strings from this inference
						# always update last_detection_summary so UI badge shows latest objects
						last_detection_summary['labels'] = new_labels
						last_detection_summary['timestamp'] = now
						# also expose a human-friendly short summary for acknowledgement UI
						if new_labels:
							dashboard_state['last_detected'] = ', '.join(new_labels[:4])
						else:
							dashboard_state['last_detected'] = ''
						
						# Rate-limited logging when label set actually changed
						prev_set = set(last_detection_summary.get('labels', []))
						new_set = set(new_labels)
						if new_set and new_set != prev_set and (now - last_detection_summary.get('timestamp', 0) > _detection_log_min_interval):
							for i, lbl in enumerate(new_labels):
								conf = last_confidences[i] if i < len(last_confidences) else 0.0
								add_log_entry(f"Camera detection: {lbl} (conf={conf:.2f})")
							if any('fire' in l.lower() for l in new_labels):
								dashboard_state['fire_status'] = 'FIRE DETECTED!'
								add_log_entry('🚨 FIRE ALERT: Camera detected fire!')
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
					video_capture.release()
			except:
				pass
			video_capture = None
		stream_ready = False

	# Update dashboard system status for camera
	dashboard_state['system_status']['camera'] = 'Online' if camera_enabled else 'Offline'

	message = 'Camera feed enabled' if camera_enabled else 'Camera feed disabled'
	add_log_entry(f"UI: {message} (ready={stream_ready})")
	return jsonify({'success': True, 'camera_enabled': camera_enabled, 'stream_ready': stream_ready, 'message': message})

# API to query camera feed status
@app.route('/api/camera_feed_status')
def api_camera_feed_status():
    if not session.get('user'):
        return jsonify({'error':'Authentication required'}), 401
    # ensure we return the live camera_enabled-based status
    return jsonify({'camera_enabled': camera_enabled, 'camera_status': dashboard_state['system_status'].get('camera','Offline')})

# API to force-disable camera (used before navigating to History)
@app.route('/api/disable_camera', methods=['POST'])
def api_disable_camera():
    if not session.get('user'):
        return jsonify({'error': 'Authentication required'}), 401
    global camera_enabled, video_capture
    with video_lock:
        try:
            camera_enabled = False
            if video_capture is not None:
                try:
                    video_capture.release()
                except:
                    pass
                video_capture = None
            # reflect status in UI
            dashboard_state['system_status']['camera'] = 'Offline'
            add_log_entry('UI: Camera disabled (navigation to history)')
            return jsonify({'success': True, 'camera_enabled': camera_enabled})
        except Exception as e:
            add_log_entry(f'Camera disable error: {e}')
            return jsonify({'success': False, 'error': str(e)}), 500

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
  </style>
</head>
<body>
  <div class="dashboard-overlay">
    <!-- REMOVED: small top title bar -->
    <!-- <div class="dashboard-title">DASHBOARD</div> -->

    <header>
      <div class="header-container">
        <div class="header-left">
          <div class="header-logo">🔥</div>
          <div class="header-title-section">
            <h1 class="header-title">PYROSENSE</h1>
            <p class="header-subtitle">Advanced Fire Detection System - Python Edition</p>
          </div>
        </div>

        <div class="header-center">
          <nav class="main-nav">
            <a href="/" class="nav-link active" id="navDashboard">Dashboard</a>
            <span class="nav-sep" aria-hidden="true"></span>
            <a href="http://localhost:5001/history" class="nav-link" id="navHistory">History</a>
          </nav>
        </div>

        <div class="header-right">
          <span class="badge python-badge">Made with Python Flask</span>
          <span class="badge system-badge">System Online</span>
          <!-- REMOVED: history button from right side -->
          <!-- <a href="http://localhost:5001/history" class="history-button">📊 HISTORY</a> -->
          <a href="#" id="logoutBtn" class="logout-button">🚪 LOGOUT</a>
        </div>
      </div>
    </header>

    <main>
      <!-- Live Camera Feed -->
      <div class="card">
        <div class="card-header">
          <div class="card-icon">📹</div>
          <h2 class="card-title">Live Camera Feed</h2>
        </div>
        <div class="card-content">
          <!-- Replaced static box with live MJPEG stream + controls -->
          <div class="video-player" id="videoPlayer">
            <div class="video-topbar">
              <div class="video-badge" id="streamStatus">Scanning for fire...</div>
            </div>
            <img id="cameraStream" class="stream" src="/video_feed" alt="Live camera stream">
            <div class="video-controls">
              <!-- Removed Toggle Fire button and Minimize button per request -->
              <button class="video-control-btn" id="fullscreenBtn" onclick="toggleFullscreen()">Fullscreen</button>
            </div>
          </div>

          <div class="status-line" style="margin-top:12px;">
            <span class="status-label">Status:</span>
            <strong id="fireStatus">{{ fire_status }}</strong>
          </div>

          <div class="button-group">
            <!-- NEW: Camera toggle button placed left of Start Recording -->
            <form action="/action/toggle_camera" method="POST" style="display:inline;">
              <button type="submit" class="action-button" id="toggleCameraBtn" style="background: linear-gradient(90deg,#6c7cff,#8fafff);">
                <span id="toggleCameraLabel">Camera: ON</span>
              </button>
            </form>

            <form action="/action/toggle_recording" method="POST" style="display:inline;">
              <button type="submit" class="action-button" id="recordButton">
                <span>Start Recording</span>
              </button>
            </form>
            <form action="/action/snapshot" method="POST" style="display:inline;">
              <button type="submit" class="action-button">
                <span>Snapshot</span>
              </button>
            </form>
            <form action="/action/toggle_night_vision" method="POST" style="display:inline;">
              <button type="submit" class="action-button">
                <span>Thermal/RGB</span>
              </button>
            </form>
          </div>
        </div>
      </div>
      
      <!-- Thermal Reading -->
      <div class="card">
        <div class="card-header">
          <div class="card-icon">🌡️</div>
          <h2 class="card-title">Thermal Reading</h2>
        </div>
        <div class="card-content">
          <div class="temperature-display" id="currentTemp">{{ current_temperature }}°C</div>
          <div class="threshold-info">Heat Threshold: <strong id="thresholdValue">{{ threshold }}°C</strong></div>
          <div class="slider-container">
            <input type="range" min="30" max="100" value="{{ threshold }}" class="slider" id="thresholdSlider" oninput="updateThreshold(this.value)">
          </div>
          <div class="button-group">
            <button class="action-button" onclick="calibrateSensor()">
              <span>Calibrate</span>
            </button>
            <button class="action-button" onclick="resetThreshold()">
              <span>Reset</span>
            </button>
          </div>
        </div>
      </div>
      
      <!-- Fire Detection Log -->
      <div class="card">
        <div class="card-header">
          <div class="card-icon">📋</div>
          <h2 class="card-title">Fire Detection Log</h2>
        </div>
        <div class="card-content">
          <div class="log-container" id="logContainer">
            {% for entry in log_entries %}
            <div class="log-entry">{{ entry }}</div>
            {% endfor %}
          </div>
          <div class="button-group">
            <form action="/action/clear_log" method="POST" id="clearLogForm" style="display:inline;">
              <button type="submit" class="action-button red" id="clearLogBtn">
                <span>Clear Log</span>
              </button>
            </form>
            <a href="/api/export_log" class="action-button" id="exportLogBtn">
              <span>Export</span>
            </a>
          </div>
        </div>
      </div>
      
      <!-- Alert Control -->
      <div class="card">
        <div class="card-header">
          <div class="card-icon">🚨</div>
          <h2 class="card-title">Alert Control</h2>
        </div>
        <div class="card-content">
          <div class="alert-panel" id="alertPanel">⚠️ FIRE DETECTED!</div>
          <div class="button-group">
            <form action="/action/simulate_alert" method="POST" style="display:inline;">
              <button type="submit" class="action-button red">
                <span>Test Alert</span>
              </button>
            </form>
            <form action="/action/acknowledge_alert" method="POST" style="display:inline;">
              <button type="submit" class="action-button">
                <span>Acknowledge</span>
              </button>
            </form>
            <form action="/action/mute_alerts" method="POST" style="display:inline;">
              <button type="submit" class="action-button">
                <span>Mute (5min)</span>
              </button>
            </form>
          </div>
        </div>
      </div>
      
      <!-- Device Status -->
      <div class="card" style="grid-column: span 2;">
        <div class="card-header">
          <div class="card-icon">💻</div>
          <h2 class="card-title">System Status</h2>
        </div>
        <div class="card-content">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
            <div class="device-row">
              <div class="device-name">
                <span class="status-indicator {{ camera_indicator }}"></span>
                <span>RGB Camera:</span>
              </div>
              <span class="status-value {{ camera_value_class }}" id="cameraStatus">{{ system_status.camera }}</span>
            </div>
            <div class="device-row">
              <div class="device-name">
                <span class="status-indicator {{ thermal_indicator }}"></span>
                <span>Thermal Sensor:</span>
              </div>
              <span class="status-value {{ thermal_value_class }}" id="thermalStatus">{{ system_status.thermal }}</span>
            </div>
            <div class="device-row">
              <div class="device-name">
                <span class="status-indicator {{ edge_indicator }}"></span>
                <span>Edge System:</span>
              </div>
              <span class="status-value {{ edge_value_class }}" id="edgeStatus">{{ system_status.edge }}</span>
            </div>
            <div class="device-row">
              <div class="device-name">
                <span class="status-indicator {{ internet_indicator }}"></span>
                <span>Internet:</span>
              </div>
              <span class="status-value {{ internet_value_class }}" id="internetStatus">{{ system_status.internet }}</span>
            </div>
          </div>
          <div class="button-group" style="margin-top: 15px;">
            <button class="action-button red" onclick="restartSystem()">
              <span>Restart</span>
            </button>
          </div>
        </div>
      </div>
    </main>
    
    <footer>
      PyroSense 2025 © All rights reserved - Python Flask Edition
    </footer>
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
</body>
</html>
"""

def simulate_temperature_variation():
    """Simulate realistic temperature changes"""
    variation = (random.random() - 0.5) * 2  # ±1 degree variation
    dashboard_state['current_temperature'] = max(20, min(100, 
        dashboard_state['current_temperature'] + variation))
    
    # Check for fire conditions
    if dashboard_state['current_temperature'] > dashboard_state['threshold']:
        dashboard_state['fire_status'] = 'FIRE DETECTED!'
        add_log_entry('🚨 FIRE ALERT: High temperature detected!')
    else:
        dashboard_state['fire_status'] = 'No fire detected'

def add_log_entry(message):
    """Add a new log entry to the system"""
    timestamp = datetime.now().strftime('[%m/%d/%Y %H:%M:%S]')
    new_entry = f"{timestamp} {message}"
    dashboard_state['log_entries'].insert(0, new_entry)
    
    # Keep only last 20 entries
    if len(dashboard_state['log_entries']) > 20:
        dashboard_state['log_entries'] = dashboard_state['log_entries'][:20]

def background_temperature_monitor():
    """Background thread for temperature monitoring"""
    while True:
        simulate_temperature_variation()
        time.sleep(3)  # Update every 3 seconds

# Start background monitoring
temperature_thread = threading.Thread(target=background_temperature_monitor, daemon=True)
temperature_thread.start()

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
    dashboard_state['system_status']['thermal'] = 'Offline'

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
        'username': session.get('name', 'User'),  # Add username from session
        # indicator classes sent to template
        'camera_indicator': _indicator(camera_stat),
        'thermal_indicator': _indicator(thermal_stat),
        'edge_indicator': _indicator(edge_stat),
        'internet_indicator': _indicator(internet_stat),
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

@app.route('/api/status')
def get_status():
    """Get current system status"""
    # Check if user is authenticated for API calls too
    if not session.get('user'):
        return jsonify({'error': 'Authentication required'}), 401
        
    return jsonify({
        'temperature': round(dashboard_state['current_temperature'], 1),
        'threshold': dashboard_state['threshold'],
        'fire_status': dashboard_state['fire_status'],
        'system_status': dashboard_state['system_status'],
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
    message = 'Python threshold reset to default (70°C)'
    add_log_entry(message)
    
    return jsonify({
        'success': True,
        'threshold': 70,
        'message': message
    })

# --- NEW: server-side form-action endpoints (redirect back with flash messages) ---
@app.route('/action/toggle_camera', methods=['POST'])
def action_toggle_camera():
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))
    global camera_enabled, video_capture
    camera_enabled = not camera_enabled
    stream_ready = False
    if camera_enabled:
        # try to open capture immediately
        with video_lock:
            try:
                if video_capture is not None:
                    try:
                        video_capture.release()
                    except:
                        pass
                    video_capture = None
                video_capture = open_capture_with_backends(0, warmup_reads=2)
                if video_capture is not None and video_capture.isOpened():
                    try:
                        video_capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        video_capture.set(cv2.CAP_PROP_FPS, 30)
                        video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                        video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    except:
                        pass
                    try:
                        ret, _ = video_capture.read()
                        if ret:
                            stream_ready = True   # <-- fixed (was `true`)
                    except:
                        stream_ready = bool(video_capture.isOpened())
            except Exception:
                stream_ready = False
    else:
        with video_lock:
            try:
                if video_capture is not None:
                    video_capture.release()
            except:
                pass
            video_capture = None
        stream_ready = False

    # Update UI status
    dashboard_state['system_status']['camera'] = 'Online' if camera_enabled else 'Offline'

    message = 'Camera feed enabled' if camera_enabled else 'Camera feed disabled'
    add_log_entry(f"UI: {message} (ready={stream_ready})")
    flash(message, 'success')
    return redirect(url_for('index'))

@app.route('/action/toggle_recording', methods=['POST'])
def action_toggle_recording():
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))

    global recording_flag, recording_thread, recording_filename

    # Toggle
    if not recording_flag:
        # start recording
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        fname = os.path.join(recordings_dir, f"recording_{ts}.mp4")
        recording_flag = True

        # Update edge status
        dashboard_state['system_status']['edge'] = 'Recording'

        # stop flag accessor
        stop_ref = lambda: not recording_flag

        # spawn thread
        t = threading.Thread(target=_recording_loop, args=(fname, stop_ref), daemon=True)
        recording_thread = t
        recording_filename = fname
        t.start()
        add_log_entry(f"UI: Recording started ({os.path.basename(fname)})")
        flash('Recording started', 'success')
    else:
        # stop recording
        recording_flag = False
        # update edge status
        dashboard_state['system_status']['edge'] = 'Running'
        # let thread finish; do not block long
        add_log_entry('UI: Recording stopped by user')
        flash('Recording stopped', 'success')

    return redirect(url_for('index'))

@app.route('/action/snapshot', methods=['POST'])
def action_snapshot():
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))
    try:
        cap = get_video_capture()
        temp_cap_opened = False
        if cap is None or not getattr(cap, "isOpened", lambda: False)():
            cap = open_capture_with_backends(0, warmup_reads=2)
            temp_cap_opened = True

        if cap is None or not getattr(cap, "isOpened", lambda: False)():
            add_log_entry('Snapshot failed: camera not available')
            flash('Snapshot failed: camera not available', 'error')
            return redirect(url_for('index'))

        ret, frame = cap.read()
        if not ret or frame is None:
            add_log_entry('Snapshot failed: no frame read')
            flash('Snapshot failed: no frame read', 'error')
            return redirect(url_for('index'))

        frame = cv2.flip(frame, 1)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(snapshots_dir, f"snapshot_{ts}.jpg")
        cv2.imwrite(filename, frame)
        add_log_entry(f'Python snapshot saved: {os.path.basename(filename)}')
        flash(f'Snapshot saved: {os.path.basename(filename)}', 'success')
    except Exception as e:
        add_log_entry(f'Snapshot error: {e}')
        flash('Snapshot failed', 'error')
    finally:
        try:
            if temp_cap_opened and cap is not None:
                cap.release()
        except:
            pass

    return redirect(url_for('index'))

@app.route('/action/simulate_alert', methods=['POST'])
def action_simulate_alert():
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))
    # set a manual alert message (kept until acknowledged)
    dashboard_state['manual_alert'] = 'TEST ALERT: User triggered test'
    # Do not overwrite model detection state; just mark alerts active
    dashboard_state['alerts_active'] = True
    add_log_entry('Python test alert (manual) triggered')
    flash('Test alert triggered (manual)', 'warning')
    return redirect(url_for('index'))

@app.route('/action/acknowledge_alert', methods=['POST'])
def action_acknowledge_alert():
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))

    # Prefer manual alert message; else use last detections
    with detection_lock:
        labels = list(last_detection_summary.get('labels', []))
    manual = dashboard_state.get('manual_alert')
    if manual:
        detected = manual
    else:
        detected = ', '.join(labels) if labels else 'Nothing detected'

    message = f'Alert acknowledged. Detected: {detected}'
    # Acknowledging will clear manual alert and mute overlays
    dashboard_state['manual_alert'] = None
    dashboard_state['alerts_active'] = False
    # keep fire_status (model) unchanged so detection history remains
    add_log_entry(message)
    flash(message, 'success')
    return redirect(url_for('index'))

# Update mute: keep detection state but suppress overlays
@app.route('/action/mute_alerts', methods=['POST'])
def action_mute_alerts():
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))
    dashboard_state['alerts_active'] = False
    message = 'Python alerts muted for 5 minutes (overlays suppressed)'
    add_log_entry(message)
    flash(message, 'info')

    def _reenable():
        dashboard_state['alerts_active'] = True
        add_log_entry('Python alerts reactivated (timer)')

    try:
        t = threading.Timer(300, _reenable)
        t.daemon = True
        t.start()
    except Exception:
        pass

    return redirect(url_for('index'))

@app.route('/action/restart_system', methods=['POST'])
def action_restart_system():
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))
    message = 'Python system restart initiated...'
    add_log_entry(message)
    flash('System restart initiated', 'info')

    # set UI state
    dashboard_state['system_status']['edge'] = 'Restarting'

    # spawn background thread to perform restart after a short delay
    def _do_restart():
        try:
            time.sleep(1.0)
            add_log_entry("System: performing process restart via execv")
            # re-exec the current Python interpreter with same args
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            add_log_entry(f"System restart failed: {e}")
            # if execv fails, attempt to exit so an external supervisor can restart
            try:
                os._exit(0)
            except:
                pass

    try:
        t = threading.Thread(target=_do_restart, daemon=True)
        t.start()
    except Exception as e:
        add_log_entry(f"Restart scheduling failed: {e}")

    return redirect(url_for('index'))

@app.route('/logout_confirm')
def logout_confirm():
	# perform actual logout (used after SweetAlert confirmation)
	session.clear()

	# Build a small page styled to match the dashboard font and set a short-lived cookie
	html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Logged out</title>
  <script src="https://unpkg.com/sweetalert/dist/sweetalert.min.js"></script>
  <style>
    /* Use same UI font as dashboard so modal text matches */
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin:0; padding:0; background:#f4f4f4; height:100vh; display:flex; align-items:center; justify-content:center; }
  </style>
</head>
<body>
<script>
  // show logout message, then redirect to login
  swal({
    title: "Logged out",
    text: "You have been logged out successfully.",
    icon: "info",
    button: "Go to Login"
  }).then(function(){
    window.location.href = "http://localhost:5000/login";
  });
  // fallback redirect after 6s
  setTimeout(function(){ window.location.href = "http://localhost:5000/login"; }, 6000);
</script>
</body>
</html>"""

	# Set a short-lived cookie so an external login page (if it checks) can detect logout
	resp = make_response(render_template_string(html))
	resp.set_cookie('pyrosense_logged_out', '1', max_age=10, path='/')
	return resp

# Modify export_log to accept GET so browser can download directly (no client AJAX)
@app.route('/api/export_log', methods=['GET', 'POST'])
def export_log():
    """Export system log as a downloadable TXT file (supports GET for direct download)"""
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))

    txt = "\r\n".join(reversed(dashboard_state.get('log_entries', [])))
    filename = f"pyrosense_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    resp = Response(txt, mimetype='text/plain; charset=utf-8')
    resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    add_log_entry('Python log exported to download')
    # If called via GET or direct link, return the file.
    return resp

# --- ADDED: debug API to report model files / class count to UI ---
@app.route('/api/fire_model_info')
def api_fire_model_info():
    if not session.get('user'):
        return jsonify({'error': 'Authentication required'}), 401
    files = find_fire_model_files()
    return jsonify({
        'found': bool(files),
        'cfg': files.get('cfg') if files else None,
        'weights': files.get('weights') if files else None,
        'names': files.get('names') if files else None,
        'classes': len(fire_classes) if fire_classes else 0,
        'model_loaded': fire_model_loaded,
        'fire_model_enabled': fire_model_enabled
    })
    
# add missing clear-log endpoint so /action/clear_log won't 404
@app.route('/action/clear_log', methods=['GET', 'POST'])
def action_clear_log():
    """Clear the in-memory log. Accepts GET and POST to avoid 404s from direct navigation."""
    if not session.get('user'):
        flash('Authentication required', 'error')
        return redirect(url_for('index'))
    dashboard_state['log_entries'] = []
    message = f'[{datetime.now().strftime("%m/%d/%Y %H:%M:%S")}] Python log cleared by user'
    dashboard_state['log_entries'].append(message)
    add_log_entry('User cleared the log')
    flash('Log cleared', 'success')
    return redirect(url_for('index'))

# --- NEW: Internet connectivity monitor to update system status periodically ---
def internet_monitor():
    while True:
        try:
            # quick lightweight check to public DNS
            sock = socket.create_connection(("8.8.8.8", 53), timeout=1.0)
            sock.close()
            dashboard_state['system_status']['internet'] = 'Connected'
        except Exception:
            dashboard_state['system_status']['internet'] = 'Disconnected'
        time.sleep(10)

# Start internet monitor thread
internet_thread = threading.Thread(target=internet_monitor, daemon=True)
internet_thread.start()

if __name__ == '__main__':
    print("🐍 Starting PyroSense Python Flask Dashboard...")
    print("🔥 Fire Detection System - Python Edition")
    print("=" * 50)
    print("Dashboard URL: http://localhost:5002")
    print("Features:")
    print("  • Real-time temperature monitoring")
    print("  • Python-powered analytics")
    print("  • Interactive controls via Flask API")
    print("  • Background temperature simulation")
    print("To stop server: Press Ctrl+C")
    print("=" * 50)
    
    # Run the Flask development server on port 5002
    app.run(debug=True, host='0.0.0.0', port=5002)
