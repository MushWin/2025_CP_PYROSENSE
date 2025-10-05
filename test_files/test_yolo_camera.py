# test_yolo_camera.py — robust backend (CUDA -> CPU fallback) + correct confidence
import cv2
import numpy as np
import os

def find_model_files():
    """Find model files in both YoloV4-Tiny_model (fire) and yolo_pretrained_files (COCO) directories"""
    current_dir = os.getcwd()
    
    # Go up one level to find the model directories in the parent folder
    parent_dir = os.path.dirname(current_dir)
    
    # Fire model directory (your trained fire detector) - FIXED to match actual structure
    fire_dir = os.path.join(parent_dir, "YoloV4-Tiny_model")
    
    # COCO model directory - FIXED: yolo_pretrained_files is inside YoloV4-Tiny_model
    possible_coco_dirs = [
        os.path.join(parent_dir, "YoloV4-Tiny_model", "yolo_pretrained_files"),
        os.path.join(parent_dir, "yolo_pretrained_files"),
        os.path.join(parent_dir, "YoloV4-Tiny_model"),  # Check main folder too
        os.path.join(parent_dir, "COCO_model"),
        os.path.join(parent_dir, "pretrained_model"),
        os.path.join(parent_dir, "coco_weights")
    ]
    
    print(f"🔍 Current directory: {current_dir}")
    print(f"🔍 Parent directory: {parent_dir}")
    print(f"🔍 Looking for fire models in: {fire_dir}")
    
    # Find COCO directory
    coco_dir = None
    for potential_dir in possible_coco_dirs:
        if os.path.exists(potential_dir):
            print(f"🔍 Checking for COCO files in: {potential_dir}")
            # Quick check if it has COCO-related files (avoid fire model files)
            has_coco_files = False
            has_fire_files = False
            try:
                for file in os.listdir(potential_dir):
                    file_lower = file.lower()
                    # Check for COCO indicators
                    if any(pattern in file_lower for pattern in ['yolov4-tiny.weights', 'yolov4-tiny.cfg', 'coco.names']):
                        has_coco_files = True
                    # Check for fire indicators
                    if any(pattern in file_lower for pattern in ['fire', 'best.weights', 'last.weights']):
                        has_fire_files = True
                
                # Prefer directories with COCO files but not fire files
                if has_coco_files and not has_fire_files:
                    coco_dir = potential_dir
                    print(f"✅ Found COCO files in: {potential_dir}")
                    break
                elif has_coco_files:
                    # Backup option if mixed files
                    if coco_dir is None:
                        coco_dir = potential_dir
                        print(f"⚠️  Found mixed files in: {potential_dir}")
            except Exception as e:
                print(f"⚠️  Error checking {potential_dir}: {e}")
                continue
    
    if not coco_dir:
        coco_dir = possible_coco_dirs[0]  # Default for error messages
        print(f"⚠️  Using default path for error reporting: {coco_dir}")
    else:
        print(f"🔍 Looking for COCO models in: {coco_dir}")
    
    models = {}
    
    # Check fire model directory
    if os.path.exists(fire_dir):
        print(f"📁 Scanning fire model directory: {fire_dir}")
        # Use ASCII-only name to avoid ???? in overlays/window titles
        fire_model = scan_model_directory(fire_dir, "FIRE MODEL")
        if fire_model['complete']:
            models['fire'] = fire_model
    else:
        print(f"❌ Fire model directory not found: {fire_dir}")
    
    # Check COCO model directory  
    if os.path.exists(coco_dir):
        print(f"📁 Scanning COCO model directory: {coco_dir}")
        # Use ASCII-only name to avoid ???? in overlays/window titles
        coco_model = scan_model_directory(coco_dir, "COCO MODEL")
        if coco_model['complete']:
            models['coco'] = coco_model
    else:
        print(f"❌ COCO model directory not found: {coco_dir}")
        
        # Show available directories for debugging
        print(f"\n🔍 Available directories in parent folder {parent_dir}:")
        try:
            for item in os.listdir(parent_dir):
                item_path = os.path.join(parent_dir, item)
                if os.path.isdir(item_path):
                    print(f"  📂 {item}/")
        except Exception as e:
            print(f"  Error listing parent directory: {e}")
    
    return models

