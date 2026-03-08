"""
Quick MiniFASNet validation: check real face scores directly.
No YOLO dependency. Just run on webcam for 30 frames.
"""
import cv2, os, torch, numpy as np
import torch.nn.functional as F
from collections import OrderedDict

from src.model_lib.MiniFASNet import MiniFASNetV2, MiniFASNetV1SE

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load V2
model_v2 = MiniFASNetV2(conv6_kernel=(5, 5))
sd = torch.load(os.path.join(BASE_DIR, "models", "anti_spoof", "2.7_80x80_MiniFASNetV2.pth"), map_location="cpu")
sd_clean = OrderedDict((k.replace("module.", ""), v) for k, v in sd.items())
model_v2.load_state_dict(sd_clean)
model_v2.eval()

# Load V1SE
model_v1se = MiniFASNetV1SE(conv6_kernel=(5, 5))
sd2 = torch.load(os.path.join(BASE_DIR, "models", "anti_spoof", "4_0_0_80x80_MiniFASNetV1SE.pth"), map_location="cpu")
sd2_clean = OrderedDict()
for k, v in sd2.items():
    key = k.replace("module.", "")
    if key.startswith("model."):
        key = key[6:]
    sd2_clean[key] = v
try:
    model_v1se.load_state_dict(sd2_clean)
except:
    model_v1se.load_state_dict(sd2_clean, strict=False)
model_v1se.eval()

print("Models loaded. Starting webcam...")

# Face detect
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
cap = cv2.VideoCapture(0)

fakes = []
reals = []

for i in range(30):
    ret, img = cap.read()
    if not ret:
        continue

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
    if len(faces) == 0:
        print(f"  Frame {i}: no face detected")
        continue

    x, y, w, h = faces[0]
    crop = img[max(0,y-10):min(img.shape[0],y+h+10), max(0,x-10):min(img.shape[1],x+w+10)]
    if crop.size == 0:
        continue

    inp = cv2.resize(crop, (80, 80)).astype(np.float32) / 255.0
    inp = cv2.cvtColor(inp, cv2.COLOR_BGR2RGB).transpose(2, 0, 1)
    tensor = torch.from_numpy(inp).unsqueeze(0)

    with torch.no_grad():
        p1 = F.softmax(model_v2(tensor), dim=1).cpu().numpy()
        p2 = F.softmax(model_v1se(tensor), dim=1).cpu().numpy()

    f1, r1 = float(p1[0][0]), float(p1[0][2])
    f2, r2 = float(p2[0][0]), float(p2[0][2])
    ens_f = (f1 + f2) / 2
    ens_r = (r1 + r2) / 2

    fakes.append(ens_f)
    reals.append(ens_r)

    decision = "FAKE" if ens_f >= 0.70 else ("REAL" if ens_r >= 0.75 else "UNCERTAIN")
    print(f"  Frame {i}: V2[F={f1:.3f} R={r1:.3f}] V1SE[F={f2:.3f} R={r2:.3f}] Ens[F={ens_f:.3f} R={ens_r:.3f}] -> {decision}")

cap.release()

if fakes:
    fakes = np.array(fakes)
    reals = np.array(reals)
    print(f"\n=== SUMMARY ({len(fakes)} frames) ===")
    print(f"  Ensemble FAKE: mean={fakes.mean():.3f}  std={fakes.std():.3f}")
    print(f"  Ensemble REAL: mean={reals.mean():.3f}  std={reals.std():.3f}")
    n_fake = int(np.sum(fakes >= 0.70))
    n_real = int(np.sum(reals >= 0.75))
    n_unc = len(fakes) - n_fake - n_real
    print(f"  Decisions: FAKE={n_fake}  REAL={n_real}  UNCERTAIN={n_unc}")
    print(f"  FRR (wrong FAKE): {n_fake/len(fakes)*100:.1f}%")
    flips = sum(1 for i in range(1, len(fakes)) if (fakes[i]>=0.70) != (fakes[i-1]>=0.70))
    print(f"  Oscillation: {flips}/{len(fakes)-1} = {flips/(len(fakes)-1)*100:.1f}%")
