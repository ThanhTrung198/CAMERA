"""
Analyze Anti-Spoof Raw Data — Statistical Report
==================================================
Đọc antispoof_data.csv và tạo báo cáo:
- Distribution (Mean/Std) cho từng label
- FAR / FRR tại threshold hiện tại
- Optimal threshold (Youden Index)
- Correlation giữa YOLO và screen_score
- Oscillation rate
- Score overlap analysis

Chạy: python analyze_data.py
"""
import csv
import sys
import numpy as np
from collections import defaultdict

CSV_PATH = "antispoof_data.csv"

# ── Load data ─────────────────────────────────────────────────────────────
print(f"Đang đọc {CSV_PATH} ...")

data_by_label = defaultdict(lambda: {
    "yolo_fake": [], "yolo_real": [], "screen": [],
    "fft": [], "color": [], "brightness": [],
    "top_class": [], "face_detected": [], "inference_ms": []
})

try:
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = row["label"]
            d = data_by_label[label]
            d["yolo_fake"].append(float(row["yolo_fake_conf"]))
            d["yolo_real"].append(float(row["yolo_real_conf"]))
            d["screen"].append(float(row["screen_score"]))
            d["fft"].append(float(row["fft_score"]))
            d["color"].append(float(row["color_score"]))
            d["brightness"].append(float(row["brightness_mean"]))
            d["top_class"].append(int(row["yolo_top_class"]))
            d["face_detected"].append(int(row["face_detected"]))
            d["inference_ms"].append(float(row["inference_ms"]))
except FileNotFoundError:
    print(f"❌ File {CSV_PATH} không tồn tại!")
    print("   Chạy collect_data.py trước: python collect_data.py --label real")
    sys.exit(1)

# ── Summary ──────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("  ANTI-SPOOF RAW SCORE ANALYSIS")
print("=" * 80)

total = sum(len(d["yolo_fake"]) for d in data_by_label.values())
print(f"\nTổng mẫu: {total}")
for label, d in sorted(data_by_label.items()):
    n = len(d["yolo_fake"])
    fd = sum(d["face_detected"])
    print(f"  {label:15s}: {n:4d} frames, face_detected={fd}/{n} ({fd/n*100:.0f}%)")

# ── Distribution per label ────────────────────────────────────────────────
print("\n" + "-" * 80)
print("  SCORE DISTRIBUTION PER LABEL")
print("-" * 80)

for label, d in sorted(data_by_label.items()):
    n = len(d["yolo_fake"])
    if n == 0:
        continue
    
    yf = np.array(d["yolo_fake"])
    yr = np.array(d["yolo_real"])
    sc = np.array(d["screen"])
    ff = np.array(d["fft"])
    co = np.array(d["color"])
    br = np.array(d["brightness"])
    ms = np.array(d["inference_ms"])
    
    print(f"\n  [{label}] ({n} frames)")
    print(f"    YOLO_fake:   mean={yf.mean():.3f}  std={yf.std():.3f}  min={yf.min():.3f}  max={yf.max():.3f}")
    print(f"    YOLO_real:   mean={yr.mean():.3f}  std={yr.std():.3f}  min={yr.min():.3f}  max={yr.max():.3f}")
    print(f"    FFT_score:   mean={ff.mean():.3f}  std={ff.std():.3f}  min={ff.min():.3f}  max={ff.max():.3f}")
    print(f"    Color_score: mean={co.mean():.3f}  std={co.std():.3f}  min={co.min():.3f}  max={co.max():.3f}")
    print(f"    Screen_fuse: mean={sc.mean():.3f}  std={sc.std():.3f}  min={sc.min():.3f}  max={sc.max():.3f}")
    print(f"    Brightness:  mean={br.mean():.0f}    std={br.std():.0f}")
    print(f"    Inference:   mean={ms.mean():.0f}ms   max={ms.max():.0f}ms")
    
    # YOLO accuracy (on this ground-truth label)
    is_attack = label in ["phone_oled", "phone_lcd", "print"]
    tc = np.array(d["top_class"])
    if is_attack:
        correct = np.sum(tc == 0)  # should be fake
        print(f"    YOLO correct: {correct}/{n} ({correct/n*100:.1f}%)")
    else:
        correct = np.sum(tc == 1)  # should be real
        print(f"    YOLO correct: {correct}/{n} ({correct/n*100:.1f}%)")

