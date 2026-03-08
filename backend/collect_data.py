"""
Data Collection Tool — Anti-Spoof Raw Score Logger
====================================================
Ghi log raw scores từ camera vào CSV file để phân tích.

Sử dụng:
  python collect_data.py --label real      # Chạy với mặt thật
  python collect_data.py --label phone     # Chạy với điện thoại 
  python collect_data.py --label print     # Chạy với ảnh in

Mỗi lần chạy thu thập 100 frame, lưu vào antispoof_data.csv
Nhấn q để dừng sớm.

Phân tích bằng: python analyze_data.py
"""
import cv2
import os
import sys
import csv
import time
import argparse
import numpy as np
from datetime import datetime

# ── Args ─────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--label", required=True, choices=["real", "phone_oled", "phone_lcd", "print"],
                    help="Ground truth label")
parser.add_argument("--frames", type=int, default=100, help="Number of frames to collect")
args = parser.parse_args()

# ── Patch torch.load ─────────────────────────────────────────────────────
os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD'] = '0'
import torch
_orig_load = torch.load
def _patched_load(*a, **kw):
    kw['weights_only'] = False
    return _orig_load(*a, **kw)
torch.load = _patched_load

from ultralytics import YOLO

# ── Load model ────────────────────────────────────────────────────────────
print("Loading chonggiamao.pt ...")
model = YOLO("chonggiamao.pt")
torch.load = _orig_load
print("✅ Model loaded")

# ── Haar face detector ───────────────────────────────────────────────────
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# ── Camera ────────────────────────────────────────────────────────────────
cap = cv2.VideoCapture(0)
cap.set(3, 640)
cap.set(4, 480)
time.sleep(1)

# ── CSV setup ─────────────────────────────────────────────────────────────
csv_path = "antispoof_data.csv"
file_exists = os.path.exists(csv_path)

csv_file = open(csv_path, "a", newline="", encoding="utf-8")
writer = csv.writer(csv_file)

if not file_exists:
    writer.writerow([
        "timestamp", "label", "frame_idx",
        "yolo_fake_conf", "yolo_real_conf", "yolo_n_boxes", "yolo_top_class",
        "fft_score", "color_score", "screen_score",
        "face_detected", "face_w", "face_h",
        "brightness_mean", "brightness_std",
        "inference_ms"
    ])

# ── FFT + Color screen detection ─────────────────────────────────────────
def compute_fft_score(face_bgr):
    """FFT moiré score trên face crop"""
    if face_bgr is None or face_bgr.size == 0:
        return 0.0
    try:
        resized = cv2.resize(face_bgr, (128, 128))
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY).astype(np.float32)
        fft = np.fft.fft2(gray)
        fft_shift = np.fft.fftshift(fft)
        mag = np.log1p(np.abs(fft_shift))
        
        h, w = mag.shape
        cx, cy = w // 2, h // 2
        r_inner = int(min(h, w) * 0.25)
        r_outer = int(min(h, w) * 0.48)
        Y, X = np.ogrid[:h, :w]
        dist = np.sqrt((X - cx)**2 + (Y - cy)**2)
        ring = (dist >= r_inner) & (dist <= r_outer)
        
        vals = mag[ring]
        if vals.size == 0:
            return 0.0
        mean_v = np.mean(vals)
        std_v = np.std(vals)
        thr = mean_v + 2.0 * std_v
        n_peaks = int(np.sum(vals > thr))
        return float(np.clip((n_peaks - 2) / 20.0, 0, 1))
    except:
        return 0.0

def compute_color_score(face_bgr):
    """Color gamut score trên face crop"""
    if face_bgr is None or face_bgr.size == 0:
        return 0.0
    try:
        resized = cv2.resize(face_bgr, (128, 128))
        b = resized[:, :, 0].astype(np.float32)
        g = resized[:, :, 1].astype(np.float32)
        r = resized[:, :, 2].astype(np.float32)
        total = r + g + b + 1e-6
        r_ratio = r / total
        b_ratio = b / total
        blue_excess = float(np.mean(b_ratio) - np.mean(r_ratio))
        return float(np.clip(blue_excess * 5.0 + 0.3, 0, 1))
    except:
        return 0.0


