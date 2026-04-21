# YOLOv4-tiny — Fire Hazard Detection Model

## Classes (order matters):
0: stove
1: candle

## Files included:
- All training weights (.weights)
- yolov4-tiny-custom.cfg
- obj.names
- obj.data
- metadata.json
- map_results.txt (mAP evaluation results)

## Example inference command:
./darknet detector test obj.data yolov4-tiny-custom.cfg yolov4-tiny-custom_10000.weights -thresh 0.25 -ext_output -dont_show