# ── Correlation ──────────────────────────────────────────────────────────
print("\n" + "-" * 80)
print("  CORRELATION: YOLO_fake vs Screen_score")
print("-" * 80)

all_yf = []
all_sc = []
for d in data_by_label.values():
    all_yf.extend(d["yolo_fake"])
    all_sc.extend(d["screen"])

if len(all_yf) > 5:
    corr = np.corrcoef(all_yf, all_sc)[0, 1]
    print(f"  Pearson r = {corr:.3f}")
    if abs(corr) > 0.7:
        print("  ⚠️ Correlation > 0.7 → hai layer đang phát hiện cùng thứ!")
        print("     Fusion KHÔNG có giá trị thêm. Cần thay thế 1 trong 2 layer.")
    elif abs(corr) > 0.4:
        print("  ℹ️ Moderate correlation. Fusion có giá trị nhưng không tối ưu.")
    else:
        print("  ✅ Low correlation → hai layer bổ sung tốt cho nhau.")

# ── FAR / FRR Analysis ───────────────────────────────────────────────────
print("\n" + "-" * 80)
print("  FAR / FRR ANALYSIS (YOLO top_class)")
print("-" * 80)

real_labels = ["real"]
attack_labels = ["phone_oled", "phone_lcd", "print"]

real_decisions = []
attack_decisions = []

for label, d in data_by_label.items():
    tc = d["top_class"]
    if label in real_labels:
        real_decisions.extend(tc)
    elif label in attack_labels:
        attack_decisions.extend(tc)

if real_decisions:
    real_arr = np.array(real_decisions)
    frr = np.sum(real_arr == 0) / len(real_arr)  # real classified as fake
    frr_unk = np.sum(real_arr == -1) / len(real_arr)
    print(f"\n  Người thật ({len(real_arr)} frames):")
    print(f"    FRR (False Reject) = {frr*100:.1f}%")
    print(f"    Undetected         = {frr_unk*100:.1f}%")
    print(f"    Accepted correctly = {(1-frr-frr_unk)*100:.1f}%")

if attack_decisions:
    att_arr = np.array(attack_decisions)
    far = np.sum(att_arr == 1) / len(att_arr)  # attack classified as real
    far_unk = np.sum(att_arr == -1) / len(att_arr)
    print(f"\n  Attack ({len(att_arr)} frames):")
    print(f"    FAR (False Accept) = {far*100:.1f}%")
    print(f"    Undetected         = {far_unk*100:.1f}%")
    print(f"    Blocked correctly  = {(1-far-far_unk)*100:.1f}%")

# ── Oscillation Rate ─────────────────────────────────────────────────────
print("\n" + "-" * 80)
print("  OSCILLATION RATE (Decision stability)")
print("-" * 80)

for label, d in sorted(data_by_label.items()):
    tc = np.array(d["top_class"])
    if len(tc) < 3:
        continue
    flips = 0
    for i in range(1, len(tc)):
        if tc[i] != tc[i-1] and tc[i] != -1 and tc[i-1] != -1:
            flips += 1
    osc_rate = flips / (len(tc) - 1)
    print(f"  {label:15s}: {flips} flips / {len(tc)-1} transitions = {osc_rate*100:.1f}% oscillation")
    if osc_rate > 0.10:
        print(f"                    ⚠️ UNSTABLE (target < 5%)")
    elif osc_rate > 0.05:
        print(f"                    ℹ️ Borderline")
    else:
        print(f"                    ✅ STABLE")

