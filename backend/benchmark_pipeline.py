"""
★ BENCHMARK PIPELINE — Đo hiệu năng Face Recognition + Anti-Spoofing
Chạy: python benchmark_pipeline.py
"""
import cv2
import time
import numpy as np
import os
import sys

# Thêm path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def benchmark():
    print("=" * 70)
    print("★ BENCHMARK: Face Recognition + Anti-Spoofing Pipeline")
    print("=" * 70)

    # ── 1. Load models ──
    print("\n[1/4] Loading models...")

    t0 = time.time()
    from insightface.app import FaceAnalysis
    face_app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
    face_app.prepare(ctx_id=0, det_size=(320, 320))
    t_face_load = time.time() - t0
    print(f"  InsightFace loaded: {t_face_load:.2f}s")

    t0 = time.time()
    import torch
    from ultralytics import YOLO
    best_pt = os.path.join(os.path.dirname(__file__), "best.pt")
    spoof_model = None
    if os.path.exists(best_pt):
        spoof_model = YOLO(best_pt)
        print(f"  Anti-Spoof YOLO loaded: {time.time() - t0:.2f}s")
    else:
        print(f"  ⚠️ best.pt not found, skipping spoof benchmark")

    from utils.image_utils import check_face_real, preprocess_face_for_spoof

    # ── 2. Capture frames ──
    NUM_FRAMES = 30
    print(f"\n[2/4] Capturing {NUM_FRAMES} frames from webcam...")

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("  ❌ Cannot open webcam!")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    frames = []
    for i in range(NUM_FRAMES + 10):  # Bỏ 10 frame đầu (warm-up)
        ret, frame = cap.read()
        if ret and frame is not None:
            if i >= 10:
                frames.append(frame)
    cap.release()
    print(f"  Captured {len(frames)} frames")

    if len(frames) == 0:
        print("  ❌ No frames captured!")
        return

    # ── 3. Warm-up (1 frame) ──
    print("\n[3/4] Warm-up inference...")
    _ = face_app.get(frames[0])
    if spoof_model:
        spoof_model.predict(frames[0][:100, :100], imgsz=320, conf=0.15, verbose=False)

    # ── 4. Benchmark ──
    print(f"\n[4/4] Running benchmark on {len(frames)} frames...\n")

    times_detect = []
    times_spoof = []
    times_recog = []
    times_total = []
    total_faces = 0

    for i, frame in enumerate(frames):
        t_start = time.time()

        # Face detection
        t_det = time.time()
        faces = face_app.get(frame)
        t_det = time.time() - t_det
        times_detect.append(t_det)

        h, w = frame.shape[:2]
        for f in faces[:5]:
            total_faces += 1
            fbbox = f.bbox.astype(int).tolist()
            fx1, fy1, fx2, fy2 = fbbox

            # Spoof check
            t_sp = time.time()
            if spoof_model:
                crop = frame[max(0, fy1):min(h, fy2), max(0, fx1):min(w, fx2)]
                if crop is not None and crop.size > 0:
                    processed = preprocess_face_for_spoof(
                        crop, full_frame=frame, face_bbox=fbbox,
                        target_size=224, padding_ratio=0.3
                    )
                    is_real, conf = check_face_real(processed, spoof_model, cam_id=0)
            t_sp = time.time() - t_sp
            times_spoof.append(t_sp)

            # Recognition (cosine similarity mock)
            t_rec = time.time()
            emb = f.normed_embedding
            # Simulate cosine similarity with 10 known faces
            for _ in range(10):
                np.dot(emb, emb)
            t_rec = time.time() - t_rec
            times_recog.append(t_rec)

        t_total = time.time() - t_start
        times_total.append(t_total)

        if (i + 1) % 10 == 0:
            print(f"  Frame {i+1}/{len(frames)} done...")

    # ── Results ──
    print("\n" + "=" * 70)
    print("★ BENCHMARK RESULTS")
    print("=" * 70)

    def stats(arr):
        if not arr:
            return 0, 0, 0
        return np.mean(arr) * 1000, np.median(arr) * 1000, np.std(arr) * 1000

    avg_det, med_det, std_det = stats(times_detect)
    avg_sp, med_sp, std_sp = stats(times_spoof)
    avg_rec, med_rec, std_rec = stats(times_recog)
    avg_tot, med_tot, std_tot = stats(times_total)

    fps = 1.0 / np.mean(times_total) if times_total else 0

    print(f"\n{'Component':<25} {'Avg (ms)':<12} {'Median (ms)':<14} {'Std (ms)':<10}")
    print("-" * 61)
    print(f"{'Face Detection':<25} {avg_det:<12.1f} {med_det:<14.1f} {std_det:<10.1f}")
    print(f"{'Spoof Check':<25} {avg_sp:<12.1f} {med_sp:<14.1f} {std_sp:<10.1f}")
    print(f"{'Recognition':<25} {avg_rec:<12.1f} {med_rec:<14.1f} {std_rec:<10.1f}")
    print(f"{'TOTAL (per frame)':<25} {avg_tot:<12.1f} {med_tot:<14.1f} {std_tot:<10.1f}")

    print(f"\n📊 Summary:")
    print(f"  Frames processed: {len(frames)}")
    print(f"  Total faces detected: {total_faces}")
    print(f"  Avg faces/frame: {total_faces / max(len(frames), 1):.1f}")
    print(f"  ★ Pipeline FPS: {fps:.1f}")
    print(f"  ★ Frame latency: {avg_tot:.0f}ms")

    print(f"\n💡 Optimization notes:")
    if avg_sp > 50:
        print(f"  - Spoof check is {avg_sp:.0f}ms/face. Consider reducing imgsz further.")
    if avg_det > 100:
        print(f"  - Face detection is {avg_det:.0f}ms. Consider reducing det_size.")
    if fps >= 15:
        print(f"  - ✅ FPS >= 15. Performance is good!")
    else:
        print(f"  - ⚠️ FPS < 15. Consider reducing model sizes or skipping frames.")


if __name__ == "__main__":
    benchmark()