def scan_model_directory(root_dir, model_name):
    """Scan a directory for model files and return model info"""
    print(f"\n{model_name} - Directory structure:")
    
    # Show directory structure
    for root, dirs, files in os.walk(root_dir):
        level = root.replace(root_dir, '').count(os.sep)
        indent = ' ' * 2 * level
        rel_path = os.path.relpath(root, root_dir)
        if rel_path == '.':
            print(f"{indent}{os.path.basename(root_dir)}/")
        else:
            print(f"{indent}{rel_path}/")
        
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            if file.endswith(('.cfg', '.weights', '.names', '.data')):
                file_path = os.path.join(root, file)
                size = os.path.getsize(file_path)
                if size > 1024*1024:
                    print(f"{subindent}📄 {file} ({size/1024/1024:.1f} MB)")
                else:
                    print(f"{subindent}📄 {file}")
    
    # Find model files
    cfg_files = []
    weights_files = []
    names_files = []
    
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            full_path = os.path.join(root, file)
            if file.endswith('.cfg'):
                cfg_files.append(full_path)
            elif file.endswith('.weights'):
                weights_files.append(full_path)
            elif file.endswith('.names'):
                names_files.append(full_path)
    
    # Select best files for this model
    model_info = {
        'name': model_name,
        'cfg': None,
        'weights': None,
        'names': None,
        'complete': False,
        'class_count': 0
    }
    
    # Select config file
    if 'fire' in model_name.lower():
        # For fire model, prefer fire-specific configs
        fire_cfg_priorities = ['yolov4-tiny-fire-only.cfg', 'yolov4-tiny-fire.cfg', 'fire.cfg']
        for priority in fire_cfg_priorities:
            for cfg in cfg_files:
                if priority in os.path.basename(cfg).lower():
                    model_info['cfg'] = cfg
                    break
            if model_info['cfg']:
                break
    else:
        # For COCO model, prefer standard configs
        coco_cfg_priorities = ['yolov4-tiny.cfg', 'yolo.cfg']
        for priority in coco_cfg_priorities:
            for cfg in cfg_files:
                if priority == os.path.basename(cfg).lower():
                    model_info['cfg'] = cfg
                    break
            if model_info['cfg']:
                break
    
    # Fallback to first config if none found
    if not model_info['cfg'] and cfg_files:
        model_info['cfg'] = cfg_files[0]
    
    # Select weights file
    if 'fire' in model_name.lower():
        # For fire model, prefer best.weights first as requested
        fire_weight_priorities = ['best.weights', 'yolov4-tiny-fire-only_best.weights', 'final.weights', 'last.weights', 'obj.weights']
        for priority in fire_weight_priorities:
            for weight in weights_files:
                if priority.lower() in os.path.basename(weight).lower():
                    model_info['weights'] = weight
                    break
            if model_info['weights']:
                break
    else:
        # For COCO model, prefer standard weights
        coco_weight_priorities = ['yolov4-tiny.weights', 'yolo.weights']
        for priority in coco_weight_priorities:
            for weight in weights_files:
                if priority == os.path.basename(weight).lower():
                    model_info['weights'] = weight
                    break
            if model_info['weights']:
                break
    
    # Fallback to largest weights file
    if not model_info['weights'] and weights_files:
        largest_weight = max(weights_files, key=lambda x: os.path.getsize(x))
        model_info['weights'] = largest_weight
    
    # Select names file
    if names_files:
        # Try to find the most appropriate names file
        best_names = None
        target_classes = 1 if 'fire' in model_name.lower() else 80
        
        for names_file in names_files:
            try:
                with open(names_file, 'r', encoding='utf-8', errors='ignore') as f:
                    classes = [line.strip() for line in f if line.strip()]
                class_count = len(classes)
                
                if class_count == target_classes:
                    best_names = names_file
                    model_info['class_count'] = class_count
                    break
                elif best_names is None:
                    best_names = names_file
                    model_info['class_count'] = class_count
            except:
                pass
        
        model_info['names'] = best_names
    
    # Check if model is complete
    model_info['complete'] = all([model_info['cfg'], model_info['weights'], model_info['names']])
    
    # Report findings
    print(f"\n{model_name} - Selected files:")
    print(f"  CFG: {os.path.basename(model_info['cfg']) if model_info['cfg'] else 'None'}")
    print(f"  WEIGHTS: {os.path.basename(model_info['weights']) if model_info['weights'] else 'None'}")
    if model_info['weights']:
        size = os.path.getsize(model_info['weights']) / (1024*1024)
        print(f"    Size: {size:.1f} MB")
    print(f"  NAMES: {os.path.basename(model_info['names']) if model_info['names'] else 'None'}")
    if model_info['names']:
        print(f"    Classes: {model_info['class_count']}")
    
    if model_info['complete']:
        print(f"  ✅ {model_name} is complete and ready for testing")
    else:
        print(f"  ❌ {model_name} is incomplete")
    
    return model_info