# ── Youden Index for optimal threshold ───────────────────────────────────
print("\n" + "-" * 80)
print("  OPTIMAL THRESHOLD (Youden Index) — YOLO fake_conf")
print("-" * 80)

if real_decisions and attack_decisions:
    real_yf = []
    attack_yf = []
    for label, d in data_by_label.items():
        if label in real_labels:
            real_yf.extend(d["yolo_fake"])
        elif label in attack_labels:
            attack_yf.extend(d["yolo_fake"])
    
    real_yf = np.array(real_yf)
    attack_yf = np.array(attack_yf)
    
    best_j = -1
    best_thr = 0.5
    
    for thr in np.arange(0.10, 0.95, 0.01):
        tpr = np.mean(attack_yf >= thr)   # true positive: attack correctly blocked
        fpr = np.mean(real_yf >= thr)      # false positive: real incorrectly blocked
        j = tpr - fpr
        if j > best_j:
            best_j = j
            best_thr = thr
    
    tpr_at_best = np.mean(attack_yf >= best_thr)
    fpr_at_best = np.mean(real_yf >= best_thr)
    
    print(f"  Optimal threshold (YOLO fake_conf): {best_thr:.2f}")
    print(f"  Youden J = {best_j:.3f}")
    print(f"  At this threshold:")
    print(f"    Attack detection rate (TPR): {tpr_at_best*100:.1f}%")
    print(f"    False rejection rate (FPR):  {fpr_at_best*100:.1f}%")

# ── Score overlap ────────────────────────────────────────────────────────
print("\n" + "-" * 80)
print("  SCORE OVERLAP ANALYSIS")
print("-" * 80)

if real_decisions and attack_decisions:
    real_yf = np.array([yf for label in real_labels for yf in data_by_label[label]["yolo_fake"]])
    attack_yf = np.array([yf for label in attack_labels for yf in data_by_label[label]["yolo_fake"]])
    
    # Check if distributions overlap
    real_max = real_yf.max() if len(real_yf) > 0 else 0
    attack_min = attack_yf.min() if len(attack_yf) > 0 else 1
    
    if real_max > attack_min:
        overlap = real_max - attack_min
        print(f"  ⚠️ OVERLAP detected!")
        print(f"     Real yolo_fake max:   {real_max:.3f}")
        print(f"     Attack yolo_fake min: {attack_min:.3f}")
        print(f"     Overlap range: [{attack_min:.3f}, {real_max:.3f}]")
        print(f"     → Không có threshold nào phân biệt 100%")
    else:
        print(f"  ✅ No overlap!")
        print(f"     Real yolo_fake max:   {real_max:.3f}")
        print(f"     Attack yolo_fake min: {attack_min:.3f}")
        print(f"     Gap: {attack_min - real_max:.3f}")

# ── Recommendations ──────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("  RECOMMENDATIONS")
print("=" * 80)

recommendations = []

# Check if YOLO is effective
if real_decisions:
    real_arr = np.array(real_decisions)
    frr = np.sum(real_arr == 0) / len(real_arr)
    if frr > 0.20:
        recommendations.append("CRITICAL: YOLO FRR > 20% → Model không phân biệt tốt mặt thật vs fake")
        recommendations.append("  → Cân nhắc retrain hoặc thay model chuyên PAD (DeepPixBiS, Silent-FAS)")

if attack_decisions:
    att_arr = np.array(attack_decisions)
    far = np.sum(att_arr == 1) / len(att_arr)
    if far > 0.10:
        recommendations.append("CRITICAL: YOLO FAR > 10% → Model không chặn được attack")
        recommendations.append("  → YOLO detection model KHÔNG phù hợp cho anti-spoof")

if not recommendations:
    recommendations.append("Chưa đủ dữ liệu. Thu thập thêm ở cả 2 nhóm (real + attack).")

for r in recommendations:
    print(f"  • {r}")

print("\n" + "=" * 80)
print("  DONE")
print("=" * 80)
