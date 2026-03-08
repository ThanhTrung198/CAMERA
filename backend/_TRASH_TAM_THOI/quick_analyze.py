import csv, numpy as np

with open("antispoof_data.csv", "r") as f:
    rows = list(csv.DictReader(f))

print(f"Total rows: {len(rows)}")

yf = np.array([float(r["yolo_fake_conf"]) for r in rows])
yr = np.array([float(r["yolo_real_conf"]) for r in rows])
sc = np.array([float(r["screen_score"]) for r in rows])
ff = np.array([float(r["fft_score"]) for r in rows])
tc = np.array([int(r["yolo_top_class"]) for r in rows])
fd = np.array([int(r["face_detected"]) for r in rows])

label = rows[0]["label"]
print(f"Label: {label}")
print()
print(f"YOLO_fake:   mean={yf.mean():.3f}  std={yf.std():.3f}  min={yf.min():.3f}  max={yf.max():.3f}")
print(f"YOLO_real:   mean={yr.mean():.3f}  std={yr.std():.3f}  min={yr.min():.3f}  max={yr.max():.3f}")
print(f"Screen:      mean={sc.mean():.3f}  std={sc.std():.3f}  min={sc.min():.3f}  max={sc.max():.3f}")
print(f"FFT:         mean={ff.mean():.3f}  std={ff.std():.3f}")
print()

correct_real = int(np.sum(tc == 1))
wrong_fake = int(np.sum(tc == 0))
undetected = int(np.sum(tc == -1))
n = len(tc)
print(f"YOLO decision on label='{label}':")
print(f"  cls=1 (Real): {correct_real}/{n} = {correct_real/n*100:.1f}%")
print(f"  cls=0 (Fake): {wrong_fake}/{n} = {wrong_fake/n*100:.1f}%")
print(f"  No box:       {undetected}/{n} = {undetected/n*100:.1f}%")
print(f"  Face detect:  {int(fd.sum())}/{n}")
print()

flips = sum(1 for i in range(1, n) if tc[i] != tc[i-1] and tc[i] != -1 and tc[i-1] != -1)
print(f"Oscillation: {flips} flips / {n-1} = {flips/(n-1)*100:.1f}%")
print()

print("First 15 frames (raw):")
for r in rows[:15]:
    print(f"  yf={r['yolo_fake_conf']}  yr={r['yolo_real_conf']}  scr={r['screen_score']}  top_cls={r['yolo_top_class']}")
