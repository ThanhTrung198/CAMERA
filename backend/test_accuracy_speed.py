# -*- coding: utf-8 -*-
"""
Test Accuracy + Speed: So sanh 3 phien ban anti-spoofing
Chay: python test_accuracy_speed.py

Su dung:
- 137 anh fake tu fake_captures/ (label = FAKE)
- 50 frame capture tu webcam (label = REAL)
"""
import cv2
import time
import numpy as np
import os
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_test_data():
    """Load test data: fake images + real webcam captures"""
    fake_dir = os.path.join(BASE_DIR, "fake_captures")
    fake_files = sorted(glob.glob(os.path.join(fake_dir, "*.jpg")))

    print(f"  Found {len(fake_files)} fake images")

    fake_images = []
    for f in fake_files[:100]:  # Max 100 fake
        img = cv2.imread(f)
        if img is not None and img.size > 0:
            fake_images.append(img)

    print(f"  Loaded {len(fake_images)} fake images")

    # Capture real faces from webcam
    print("  Capturing 50 real frames from webcam...")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("  WARNING: Cannot open webcam, using only fake data")
        return fake_images, [], fake_files[:len(fake_images)]

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    real_images = []
    for i in range(60):  # 10 warmup + 50 capture
        ret, frame = cap.read()
        if ret and frame is not None:
            if i >= 10:
                real_images.append(frame)
    cap.release()
    print(f"  Captured {len(real_images)} real frames")

    return fake_images, real_images, fake_files[:len(fake_images)]


def run_version_test(version_name, model, face_app, fake_images, real_images,
                     check_fn, preprocess_fn, imgsz):
    """Test 1 phien ban, tra ve metrics"""

    tp = 0  # True Positive (fake detected as fake)
    fp = 0  # False Positive (real detected as fake)
    tn = 0  # True Negative (real detected as real)
    fn = 0  # False Negative (fake detected as real)
    times = []

    # --- Test FAKE images ---
    for img in fake_images:
        faces = face_app.get(img)
        if not faces:
            fn += 1  # No face detected, missed fake
            continue

        f = faces[0]
        fbbox = f.bbox.astype(int).tolist()
        fx1, fy1, fx2, fy2 = fbbox
        h, w = img.shape[:2]
        crop = img[max(0, fy1):min(h, fy2), max(0, fx1):min(w, fx2)]

        if crop is None or crop.size == 0:
            fn += 1
            continue

        processed = preprocess_fn(crop, full_frame=img, face_bbox=fbbox,
                                   target_size=224, padding_ratio=0.3)

        t0 = time.time()
        is_real, conf = check_fn(processed, model, cam_id=0,
                                  full_frame=img, face_bbox=fbbox)
        t1 = time.time()
        times.append(t1 - t0)

        if not is_real:
            tp += 1  # Correctly detected fake
        else:
            fn += 1  # Missed fake

    # --- Test REAL images ---
    for img in real_images:
        faces = face_app.get(img)
        if not faces:
            tn += 1  # No face, assume correct (no false alarm)
            continue

        f = faces[0]
        fbbox = f.bbox.astype(int).tolist()
        fx1, fy1, fx2, fy2 = fbbox
        h, w = img.shape[:2]
        crop = img[max(0, fy1):min(h, fy2), max(0, fx1):min(w, fx2)]

        if crop is None or crop.size == 0:
            tn += 1
            continue

        processed = preprocess_fn(crop, full_frame=img, face_bbox=fbbox,
                                   target_size=224, padding_ratio=0.3)

        t0 = time.time()
        is_real, conf = check_fn(processed, model, cam_id=0,
                                  full_frame=img, face_bbox=fbbox)
        t1 = time.time()
        times.append(t1 - t0)

        if is_real:
            tn += 1  # Correctly detected real
        else:
            fp += 1  # False alarm on real face

    total = tp + fp + tn + fn
    accuracy = (tp + tn) / max(total, 1) * 100
    fake_total = tp + fn
    real_total = tn + fp
    fpr = fp / max(real_total, 1) * 100  # False Positive Rate
    fnr = fn / max(fake_total, 1) * 100  # False Negative Rate (miss rate)
    avg_ms = np.mean(times) * 1000 if times else 0
    med_ms = np.median(times) * 1000 if times else 0

    return {
        "version": version_name,
        "accuracy": accuracy,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "fpr": fpr, "fnr": fnr,
        "avg_ms": avg_ms, "med_ms": med_ms,
        "total": total,
    }


def check_face_real_v1_320(face_img, model, cam_id=0, full_frame=None, face_bbox=None):
    """V1: Single inference at 320px (fastest, lowest accuracy)"""
    if model is None or face_img is None or face_img.size == 0:
        return True, 0.0
    try:
        h_c, w_c = face_img.shape[:2]
        if h_c < 160 or w_c < 160:
            scale = max(160 / h_c, 160 / w_c)
            input_img = cv2.resize(face_img, (int(w_c * scale), int(h_c * scale)))
        else:
            input_img = face_img
        results = model.predict(input_img, imgsz=320, conf=0.15, verbose=False)
        bf, br = 0.0, 0.0
        for r in results:
            if r.boxes is None: continue
            for box in r.boxes:
                c = int(box.cls[0]); v = float(box.conf[0])
                if c == 0 and v > bf: bf = v
                elif c == 1 and v > br: br = v
        if bf == 0 and br == 0: return True, 0.5
        if bf >= 0.35: return False, bf
        if br >= 0.30: return True, br
        return (False, bf) if bf > br else (True, br)
    except:
        return True, 0.0


