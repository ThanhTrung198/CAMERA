"""
Test best.pt model - tim imgsz phu hop
"""
import cv2
import sys
import numpy as np
sys.path.insert(0, '.')
from ultralytics import YOLO

model = YOLO('best.pt')
print(f"Classes: {model.names}")
print(f"Model task: {model.task}")
print()

# Tao face crop gia lap voi nhieu kich thuoc
for crop_size in [(80, 80), (160, 160), (200, 200), (300, 300)]:
    img = np.zeros((*crop_size, 3), dtype=np.uint8)
    # Them vung "mat" gia lap (hinh oval trang)
    h, w = crop_size
    cv2.ellipse(img, (w//2, h//2), (w//3, h//2), 0, 0, 360, (220, 190, 170), -1)

    for imgsz in [160, 320, 640]:
        results = model.predict(img, imgsz=imgsz, conf=0.10, verbose=False)
        boxes = results[0].boxes
        if boxes is not None and len(boxes) > 0:
            for b in boxes:
                cls = int(b.cls[0])
                conf = float(b.conf[0])
                print(f"crop={crop_size} imgsz={imgsz}: DETECT {model.names[cls]} conf={conf:.3f}")
        else:
            print(f"crop={crop_size} imgsz={imgsz}: no detection")

print()
print("Test voi toan bo frame (640x480):")
full_frame = np.zeros((480, 640, 3), dtype=np.uint8)
cv2.ellipse(full_frame, (320, 240), (120, 160), 0, 0, 360, (220, 190, 170), -1)
for imgsz in [160, 320, 640]:
    results = model.predict(full_frame, imgsz=imgsz, conf=0.10, verbose=False)
    boxes = results[0].boxes
    if boxes is not None and len(boxes) > 0:
        for b in boxes:
            cls = int(b.cls[0])
            conf = float(b.conf[0])
            print(f"  full_frame imgsz={imgsz}: DETECT {model.names[cls]} conf={conf:.3f}")
    else:
        print(f"  full_frame imgsz={imgsz}: no detection")

print("\nDONE")
