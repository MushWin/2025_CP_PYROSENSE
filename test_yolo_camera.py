# test_yolo_camera.py — robust backend (CUDA -> CPU fallback) + correct confidence
import cv2
import numpy as np
import os
from glob import glob

def find_model_files():
    """Find model files in both fire_extracted_files (fire) and yolo_pretrained_files (COCO) directories"""
    current_dir = os.getcwd()

    # Fire model directory (your trained fire detector)
    # Now stored inside the YoloV4-Tiny_Model folder
    fire_dir = os.path.join(current_dir, "YoloV4-Tiny_Model", "fire_extracted_files")

    models = {}

    # Use the generic scanner so we pick up any .cfg/.weights/.names under the fire directory
    if os.path.exists(fire_dir):
        print(f"📁 Scanning Fire model directory: {fire_dir}")
        fire_model = scan_model_directory(fire_dir, "🔥 FIRE MODEL")
        if fire_model['complete']:
            fire_model['name'] = "🔥 FIRE MODEL"
            models['fire'] = fire_model
        else:
            print(f"❌ Fire model files not found or incomplete in: {fire_dir}")
            print("  Scanned for .cfg/.weights/.names and reported above.")
    else:
        print(f"❌ Fire model directory not found: {fire_dir}")

    # COCO model directory (original pretrained)
    coco_dir = os.path.join(current_dir, "yolo_pretrained_files")

    # Check COCO model directory  
    if os.path.exists(coco_dir):
        print(f"📁 Scanning COCO model directory: {coco_dir}")
        coco_model = scan_model_directory(coco_dir, "📦 COCO MODEL")
        if coco_model['complete']:
            models['coco'] = coco_model
    else:
        print(f"❌ COCO model directory not found: {coco_dir}")
        
        # ADDED: Show available directories for debugging
        print(f"\n🔍 Available directories:")
        try:
            for item in os.listdir(current_dir):
                item_path = os.path.join(current_dir, item)
                if os.path.isdir(item_path):
                    print(f"  📂 {item}/")
        except:
            pass
    
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
            if file.endswith(('.cfg', '.weights', '.names', '.data', '.log')):
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
    data_files = []
    
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            full_path = os.path.join(root, file)
            if file.endswith('.cfg'):
                cfg_files.append(full_path)
            elif file.endswith('.weights'):
                weights_files.append(full_path)
            elif file.endswith('.names'):
                names_files.append(full_path)
            elif file.endswith('.data'):
                data_files.append(full_path)
    
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
        # For fire model, prefer enhanced configs in cfg/ subdirectory
        fire_cfg_priorities = [
            'yolov4-tiny-enhanced.cfg',
            'yolov4-tiny-fire-enhanced.cfg',
            'yolov4-tiny-fire-only.cfg',
            'yolov4-tiny-fire.cfg',
            'fire.cfg'
        ]
        for priority in fire_cfg_priorities:
            for cfg in cfg_files:
                if priority == os.path.basename(cfg).lower():
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
        # For fire model, prefer enhanced weights in weights/ subdirectory
        fire_weight_priorities = [
            'yolov4-tiny-fire-enhanced_best.weights',
            'yolov4-tiny-enhanced_best.weights',
            'yolov4-tiny-fire-enhanced_last.weights',
            'yolov4-tiny-enhanced_last.weights',
            'yolov4-tiny-fire-enhanced_final.weights',
            'yolov4-tiny-enhanced_final.weights',
            'enhanced_best.weights',
            'best.weights', 
            'final.weights', 
            'last.weights', 
            'obj.weights'
        ]
        for priority in fire_weight_priorities:
            for weight in weights_files:
                if priority == os.path.basename(weight).lower():
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
    
    # Select names file - prefer enhanced names in data/ subdirectory
    if names_files:
        # Try to find the most appropriate names file
        best_names = None
        # UPDATED: Handle both 1-class fire and 44-class enhanced models
        target_classes = 44 if 'enhanced' in model_name.lower() else 1

        # For fire model, prioritize enhanced names
        if 'fire' in model_name.lower():
            enhanced_priorities = [
                'enhanced_obj.names',
                'obj.names',
                'fire.names'
            ]
            for priority in enhanced_priorities:
                for names_file in names_files:
                    if priority == os.path.basename(names_file).lower():
                        best_names = names_file
                        try:
                            with open(names_file, 'r', encoding='utf-8', errors='ignore') as f:
                                classes = [line.strip() for line in f if line.strip()]
                            model_info['class_count'] = len(classes)
                            print(f"   🔍 Found {len(classes)} classes in {os.path.basename(names_file)}")
                        except:
                            pass
                        break
                if best_names:
                    break
        
        # If no enhanced names found or for COCO model, use original logic
        if not best_names:
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
            print(f"📋 Fire model classes: {classes[:10]}{'...' if len(classes) > 10 else ''}")
            
            # ADDED: Debug class mapping for 44-class model
            if len(classes) == 44:
                print(f"🔍 DEBUGGING 44-CLASS MODEL:")
                print(f"   Class 0 (should be fire): {classes[0]}")
                print(f"   Class 1 (should be person): {classes[1] if len(classes) > 1 else 'Missing'}")
                print(f"   Class 2 (should be car): {classes[2] if len(classes) > 2 else 'Missing'}")
                print(f"   ⚠️  Your phone/face detected as 'car' = Class {classes.index('car') if 'car' in classes else 'NOT_FOUND'}")
                
                # Show which class index corresponds to common objects
                common_objects = ['fire', 'person', 'car', 'cell_phone', 'laptop', 'chair']
                print(f"   🔍 Class index mapping:")
                for obj in common_objects:
                    if obj in classes:
                        idx = classes.index(obj)
                        print(f"      {obj} = Class {idx}")
                    else:
                        print(f"      {obj} = NOT FOUND")
                        
                print(f"   🚨 ISSUE: Model is probably outputting wrong class IDs!")
                print(f"   💡 Solution: Need to retrain with proper class mapping")
            
            if len(classes) == 1 and 'fire' in classes[0].lower():
                print("🔥 CONFIRMED: Fire-only detection model")
            elif len(classes) > 1:
                print(f"🏠 CONFIRMED: Enhanced fire + fire-hazard model ({len(classes)} classes)")
                # Show fire and some key hazard classes
                fire_class = next((i for i, c in enumerate(classes) if 'fire' in c.lower()), None)
                if fire_class is not None:
                    print(f"   🔥 Fire class at index {fire_class}: {classes[fire_class]}")
                else:
                    print(f"   ⚠️  WARNING: No 'fire' class found in {len(classes)}-class model!")
                
                # Show some key hazard classes
                hazard_samples = [c for c in classes[1:6] if 'fire' not in c.lower()]
                if hazard_samples:
                    print(f"   🏠 Sample hazards: {', '.join(hazard_samples)}")
            else:
                print(f"⚠️  Unexpected class count: {len(classes)} classes")
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