def check_face_real_v0_640(face_img, model, cam_id=0, full_frame=None, face_bbox=None):
    """V0: Original dual-inference at 640px (slowest, highest accuracy)"""
    if model is None or face_img is None or face_img.size == 0:
        return True, 0.0

    def _parse(results):
        bf, br = 0.0, 0.0
        for r in results:
            if r.boxes is None: continue
            for box in r.boxes:
                c = int(box.cls[0]); v = float(box.conf[0])
                if c == 0 and v > bf: bf = v
                elif c == 1 and v > br: br = v
        return bf, br

    def _decide(bf, br):
        if bf == 0 and br == 0: return None, 0.0
        if bf >= 0.35: return False, bf
        if br >= 0.30: return True, br
        return (False, bf) if bf > br else (True, br)

    try:
        # Full frame first
        if full_frame is not None and full_frame.size > 0:
            results_ff = model.predict(full_frame, imgsz=640, conf=0.15, verbose=False)
            if face_bbox is not None:
                fx1, fy1, fx2, fy2 = face_bbox
                fpad_x, fpad_y = int((fx2-fx1)*0.5), int((fy2-fy1)*0.5)
                bf2, br2 = 0.0, 0.0
                for r in results_ff:
                    if r.boxes is None: continue
                    for box in r.boxes:
                        bx1,by1,bx2,by2 = box.xyxy[0].tolist()
                        ox = max(0, min(bx2, fx2+fpad_x) - max(bx1, fx1-fpad_x))
                        oy = max(0, min(by2, fy2+fpad_y) - max(by1, fy1-fpad_y))
                        if ox > 0 and oy > 0:
                            c = int(box.cls[0]); v = float(box.conf[0])
                            if c == 0 and v > bf2: bf2 = v
                            elif c == 1 and v > br2: br2 = v
                d, cv_ = _decide(bf2, br2)
            else:
                bf2, br2 = _parse(results_ff)
                d, cv_ = _decide(bf2, br2)
            if d is not None:
                return d, cv_

        # Crop fallback
        h_c, w_c = face_img.shape[:2]
        if h_c < 160 or w_c < 160:
            scale = max(160/h_c, 160/w_c)
            inp = cv2.resize(face_img, (int(w_c*scale), int(h_c*scale)))
        else:
            inp = face_img
        results = model.predict(inp, imgsz=640, conf=0.15, verbose=False)
        bf, br = _parse(results)
        d, cv_ = _decide(bf, br)
        if d is not None: return d, cv_
        return True, 0.5
    except:
        return True, 0.0


def main():
    print("=" * 70)
    print("  ACCURACY + SPEED TEST: Anti-Spoofing 3 Versions")
    print("=" * 70)

    # Load models
    print("\n[1/3] Loading models...")
    from insightface.app import FaceAnalysis
    face_app = FaceAnalysis(name='buffalo_l',
                            allowed_modules=['detection', 'recognition'],
                            providers=['CPUExecutionProvider'])
    face_app.prepare(ctx_id=0, det_size=(320, 320))

    import torch
    from ultralytics import YOLO
    best_pt = os.path.join(BASE_DIR, "best.pt")
    if not os.path.exists(best_pt):
        print("  ERROR: best.pt not found!")
        return
    spoof_model = YOLO(best_pt)
    print("  Models loaded OK")

    from utils.image_utils import preprocess_face_for_spoof, check_face_real

    # Load data
    print("\n[2/3] Loading test data...")
    fake_images, real_images, _ = load_test_data()

    if not fake_images:
        print("  ERROR: No test data!")
        return

    # Warm-up
    print("\n  Warm-up inference...")
    _ = face_app.get(fake_images[0])
    spoof_model.predict(fake_images[0][:100, :100], imgsz=320, conf=0.15, verbose=False)

    # Run tests
    print("\n[3/3] Running tests...")

    versions = [
        ("V0: Original (640px dual)", check_face_real_v0_640),
        ("V1: Optimized (320px single)", check_face_real_v1_320),
        ("V2: Balanced (480px smart)", check_face_real),
    ]

    results = []
    for name, fn in versions:
        print(f"\n  Testing: {name}...")
        r = run_version_test(name, spoof_model, face_app,
                             fake_images, real_images, fn, preprocess_face_for_spoof, 0)
        results.append(r)
        print(f"    Accuracy: {r['accuracy']:.1f}% | Speed: {r['avg_ms']:.0f}ms/face")

    # Print results
    print("\n" + "=" * 70)
    print("  COMPARISON RESULTS")
    print("=" * 70)

    header = f"{'Version':<32} {'Acc%':<8} {'FPR%':<8} {'FNR%':<8} {'Avg ms':<10} {'Med ms':<10}"
    print(f"\n{header}")
    print("-" * len(header))
    for r in results:
        print(f"{r['version']:<32} {r['accuracy']:<8.1f} {r['fpr']:<8.1f} {r['fnr']:<8.1f} {r['avg_ms']:<10.0f} {r['med_ms']:<10.0f}")

    print(f"\n  Detail:")
    for r in results:
        print(f"  {r['version']}:")
        print(f"    TP={r['tp']} FP={r['fp']} TN={r['tn']} FN={r['fn']} Total={r['total']}")

    print("\n  Legend:")
    print("    Acc% = Overall accuracy (higher is better)")
    print("    FPR% = False Positive Rate (real flagged as fake, lower is better)")
    print("    FNR% = False Negative Rate (fake missed, lower is better)")
    print("    Avg/Med ms = Spoof check latency per face")


if __name__ == "__main__":
    main()