def load_classes(names_path, model_name):
    """Load class names with validation"""
    if names_path and os.path.exists(names_path):
        with open(names_path, 'r', encoding='utf-8', errors='ignore') as f:
            classes = [line.strip() for line in f.readlines() if line.strip()]
        
        print(f"✅ {model_name} - Loaded {len(classes)} classes")
        
        # Show class info based on model type
        if 'fire' in model_name.lower():
            print(f"📋 Fire model classes: {classes}")
            if len(classes) == 1 and 'fire' in classes[0].lower():
                print("🔥 CONFIRMED: Fire-only detection model")
            else:
                print(f"⚠️  Expected 1 fire class, got {len(classes)} classes")
        else:
            print(f"📋 COCO model - First 5 classes: {classes[:5]}")
            print(f"📋 COCO model - Last 5 classes: {classes[-5:]}")
            if len(classes) == 80:
                print("📦 CONFIRMED: Standard 80-class COCO model")
            else:
                print(f"⚠️  Expected 80 COCO classes, got {len(classes)} classes")
        
        return classes
    
    print(f"❌ {model_name} - Could not load classes")
    return []

def get_output_layers(net):
    """Get output layers with OpenCV version compatibility"""
    layer_names = net.getLayerNames()
    
    try:
        unconnected = net.getUnconnectedOutLayers()
        if isinstance(unconnected, np.ndarray) and unconnected.ndim == 2:
            output_layers = [layer_names[i[0] - 1] for i in unconnected]
        else:
            output_layers = [layer_names[i - 1] for i in unconnected]
        return output_layers
    except Exception as e:
        print(f"⚠️  Using fallback output layer detection: {e}")
        output_layers = []
        for name in layer_names:
            if 'yolo' in name.lower():
                output_layers.append(name)
        if not output_layers:
            output_layers = [layer_names[-1]]
        return output_layers

def test_camera_access():
    """Test camera access"""
    print("🔍 Testing camera access...")
    
    camera_indices = [0, 1, 2]
    working_cameras = []
    
    for idx in camera_indices:
        backends = [
            (cv2.CAP_DSHOW, "DirectShow"),
            (cv2.CAP_MSMF, "Media Foundation"), 
            (cv2.CAP_ANY, "Any Available")
        ]
        
        for backend_id, backend_name in backends:
            try:
                cap = cv2.VideoCapture(idx, backend_id)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        height, width = frame.shape[:2]
                        print(f"✅ Camera {idx} works with {backend_name} ({width}x{height})")
                        working_cameras.append((idx, backend_id, backend_name, width, height))
                        cap.release()
                        break
                cap.release()
            except Exception as e:
                pass
    
    return working_cameras

