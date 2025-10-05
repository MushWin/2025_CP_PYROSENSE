#!/usr/bin/env python3
"""
Enhanced Fire Model Inference Script (4K Iterations)
Improved accuracy with continuation training
Use this alongside your existing COCO model
"""

import cv2
import numpy as np
import argparse

def detect_fire_enhanced(image_path, weights_path="weights/yolov4-tiny-fire-enhanced_best.weights", 
                        config_path="cfg/yolov4-tiny-fire-enhanced.cfg", confidence=0.35):
    """Detect fire using enhanced model with improved accuracy"""
    
    # Load enhanced fire model
    net = cv2.dnn.readNet(weights_path, config_path)
    
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image {image_path}")
        return []
    
    height, width = image.shape[:2]
    
    # Prepare image for detection
    blob = cv2.dnn.blobFromImage(image, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
    net.setInput(blob)
    outputs = net.forward(net.getUnconnectedOutLayersNames())
    
    # Extract enhanced fire detections
    fire_detections = []
    for output in outputs:
        for detection in output:
            scores = detection[5:]
            confidence_score = scores[0]  # Only 1 class (fire)
            
            if confidence_score > confidence:
                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)
                
                x = int(center_x - w / 2)
                y = int(center_y - h / 2)
                
                fire_detections.append({
                    'class': 'fire',
                    'confidence': confidence_score,
                    'bbox': [x, y, w, h],
                    'model': 'enhanced_4k'
                })
    
    return fire_detections

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Enhanced Fire Detection (4K iterations)')
    parser.add_argument('image', help='Path to input image')
    parser.add_argument('--confidence', type=float, default=0.35, help='Confidence threshold (higher due to better accuracy)')
    
    args = parser.parse_args()
    
    detections = detect_fire_enhanced(args.image, confidence=args.confidence)
    
    if detections:
        print(f"🔥 Enhanced model found {len(detections)} fire detection(s):")
        for i, det in enumerate(detections):
            print(f"   Fire {i+1}: confidence={det['confidence']:.3f}, bbox={det['bbox']}")
            print(f"            model={det['model']} (improved accuracy)")
    else:
        print("No fire detected with enhanced model")
