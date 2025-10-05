import os
import zipfile
import shutil
import glob

def extract_yolo_zip():
    """Extract fire model export zip and replace the contents of YoloV4-Tiny_model/yolo_fire_files"""
    
    current_dir = os.getcwd()
    # Extract directly into the user's existing YOLO folder
    yolo_extracted_dir = os.path.join(current_dir, "YoloV4-Tiny_model", "yolo_fire_files")
    tmp_extract_dir = os.path.join(current_dir, "__yolo_tmp_extract__")
    
    # Look for fire model export zip files (your recent training results)
    zip_patterns = [
        "fire_model_export_*.zip",
        "*fire*.zip",
        "yolov4_training_export_*.zip",
        "yolov4tiny_export.zip",  # prefer this exact name if present
        "*training_export*.zip",
        "*.zip"
    ]
    
    zip_file = None
    for pattern in zip_patterns:
        zip_files = glob.glob(pattern)
        if zip_files:
            # Get the most recent zip file
            zip_file = max(zip_files, key=os.path.getmtime)
            print(f"Found fire model export: {zip_file}")
            break
    
    if not zip_file:
        print("ERROR: No zip file found in current directory")
        print("Please ensure your fire_model_export_*.zip is in this directory")
        return

    # Ensure target folder exists and is emptied (do NOT create a new sibling folder)
    os.makedirs(yolo_extracted_dir, exist_ok=True)
    print(f"Replacing contents of: {yolo_extracted_dir}")
    for entry in os.listdir(yolo_extracted_dir):
        path = os.path.join(yolo_extracted_dir, entry)
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except Exception as e:
            print(f"  Could not remove {path}: {e}")

    # Extract zip to a temp folder, then move its CONTENTS into yolo_fire_files (flatten one top-level dir, if any)
    try:
        if os.path.exists(tmp_extract_dir):
            shutil.rmtree(tmp_extract_dir)
        os.makedirs(tmp_extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            print(f"Extracting {zip_file} to temporary folder...")
            zip_ref.extractall(tmp_extract_dir)

        # Flatten if the zip contains a single top-level directory
        top = os.listdir(tmp_extract_dir)
        if len(top) == 1 and os.path.isdir(os.path.join(tmp_extract_dir, top[0])):
            source_root = os.path.join(tmp_extract_dir, top[0])
        else:
            source_root = tmp_extract_dir

        # Move all extracted items into the real target folder
        for item in os.listdir(source_root):
            shutil.move(os.path.join(source_root, item), os.path.join(yolo_extracted_dir, item))

        # Build list of extracted files from the target (used by the existing reporting logic)
        extracted_files = []
        for r, _, files in os.walk(yolo_extracted_dir):
            for f in files:
                extracted_files.append(os.path.relpath(os.path.join(r, f), yolo_extracted_dir))

        shutil.rmtree(tmp_extract_dir, ignore_errors=True)
        print(f"Successfully extracted all contents to {yolo_extracted_dir}")

        # Organize by file type based on your structure
        weights = [f for f in extracted_files if f.endswith('.weights')]
        configs = [f for f in extracted_files if f.endswith('.cfg')]
        data_files = [f for f in extracted_files if f.endswith('.names') or f.endswith('.data')]
        guides = [f for f in extracted_files if f.endswith('.txt')]
        scripts = [f for f in extracted_files if f.endswith('.py')]
        logs = [f for f in extracted_files if 'training.log' in f]
        
        if weights:
            print(f"\n🔥 Fire model weights ({len(weights)}):")
            for w in weights:
                full_path = os.path.join(yolo_extracted_dir, w)
                if os.path.exists(full_path):
                    size = os.path.getsize(full_path) / (1024*1024)
                    # Identify the best model
                    if 'best' in w:
                        print(f"  ⭐ {w} ({size:.1f} MB) - BEST MODEL")
                    elif 'final' in w:
                        print(f"  🏁 {w} ({size:.1f} MB) - Final model")
                    else:
                        print(f"  📦 {w} ({size:.1f} MB)")
                else:
                    print(f"  ❌ {w} (file missing!)")
                    
        if configs:
            print(f"\n⚙️  Fire model configs ({len(configs)}):")
            for c in configs:
                print(f"  - {c}")
                
        if data_files:
            print(f"\n📋 Fire model data files ({len(data_files)}):")
            for d in data_files:
                full_path = os.path.join(yolo_extracted_dir, d)
                if d.endswith('.names') and os.path.exists(full_path):
                    try:
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                            class_count = len([line for line in f if line.strip()])
                        print(f"  - {d} ({class_count} class{'es' if class_count != 1 else ''})")
                    except:
                        print(f"  - {d}")
                else:
                    print(f"  - {d}")
                    
        if guides:
            print(f"\n📖 Documentation ({len(guides)}):")
            for g in guides:
                print(f"  - {g}")
                
        if scripts:
            print(f"\n🐍 Python scripts ({len(scripts)}):")
            for s in scripts:
                print(f"  - {s}")
                
        if logs:
            print(f"\n📊 Training logs ({len(logs)}):")
            for l in logs:
                print(f"  - {l}")
        
    except zipfile.BadZipFile:
        print(f"ERROR: {zip_file} is not a valid zip file")
        return
    except Exception as e:
        print(f"ERROR extracting zip file: {e}")
        return
    
    # CRITICAL: Analyze the fire detection model files
    print("\n🔍 Analyzing fire detection model...")
    
    # Find the best trained weights
    best_weights = None
    all_weights = []
    
    for root, dirs, files in os.walk(yolo_extracted_dir):
        for file in files:
            if file.endswith('.weights'):
                full_path = os.path.join(root, file)
                size = os.path.getsize(full_path) / (1024*1024)
                all_weights.append((file, full_path, size))
                
                # Priority: best > final > last > numbered
                if 'best' in file.lower():
                    best_weights = (file, full_path, size)
                elif best_weights is None and 'final' in file.lower():
                    best_weights = (file, full_path, size)
                elif best_weights is None and 'last' in file.lower():
                    best_weights = (file, full_path, size)
    
    if best_weights:
        name, path, size = best_weights
        print(f"🏆 Best fire model: {name} ({size:.1f} MB)")
        print(f"   Location: {os.path.relpath(path, yolo_extracted_dir)}")
    else:
        print("⚠️  No fire model weights found!")
    
    # Find fire-only config
    fire_config = None
    for root, dirs, files in os.walk(yolo_extracted_dir):
        for file in files:
            if file.endswith('.cfg') and 'fire' in file.lower():
                full_path = os.path.join(root, file)
                fire_config = (file, full_path)
                break
    
    if fire_config:
        name, path = fire_config
        print(f"⚙️  Fire config: {name}")
        print(f"   Location: {os.path.relpath(path, yolo_extracted_dir)}")
        
        # Analyze config to confirm it's for fire detection
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                config_content = f.read()
                if 'classes=1' in config_content:
                    print("   ✅ Confirmed: 1-class fire-only model")
                elif 'classes=81' in config_content:
                    print("   ✅ Confirmed: 81-class model (80 COCO + 1 fire)")
                else:
                    # Count classes in config
                    import re
                    classes_matches = re.findall(r'classes\s*=\s*(\d+)', config_content)
                    if classes_matches:
                        class_count = classes_matches[0]
                        print(f"   📊 Classes: {class_count}")
        except:
            print("   ⚠️  Could not analyze config file")
    
    # Find fire names file
    fire_names = None
    for root, dirs, files in os.walk(yolo_extracted_dir):
        for file in files:
            if file.endswith('.names'):
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        classes = [line.strip() for line in f if line.strip()]
                    
                    if len(classes) == 1 and 'fire' in classes[0].lower():
                        fire_names = (file, full_path, classes)
                        break
                except:
                    pass
    
    if fire_names:
        name, path, classes = fire_names
        print(f"📋 Fire names: {name}")
        print(f"   Classes: {', '.join(classes)}")
        print(f"   Location: {os.path.relpath(path, yolo_extracted_dir)}")
    
    # Check for deployment guide
    deployment_guide = None
    for root, dirs, files in os.walk(yolo_extracted_dir):
        for file in files:
            if 'deployment' in file.lower() and file.endswith('.txt'):
                full_path = os.path.join(root, file)
                deployment_guide = (file, full_path)
                break
    
    if deployment_guide:
        name, path = deployment_guide
        print(f"📖 Deployment guide: {name}")
        print(f"   Location: {os.path.relpath(path, yolo_extracted_dir)}")
    
    # Check for inference script
    inference_script = None
    for root, dirs, files in os.walk(yolo_extracted_dir):
        for file in files:
            if 'fire_inference' in file.lower() and file.endswith('.py'):
                full_path = os.path.join(root, file)
                inference_script = (file, full_path)
                break
    
    if inference_script:
        name, path = inference_script
        print(f"🐍 Inference script: {name}")
        print(f"   Location: {os.path.relpath(path, yolo_extracted_dir)}")
    
    # Show final directory structure (print the actual folder name instead of 'yolo_extracted/')
    print("\n📁 Final directory structure:")
    for root, dirs, files in os.walk(yolo_extracted_dir):
        level = root.replace(yolo_extracted_dir, '').count(os.sep)
        indent = ' ' * 2 * level
        rel_path = os.path.relpath(root, yolo_extracted_dir)
        if rel_path == '.':
            print(f"{indent}{os.path.basename(yolo_extracted_dir)}/")
        else:
            print(f"{indent}{rel_path}/")
        subindent = ' ' * 2 * (level + 1)
        for file in sorted(files):
            file_path = os.path.join(root, file)
            size = os.path.getsize(file_path)
            if size > 1024*1024:
                print(f"{subindent}{file} ({size/1024/1024:.1f} MB)")
            elif file.endswith('.weights'):
                print(f"{subindent}{file} ({size/1024:.0f} KB)")
            else:
                print(f"{subindent}{file}")

    print(f"\n🎉 Fire model extraction complete!")
    
    # FINAL ASSESSMENT
    has_weights = best_weights is not None
    has_config = fire_config is not None
    has_names = fire_names is not None
    
    if has_weights and has_config and has_names:
        print("\n🔥 SUCCESS! Complete fire detection model found!")
        print("✅ Your fire-only model (54.76% mAP) is ready!")
        print("✅ Use this ALONGSIDE your existing COCO model")
        print("✅ Zero risk to your existing detection capabilities")
        print("\n📦 Model components:")
        if best_weights:
            print(f"   🏆 Weights: {best_weights[0]}")
        if fire_config:
            print(f"   ⚙️  Config: {fire_config[0]}")
        if fire_names:
            print(f"   📋 Names: {fire_names[0]} ({len(fire_names[2])} class)")
        
        print("\n💡 DEPLOYMENT:")
        print("   1. Keep your existing COCO model unchanged")
        print("   2. Use this fire model for fire detection only")
        print("   3. Combine results from both models")
        print("   4. Read DEPLOYMENT_GUIDE.txt for detailed instructions")
        
    elif has_weights:
        print("\n⚠️  Partial model found - missing config or names files")
        print("Check if all files extracted properly")
    else:
        print("\n❌ No complete fire model found!")
        print("The ZIP might not contain your trained model")

if __name__ == "__main__":
    extract_yolo_zip()