def main():
    print("🔥 DUAL MODEL TESTING - Fire Detection + COCO Detection")
    print("=" * 60)
    
    # Find both models
    models = find_model_files()
    
    if not models:
        print("❌ No complete models found!")
        
        # Fix: Get parent_dir here for the error message
        current_dir = os.getcwd()
        parent_dir = os.path.dirname(current_dir)
        
        print("\n💡 Based on your actual directory structure:")
        print(f"  📂 {parent_dir}/")
        print("    📂 YoloV4-Tiny_model/ (EXISTS)")
        print("      📂 yolo_fire_files/ (your fire model files)")
        print("      📂 yolo_pretrained_files/ (COCO model files)")
        print("    📂 test_files/ (where these test scripts are)")
        print("\n🔧 The script will now look in:")
        print("  - YoloV4-Tiny_model/ for fire model")
        print("  - YoloV4-Tiny_model/yolo_pretrained_files/ for COCO model")
        return
    
    # Show available models
    print(f"\n🎯 Found {len(models)} complete model(s):")
    for model_type, model_info in models.items():
        print(f"  ✅ {model_info['name']} ({model_info['class_count']} classes)")
    
    # Let user choose which model to test
    if len(models) == 1:
        chosen_model = list(models.values())[0]
        print(f"\n🎯 Testing the only available model: {chosen_model['name']}")
        test_single_model(chosen_model)
    else:
        print(f"\n🎯 Choose model to test:")
        model_list = list(models.items())
        for i, (model_type, model_info) in enumerate(model_list):
            print(f"  {i+1}. {model_info['name']} ({model_info['class_count']} classes)")
        print(f"  {len(model_list)+1}. Test both models simultaneously")
        
        while True:
            try:
                choice = input("\nEnter your choice (1-{}): ".format(len(model_list)+1))
                choice = int(choice)
                if 1 <= choice <= len(model_list):
                    chosen_model = model_list[choice-1][1]
                    print(f"Selected: {chosen_model['name']}")
                    test_single_model(chosen_model)
                    break
                elif choice == len(model_list)+1:
                    print("🔄 Dual model testing selected!")
                    test_dual_models(models)
                    break
                else:
                    print("Invalid choice, please try again.")
            except ValueError:
                print("Please enter a valid number.")
    