# ── Collection loop ──────────────────────────────────────────────────────
print(f"\n📊 Thu thập dữ liệu: label={args.label}, frames={args.frames}")
print(f"   Hướng camera vào {'MẶT THẬT' if args.label == 'real' else 'ĐIỆN THOẠI' if 'phone' in args.label else 'ẢNH IN'}")
print(f"   Nhấn 'q' để dừng sớm\n")

collected = 0
session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

for i in range(args.frames):
    ret, img = cap.read()
    if not ret:
        continue
    
    t0 = time.time()
    
    # ── Face detection ────────────────────────────────────────────────
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
    
    face_detected = len(faces) > 0
    face_w, face_h = 0, 0
    fft_score = 0.0
    color_score = 0.0
    
    if face_detected:
        x, y, w, h = faces[0]
        face_w, face_h = w, h
        pad = 15
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(img.shape[1], x + w + pad)
        y2 = min(img.shape[0], y + h + pad)
        face_crop = img[y1:y2, x1:x2]
        
        fft_score = compute_fft_score(face_crop)
        color_score = compute_color_score(face_crop)
    
    screen_score = 0.55 * fft_score + 0.45 * color_score
    
    # ── YOLO ──────────────────────────────────────────────────────────
    results = model(img, verbose=False, stream=True)
    
    yolo_fake = 0.0
    yolo_real = 0.0
    n_boxes = 0
    top_class = -1
    
    for r in results:
        if r.boxes is None:
            continue
        for box in r.boxes:
            conf = float(box.conf[0])
            cls = int(box.cls[0])
            n_boxes += 1
            if cls == 0:  # fake
                yolo_fake = max(yolo_fake, conf)
            else:         # real
                yolo_real = max(yolo_real, conf)
    
    if yolo_fake > yolo_real:
        top_class = 0
    elif yolo_real > 0:
        top_class = 1
    
    t1 = time.time()
    inference_ms = (t1 - t0) * 1000
    
    # ── Brightness ────────────────────────────────────────────────────
    brightness_mean = float(np.mean(gray))
    brightness_std  = float(np.std(gray))
    
    # ── Write CSV row ─────────────────────────────────────────────────
    writer.writerow([
        datetime.now().isoformat(),
        args.label,
        i,
        f"{yolo_fake:.4f}",
        f"{yolo_real:.4f}",
        n_boxes,
        top_class,
        f"{fft_score:.4f}",
        f"{color_score:.4f}",
        f"{screen_score:.4f}",
        int(face_detected),
        face_w,
        face_h,
        f"{brightness_mean:.1f}",
        f"{brightness_std:.1f}",
        f"{inference_ms:.0f}"
    ])
    csv_file.flush()
    collected += 1
    
    # ── Display ───────────────────────────────────────────────────────
    decision = "REAL" if top_class == 1 else "FAKE" if top_class == 0 else "?"
    color = (0, 255, 0) if top_class == 1 else (0, 0, 255)
    
    cv2.rectangle(img, (0, 0), (640, 65), (15, 15, 15), -1)
    cv2.putText(img, f"[{args.label}] {decision} | YOLO F={yolo_fake:.2f} R={yolo_real:.2f} | Scr={screen_score:.2f}",
                (5, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)
    cv2.putText(img, f"FFT={fft_score:.2f} Col={color_score:.2f} | Bright={brightness_mean:.0f} | {i+1}/{args.frames}",
                (5, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
    
    if face_detected:
        x, y, w, h = faces[0]
        cv2.rectangle(img, (x, y), (x+w, y+h), color, 2)
    
    cv2.imshow(f"Collecting: {args.label}", img)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

csv_file.close()
cap.release()
cv2.destroyAllWindows()

print(f"\n✅ Thu thập xong: {collected} frames, label={args.label}")
print(f"   Đã lưu vào: {csv_path}")
print(f"\n▶ Bước tiếp: chạy thêm labels khác, sau đó: python analyze_data.py")