def debug_fire_model_files():
    """Print fire model file paths and contents for verification."""
    import os
    from glob import glob
    # Debug helper should point at the nested location
    fire_dir = os.path.join(os.getcwd(), "YoloV4-Tiny_Model", "fire_extracted_files")
    print("\n--- FIRE MODEL FILES ---")
    if not os.path.exists(fire_dir):
        print("Directory not found:", fire_dir)
        print("--- END FIRE MODEL FILES ---\n")
        return

    # Find any cfg/weights/names under the directory (recursive)
    cfgs = glob(os.path.join(fire_dir, "**", "*.cfg"), recursive=True)
    weights = glob(os.path.join(fire_dir, "**", "*.weights"), recursive=True)
    names = glob(os.path.join(fire_dir, "**", "*.names"), recursive=True)

    print("Found cfg files:")
    for p in cfgs:
        print("  ", p)
    print("Found weights files:")
    for p in weights:
        size = os.path.getsize(p) if os.path.exists(p) else 0
        print(f"  {p}  ({size/1024/1024:.2f} MB)" if size else f"  {p}")
    print("Found names files:")
    for p in names:
        print("  ", p)

    # Prefer common filenames if present
    chosen_cfg = next((p for p in cfgs if os.path.basename(p).lower().startswith("yolov4")), cfgs[0] if cfgs else None)
    chosen_weights = next((p for p in weights if "best" in os.path.basename(p).lower() or "final" in os.path.basename(p).lower()), weights[0] if weights else None)
    chosen_names = next((p for p in names if os.path.basename(p).lower().startswith("obj") or "names" in os.path.basename(p).lower()), names[0] if names else None)

    print("\nPreferred selection (if exists):")
    print("Config:", chosen_cfg, "| Exists:", os.path.exists(chosen_cfg) if chosen_cfg else False)
    print("Weights:", chosen_weights, "| Exists:", os.path.exists(chosen_weights) if chosen_weights else False)
    print("Names:", chosen_names, "| Exists:", os.path.exists(chosen_names) if chosen_names else False)

    if chosen_names and os.path.exists(chosen_names):
        print("\nobj.names contents:")
        with open(chosen_names, encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                print(f"  {i}: {line.strip()}")
    if chosen_cfg and os.path.exists(chosen_cfg):
        print("\nFirst 10 lines of cfg:")
        with open(chosen_cfg, encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                if i >= 10: break
                print(line.strip())
    print("--- END FIRE MODEL FILES ---\n")

def main():
    print("🔥 DUAL MODEL TESTING - Fire Detection + COCO Detection")
    print("=" * 60)
    
    # Find both models
    models = find_model_files()
    
    if not models:
        print("❌ No complete models found!")
        print("\n💡 Make sure you have:")
        print("  - YoloV4-Tiny_Model/fire_extracted_files/ folder (your trained fire model)")
        print("  - yolo_pretrained_files/ folder (original COCO model)")  # FIXED
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
    print("Controls: q=quit, +/-=adjust confidence, SPACE=screenshot, r=class report")
    
    # FIXED: Proper confidence thresholds for 44-class model
    if len(classes) == 44:
        print(f"\n✅ DETECTED YOUR 44-CLASS ENHANCED MODEL!")
        print(f"   🎯 This model is working perfectly")
        print(f"   🔧 Using CORRECT confidence threshold for 44 classes")
        confidence_threshold = 0.15  # CORRECT threshold for 44-class model
        print(f"   📊 Starting confidence: {confidence_threshold}")
        print(f"   💡 Your model will now detect people properly!")
    elif 'fire' in model_info['name'].lower():
        if model_info['class_count'] > 10:  # Enhanced model with many classes
            confidence_threshold = 0.25  # Proper threshold for multi-class
            print(f"🏠 Enhanced model detected - using confidence threshold: {confidence_threshold}")
        else:  # Original fire-only model
            confidence_threshold = 0.3
            print(f"🔥 Fire-only model detected - using confidence threshold: {confidence_threshold}")
    else:
        confidence_threshold = 0.5  # COCO model
    
    nms_threshold = 0.4
    frame_count = 0
    
    output_layers = get_output_layers(net)
    
    min_person_area = 5000  # Minimum area for person detection (tune as needed)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        # --- MIRROR CAMERA ---
        frame = cv2.flip(frame, 1)  # Mirror horizontally

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
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                
                if confidence > confidence_threshold:
                    center_x = int(detection[0] * width)
                    center_y = int(detection[1] * height)
                    w = int(detection[2] * width)
                    h = int(detection[3] * height)
                    
                    x = int(center_x - w / 2)
                    y = int(center_y - h / 2)
                    
                    # Filter small person boxes
                    if class_id < len(classes) and classes[class_id].lower() == "person":
                        if w * h < min_person_area:
                            continue  # Skip small person detections
                    
                    boxes.append([x, y, w, h])
                    confidences.append(float(confidence))
                    class_ids.append(class_id)
        
        # Apply NMS and draw
        detections_found = False
        detection_debug = []  # ADDED: Debug detection info
        
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
                    
                    # ADDED: Debug info for problematic detections
                    detection_debug.append(f"Class {class_id}: {label} ({confidence:.2f})")
                    
                    # UPDATED: Enhanced color coding for 44-class model
                    if label.lower() == 'fire':
                        color = (0, 0, 255)  # Red for fire
                        thickness = 6
                        print(f"🔥 FIRE DETECTED: {confidence:.2f}")
                    elif label.lower() == 'person':
                        color = (0, 255, 0)  # Green for person
                        thickness = 4
                        # ADDED: Debug for person detection
                        if len(classes) == 44:
                            print(f"👤 PERSON detected: {confidence:.2f} (Class {class_id})")
                    elif label.lower() == 'car':
                        color = (255, 0, 0)  # Blue for car
                        thickness = 3
                        # ADDED: Debug for car misclassification
                        if len(classes) == 44:
                            print(f"🚗 CAR detected: {confidence:.2f} (Class {class_id}) - ❓ Is this correct?")
                    elif label.lower() == 'cell_phone':
                        color = (255, 255, 0)  # Yellow for phone
                        thickness = 3
                        print(f"📱 PHONE detected: {confidence:.2f} (Class {class_id})")
                    elif label.lower() in ['stove', 'oven', 'candle', 'fireplace']:
                        color = (0, 140, 255)  # Orange for high-risk items
                        thickness = 4
                        print(f"⚡ HIGH RISK: {label} detected ({confidence:.2f})")
                    elif label.lower() in ['laptop', 'microwave_oven', 'television', 'toaster']:
                        color = (0, 255, 255)  # Yellow for electrical items
                        thickness = 3
                    elif label.lower() in ['motorcycle', 'truck', 'bus']:
                        color = (255, 0, 0)  # Blue for vehicles
                        thickness = 3
                    else:
                        color = (255, 100, 0)  # Light blue for other objects
                        thickness = 2
                    
                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, thickness)
                    cv2.putText(frame, f"{label}: {confidence:.2f}", (x, y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                    # ADDED: Show class ID for debugging
                    cv2.putText(frame, f"ID:{class_id}", (x, y + h + 20),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        
        # ADDED: Print debug info every few frames
        if detections_found and frame_count % 30 == 0 and len(classes) == 44:
            print(f"🔍 Frame {frame_count} detections: {'; '.join(detection_debug[:3])}")
        
        # UPDATED: Better status display for enhanced model
        status_color = (0, 255, 0) if detections_found else (255, 255, 0)
        cv2.putText(frame, f"Model: {model_info['name']}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"Confidence: {confidence_threshold:.2f}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"Classes: {len(classes)}", (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        
        # Show model type and status
        if len(classes) > 10:
            if len(classes) == 44:
                cv2.putText(frame, "Enhanced: 44 classes (WORKING!)", (10, 120),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)  # Green text - working
            else:
                cv2.putText(frame, "Enhanced: Fire + Hazards", (10, 120),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        else:
            cv2.putText(frame, "Fire Detection Only", (10, 120),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # FIXED: Remove conflicting warning messages for 44-class model
        if len(classes) == 44:
            cv2.putText(frame, "Model works! Confidence: 0.15", (10, 150),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.putText(frame, "Press 'r' for class mapping", (10, 170),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
    
        # ADDED: Show class mapping issue warning
        if len(classes) == 44:
            cv2.putText(frame, "WARNING: Possible class mapping issue", (10, 150),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            cv2.putText(frame, "Press 'r' for class mapping report", (10, 170),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        
        cv2.imshow(f'{model_info["name"]} Test', frame)
        
        # Controls
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r') and len(classes) == 44:
            # ADDED: Print full class mapping report
            print(f"\n📋 FULL CLASS MAPPING REPORT:")
            for i, class_name in enumerate(classes):
                print(f"   Class {i:2d}: {class_name}")
            print(f"\n💡 This helps debug why your face/phone is detected as 'car'")
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
    
    # Detection settings - UPDATED for enhanced model
    fire_confidence = 0.15   # CORRECT threshold for 44-class model
    coco_confidence = 0.5    # Standard COCO threshold
    frame_count = 0
    
    # Display modes
    show_fire = True
    show_coco = True
    
    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        # --- MIRROR CAMERA ---
        frame = cv2.flip(frame, 1)  # Mirror horizontally

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
                
            # FIXED: Proper confidence for 44-class model in dual mode
            fire_confidence = 0.15   # CORRECT threshold for 44-class model
            coco_confidence = 0.5    # Standard COCO threshold
            
            # UPDATED: Better confidence handling for enhanced model
            if model_type == 'fire':
                # Use correct confidence for 44-class model
                if len(model_data['classes']) == 44:
                    model_confidence = 0.15  # CORRECT for 44-class model
                elif len(model_data['classes']) > 10:
                    model_confidence = 0.25  # Multi-class model
                else:
                    model_confidence = fire_confidence  # Original fire model
            else:
                model_confidence = coco_confidence
            
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
                        class_id = np.argmax(scores)
                        confidence = scores[class_id]
                        
                        if confidence > model_confidence:
                            center_x = int(detection[0] * width)
                            center_y = int(detection[1] * height)
                            w = int(detection[2] * width)
                            h = int(detection[3] * height)
                            
                            x = int(center_x - w / 2)
                            y = int(center_y - h / 2)
                            
                            boxes.append([x, y, w, h])
                            confidences.append(float(confidence))
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
                                
                                # Color and prefix by model type
                                if model_type == 'fire':
                                    # UPDATED: Better handling for enhanced fire model
                                    if label.lower() == 'fire':
                                        color = (0, 0, 255)  # Red for fire
                                        prefix = "🔥 FIRE"
                                        thickness = 6
                                        detection_counts['fire'] += 1
                                        if frame_count % 30 == 0:
                                            print(f"🔥 FIRE DETECTED: {confidence:.2f}")
                                    elif label.lower() in ['stove', 'oven', 'candle', 'fireplace']:
                                        color = (0, 140, 255)  # Orange for high-risk
                                        prefix = "⚡ HAZARD"
                                        thickness = 5
                                        detection_counts['fire'] += 1
                                    else:
                                        color = (0, 255, 255)  # Yellow for other hazards
                                        prefix = "🏠 HAZARD"
                                        thickness = 3
                                        detection_counts['fire'] += 1
                                else:
                                    # COCO model colors
                                    if label == 'person':
                                        color = (0, 255, 0)  # Green for person
                                        thickness = 4
                                    elif label in ['car', 'truck', 'bus', 'motorcycle']:
                                        color = (255, 0, 0)  # Blue for vehicles
                                        thickness = 3
                                    elif label in ['cell phone', 'laptop', 'tv', 'remote']:
                                        color = (255, 255, 0)  # Cyan for electronics
                                        thickness = 3
                                    else:
                                        color = (255, 100, 0)  # Orange for other objects
                                        thickness = 2
                                    
                                    # FIXED: Remove ??? prefix
                                    prefix = "COCO"
                                    # FIXED: Update detection count properly
                                    detection_counts['coco'] += 1
                                
                                # Store detection for drawing
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
        cv2.imshow('Dual Model Detection - Fire + COCO', display_frame)
        
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

if __name__ == "__main__":
    debug_fire_model_files()
    main()
    cv2.destroyAllWindows()