def test_single_model(model_info):
    """Test a single model"""
    print(f"\n🔄 Loading {model_info['name']}...")
    
    # Load model
    try:
        net = cv2.dnn.readNet(model_info['weights'], model_info['cfg'])
        print(f"✅ {model_info['name']} loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load {model_info['name']}: {e}")
        return
    
    # Set backend with fallback
    try:
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    except Exception as e:
        print(f"⚠️  Using fallback backend: {e}")
        try:
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_DEFAULT)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        except:
            print("⚠️  Using default backend settings")
    
    # Load classes
    classes = load_classes(model_info['names'], model_info['name'])
    if not classes:
        print(f"❌ Could not load classes for {model_info['name']}")
        return
    
    # Test camera
    working_cameras = test_camera_access()
    if not working_cameras:
        print("❌ No working cameras found!")
        return
    
    camera_idx, backend_id, backend_name, cam_width, cam_height = working_cameras[0]
    print(f"📹 Using camera {camera_idx} with {backend_name}")
    
    # Open camera
    cap = cv2.VideoCapture(camera_idx, backend_id)
    if not cap.isOpened():
        print("❌ Failed to open camera")
        return
    
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    print(f"✅ Testing {model_info['name']}")
    print("Controls: q=quit, +/-=adjust confidence, SPACE=screenshot")
    
    # Use a slightly lower COCO default threshold to improve recall
    confidence_threshold = 0.3 if 'fire' in model_info['name'].lower() else 0.4
    nms_threshold = 0.4
    frame_count = 0
    
    output_layers = get_output_layers(net)
    
    # Ensure overlay/window title text is ASCII-only
    display_name = safe_ascii(model_info['name'])
    # Define and prepare the window so it appears on top and in view
    window_name = f'{display_name} Test'
    ensure_window_on_top(window_name, x=100, y=100, w=640, h=480)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        
        frame_count += 1
        height, width = frame.shape[:2]
        
        # Detection
        blob = cv2.dnn.blobFromImage(frame, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
        net.setInput(blob)
        
        try:
            outputs = net.forward(output_layers)
        except Exception as e:
            print(f"❌ Inference error: {e}")
            break
        
        # Process detections
        boxes = []
        confidences = []
        class_ids = []
        
        for output in outputs:
            for detection in output:
                scores = detection[5:]
                class_id = int(np.argmax(scores))
                # FIX: correct YOLO confidence uses objectness * class score
                confidence = float(detection[4] * scores[class_id])
                if confidence > confidence_threshold:
                    center_x = int(detection[0] * width)
                    center_y = int(detection[1] * height)
                    w = int(detection[2] * width)
                    h = int(detection[3] * height)
                    
                    x = int(center_x - w / 2)
                    y = int(center_y - h / 2)
                    
                    boxes.append([x, y, w, h])
                    confidences.append(confidence)
                    class_ids.append(class_id)
        
        # Apply NMS and draw
        detections_found = False
        if len(boxes) > 0:
            indexes = cv2.dnn.NMSBoxes(boxes, confidences, confidence_threshold, nms_threshold)
            
            if len(indexes) > 0:
                detections_found = True
                for i in indexes.flatten():
                    x, y, w, h = boxes[i]
                    class_id = class_ids[i]
                    confidence = confidences[i]
                    if class_id < len(classes):
                        label = classes[class_id]
                    else:
                        label = f"UNKNOWN_{class_id}"
                    # Normalize legacy COCO labels for consistent logic
                    norm_label = normalize_label(label)

                    # Color based on detection type
                    if 'fire' in model_info['name'].lower() and norm_label.lower() == 'fire':
                        color = (0, 0, 255)
                        thickness = 6
                        print(f"🔥 FIRE DETECTED: {confidence:.2f}")
                    elif norm_label.lower() in ['person']:
                        color = (0, 255, 0)
                        thickness = 3
                    elif norm_label.lower() in ['car', 'truck', 'bus', 'motorcycle']:
                        color = (255, 0, 0)
                        thickness = 3
                    else:
                        color = (255, 100, 0)
                        thickness = 2

                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, thickness)
                    cv2.putText(frame, f"{norm_label}: {confidence:.2f}", (x, y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        # Status info
        status_color = (0, 255, 0) if detections_found else (255, 255, 0)
        cv2.putText(frame, f"Model: {display_name}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"Confidence: {confidence_threshold:.2f}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"Classes: {len(classes)}", (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        
        # Use ASCII-only window title
        cv2.imshow(window_name, frame)
        
        # Controls
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('+') or key == ord('='):
            confidence_threshold = min(0.95, confidence_threshold + 0.05)
            print(f"Confidence: {confidence_threshold:.2f}")
        elif key == ord('-'):
            confidence_threshold = max(0.05, confidence_threshold - 0.05)
            print(f"Confidence: {confidence_threshold:.2f}")
        elif key == ord(' '):
            screenshot_name = f"{model_info['name'].lower().replace(' ', '_')}_screenshot_{frame_count}.jpg"
            cv2.imwrite(screenshot_name, frame)
            print(f"📷 Screenshot saved: {screenshot_name}")
    
    cap.release()
    cv2.destroyAllWindows()

def test_dual_models(models):
    """Test both models simultaneously - Professional dual detection system"""
    if len(models) < 2:
        print("❌ Need both fire and COCO models for dual testing")
        return
    
    print("\n🎯 PROFESSIONAL DUAL MODEL SYSTEM")
    print("   🔥 Fire detection model (1 class)")
    print("   📦 COCO detection model (80 classes)")
    print("   🤝 Combined detection system")
    
    # Load both models
    loaded_models = {}
    for model_type, model_info in models.items():
        try:
            print(f"\n🔄 Loading {model_info['name']}...")
            net = cv2.dnn.readNet(model_info['weights'], model_info['cfg'])
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)  # FIXED: Correct constant
            classes = load_classes(model_info['names'], model_info['name'])
            
            loaded_models[model_type] = {
                'net': net,
                'classes': classes,
                'info': model_info,
                'output_layers': get_output_layers(net)
            }
            print(f"✅ {model_info['name']} loaded successfully")
        except Exception as e:
            print(f"❌ Failed to load {model_info['name']}: {e}")
            # ADDED: Try fallback target
            try:
                print(f"🔄 Trying fallback backend for {model_info['name']}...")
                net = cv2.dnn.readNet(model_info['weights'], model_info['cfg'])
                net.setPreferableBackend(cv2.dnn.DNN_BACKEND_DEFAULT)
                net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                classes = load_classes(model_info['names'], model_info['name'])
                
                loaded_models[model_type] = {
                    'net': net,
                    'classes': classes,
                    'info': model_info,
                    'output_layers': get_output_layers(net)
                }
                print(f"✅ {model_info['name']} loaded with fallback backend")
            except Exception as e2:
                print(f"❌ Fallback also failed for {model_info['name']}: {e2}")
                return
    
    # Test camera
    working_cameras = test_camera_access()
    if not working_cameras:
        print("❌ No working cameras found!")
        return
    
    camera_idx, backend_id, backend_name, cam_width, cam_height = working_cameras[0]
    cap = cv2.VideoCapture(camera_idx, backend_id)
    if not cap.isOpened():
        print("❌ Failed to open camera")
        return
    
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    print("\n🚀 DUAL MODEL DETECTION ACTIVE")
    print("Controls:")
    print("  q = quit")
    print("  + = increase confidence threshold")
    print("  - = decrease confidence threshold")
    print("  SPACE = save screenshot")
    print("  f = toggle fire model only")
    print("  c = toggle COCO model only") 
    print("  b = show both models (default)")
    
    # Detection settings
    fire_confidence = 0.25
    coco_confidence = 0.4  # was 0.5; improve recall for small objects
    frame_count = 0
    
    # Display modes
    show_fire = True
    show_coco = True
    
    # Prepare the dual-view window so it appears on top and in view
    window_name = 'Dual Model Detection - Fire + COCO'
    ensure_window_on_top(window_name, x=120, y=120, w=800, h=600)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        
        frame_count += 1
        height, width = frame.shape[:2]
        
        # Create display frame
        display_frame = frame.copy()
        
        # Run detection on both models
        all_detections = []
        detection_counts = {'fire': 0, 'coco': 0}
        
        for model_type, model_data in loaded_models.items():
            # Skip if model is disabled
            if model_type == 'fire' and not show_fire:
                continue
            if model_type == 'coco' and not show_coco:
                continue
                
            # Set model-specific confidence
            model_confidence = fire_confidence if model_type == 'fire' else coco_confidence
            
            try:
                # Prepare input
                blob = cv2.dnn.blobFromImage(frame, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
                model_data['net'].setInput(blob)
                outputs = model_data['net'].forward(model_data['output_layers'])
                
                # Process detections
                boxes = []
                confidences = []
                class_ids = []
                for output in outputs:
                    for detection in output:
                        scores = detection[5:]
                        class_id = int(np.argmax(scores))
                        # FIX: objectness * class score
                        confidence = float(detection[4] * scores[class_id])
                        if confidence > model_confidence:
                            center_x = int(detection[0] * width)
                            center_y = int(detection[1] * height)
                            w = int(detection[2] * width)
                            h = int(detection[3] * height)
                            
                            x = int(center_x - w / 2)
                            y = int(center_y - h / 2)
                            
                            boxes.append([x, y, w, h])
                            confidences.append(confidence)
                            class_ids.append(class_id)
                
                # Apply NMS
                if len(boxes) > 0:
                    indexes = cv2.dnn.NMSBoxes(boxes, confidences, model_confidence, 0.4)
                    
                    if len(indexes) > 0:
                        for i in indexes.flatten():
                            x, y, w, h = boxes[i]
                            class_id = class_ids[i]
                            confidence = confidences[i]
                            if class_id < len(model_data['classes']):
                                label = model_data['classes'][class_id]
                                # Normalize and sanitize label for UI/logic
                                label = safe_ascii(normalize_label(label))
                                if model_type == 'fire':
                                    color = (0, 0, 255)
                                    prefix = "FIRE"
                                    thickness = 6
                                    detection_counts['fire'] += 1
                                else:
                                    # Compare in lowercase to avoid case issues
                                    label_lower = label.lower()
                                    if label_lower == 'person':
                                        color = (0, 255, 0)
                                        thickness = 4
                                    elif label_lower in ['car', 'truck', 'bus', 'motorcycle']:
                                        color = (255, 0, 0)
                                        thickness = 3
                                    elif label_lower in ['cell phone', 'laptop', 'tv', 'remote']:
                                        color = (255, 255, 0)
                                        thickness = 3
                                    else:
                                        color = (255, 100, 0)
                                        thickness = 2
                                    prefix = "COCO"
                                    detection_counts['coco'] += 1
                            all_detections.append({
                                'box': [x, y, w, h],
                                'label': f"{prefix} {label}",
                                'confidence': confidence,
                                'color': color,
                                'thickness': thickness,
                                'model': model_type
                            })
            except Exception as e:
                print(f"⚠️  Detection error for {model_type} model: {e}")
                continue
        
        # Draw all detections
        for det in all_detections:
            x, y, w, h = det['box']
            cv2.rectangle(display_frame, (x, y), (x + w, y + h), det['color'], det['thickness'])
            cv2.putText(display_frame, f"{det['label']}: {det['confidence']:.2f}", 
                       (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, det['color'], 2)
        
        # FIXED: Status overlay with better detection counts
        status_y = 30
        cv2.putText(display_frame, "DUAL MODEL DETECTION SYSTEM", (10, status_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        status_y += 30
        # FIXED: Show current frame detection counts
        fire_status = f"Fire: {'ON' if show_fire else 'OFF'} ({detection_counts['fire']} detections)"
        fire_color = (0, 255, 0) if show_fire else (128, 128, 128)
        cv2.putText(display_frame, fire_status, (10, status_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, fire_color, 2)
        
        status_y += 25
        coco_status = f"COCO: {'ON' if show_coco else 'OFF'} ({detection_counts['coco']} detections)"
        coco_color = (0, 255, 0) if show_coco else (128, 128, 128)
        cv2.putText(display_frame, coco_status, (10, status_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, coco_color, 2)
        
        status_y += 25
        cv2.putText(display_frame, f"Fire Confidence: {fire_confidence:.2f}", (10, status_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        status_y += 20
        cv2.putText(display_frame, f"COCO Confidence: {coco_confidence:.2f}", (10, status_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # ADDED: Show total detections in current frame
        total_detections = len(all_detections)
        status_y += 20
        cv2.putText(display_frame, f"Total Objects: {total_detections}", (10, status_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # Show combined result
        cv2.imshow(window_name, display_frame)
        
        # Handle controls
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('+') or key == ord('='):
            fire_confidence = min(0.95, fire_confidence + 0.05)
            coco_confidence = min(0.95, coco_confidence + 0.05)
            print(f"Confidence: Fire={fire_confidence:.2f}, COCO={coco_confidence:.2f}")
        elif key == ord('-'):
            fire_confidence = max(0.05, fire_confidence - 0.05)
            coco_confidence = max(0.05, coco_confidence - 0.05)
            print(f"Confidence: Fire={fire_confidence:.2f}, COCO={coco_confidence:.2f}")
        elif key == ord('f'):
            show_fire = not show_fire
            show_coco = False  # Fire only mode
            print(f"🔥 Fire model: {'ON' if show_fire else 'OFF'}")
        elif key == ord('c'):
            show_coco = not show_coco  
            show_fire = False  # COCO only mode
            print(f"📦 COCO model: {'ON' if show_coco else 'OFF'}")
        elif key == ord('b'):
            show_fire = True
            show_coco = True
            print("🤝 Both models: ON")
        elif key == ord(' '):
            screenshot_name = f"dual_detection_screenshot_{frame_count}.jpg"
            cv2.imwrite(screenshot_name, display_frame)
            print(f"📷 Dual detection screenshot saved: {screenshot_name}")
    
    cap.release()
    cv2.destroyAllWindows()
    print("✅ Dual model testing completed")

# Add: ASCII sanitizer (already present) + label normalizer
def safe_ascii(text: str) -> str:
    try:
        return text.encode('ascii', 'ignore').decode()
    except Exception:
        return ''.join(ch for ch in text if ord(ch) < 128)

def normalize_label(label: str) -> str:
    """Map legacy names to standard COCO names for consistent UI/logic"""
    mapping = {
        'motorbike': 'motorcycle',
        'aeroplane': 'airplane',
        'sofa': 'couch',
        'pottedplant': 'potted plant',
        'diningtable': 'dining table',
        'tvmonitor': 'tv'
    }
    return mapping.get(label.strip().lower(), label).title() if label.islower() else mapping.get(label.strip().lower(), label)

# NEW: Ensure the OpenCV window is visible, focused, and top-most (with Windows fallback)
def ensure_window_on_top(window_name: str, x: int = 100, y: int = 100, w: int = 1280, h: int = 720):
    try:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.moveWindow(window_name, x, y)
        cv2.resizeWindow(window_name, w, h)
        if hasattr(cv2, 'WND_PROP_TOPMOST'):
            cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
    except Exception:
        pass
    # Windows-specific fallback using WinAPI
    try:
        import sys
        if sys.platform.startswith('win'):
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, window_name)
            if hwnd:
                SW_RESTORE = 9
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetForegroundWindow(hwnd)
                HWND_TOPMOST = -1  # (HWND)-1
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
    except Exception:
        pass

if __name__ == "__main__":
    main()
    cv2.destroyAllWindows()