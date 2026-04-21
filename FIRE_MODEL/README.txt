# PyroSense YOLOv4-tiny (2-class)

**Classes (order matters):**
0: fire
1: person

## Files
- yolov4-tiny-custom_best.weights — trained weights
- yolov4-tiny-custom.cfg — network config (classes=2, filters=21 at both heads)
- obj.names — class labels (fire, person)
- metadata.json — quick metadata

## Darknet inference (example)
Run these commands from the directory where the files live:
./darknet detector test /kaggle/working/obj.data yolov4-tiny-custom.cfg yolov4-tiny-custom_best.weights -thresh 0.25 -ext_output -dont_show -map

## Notes
- Ensure your runtime has CUDA/cuDNN (GPU) or run with CPU build accordingly.
- The model expects class IDs: fire=0, person=1.