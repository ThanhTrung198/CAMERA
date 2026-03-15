import cv2
import numpy as np
import insightface
from insightface.app import FaceAnalysis
import os
import time
import queue
from pathlib import Path
from datetime import datetime
from flask import Flask, Response, request, jsonify, session, send_from_directory
import threading
import json
import hashlib
from collections import Counter, deque as _deque
from flask_cors import CORS

from database import get_connection
import torch
from ultralytics import YOLO
from tracking_module import TelegramNotifier, ZoneManager, FixedPersonTracker

from config.settings import (
    BASE_DIR, ABS_VECTOR_DIR, STATIC_DIR, STRANGER_DIR,
    SECRET_KEY, CORS_ORIGINS,
    RECOGNITION_THRESHOLD, SPOOF_FAKE_THRESHOLD, SPOOF_REAL_THRESHOLD,
    SYSTEM_SETTINGS, PERFORMANCE_SETTINGS,
    TRACKING_ENABLED, YOLO_MODEL_PATH,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    STRANGER_MATCH_THRESHOLD, LOG_COOLDOWN,
    SPOOF_CHECK_ENABLED, SPOOF_BLOCK_FACE,
    USERS
)
from utils.image_utils import put_text_utf8, create_placeholder_frame, calculate_iou, check_face_real
from utils.screen_detector import screen_detector
from utils.auth_utils import login_required

try:
    from utils.image_utils import preprocess_face_for_spoof
except ImportError:
    def preprocess_face_for_spoof(face_crop, full_frame=None, face_bbox=None,
                                    target_size=224, padding_ratio=0.3):
        if full_frame is not None and face_bbox is not None:
            h, w = full_frame.shape[:2]
            x1, y1, x2, y2 = face_bbox
            fw, fh = x2 - x1, y2 - y1
            pad_w, pad_h = int(fw * padding_ratio), int(fh * padding_ratio)
            nx1 = max(0, x1 - pad_w); ny1 = max(0, y1 - pad_h)
            nx2 = min(w, x2 + pad_w); ny2 = min(h, y2 + pad_h)
            face_crop = full_frame[ny1:ny2, nx1:nx2]
        if face_crop is None or face_crop.size == 0:
            return face_crop
        try:
            lab = cv2.cvtColor(face_crop, cv2.COLOR_BGR2LAB)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
            lab[:, :, 0] = clahe.apply(lab[:, :, 0])
            face_crop = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        except Exception:
            pass
        try:
            if face_crop.shape[0] > 0 and face_crop.shape[1] > 0:
                face_crop = cv2.resize(face_crop, (target_size, target_size))
        except Exception:
            pass
        return face_crop

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')
app.secret_key = SECRET_KEY
np.int = int
CORS(app, resources={r"/*": {"origins": CORS_ORIGINS}}, supports_credentials=True)

try:
    from config.settings import SPOOF_MIN_FACE_SIZE
except ImportError:
    SPOOF_MIN_FACE_SIZE = 60

# ==============================================================================
# QUEUE PIPELINE
# ==============================================================================
AI_FRAME_QUEUE_SIZE = 2
ai_frame_queue: queue.Queue = queue.Queue(maxsize=AI_FRAME_QUEUE_SIZE)

# ==============================================================================
# GLOBAL STATE
# ==============================================================================
lock = threading.Lock()
global_frame_0 = None
global_frame_1 = None
lock_spoof = threading.Lock()
RECENT_STRANGERS = []
NEXT_STRANGER_ID = 1
LAST_LOG_TIME = {}
anti_spoof_state = {0: {"is_live": True, "confidence": 0.5}, 1: {"is_live": True, "confidence": 0.5}}

ENROLLMENT_BACKUP_DIR = os.path.join(BASE_DIR, "enrollment_images")
os.makedirs(ENROLLMENT_BACKUP_DIR, exist_ok=True)

# Per-face state (track_id → state dict)
_face_state: dict = {}

# ==============================================================================
# QUALITY GATE  (FIX #5 #12)
# ==============================================================================
def _get_quality_embedding(face, frame):
    emb = face.normed_embedding
    bbox = face.bbox.astype(int)
    x1, y1, x2, y2 = bbox
    h, w = frame.shape[:2]
    det_score = getattr(face, 'det_score', 0)
    if det_score < 0.5: return None, 0
    face_w, face_h = x2 - x1, y2 - y1
    if face_w < 40 or face_h < 40: return None, 0
    ratio = face_w / max(face_h, 1)
    if ratio < 0.4 or ratio > 1.5: return None, 0
    quality = det_score * (0.8 if (x1 < 10 or y1 < 10 or x2 > w-10 or y2 > h-10) else 1.0)
    face_crop = frame[max(0,y1):min(h,y2), max(0,x1):min(w,x2)]
    if face_crop.size > 0:
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        if cv2.Laplacian(gray, cv2.CV_64F).var() < 20:
            return None, 0
    return emb, quality


# ==============================================================================
# ENROLLMENT QUALITY  (FIX #4)
# ==============================================================================
def check_face_quality(face, img):
    issues = []
    bbox = face.bbox.astype(int)
    x1, y1, x2, y2 = bbox
    face_w, face_h = x2 - x1, y2 - y1
    if face_w < 80 or face_h < 80:
        issues.append(f"Mat qua nho ({face_w}x{face_h}px, can >=80x80)")
    det_score = getattr(face, 'det_score', 0)
    if det_score < 0.7:
        issues.append(f"Do tin cay phat hien thap ({det_score:.2f}, can >=0.70)")
    if hasattr(face, 'pose') and face.pose is not None:
        try:
            yaw, pitch, roll = face.pose
            if abs(yaw) > 30:  issues.append(f"Mat quay ngang qua nhieu (yaw={yaw:.0f})")
            if abs(pitch) > 25: issues.append(f"Mat ngang/cui qua nhieu (pitch={pitch:.0f})")
        except: pass
    emb = face.normed_embedding
    norm = np.linalg.norm(emb)
    if abs(norm - 1.0) > 0.05:
        issues.append(f"Embedding bat thuong (norm={norm:.3f})")
    face_crop = img[max(0,y1):min(img.shape[0],y2), max(0,x1):min(img.shape[1],x2)]
    if face_crop.size > 0:
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        if cv2.Laplacian(gray, cv2.CV_64F).var() < 50:
            issues.append("Anh qua mo")
        hsv = cv2.cvtColor(face_crop, cv2.COLOR_BGR2HSV)
        br = hsv[:, :, 2].mean()
        if br < 40:   issues.append(f"Anh qua toi (brightness={br:.0f})")
        elif br > 240: issues.append(f"Anh qua sang (brightness={br:.0f})")
    return issues


# ==============================================================================
# ENROLLMENT BACKUP  (FIX #19)
# ==============================================================================
def _save_enrollment_image(ma_nv, face_crop, img_index):
    try:
        person_dir = os.path.join(ENROLLMENT_BACKUP_DIR, f"nv_{ma_nv}")
        os.makedirs(person_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(person_dir, f"face_{img_index}_{ts}.jpg")
        cv2.imwrite(filepath, face_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return filepath
    except Exception as e:
        print(f"[Enrollment] Save error: {e}")
        return None


# ==============================================================================
# ADAPTIVE THRESHOLD  (FIX #17)
# ==============================================================================
class AdaptiveThresholdManager:
    MIN_THRESHOLD = 0.45
    MAX_THRESHOLD = 0.70
    HISTORY_SIZE  = 50
    UPDATE_INTERVAL = 20

    def __init__(self, base_threshold=0.50):
        self.base = base_threshold
        self.current = base_threshold
        self.score_history = []
        self.recognize_count = 0

    def record_score(self, max_score, was_recognized):
        self.score_history.append({"score": max_score, "recognized": was_recognized})
        if len(self.score_history) > self.HISTORY_SIZE:
            self.score_history = self.score_history[-self.HISTORY_SIZE:]
        self.recognize_count += 1
        if self.recognize_count % self.UPDATE_INTERVAL == 0:
            self._update_threshold()

    def _update_threshold(self):
        if len(self.score_history) < 20: return
        recognized = [h for h in self.score_history if h["recognized"]]
        if not recognized: return
        rec_scores = [h["score"] for h in recognized]
        avg_rec = np.mean(rec_scores)
        std_rec = np.std(rec_scores)
        new_th = max(self.MIN_THRESHOLD, min(self.MAX_THRESHOLD, avg_rec - 2 * std_rec))
        self.current = max(self.MIN_THRESHOLD, min(self.MAX_THRESHOLD, 0.8*self.current + 0.2*new_th))
        if abs(self.current - self.base) > 0.05:
            print(f"[AdaptiveThreshold] {self.base:.3f} → {self.current:.3f} (avg={avg_rec:.3f})")

    def get_threshold(self):
        return self.current


adaptive_threshold = AdaptiveThresholdManager(
    base_threshold=SYSTEM_SETTINGS.get("threshold", 0.50)
)


# ==============================================================================
# FACE DATABASE  (FIX #2)
# ==============================================================================
class FaceDatabase:
    def __init__(self):
        self.known_embeddings = []
        self.stranger_embeddings = []
        self.next_stranger_id = 1
        self._person_groups = {}
        self._person_centroids = {}
        self.reload_db()

    def reload_db(self):
        print("System: Dang tai du lieu khuon mat tu Database...")
        self.known_embeddings = []
        self.stranger_embeddings = []
        self._person_groups = {}
        self._person_centroids = {}
        conn = None
        try:
            conn = get_connection()
            if not conn:
                print("❌ Khong the ket noi database"); return
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT nv.ho_ten, nv.ten_phong, nv.ten_chuc_vu, fe.vector_data
                FROM face_embeddings fe
                JOIN nhan_vien nv ON fe.ma_nv = nv.ma_nv
            """)
            for row in cursor.fetchall():
                if not row['vector_data']: continue
                try:
                    arr = np.array(json.loads(row['vector_data']), dtype=np.float32)
                    name = row['ho_ten']
                    entries = [arr] if arr.ndim == 1 else list(arr)
                    for emb in entries:
                        norm = np.linalg.norm(emb)
                        if norm > 0: emb = emb / norm
                        self.known_embeddings.append({"name": name, "dept": row['ten_phong'],
                                                       "role": row['ten_chuc_vu'], "embedding": emb})
                        if name not in self._person_groups: self._person_groups[name] = []
                        self._person_groups[name].append(emb)
                except Exception as e:
                    print(f"⚠️ Loi data {row['ho_ten']}: {e}")
            for name, embs in self._person_groups.items():
                c = np.mean(embs, axis=0); cn = np.linalg.norm(c)
                self._person_centroids[name] = c / cn if cn > 0 else c
            cursor.execute("SELECT stranger_label, vector_data FROM vector_nguoi_la")
            for row in cursor.fetchall():
                if row['vector_data']:
                    emb = np.array(json.loads(row['vector_data']), dtype=np.float32)
                    n = np.linalg.norm(emb)
                    if n > 0: emb = emb / n
                    self.stranger_embeddings.append({"name": row['stranger_label'], "embedding": emb})
                    try:
                        sid = int(row['stranger_label'].split('_')[-1])
                        if sid >= self.next_stranger_id: self.next_stranger_id = sid + 1
                    except: pass
            cursor.close()
            print(f"✅ {len(self.known_embeddings)} vectors, {len(self._person_groups)} nguoi, "
                  f"{len(self.stranger_embeddings)} nguoi la.")
        except Exception as e:
            print(f"❌ Loi tai DB: {e}")
        finally:
            if conn:
                try: conn.close()
                except: pass

    def recognize(self, target_embedding, method="hybrid"):
        norm_t = np.linalg.norm(target_embedding)
        if norm_t != 0 and abs(norm_t - 1.0) > 0.01:
            target_embedding = target_embedding / norm_t
        if method == "simple" or not self._person_groups:
            return self._recognize_simple(target_embedding)
        threshold = adaptive_threshold.get_threshold()
        MARGIN = 0.12
        top5 = sorted(
            {n: float(np.dot(target_embedding, c)) for n, c in self._person_centroids.items()}.items(),
            key=lambda x: x[1], reverse=True)[:5]
        detailed = {}
        for name, _ in top5:
            embs = self._person_groups[name]
            sc = sorted([float(np.dot(target_embedding, e)) for e in embs], reverse=True)
            k = min(3, len(sc))
            detailed[name] = sum(sc[:k]) / k
        ranked = sorted(detailed.items(), key=lambda x: x[1], reverse=True)
        if not ranked: return "Unknown", 0.0
        best_name, best_score = ranked[0]
        if best_score < threshold:
            adaptive_threshold.record_score(best_score, False)
            return "Unknown", best_score
        if len(ranked) >= 2:
            second_name, second_score = ranked[1]
            if best_score - second_score < MARGIN and second_score >= threshold * 0.8:
                adaptive_threshold.record_score(best_score, False)
                return "Unknown", best_score
        adaptive_threshold.record_score(best_score, True)
        return best_name, best_score

    def _recognize_simple(self, target_embedding):
        max_score, identity = 0, "Unknown"
        for face in self.known_embeddings:
            score = float(np.dot(target_embedding, face["embedding"]))
            if score > max_score:
                max_score = score; identity = face["name"]
        threshold = adaptive_threshold.get_threshold()
        recognized = max_score >= threshold
        adaptive_threshold.record_score(max_score, recognized)
        return (identity if recognized else "Unknown"), max_score

    def get_person_info(self, name):
        for f in self.known_embeddings:
            if f["name"] == name:
                return {"dept": f["dept"], "role": f["role"]}
        return {"dept": "Unknown", "role": "Khách"}


# ==============================================================================
# INIT INSIGHTFACE  (FIX #1)
# ==============================================================================
print("System: Dang khoi tao InsightFace...")
face_app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
face_app.prepare(ctx_id=0, det_size=(320, 320))
print("✅ InsightFace ready! (det_size=320x320, optimized for realtime)")

print("System: Dang khoi tao Anti-Spoof Model (best.pt)...")
best_pt_path = os.path.join(BASE_DIR, "best.pt")
spoof_model = None
if os.path.exists(best_pt_path):
    try:
        spoof_model = YOLO(best_pt_path)
        print(f"✅ Anti-Spoof YOLO loaded! Classes: {spoof_model.names}")
    except Exception as e:
        print(f"⚠️ best.pt error: {e}")
else:
    print(f"⚠️ best.pt not found")

db = FaceDatabase()

# ==============================================================================
# YOLO + TRACKING
# ==============================================================================
print("System: Dang khoi tao YOLO...")
yolo_model_path = os.path.join(BASE_DIR, "yolo11n.pt")
yolo_model = None
if os.path.exists(yolo_model_path):
    try:
        os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD'] = '0'
        _orig_load = torch.load
        def _patched_load(*a, **kw): kw['weights_only'] = False; return _orig_load(*a, **kw)
        torch.load = _patched_load
        yolo_model = YOLO(yolo_model_path)
        print("✅ YOLO loaded!")
        torch.load = _orig_load
    except Exception as e:
        print(f"⚠️ YOLO error: {e}")

person_tracker = FixedPersonTracker(max_disappeared=100)
telegram_notifier = TelegramNotifier(
    "8097310654:AAEtu13Fmqrc9lTV4LUX6730ESaGhOmsvRg",
    "7224086648"
)
zone_manager = ZoneManager(telegram_notifier=telegram_notifier)
TRACKING_ENABLED = True
print("✅ Tracking Module initialized!")


# ==============================================================================
# FIX #14: MULTI-SCALE FACE DETECTOR
# ==============================================================================
class MultiScaleFaceDetector:
    def __init__(self, face_app_main):
        self.face_app = face_app_main
        # Single-scale only — 320×320 is already fast enough for real-time
        print("✅ FaceDetector: single 320x320 (realtime mode)")

    def detect(self, frame):
        return self.face_app.get(frame)


multi_scale_detector = MultiScaleFaceDetector(face_app)


# ==============================================================================
# ★ IMPROVED ANTI-SPOOF v2
#
#  Cải tiến so với v1:
#  1. YOLO REAL chủ động kéo về real (không bỏ qua như cũ)
#  2. Thêm Moiré/FFT — phát hiện pixel grid của màn hình
#  3. Thêm Gradient Entropy — mặt thật có gradient hỗn loạn hơn ảnh/màn hình
#  4. YOLO fast-path hạ xuống 0.50 (từ 0.55) — bắt giả mạo nhanh hơn
#  5. YOLO very-high-conf (>=0.75) → trả về ngay, không cần check thêm
#  6. Temporal EMA trên spoof_conf xử lý ở FaceStateTracker
# ==============================================================================
class FastAntiSpoof:
    def __init__(self, yolo_model=None):
        self.yolo_model = yolo_model
        self._yolo_cache: dict = {}   # cam_id → (dets, timestamp)

    # ── YOLO full-frame — cache 100ms ─────────────────────────────────────────
    def run_yolo(self, frame, cam_id: int):
        cached = self._yolo_cache.get(cam_id)
        if cached and time.time() - cached[1] < 0.10:
            return cached[0]
        if self.yolo_model is None or not SPOOF_CHECK_ENABLED:
            return []
        try:
            from utils.image_utils import _spoof_model_lock
            with _spoof_model_lock:
                results = self.yolo_model.predict(frame, imgsz=640, conf=0.20, verbose=False)
            dets = []
            for result in results:
                if result.boxes is None: continue
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    conf   = float(box.conf[0])
                    xyxy   = box.xyxy[0].cpu().numpy().astype(int).tolist()
                    is_fake = (cls_id == 0)
                    if is_fake and conf < 0.30: continue   # bỏ FAKE noise thấp
                    dets.append({"bbox": xyxy, "is_fake": is_fake, "conf": conf})
            self._yolo_cache[cam_id] = (dets, time.time())
            if dets:
                parts = [f"{'FK' if d['is_fake'] else 'RL'}={d['conf']:.2f}" for d in dets]
                print(f"[YOLO] cam{cam_id} {' '.join(parts)}")
            return dets
        except Exception as e:
            print(f"[YOLO] Error: {e}"); return []

    # ── Match YOLO bbox → face bbox ───────────────────────────────────────────
    def _match_yolo(self, face_bbox, dets):
        """Returns (is_fake, conf, matched)"""
        fx1, fy1, fx2, fy2 = face_bbox
        fcx, fcy = (fx1+fx2)/2, (fy1+fy2)/2
        fdiag = ((fx2-fx1)**2 + (fy2-fy1)**2) ** 0.5
        fakes, reals = [], []
        for det in dets:
            iou  = calculate_iou(face_bbox, det["bbox"])
            dcx  = (det["bbox"][0]+det["bbox"][2])/2
            dcy  = (det["bbox"][1]+det["bbox"][3])/2
            dist = ((fcx-dcx)**2 + (fcy-dcy)**2) ** 0.5
            if iou >= 0.20 or (dist < fdiag*0.55 and iou >= 0.08):
                (fakes if det["is_fake"] else reals).append(det["conf"])
        if not fakes and not reals: return False, 0.0, False
        if fakes and reals:
            mf, mr = max(fakes), max(reals)
            if mf > mr + 0.12: return True,  mf, True
            if mr > mf + 0.12: return False, mr, True
            return False, mr, True   # tie → REAL (tránh false positive)
        if fakes: return True,  max(fakes), True
        return False, max(reals), True

    # ── Texture liveness ──────────────────────────────────────────────────────
    def _texture_score(self, face_crop) -> float:
        """0.0=fake, 1.0=real. LBP + sharpness + color std."""
        if face_crop is None or face_crop.size == 0: return 0.5
        try:
            g64 = cv2.resize(cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY), (64, 64))
            # LBP variance
            c = g64[1:-1, 1:-1].astype(np.int16)
            lbp = np.zeros_like(c, dtype=np.uint8)
            for bit, (dy, dx) in enumerate([(0,0),(0,1),(0,2),(1,2),(2,2),(2,1),(2,0),(1,0)]):
                lbp |= ((g64[dy:dy+62, dx:dx+62] >= c).astype(np.uint8) << bit)
            hist = np.histogram(lbp, bins=256, range=(0,256))[0].astype(np.float32)
            hist /= max(hist.sum(), 1)
            lbp_s = min(1.0, np.var(hist) / 0.003)
            # Laplacian sharpness
            lap_s = min(1.0, cv2.Laplacian(g64, cv2.CV_64F).var() / 300.0)
            # Saturation std
            hsv = cv2.cvtColor(cv2.resize(face_crop, (64, 64)), cv2.COLOR_BGR2HSV)
            col_s = min(1.0, float(hsv[:,:,1].std()) / 35.0)
            return lbp_s*0.40 + lap_s*0.35 + col_s*0.25
        except: return 0.5

    # ── Moiré / FFT screen pattern ────────────────────────────────────────────
    def _moire_score(self, face_crop) -> float:
        """
        Màn hình điện thoại/máy tính tạo ra pixel grid đều đặn.
        FFT của ảnh màn hình sẽ có các peak cao ở tần số trung bình.
        Returns: 0.0=likely screen, 1.0=likely real face
        """
        if face_crop is None or face_crop.size == 0: return 0.5
        try:
            gray = cv2.resize(cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY), (64, 64))
            gray_f = gray.astype(np.float32)
            f = np.fft.fft2(gray_f)
            fshift = np.fft.fftshift(f)
            mag = np.abs(fshift)

            h, w = mag.shape
            cy, cx = h//2, w//2

            # Chia vùng tần số: low(<8), mid(8–20), high(>20)
            low_mask  = np.zeros((h,w), bool)
            mid_mask  = np.zeros((h,w), bool)
            Y, X = np.ogrid[:h, :w]
            dist_from_center = np.sqrt((Y-cy)**2 + (X-cx)**2)
            low_mask[dist_from_center < 8]  = True
            mid_mask[(dist_from_center >= 8) & (dist_from_center < 24)] = True

            low_energy  = mag[low_mask].sum()
            mid_energy  = mag[mid_mask].sum()
            total_energy = mag.sum() - mag[cy, cx]  # bỏ DC component

            if total_energy < 1e-6: return 0.5

            mid_ratio = mid_energy / total_energy

            # Màn hình: mid_ratio thường > 0.45 (pixel grid đều)
            # Mặt thật: mid_ratio thường < 0.35 (năng lượng tập trung ở low)
            if mid_ratio > 0.50:   return 0.1   # rất có khả năng là màn hình
            if mid_ratio > 0.42:   return 0.35
            if mid_ratio > 0.32:   return 0.65
            return 0.85   # ít màn hình
        except: return 0.5

    # ── Gradient Entropy ──────────────────────────────────────────────────────
    def _gradient_entropy(self, face_crop) -> float:
        """
        Mặt thật: gradient hướng phân bố ngẫu nhiên → entropy cao.
        Ảnh in/màn hình: gradient đều đặn → entropy thấp.
        Returns: 0.0=uniform(fake), 1.0=chaotic(real)
        """
        if face_crop is None or face_crop.size == 0: return 0.5
        try:
            gray = cv2.resize(cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY), (64, 64))
            gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            angles = np.arctan2(gy, gx)  # -π to π
            # Quantize vào 18 bins (mỗi 20°)
            bins = np.histogram(angles, bins=18, range=(-np.pi, np.pi))[0].astype(float)
            bins /= max(bins.sum(), 1)
            # Shannon entropy
            bins_nz = bins[bins > 0]
            entropy = -float(np.sum(bins_nz * np.log2(bins_nz)))
            # Normalize: max entropy = log2(18) ≈ 4.17
            norm_entropy = entropy / 4.17
            return min(1.0, norm_entropy)
        except: return 0.5

    # ── Screen detector wrapper ───────────────────────────────────────────────
    def _screen_check(self, face_crop, cam_id: int):
        if face_crop is None or face_crop.size == 0: return False, 0.0
        try:
            is_screen, conf, _ = screen_detector.check_screen(face_crop, cam_id=cam_id)
            return is_screen, conf
        except: return False, 0.0

    # ── MAIN CHECK ────────────────────────────────────────────────────────────
    def check(self, frame, face_bbox, face_crop, cam_id: int, yolo_dets=None):
        """
        Returns: (is_real: bool, spoof_conf: float, detail: str)

        Thứ tự quyết định:
          1. YOLO >= 0.75 → kết luận ngay (bỏ qua mọi check khác)
          2. Screen >= 0.70 → FAKE ngay
          3. YOLO 0.50–0.74 → kết luận ngay (fast path)
          4. Weighted vote: YOLO + Texture + Moiré + GradEntropy + Screen
        """
        if yolo_dets is None:
            yolo_dets = self.run_yolo(frame, cam_id)

        is_fake_yolo, yolo_conf, yolo_matched = self._match_yolo(face_bbox, yolo_dets)

        # ── FAST PATH 1: YOLO rất cao — tin tuyệt đối
        if yolo_matched and yolo_conf >= 0.65:
            is_real = not is_fake_yolo
            return is_real, yolo_conf, f"YOLO_VH({'FK' if is_fake_yolo else 'RL'} {yolo_conf:.2f})"

        # Chỉ tính các score phụ nếu cần
        tex_s    = self._texture_score(face_crop)
        moire_s  = self._moire_score(face_crop)
        grad_s   = self._gradient_entropy(face_crop)
        is_screen, scr_conf = self._screen_check(face_crop, cam_id)

        # ── FAST PATH 2: Screen rõ ràng
        if is_screen and scr_conf >= 0.65:
            return False, scr_conf, f"SCREEN({scr_conf:.2f})"

        # ── FAST PATH 3: YOLO trung-cao → kết luận ngay
        if yolo_matched and yolo_conf >= 0.40:
            is_real = not is_fake_yolo
            return is_real, yolo_conf, f"YOLO_H({'FK' if is_fake_yolo else 'RL'} {yolo_conf:.2f})"

        # ── NORMAL PATH: weighted vote
        #
        #  Mỗi signal đóng góp vào fake_score [0, weight]:
        #    YOLO FAKE  → +W_YOLO * conf
        #    YOLO REAL  → -W_YOLO * conf  (kéo về real chủ động)
        #    Texture    → thấp = fake (tuyến tính)
        #    Moiré      → thấp = fake (tuyến tính)
        #    GradEntr   → thấp = fake (tuyến tính)
        #    Screen     → +W_SCR * conf nếu is_screen
        #
        W_YOLO = 3.5
        W_TEX  = 1.2
        W_MOR  = 1.5
        W_GRAD = 1.0
        W_SCR  = 2.0

        fake_score = 0.0

        if yolo_matched:
            if is_fake_yolo: fake_score += W_YOLO * yolo_conf
            else:            fake_score -= W_YOLO * yolo_conf   # ★ chủ động kéo real
        total_w = W_YOLO if yolo_matched else 0.0

        # Texture: 0=fake, 1=real → fake contrib = 1-tex_s
        fake_score += W_TEX * (1.0 - tex_s);  total_w += W_TEX
        # Moiré:   0=fake, 1=real → fake contrib = 1-moire_s
        fake_score += W_MOR * (1.0 - moire_s); total_w += W_MOR
        # Gradient: 0=fake, 1=real → fake contrib = 1-grad_s
        fake_score += W_GRAD * (1.0 - grad_s); total_w += W_GRAD
        # Screen
        if is_screen:
            fake_score += W_SCR * scr_conf; total_w += W_SCR
        else:
            total_w += W_SCR * 0.3   # screen không phát hiện → nhỏ weight

        # Normalize về [0,1]
        # Clip về [0, total_w] trước vì YOLO REAL có thể kéo âm
        fake_score = max(0.0, fake_score)
        fake_ratio = fake_score / max(total_w, 0.01)

        # Ngưỡng: nếu có YOLO hỗ trợ thì 0.38, không có thì 0.48
        # ★ Thấp hơn trước → nhạy hơn với fake, giảm false negative
        thresh = 0.38 if yolo_matched else 0.48

        is_real    = fake_ratio < thresh
        confidence = fake_ratio if not is_real else (1.0 - fake_ratio)
        detail = (f"WV yolo={'FK' if is_fake_yolo else 'RL'}{yolo_conf:.2f} "
                  f"tex={tex_s:.2f} mor={moire_s:.2f} grd={grad_s:.2f} "
                  f"scr={'Y' if is_screen else 'N'} ratio={fake_ratio:.2f}")
        return is_real, confidence, detail


fast_spoof = FastAntiSpoof(yolo_model=spoof_model)
print("✅ FastAntiSpoof v2 initialized! (YOLO + Texture + Moiré + GradEntropy + Screen)")


# ==============================================================================
# ★ PER-FACE STATE  — bộ nhớ trạng thái cho từng track
#
#  Thiết kế:
#  - SPOOF hysteresis: cần 2 frame FAKE liên tiếp để kết luận → FAKE
#                      cần 3 frame REAL liên tiếp để thoát FAKE
#  - Identity: nhận diện NGAY frame đầu tiên REAL, dùng EMA vote để ổn định
#  - Pin sau 2 vote đồng nhất (thay vì 3 giây)
# ==============================================================================
class FaceStateTracker:
    FAKE_CONFIRM   = 1     # 1 frame FAKE đủ mạnh → kết luận ngay
    REAL_CONFIRM   = 2     # 2 frame REAL liên tiếp → thoát CHECKING
    REAL_CLEAR     = 4     # 4 frame REAL + EMA thấp → thoát FAKE
    PIN_VOTES      = 1     # hiện tên ngay frame đầu, không chờ vote
    RECOG_INTERVAL = 2     # nhận diện mỗi N frame
    MAX_AGE        = 8.0
    EMA_ALPHA      = 0.50  # phản ứng nhanh hơn

    def __init__(self):
        self._states: dict = {}
        self._next_id = 0

    def _new_state(self):
        return {
            "spoof_state":  "CHECKING",
            "consec_fake":  0,
            "consec_real":  0,
            "spoof_ema":    0.4,    # ★ khởi đầu nghiêng về nghi ngờ, không trung tính
            "name":         "...",
            "score":        0.0,
            "pinned":       False,
            "vote_names":   [],
            "vote_scores":  [],
            "recog_frame":  0,
            "last_seen":    time.time(),
            "alert_sent":   False,
        }

    # ── Khớp track bằng cosine similarity ────────────────────────────────────
    def _match(self, emb) -> str | None:
        best_key, best_sim = None, 0.60
        for key, st in self._states.items():
            ref = st.get("_emb")
            if ref is None: continue
            dot = float(np.dot(emb, ref))
            na  = float(np.linalg.norm(emb))
            nb  = float(np.linalg.norm(ref))
            sim = dot / (na*nb) if na>0 and nb>0 else 0
            if sim > best_sim:
                best_sim = sim; best_key = key
        return best_key

    # ── Cập nhật 1 face và trả về kết quả hiển thị ───────────────────────────
    def update(self, emb, is_real_raw: bool, spoof_conf: float,
               frame, face_bbox, cam_id: int) -> dict:
        """
        Returns dict:
          name, score, is_real, spoof_conf, should_log, track_id
        """
        now = time.time()
        key = self._match(emb)
        if key is None:
            key = str(self._next_id); self._next_id += 1
            self._states[key] = self._new_state()
        st = self._states[key]
        st["_emb"]      = emb
        st["last_seen"] = now
        st["recog_frame"] += 1

        # ── 1. Spoof state machine ────────────────────────────────────────────
        # ★ Cập nhật EMA của spoof confidence — smooth hơn frame đơn lẻ
        alpha = self.EMA_ALPHA
        if not is_real_raw:
            # FAKE frame → EMA kéo lên (về phía fake)
            st["spoof_ema"] = alpha * spoof_conf + (1-alpha) * st["spoof_ema"]
        else:
            # REAL frame → EMA kéo xuống
            st["spoof_ema"] = alpha * (1.0 - spoof_conf) + (1-alpha) * st["spoof_ema"]
        ema = st["spoof_ema"]

        # Dùng EMA để quyết định "confident" hay không
        # ★ certain_fake: nhạy hơn — bắt fake dù conf chỉ 0.30
        MIN_REAL_CONF = 0.50    # tăng từ 0.45 → 0.50 (chặt hơn với REAL)
        certain_fake   = (not is_real_raw) and (spoof_conf >= 0.30 or ema >= 0.50)
        confident_real = is_real_raw and spoof_conf >= MIN_REAL_CONF and ema < 0.45

        old_spoof_state = st["spoof_state"]

        if certain_fake:
            st["consec_fake"] += 1
            st["consec_real"]  = 0
        elif confident_real:
            st["consec_real"] += 1
            st["consec_fake"]  = 0
        else:
            # Không chắc — không tăng chuỗi nào
            pass

        if st["spoof_state"] == "CHECKING":
            if st["consec_fake"] >= self.FAKE_CONFIRM:
                st["spoof_state"] = "FAKE"
                st["pinned"] = False
                st["vote_names"] = []; st["vote_scores"] = []
            elif st["consec_real"] >= self.REAL_CONFIRM:
                st["spoof_state"] = "REAL"
        elif st["spoof_state"] == "REAL":
            if st["consec_fake"] >= self.FAKE_CONFIRM:
                st["spoof_state"] = "FAKE"
                st["pinned"] = False
                st["vote_names"] = []; st["vote_scores"] = []
        elif st["spoof_state"] == "FAKE":
            if st["consec_real"] >= self.REAL_CLEAR and ema < 0.45:
                # ★ Chỉ thoát FAKE nếu EMA cũng đã xuống thấp
                st["spoof_state"] = "REAL"
                st["pinned"] = False
                st["vote_names"] = []; st["vote_scores"] = []

        if st["spoof_state"] != old_spoof_state:
            print(f"[STATE] track={key}: {old_spoof_state}→{st['spoof_state']} "
                  f"fake={st['consec_fake']} real={st['consec_real']} "
                  f"conf={spoof_conf:.2f} ema={ema:.2f}")

        # ── 2. Tên hiển thị và nhận diện ─────────────────────────────────────
        # ★ QUY TẮC DUY NHẤT:
        #   - FAKE state                          → GIA MAO
        #   - Mọi trường hợp còn lại mà chưa chắc → Dang quet...
        #   - REAL state + frame này cũng REAL + EMA thấp → hiện tên
        #
        #   Điều này đảm bảo KHÔNG BAO GIỜ hiện tên người khi đang/sắp FAKE.
        # ─────────────────────────────────────────────────────────────────────
        should_log = False

        if st["spoof_state"] == "FAKE":
            # ── Đã xác nhận giả mạo
            if not st["pinned"]:
                st["name"]   = "GIA MAO"
                st["score"]  = spoof_conf
                st["pinned"] = True
                should_log   = not st["alert_sent"]
                print(f"[PIN-FAKE] track={key}: GIA MAO conf={spoof_conf:.2f} ema={ema:.2f}")
            display_name  = "GIA MAO"
            is_real_final = False

        elif st["spoof_state"] == "REAL" and is_real_raw and ema < 0.35:
            # ── Hiện tên NGAY — không cần tích lũy vote
            #    Điều kiện chặt: state=REAL + frame này REAL + EMA thấp (< 0.35)
            if st["pinned"]:
                display_name  = st["name"]
                is_real_final = True
            else:
                # Nhận diện mỗi RECOG_INTERVAL frame
                if st["recog_frame"] % self.RECOG_INTERVAL == 0 or len(st["vote_names"]) == 0:
                    rec_name, rec_score = self._recognize_cached(emb)
                    st["vote_names"].append(rec_name)
                    st["vote_scores"].append(rec_score)
                    if len(st["vote_names"]) > 5:
                        st["vote_names"].pop(0); st["vote_scores"].pop(0)

                if not st["vote_names"]:
                    display_name  = "Dang quet..."
                    is_real_final = True
                else:
                    # Lấy tên phổ biến nhất trong vote window
                    counter   = Counter(st["vote_names"])
                    best_name, best_count = counter.most_common(1)[0]
                    best_scores = [s for n, s in zip(st["vote_names"], st["vote_scores"]) if n == best_name]
                    best_score  = max(best_scores) if best_scores else 0.0

                    if best_name == "Unknown":
                        stranger_id  = get_stranger_identity(emb)
                        display_name = f"Nguoi_La_{stranger_id}"
                        st["name"]   = display_name
                        st["score"]  = best_score
                    else:
                        display_name = best_name
                        st["name"]   = best_name
                        st["score"]  = best_score
                    is_real_final = True

                    # ★ PIN_VOTES=1 → ghim ngay từ vote đầu tiên (hiện tên tức thì)
                    if best_count >= self.PIN_VOTES:
                        st["pinned"] = True
                        should_log   = not st["alert_sent"]
                        print(f"[PIN-REAL] track={key}: '{display_name}' "
                              f"score={best_score:.2f} ema={ema:.2f}")

        else:
            # ── Tất cả trường hợp còn lại: CHECKING, hoặc REAL nhưng còn nghi ngờ
            # (frame fake, EMA cao, vừa mới chuyển state) → ẩn tên hoàn toàn
            display_name  = "Dang quet..."
            is_real_final = True   # chưa kết luận → không hiện cảnh báo đỏ

        if should_log:
            st["alert_sent"] = True

        return {
            "name":       display_name,
            "score":      st["score"],
            "is_real":    is_real_final,
            "spoof_conf": round(spoof_conf, 3),
            "should_log": should_log,
            "track_id":   key,
        }

    # ── Nhận diện có cache ────────────────────────────────────────────────────
    def _recognize_cached(self, emb):
        cached_name, cached_score = _lookup_face_cache(emb)
        if cached_name is not None:
            return cached_name, cached_score
        name, score = db.recognize(emb, method="hybrid")
        _cache_face_identity(emb, name, score)
        return name, score

    # ── Cleanup tracks cũ ────────────────────────────────────────────────────
    def cleanup(self):
        now = time.time()
        expired = [k for k, st in self._states.items()
                   if now - st["last_seen"] > self.MAX_AGE]
        for k in expired:
            del self._states[k]

    def get_alert_level(self, cam_id: int) -> int:
        return spoof_session_stats[cam_id]["alert_level"]


face_state_tracker = FaceStateTracker()


# ==============================================================================
# LOG + STRANGER
# ==============================================================================
def add_log(name, cam_id, score, face_img=None):
    global LAST_LOG_TIME
    now = time.time()
    if name in LAST_LOG_TIME and now - LAST_LOG_TIME[name] < LOG_COOLDOWN:
        return True
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    camera_name = f"CAM {cam_id + 1}"
    conn = None
    try:
        conn = get_connection()
        if not conn: return False
        cursor = conn.cursor()
        if "GIA_MAO" in name or "Nguoi_La" in name or "Unknown" in name:
            img_blob = None
            if face_img is not None and face_img.size > 0:
                ok, enc = cv2.imencode('.jpg', face_img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
                if ok: img_blob = enc.tobytes()
            cursor.execute(
                "INSERT INTO nguoi_la (thoi_gian, camera, trang_thai, image_data, image_path) VALUES (%s,%s,%s,%s,%s)",
                (now_str, camera_name, name, img_blob, ""))
        else:
            info = db.get_person_info(name)
            dept = info.get('dept') or "Chua cap nhat"
            cursor.execute(
                "INSERT INTO nhat_ky_nhan_dien (thoi_gian, ten, phong_ban, camera, do_tin_cay, trang_thai, image_path) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (now_str, name, dept, camera_name, float(score), "authorized", ""))
        conn.commit(); cursor.close()
        LAST_LOG_TIME[name] = now
        return True
    except Exception as e:
        print(f"❌ Loi DB: {e}")
        return False
    finally:
        if conn:
            try: conn.close()
            except: pass


def get_stranger_identity(embedding):
    global RECENT_STRANGERS, NEXT_STRANGER_ID
    max_score, match_idx = 0, -1
    for i, stranger in enumerate(RECENT_STRANGERS):
        score = float(np.dot(embedding, stranger['embedding']))
        if score > max_score:
            max_score = score; match_idx = i
    if max_score > STRANGER_MATCH_THRESHOLD:
        RECENT_STRANGERS[match_idx]['last_seen'] = time.time()
        return RECENT_STRANGERS[match_idx]['id']
    new_id = NEXT_STRANGER_ID; NEXT_STRANGER_ID += 1
    if len(RECENT_STRANGERS) >= 50: RECENT_STRANGERS.pop(0)
    RECENT_STRANGERS.append({'id': new_id, 'embedding': embedding, 'last_seen': time.time()})
    return new_id


# ==============================================================================
# AI OVERLAY CACHE
# ==============================================================================
ai_overlay_cache = {
    0: {"boxes": [], "faces": [], "last_update": 0},
    1: {"boxes": [], "faces": [], "last_update": 0}
}
lock_overlay = threading.Lock()


# ==============================================================================
# CSRT TRACKER  (FIX #8)
# ==============================================================================
class FaceCSRTTracker:
    MAX_TRACK_AGE = 12

    def __init__(self):
        self.trackers = {}

    def on_detection(self, cam_id, frame, detected_faces):
        h, w = frame.shape[:2]
        new_trackers = []
        for det in detected_faces:
            x1, y1, x2, y2 = det["bbox"]
            x1=max(0,min(x1,w-1)); y1=max(0,min(y1,h-1))
            x2=max(x1+1,min(x2,w)); y2=max(y1+1,min(y2,h))
            bw, bh = x2-x1, y2-y1
            if bw < 10 or bh < 10: continue
            try:
                tracker = cv2.TrackerCSRT_create()
                tracker.init(frame, (x1, y1, bw, bh))
            except:
                tracker = None
            new_trackers.append({
                "tracker": tracker, "bbox": [x1,y1,x2,y2],
                "name": det.get("name","..."), "score": det.get("score",0),
                "is_real": det.get("is_real",True), "spoof_conf": det.get("spoof_conf",0),
                "alert_level": det.get("alert_level",0), "age": 0,
            })
        self.trackers[cam_id] = new_trackers

    def update_frame(self, cam_id, frame):
        h, w = frame.shape[:2]; alive = []
        for t in self.trackers.get(cam_id, []):
            if t["tracker"] is None:
                t["age"] += 1
                if t["age"] < self.MAX_TRACK_AGE: alive.append(t)
                continue
            ok, roi = t["tracker"].update(frame)
            if ok:
                rx,ry,rw,rh = [int(v) for v in roi]
                rx=max(0,min(rx,w-1)); ry=max(0,min(ry,h-1))
                rw=max(10,min(rw,w-rx)); rh=max(10,min(rh,h-ry))
                t["bbox"] = [rx,ry,rx+rw,ry+rh]; t["age"] = 0
                alive.append(t)
            else:
                t["age"] += 1
                if t["age"] < self.MAX_TRACK_AGE: alive.append(t)
        self.trackers[cam_id] = alive
        return [{"bbox": t["bbox"], "name": t["name"], "score": t["score"],
                 "is_real": t["is_real"], "spoof_conf": t["spoof_conf"],
                 "alert_level": t["alert_level"]} for t in alive]


face_csrt_tracker = FaceCSRTTracker()


# ==============================================================================
# SPOOF SESSION STATS + CAPTURE
# ==============================================================================
spoof_history = {0: _deque(maxlen=200), 1: _deque(maxlen=200)}
consecutive_fake = {0: 0, 1: 0}
last_fake_capture = {0: 0.0, 1: 0.0}
spoof_session_stats = {
    0: {"real": 0, "fake": 0, "alert_level": 0, "start": time.time()},
    1: {"real": 0, "fake": 0, "alert_level": 0, "start": time.time()},
}
os.makedirs(os.path.join(BASE_DIR, "fake_captures"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "screenshots"), exist_ok=True)
_spoof_log = os.path.join(BASE_DIR, f"spoof_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
with open(_spoof_log, 'w', encoding='utf-8') as _f:
    _f.write(f"Anti-Spoofing Log v4.0\nStarted: {datetime.now()}\n{'='*50}\n\n")


def _update_spoof_stats(cid, is_real, conf, face_crop):
    global consecutive_fake, last_fake_capture
    spoof_history[cid].append(1 if is_real else 0)
    st = spoof_session_stats[cid]
    if is_real:
        st["real"] += 1; consecutive_fake[cid] = 0
    else:
        st["fake"] += 1; consecutive_fake[cid] += 1
    cf = consecutive_fake[cid]
    st["alert_level"] = 3 if cf>=20 else 2 if cf>=10 else 1 if cf>=5 else 0
    if (not is_real) and conf >= 0.55:
        now = time.time()
        if now - last_fake_capture[cid] >= 3.0:
            last_fake_capture[cid] = now
            try:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fname = os.path.join(BASE_DIR, "fake_captures", f"fake_cam{cid}_{ts}.jpg")
                if face_crop is not None and face_crop.size > 0:
                    cv2.imwrite(fname, face_crop)
                with open(_spoof_log, 'a', encoding='utf-8') as lf:
                    lf.write(f"[{ts}] FAKE cam{cid} | conf={conf:.0%}\n")
            except: pass
    if st["alert_level"] >= 2:
        print(f"[SPOOF] 🚨 ALERT LVL {st['alert_level']} cam{cid} | consec={cf}")


# ==============================================================================
# FACE CACHE  (FIX #3)
# ==============================================================================
_shared_face_cache = {}
_shared_cache_lock = threading.Lock()

def _make_cache_key(emb, n=128):
    return hashlib.md5(emb[:n].round(4).tobytes()).hexdigest()

def _cache_face_identity(emb, name, score):
    key = _make_cache_key(emb)
    with _shared_cache_lock:
        _shared_face_cache[key] = {"name": name, "score": score,
                                    "time": time.time(), "norm": float(np.linalg.norm(emb))}

def _lookup_face_cache(emb, ttl=8.0):
    key = _make_cache_key(emb)
    now = time.time()
    with _shared_cache_lock:
        for k in [k for k,v in _shared_face_cache.items() if now-v["time"]>ttl]:
            del _shared_face_cache[k]
        if key in _shared_face_cache:
            e = _shared_face_cache[key]
            if abs(float(np.linalg.norm(emb)) - e["norm"]) < 0.05:
                return e["name"], e["score"]
            del _shared_face_cache[key]
    return None, None


# ==============================================================================
# NMS
# ==============================================================================
def _nms_faces(faces, iou_threshold=0.4):
    if len(faces) <= 1: return faces
    scored = sorted(faces, key=lambda f: getattr(f, 'det_score', 0), reverse=True)
    keep = []
    for f in scored:
        bbox = f.bbox.astype(int).tolist()
        if not any(calculate_iou(bbox, k.bbox.astype(int).tolist()) > iou_threshold for k in keep):
            keep.append(f)
    return keep

def _dedup_faces(face_results, threshold=0.85):
    if len(face_results) <= 1: return face_results
    kept, used = [], set()
    for i, r in enumerate(face_results):
        if i in used: continue
        best = r
        for j in range(i+1, len(face_results)):
            if j in used: continue
            ei, ej = r.get("_emb"), face_results[j].get("_emb")
            if ei is not None and ej is not None:
                ni, nj = np.linalg.norm(ei), np.linalg.norm(ej)
                sim = float(np.dot(ei,ej)) / (ni*nj) if ni>0 and nj>0 else 0
                if sim > threshold:
                    used.add(j)
                    if face_results[j].get("score",0) > best.get("score",0):
                        best = face_results[j]
        kept.append(best); used.add(i)
    return kept


# ==============================================================================
# PROCESS SINGLE FRAME
# ==============================================================================
DETECT_EVERY_N = 2   # detect mỗi 2 frame — cân bằng tốc độ và độ trễ label

def _process_single_frame(cid: int, frame: np.ndarray, frame_counter: int, is_detect: bool):
    h, w = frame.shape[:2]
    new_boxes = []
    new_faces = []

    # ── YOLO person tracking
    if is_detect:
        try:
            if TRACKING_ENABLED and yolo_model is not None:
                yr = yolo_model.track(frame, conf=0.25, iou=0.5, persist=True,
                                       tracker="bytetrack.yaml", verbose=False,
                                       max_det=10, classes=[0],
                                       imgsz=PERFORMANCE_SETTINGS["yolo_imgsz"])
                if yr and len(yr) > 0:
                    _, tracked = person_tracker.update(frame, yr[0])
                    try: zone_manager.begin_frame(cid)
                    except TypeError:
                        try: zone_manager.begin_frame()
                        except: pass
                    for pid, bbox in tracked.items():
                        is_intruding = False
                        try: is_intruding, _ = zone_manager.check_intrusion(pid, bbox, frame)
                        except: pass
                        new_boxes.append((pid, bbox, is_intruding))
                    try: zone_manager.end_frame(frame, cid)
                    except TypeError:
                        try: zone_manager.end_frame(frame)
                        except: pass
        except Exception as e:
            print(f"[Worker] YOLO-track error cam{cid}: {e}")

    # ── Face detection + recognition + anti-spoof
    if is_detect:
        try:
            # ── Run YOLO anti-spoof ONCE per frame (shared across faces)
            yolo_spoof_dets = fast_spoof.run_yolo(frame, cid)

            raw_faces = multi_scale_detector.detect(frame)
            faces = _nms_faces(raw_faces, iou_threshold=0.4)
            pre_dedup = []

            for f in faces[:5]:
                fbbox = f.bbox.astype(int).tolist()
                fx1, fy1, fx2, fy2 = fbbox
                fw, fh = fx2-fx1, fy2-fy1
                det_score = getattr(f, 'det_score', 0)

                # Quality gates
                if fw < SPOOF_MIN_FACE_SIZE or fh < SPOOF_MIN_FACE_SIZE:
                    new_faces.append({"bbox": fbbox, "name": "...", "score": 0,
                                      "is_real": True, "spoof_conf": 0, "alert_level": 0})
                    continue
                if det_score < 0.5:
                    new_faces.append({"bbox": fbbox, "name": "...", "score": 0,
                                      "is_real": True, "spoof_conf": 0, "alert_level": 0})
                    continue

                crop = frame[max(0,fy1):min(h,fy2), max(0,fx1):min(w,fx2)]
                if crop.size > 0:
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                    if cv2.Laplacian(gray, cv2.CV_64F).var() < 15:
                        new_faces.append({"bbox": fbbox, "name": "...", "score": 0,
                                          "is_real": True, "spoof_conf": 0, "alert_level": 0})
                        continue

                emb, quality = _get_quality_embedding(f, frame)
                if emb is None:
                    new_faces.append({"bbox": fbbox, "name": "...", "score": 0,
                                      "is_real": True, "spoof_conf": 0, "alert_level": 0})
                    continue

                # ── Anti-spoof check (fast, YOLO-first)
                is_real_raw, spoof_conf, spoof_detail = fast_spoof.check(
                    frame, fbbox, crop, cid, yolo_dets=yolo_spoof_dets)

                # ── Update face state (nhận diện ngay, không đợi)
                result = face_state_tracker.update(
                    emb, is_real_raw, spoof_conf, frame, fbbox, cid)

                _update_spoof_stats(cid, result["is_real"], spoof_conf, crop)

                # ── Gửi alert/log nếu cần
                if result["should_log"]:
                    name   = result["name"]
                    score  = result["score"]
                    is_real = result["is_real"]
                    if not is_real and SPOOF_BLOCK_FACE and spoof_conf >= 0.40:
                        try:
                            telegram_notifier.send_spoof_alert(frame, face_bbox=fbbox,
                                                               confidence=spoof_conf, cam_id=cid)
                            add_log(name, cid, spoof_conf, frame)
                        except Exception as e: print(f"[Alert] Spoof: {e}")
                    elif "Nguoi_La" in name:
                        try:
                            telegram_notifier.send_stranger_alert(name, frame, face_bbox=fbbox, cam_id=cid)
                            add_log(name, cid, score, frame)
                        except Exception as e: print(f"[Alert] Stranger: {e}")
                    elif name != "Unknown" and is_real and "GIA" not in name and "quet" not in name:
                        try: add_log(name, cid, score)
                        except Exception as e: print(f"[Log] {e}")

                alert_lvl = spoof_session_stats[cid]["alert_level"]
                pre_dedup.append({
                    "bbox": fbbox, "name": result["name"], "score": result["score"],
                    "is_real": result["is_real"], "spoof_conf": result["spoof_conf"],
                    "alert_level": alert_lvl, "_emb": emb,
                })

            deduped = _dedup_faces(pre_dedup, threshold=0.85)
            for r in deduped:
                r.pop("_emb", None)
                new_faces.append(r)

            if new_faces:
                face_csrt_tracker.on_detection(cid, frame, new_faces)

        except Exception as e:
            print(f"[Worker] Face error cam{cid}: {e}")
    else:
        # Non-detect frame → CSRT tracking only
        tracked = face_csrt_tracker.update_frame(cid, frame)
        if tracked: new_faces = tracked

    return new_boxes, new_faces


# ==============================================================================
# CAMERA THREAD → QUEUE PRODUCER
# ==============================================================================
def camera_thread():
    global global_frame_0, global_frame_1
    print("System: Dang khoi dong WEBCAM...")
    cap0 = None
    for backend in [cv2.CAP_DSHOW, cv2.CAP_ANY]:
        cap0 = cv2.VideoCapture(0, backend)
        if cap0.isOpened():
            print(f"✅ Camera 0 OK (backend={backend})")
            break
        cap0.release(); cap0 = None
    if cap0 is None:
        print("❌ Khong mo duoc webcam 0!")
    else:
        cap0.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap0.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap0.set(cv2.CAP_PROP_FPS, 30)
    fail = 0
    try:
        while True:
            frame0 = None
            if cap0 is not None and cap0.isOpened():
                ret, f = cap0.read()
                if ret and f is not None:
                    frame0 = f; fail = 0
                else:
                    fail += 1
                    if fail >= 30:
                        cap0.release()
                        cap0 = cv2.VideoCapture(0, cv2.CAP_DSHOW); fail = 0
            else:
                fail += 1
                if fail >= 30:
                    cap0 = cv2.VideoCapture(0, cv2.CAP_DSHOW); fail = 0

            with lock:
                global_frame_0 = frame0.copy() if frame0 is not None else None
                global_frame_1 = None

            if frame0 is not None:
                item = {"cam_id": 0, "frame": frame0.copy(), "ts": time.time()}
                try:
                    ai_frame_queue.put_nowait(item)
                except queue.Full:
                    try: ai_frame_queue.get_nowait()
                    except: pass
                    try: ai_frame_queue.put_nowait(item)
                    except: pass
            time.sleep(0.025)
    except Exception as e:
        print(f"❌ Camera thread error: {e}")
    finally:
        if cap0: cap0.release()


t = threading.Thread(target=camera_thread, daemon=True)
t.start()


# ==============================================================================
# AI WORKER THREAD → QUEUE CONSUMER
# ==============================================================================
def ai_worker_thread():
    frame_counter = 0
    print("[AI Worker] Waiting for frames...")
    # Wait for first frame
    while True:
        try:
            item = ai_frame_queue.get(timeout=0.5)
            ai_frame_queue.put_nowait(item); break
        except: continue
    print(f"[AI Worker] ✅ Started! v4.0 REALTIME — DETECT every {DETECT_EVERY_N} frames")

    while True:
        try:
            try:
                item = ai_frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            cid   = item["cam_id"]
            frame = item["frame"]
            frame_counter += 1

            # Periodic cleanup
            if frame_counter % 60 == 0:
                face_state_tracker.cleanup()

            t0 = time.time()
            is_detect = (frame_counter % DETECT_EVERY_N == 0)
            new_boxes, new_faces = _process_single_frame(cid, frame, frame_counter, is_detect)

            with lock_overlay:
                if new_boxes: ai_overlay_cache[cid]["boxes"] = new_boxes
                if new_faces: ai_overlay_cache[cid]["faces"] = new_faces
                ai_overlay_cache[cid]["last_update"] = time.time()

            elapsed = time.time() - t0
            if frame_counter % 30 == 0:
                mode = "DET" if is_detect else "TRK"
                print(f"[AI] {mode}#{frame_counter}: {elapsed*1000:.0f}ms "
                      f"FPS~{1/elapsed:.0f} q={ai_frame_queue.qsize()}")

        except Exception as e:
            print(f"[AI Worker] Error: {e}")
            time.sleep(0.1)


ai_thread = threading.Thread(target=ai_worker_thread, daemon=True)
ai_thread.start()


# ==============================================================================
# VIDEO FEED (MJPEG)
# ==============================================================================
_placeholder_frame = create_placeholder_frame("WAITING FOR CAMERA...")
_ret_ph, _placeholder_jpg = cv2.imencode('.jpg', _placeholder_frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
PLACEHOLDER_JPEG = _placeholder_jpg.tobytes() if _ret_ph else b''


@app.route('/video_feed/<int:cam_id>')
def video_feed(cam_id):
    def generate(cid):
        jpeg_q    = PERFORMANCE_SETTINGS["jpeg_quality"]
        frame_t   = 1.0 / PERFORMANCE_SETTINGS["stream_fps"]
        while True:
            t0 = time.time()
            try:
                with lock:
                    raw = global_frame_0 if cid == 0 else global_frame_1
                if raw is None:
                    yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + PLACEHOLDER_JPEG + b'\r\n'
                    time.sleep(0.1); continue

                disp = raw.copy()
                with lock_overlay:
                    boxes = list(ai_overlay_cache[cid]["boxes"])
                    faces = list(ai_overlay_cache[cid]["faces"])

                # Draw person boxes
                for pid, bbox, is_intruding in boxes:
                    x1,y1,x2,y2 = map(int, bbox)
                    if is_intruding:
                        cv2.rectangle(disp, (x1,y1),(x2,y2),(0,0,255),3)
                        label = f"INTRUDER P{pid}"
                        (tw,th),_ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                        cv2.rectangle(disp,(x1,y1-th-10),(x1+tw+10,y1),(0,0,200),-1)
                        cv2.putText(disp, label,(x1+5,y1-5),cv2.FONT_HERSHEY_SIMPLEX,0.55,(255,255,255),2)
                    else:
                        cv2.rectangle(disp,(x1,y1),(x2,y2),(0,255,0),2)
                        cv2.putText(disp,f"P{pid}",(x1,y1-5),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,255,0),2)

                # Draw face results
                for fd in faces:
                    x1,y1,x2,y2 = fd["bbox"]
                    nm  = fd["name"]; sc = fd["score"]
                    rl  = fd["is_real"]; sp = fd.get("spoof_conf",0)
                    cl  = min(18,(x2-x1)//4,(y2-y1)//4)

                    if not rl:
                        # ── GIẢ MẠO — đỏ nhấp nháy
                        pulse = 3 if int(time.time()*4)%2==0 else 2
                        cv2.rectangle(disp,(x1,y1),(x2,y2),(0,0,255),pulse)
                        for cx,cy,dx,dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
                            cv2.line(disp,(cx,cy),(cx+cl*dx,cy),(0,0,255),3)
                            cv2.line(disp,(cx,cy),(cx,cy+cl*dy),(0,0,255),3)
                        lbl = f"GIA MAO ({int(sp*100)}%)"
                        (tw,th),_ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                        ol = disp.copy()
                        cv2.rectangle(ol,(x1,y1-th-14),(x1+tw+16,y1),(0,0,180),-1)
                        cv2.addWeighted(ol,0.85,disp,0.15,0,disp)
                        cv2.putText(disp,lbl,(x1+8,y1-6),cv2.FONT_HERSHEY_SIMPLEX,0.55,(100,200,255),2)

                    elif nm in ("...","Dang quet...","Scanning..."):
                        # ── Đang quét — vàng nhạt
                        cv2.rectangle(disp,(x1,y1),(x2,y2),(0,220,255),1)
                        for cx,cy,dx,dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
                            cv2.line(disp,(cx,cy),(cx+cl*dx,cy),(0,230,255),2)
                            cv2.line(disp,(cx,cy),(cx,cy+cl*dy),(0,230,255),2)
                        cv2.putText(disp,"Scanning...",(x1+4,y1-6),cv2.FONT_HERSHEY_SIMPLEX,0.45,(0,230,255),1)

                    elif "Nguoi_La" in nm or nm == "Unknown":
                        # ── Người lạ — cam
                        cv2.rectangle(disp,(x1,y1),(x2,y2),(0,140,255),2)
                        for cx,cy,dx,dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
                            cv2.line(disp,(cx,cy),(cx+cl*dx,cy),(0,165,255),3)
                            cv2.line(disp,(cx,cy),(cx,cy+cl*dy),(0,165,255),3)
                        ol = disp.copy()
                        (tw,_th),_ = cv2.getTextSize("NGUOI LA",cv2.FONT_HERSHEY_SIMPLEX,0.6,2)
                        cv2.rectangle(ol,(x1,y1-_th-14),(x1+tw+16,y1),(0,100,200),-1)
                        cv2.addWeighted(ol,0.8,disp,0.2,0,disp)
                        cv2.putText(disp,"NGUOI LA",(x1+8,y1-6),cv2.FONT_HERSHEY_SIMPLEX,0.6,(255,255,255),2)

                    else:
                        # ── Người quen — vàng xanh
                        cv2.rectangle(disp,(x1,y1),(x2,y2),(255,180,0),2)
                        for cx,cy,dx,dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
                            cv2.line(disp,(cx,cy),(cx+cl*dx,cy),(255,220,50),2)
                            cv2.line(disp,(cx,cy),(cx,cy+cl*dy),(255,220,50),2)
                        disp = put_text_utf8(disp, f"{nm} ({int(sc*100)}%)", (x1,y1-30),(255,220,50))

                try: disp = zone_manager.draw_zones(disp)
                except: pass
                try: disp = zone_manager.draw_recording_status(disp)
                except: pass

                # FPS overlay
                fps = int(1.0/max(0.001, time.time()-t0))
                so = disp.copy()
                cv2.rectangle(so,(0,0),(240,32),(40,40,40),-1)
                cv2.addWeighted(so,0.6,disp,0.4,0,disp)
                cv2.putText(disp,f"CAM {cid+1} | FPS:{fps}",(8,22),cv2.FONT_HERSHEY_SIMPLEX,0.55,(0,255,120),2)

                al = spoof_session_stats[cid]["alert_level"]
                if al >= 1:
                    hd,wd = disp.shape[:2]
                    o = disp.copy()
                    cv2.rectangle(o,(0,0),(wd,hd),(0,0,180),8)
                    cv2.addWeighted(o,0.25,disp,0.75,0,disp)
                if al >= 2:
                    hd,wd = disp.shape[:2]
                    banner = f"!! PHAT HIEN GIA MAO !! [L{al}]"
                    (tw,_th),_ = cv2.getTextSize(banner,cv2.FONT_HERSHEY_SIMPLEX,0.7,2)
                    bo = disp.copy()
                    cv2.rectangle(bo,(0,hd-45),(wd,hd),(0,0,160),-1)
                    cv2.addWeighted(bo,0.75,disp,0.25,0,disp)
                    cv2.putText(disp,banner,((wd-tw)//2,hd-12),cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,255,255),2)

                ret, buf = cv2.imencode('.jpg', disp, [cv2.IMWRITE_JPEG_QUALITY, jpeg_q])
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                       (buf.tobytes() if ret else PLACEHOLDER_JPEG) + b'\r\n')

            except GeneratorExit: return
            except Exception as e:
                print(f"[Stream CAM{cid}] {e}")
                try: yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + PLACEHOLDER_JPEG + b'\r\n'
                except: return
                time.sleep(0.1); continue

            sl = max(0, frame_t - (time.time()-t0))
            if sl > 0: time.sleep(sl)

    resp = Response(generate(cam_id), mimetype='multipart/x-mixed-replace; boundary=frame')
    resp.headers.update({
        'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0',
        'Pragma': 'no-cache', 'Expires': '0',
        'X-Accel-Buffering': 'no', 'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': 'http://localhost:3000',
    })
    return resp


@app.route('/snapshot/<int:cam_id>')
def snapshot(cam_id):
    with lock:
        frame = global_frame_0 if cam_id == 0 else global_frame_1
    if frame is None:
        return Response(PLACEHOLDER_JPEG, mimetype='image/jpeg')
    disp = frame.copy()
    with lock_overlay:
        faces = list(ai_overlay_cache[cam_id]["faces"])
        boxes = list(ai_overlay_cache[cam_id]["boxes"])
    for pid,bbox,intr in boxes:
        x1,y1,x2,y2 = map(int,bbox)
        cv2.rectangle(disp,(x1,y1),(x2,y2),(0,0,255) if intr else (0,255,0),2)
    for fd in faces:
        x1,y1,x2,y2 = fd["bbox"]; fn=fd["name"]; fs=fd["score"]
        if not fd["is_real"]:
            cv2.rectangle(disp,(x1,y1),(x2,y2),(0,0,255),2)
            cv2.putText(disp,"FAKE",(x1,y1-10),cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,0,255),2)
        elif fn not in ("Unknown","..."):
            cv2.rectangle(disp,(x1,y1),(x2,y2),(255,200,0),2)
            cv2.putText(disp,f"{fn} ({int(fs*100)}%)",(x1,y1-10),cv2.FONT_HERSHEY_SIMPLEX,0.6,(255,200,0),2)
    ret, buf = cv2.imencode('.jpg', disp, [cv2.IMWRITE_JPEG_QUALITY, 65])
    return Response(buf.tobytes() if ret else PLACEHOLDER_JPEG, mimetype='image/jpeg',
                    headers={'Cache-Control': 'no-cache'})


@app.route('/test_video/<int:cam_id>')
def test_video(cam_id):
    def gen(cid):
        while True:
            with lock:
                frame = global_frame_0 if cid == 0 else global_frame_1
            if frame is None:
                yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + PLACEHOLDER_JPEG + b'\r\n'
                time.sleep(0.1); continue
            d = frame.copy()
            cv2.putText(d, f"RAW CAM {cid}", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
            ret, buf = cv2.imencode('.jpg', d, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ret: yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n'
            time.sleep(0.033)
    resp = Response(gen(cam_id), mimetype='multipart/x-mixed-replace; boundary=frame')
    resp.headers['Cache-Control'] = 'no-cache, no-store'
    resp.headers['X-Accel-Buffering'] = 'no'
    return resp


# ==============================================================================
# API ROUTES (giữ nguyên 100%)
# ==============================================================================
@app.route('/api/spoof-stats', methods=['GET'])
def get_spoof_stats():
    result = {}
    for cid in [0, 1]:
        st = spoof_session_stats[cid]
        hist = list(spoof_history[cid])
        total = st["real"] + st["fake"]
        result[f"cam{cid}"] = {
            "real": st["real"], "fake": st["fake"], "total": total,
            "real_pct": round(st["real"]/max(total,1)*100, 1),
            "fake_pct": round(st["fake"]/max(total,1)*100, 1),
            "consecutive_fake": consecutive_fake[cid],
            "alert_level": st["alert_level"],
            "uptime_s": round(time.time()-st["start"], 0),
            "history_tail": hist[-20:],
        }
    result["fake_captures_dir"] = os.path.join(BASE_DIR, "fake_captures")
    result["log_file"] = _spoof_log
    return jsonify(result)

@app.route('/api/spoof-stats/reset', methods=['POST'])
def reset_spoof_stats():
    for cid in [0, 1]:
        spoof_session_stats[cid].update({"real":0,"fake":0,"alert_level":0,"start":time.time()})
        consecutive_fake[cid] = 0; spoof_history[cid].clear()
    return jsonify({"success": True})

@app.route('/api/spoof-stats/captures', methods=['GET'])
def list_fake_captures():
    cap_dir = os.path.join(BASE_DIR, "fake_captures"); files = []
    if os.path.exists(cap_dir):
        for f in sorted(os.listdir(cap_dir), reverse=True)[:50]:
            if f.endswith('.jpg'):
                fpath = os.path.join(cap_dir, f)
                files.append({"filename": f, "size_kb": round(os.path.getsize(fpath)/1024,1),
                               "url": f"/api/spoof-stats/capture/{f}"})
    return jsonify({"count": len(files), "captures": files})

@app.route('/api/spoof-stats/capture/<filename>')
def serve_fake_capture(filename):
    return send_from_directory(os.path.join(BASE_DIR, "fake_captures"), filename)

@app.route('/api/spoof-calibration', methods=['GET'])
def get_spoof_calibration():
    return jsonify({
        "adaptive_recognition_threshold": adaptive_threshold.get_threshold(),
        "fake_confirm_frames": FaceStateTracker.FAKE_CONFIRM,
        "real_confirm_frames": FaceStateTracker.REAL_CONFIRM,
        "pin_votes": FaceStateTracker.PIN_VOTES,
        "queue_size": ai_frame_queue.qsize(),
        "queue_maxsize": AI_FRAME_QUEUE_SIZE,
    })

@app.route('/api/spoof-calibration', methods=['POST'])
def update_spoof_calibration():
    try:
        data = request.get_json()
        # Có thể mở rộng để điều chỉnh ngưỡng runtime nếu cần
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    try: data = request.get_json(force=True)
    except: data = request.form.to_dict()
    user = USERS.get(data.get('username','').split('@')[0])
    if user and user['password'] == data.get('password'):
        session['user'] = user['name']
        return jsonify({"success": True, "user": user})
    return jsonify({"success": False}), 401

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear(); return jsonify({"success": True})

@app.route('/api/me', methods=['GET'])
def api_me():
    if 'user' in session:
        return jsonify({"authenticated": True, "user": USERS.get(session.get('user'))})
    return jsonify({"authenticated": False})

@app.route('/nguoi_dung', methods=['GET'])
def get_user_all():
    conn = None
    try:
        conn = get_connection()
        if not conn: return jsonify({"status":"error"}),500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM nhan_vien ORDER BY ma_nv DESC")
        data = cursor.fetchall(); cursor.close()
        return jsonify({"status":"success","data":data})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)}),500
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/delete_employee', methods=['DELETE'])
def delete_employee():
    conn = None
    try:
        ma_nv = request.get_json().get('ma_nv')
        conn = get_connection()
        if not conn: return jsonify({"success":False}),500
        cursor = conn.cursor()
        cursor.execute("DELETE FROM face_embeddings WHERE ma_nv=%s",(ma_nv,))
        cursor.execute("DELETE FROM nhan_vien WHERE ma_nv=%s",(ma_nv,))
        conn.commit(); cursor.close(); db.reload_db()
        return jsonify({"success":True})
    except Exception as e:
        return jsonify({"success":False,"message":str(e)}),500
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/update_employee', methods=['POST'])
def update_employee():
    conn = None
    try:
        d = request.get_json(); conn = get_connection()
        if not conn: return jsonify({"success":False}),500
        cursor = conn.cursor()
        cursor.execute("UPDATE nhan_vien SET ho_ten=%s,email=%s,sdt=%s,dia_chi=%s,ten_phong=%s,ten_chuc_vu=%s,trang_thai=%s WHERE ma_nv=%s",
                       (d.get('ho_ten'),d.get('email'),d.get('sdt'),d.get('dia_chi'),
                        d.get('ten_phong'),d.get('ten_chuc_vu'),d.get('trang_thai'),d.get('ma_nv')))
        conn.commit(); cursor.close()
        return jsonify({"success":True})
    except Exception as e:
        return jsonify({"success":False,"message":str(e)}),500
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/dashboard-stats', methods=['GET'])
def get_dashboard_stats():
    stats = {"present_count":0,"total_employees":0,"warning_count":0,"logs":[]}
    conn = None
    try:
        conn = get_connection()
        if conn:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT COUNT(*) as c FROM nhan_vien")
            stats['total_employees'] = cur.fetchone()['c']
            cur.execute("SELECT COUNT(DISTINCT trang_thai) as c FROM nguoi_la WHERE DATE(thoi_gian)=CURDATE()")
            stats['warning_count'] = cur.fetchone()['c']
            cur.execute("SELECT COUNT(DISTINCT ten) as c FROM nhat_ky_nhan_dien WHERE DATE(thoi_gian)=CURDATE()")
            stats['present_count'] = cur.fetchone()['c']
            cur.execute("SELECT * FROM nhat_ky_nhan_dien ORDER BY id DESC LIMIT 10")
            for row in cur.fetchall():
                stats['logs'].append({"id":row['id'],"name":row['ten'],"dept":row['phong_ban'],
                                      "loc":row['camera'],"time":row['thoi_gian'].strftime("%H:%M:%S %d/%m"),
                                      "status":"Hop le"})
            cur.close()
    except Exception as e: print(f"Dashboard Error: {e}")
    finally:
        if conn:
            try: conn.close()
            except: pass
    import random
    stats.update({"gpu_load":random.randint(10,40),"temp":random.randint(45,65)})
    return jsonify(stats)

@app.route('/api/security/alerts', methods=['GET'])
def get_security_alerts():
    conn = None
    try:
        conn = get_connection()
        if not conn: return jsonify([])
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id,thoi_gian,camera,trang_thai FROM nguoi_la ORDER BY thoi_gian DESC LIMIT 100")
        rows = cursor.fetchall(); cursor.close(); grouped = []
        for row in rows:
            dt = row['thoi_gian']; img_url = f"http://localhost:5000/api/image/view/{row['id']}"
            detail = {"time":dt.strftime("%H:%M:%S"),"img":img_url}
            name=row['trang_thai']; cam=row['camera']; found=False
            for g in grouped:
                if g['location']==name and g['cam']==cam:
                    g['count']+=1; g['details'].append(detail); g['img']=img_url; found=True; break
            if not found:
                grouped.append({"id":row['id'],"location":name,"cam":cam,
                                "date":dt.strftime("%d/%m/%Y"),"time":dt.strftime("%H:%M:%S"),
                                "img":img_url,"count":1,"details":[detail]})
        return jsonify(grouped)
    except: return jsonify([])
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/security/blacklist', methods=['GET'])
def get_blacklist():
    conn = None
    try:
        conn = get_connection()
        if not conn: return jsonify([])
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM blacklist ORDER BY id DESC")
        rows = cursor.fetchall(); gl=[]; pn={}
        for r in rows:
            name=r['name']; img=r['image_path'] or "https://placehold.co/400"
            ds=r['created_at'].strftime("%d/%m/%Y"); ts=r['created_at'].strftime("%H:%M:%S")
            di={"time":ts,"img":img,"reason":r['reason']}
            if name in pn:
                gl[pn[name]]['count']+=1; gl[pn[name]]['details'].append(di)
            else:
                gl.append({"id":r['id'],"name":name,"reason":r['reason'],"date":ds,"img":img,
                           "status":"Dangerous","count":1,"location":"Blacklist","cam":"DB","details":[di]})
                pn[name] = len(gl)-1
        cursor.close(); return jsonify(gl)
    except: return jsonify([])
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/security/blacklist/add', methods=['POST'])
def add_to_blacklist():
    conn = None
    try:
        d=request.get_json(); conn=get_connection()
        if not conn: return jsonify({"success":False}),500
        cursor=conn.cursor()
        cursor.execute("INSERT INTO blacklist (name,reason,image_path,created_at) VALUES (%s,%s,%s,%s)",
                       (d.get('name'),d.get('reason'),d.get('image'),datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit(); cursor.close(); return jsonify({"success":True})
    except Exception as e:
        return jsonify({"success":False,"message":str(e)}),500
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/security/blacklist/<int:bl_id>', methods=['DELETE'])
def delete_from_blacklist(bl_id):
    conn = None
    try:
        conn=get_connection()
        if not conn: return jsonify({"success":False}),500
        cursor=conn.cursor()
        cursor.execute("DELETE FROM blacklist WHERE id=%s",(bl_id,))
        conn.commit(); af=cursor.rowcount; cursor.close()
        return jsonify({"success":True}) if af>0 else jsonify({"success":False}),404
    except Exception as e:
        return jsonify({"success":False,"message":str(e)}),500
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/security/alerts/<int:alert_id>/verify', methods=['PUT'])
def verify_alert(alert_id):
    conn = None
    try:
        conn=get_connection()
        if not conn: return jsonify({"success":False}),500
        cursor=conn.cursor()
        cursor.execute("UPDATE nguoi_la SET trang_thai='Da xac minh' WHERE id=%s",(alert_id,))
        conn.commit(); cursor.close(); return jsonify({"success":True})
    except Exception as e:
        return jsonify({"success":False,"message":str(e)}),500
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/security/intrusion-events', methods=['GET'])
def get_intrusion_events():
    try:
        page=int(request.args.get('page',1)); per_page=int(request.args.get('per_page',12))
        date_filter=request.args.get('date',None)
        rdir=Path(BASE_DIR)/"intrusion_recordings"; sdir=Path(BASE_DIR)/"intrusion_snapshots"; events=[]
        if rdir.exists():
            for vf in sorted(rdir.glob("*.mp4"),reverse=True):
                stat=vf.stat(); created=datetime.fromtimestamp(stat.st_ctime)
                if date_filter:
                    try:
                        if created.date()!=datetime.strptime(date_filter,"%Y-%m-%d").date(): continue
                    except: pass
                ms=[]
                if sdir.exists():
                    for sf in sdir.glob("*.jpg"):
                        st2=sf.stat(); st2t=datetime.fromtimestamp(st2.st_ctime)
                        if abs((st2t-created).total_seconds())<300:
                            ms.append({"filename":sf.name,"url":f"http://localhost:5000/api/security/snapshot/{sf.name}",
                                       "time":st2t.strftime("%Y-%m-%d %H:%M:%S")})
                events.append({"id":len(events)+1,"video_filename":vf.name,
                               "video_url":f"http://localhost:5000/api/tracking/video/{vf.name}",
                               "cam_id":vf.stem.split('_')[0],"timestamp":created.strftime("%Y-%m-%d %H:%M:%S"),
                               "date":created.strftime("%Y-%m-%d"),"time":created.strftime("%H:%M:%S"),
                               "size_mb":round(stat.st_size/(1024*1024),2),"snapshots":ms[:5],
                               "snapshot_count":len(ms),"thumbnail":ms[0]["url"] if ms else None})
        total=len(events); start=(page-1)*per_page
        return jsonify({"events":events[start:start+per_page],"total":total,"page":page,
                        "total_pages":(total+per_page-1)//per_page if total>0 else 0})
    except Exception as e:
        return jsonify({"events":[],"total":0,"error":str(e)})

@app.route('/api/security/intrusion-events/<int:event_id>', methods=['GET'])
def get_intrusion_event_detail(event_id):
    try:
        rdir=Path(BASE_DIR)/"intrusion_recordings"; sdir=Path(BASE_DIR)/"intrusion_snapshots"
        videos=sorted(rdir.glob("*.mp4"),reverse=True) if rdir.exists() else []
        if event_id<1 or event_id>len(videos): return jsonify({"error":"Not found"}),404
        vf=videos[event_id-1]; stat=vf.stat(); created=datetime.fromtimestamp(stat.st_ctime)
        snaps=[]
        if sdir.exists():
            for sf in sorted(sdir.glob("*.jpg"),reverse=True):
                st2=sf.stat(); st2t=datetime.fromtimestamp(st2.st_ctime)
                if abs((st2t-created).total_seconds())<300:
                    snaps.append({"filename":sf.name,"url":f"http://localhost:5000/api/security/snapshot/{sf.name}",
                                  "time":st2t.strftime("%Y-%m-%d %H:%M:%S")})
        return jsonify({"id":event_id,"video_filename":vf.name,
                        "video_url":f"http://localhost:5000/api/tracking/video/{vf.name}",
                        "timestamp":created.strftime("%Y-%m-%d %H:%M:%S"),
                        "size_mb":round(stat.st_size/(1024*1024),2),"snapshots":snaps,"snapshot_count":len(snaps)})
    except Exception as e:
        return jsonify({"error":str(e)}),500

@app.route('/api/security/snapshot/<filename>')
def serve_snapshot(filename):
    return send_from_directory(str(Path(BASE_DIR)/"intrusion_snapshots"), filename)

@app.route('/api/image/view/<int:log_id>')
def view_image_from_db(log_id):
    conn=None
    try:
        conn=get_connection()
        if not conn: return "DB fail",500
        cursor=conn.cursor()
        cursor.execute("SELECT image_data FROM nguoi_la WHERE id=%s",(log_id,))
        row=cursor.fetchone(); cursor.close()
        if row and row[0]: return Response(row[0],mimetype='image/jpeg')
        return Response(b'',mimetype='image/jpeg')
    except: return "Error",500
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/door-status', methods=['GET'])
def get_door_status():
    return jsonify({"door_status":"CLOSED","last_user":None,"time":None})

@app.route('/api/anti-spoof-status', methods=['GET'])
def get_anti_spoof_status():
    with lock_spoof:
        return jsonify({"enabled":SPOOF_CHECK_ENABLED,"camera_0":anti_spoof_state[0],"camera_1":anti_spoof_state[1]})

@app.route('/api/tracking/stats', methods=['GET'])
def get_tracking_stats():
    try: ts=person_tracker.get_stats()
    except: ts={}
    try: rs=zone_manager.recorder.get_stats()
    except: rs={}
    try: zc=zone_manager.get_zone_count()
    except: zc=0
    return jsonify({"tracking_enabled":TRACKING_ENABLED,"total_unique_people":ts.get('total_unique_people',0),
                    "current_active":ts.get('current_active',0),"zones_count":zc,
                    "is_recording":rs.get('is_recording',False),"total_recordings":rs.get('total_recordings',0)})

@app.route('/api/tracking/zones', methods=['GET'])
def get_zones():
    return jsonify({"zones":zone_manager.get_zones(),"count":zone_manager.get_zone_count()})

@app.route('/api/tracking/zones', methods=['POST'])
def add_zone():
    try:
        data=request.get_json(); points=data.get('points',[])
        if len(points)<3: return jsonify({"success":False}),400
        zone_manager.add_zone([(p['x'],p['y']) for p in points])
        return jsonify({"success":True})
    except Exception as e:
        return jsonify({"success":False,"message":str(e)}),500

@app.route('/api/tracking/zones', methods=['DELETE'])
def clear_zones():
    zone_manager.clear_all_zones(); return jsonify({"success":True})

@app.route('/api/tracking/recordings', methods=['GET'])
def get_recordings():
    try:
        rdir=Path(BASE_DIR)/"intrusion_recordings"; recs=[]
        if rdir.exists():
            for vf in sorted(rdir.glob("*.mp4"),reverse=True)[:100]:
                stat=vf.stat()
                if stat.st_size<1024: continue
                recs.append({"filename":vf.name,"size_mb":round(stat.st_size/(1024*1024),2),
                             "created":datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")})
        return jsonify({"recordings":recs,"count":len(recs)})
    except Exception as e:
        return jsonify({"recordings":[],"error":str(e)})

@app.route('/api/tracking/video/<filename>')
def stream_recording(filename):
    vdir=Path(BASE_DIR)/"intrusion_recordings"; vp=vdir/filename
    if not vp.exists(): return jsonify({"error":"Not found"}),404
    return send_from_directory(str(vdir),filename,mimetype='video/mp4',conditional=True)

@app.route('/api/tracking/config', methods=['GET'])
def get_tracking_config():
    return jsonify({"tracking_enabled":TRACKING_ENABLED,
                    "telegram_enabled":telegram_notifier.enabled if telegram_notifier else False,
                    "zones_count":zone_manager.get_zone_count()})

@app.route('/api/tracking/config', methods=['POST'])
def update_tracking_config():
    global TRACKING_ENABLED
    try:
        data=request.get_json()
        if 'tracking_enabled' in data: TRACKING_ENABLED=bool(data['tracking_enabled'])
        return jsonify({"success":True,"tracking_enabled":TRACKING_ENABLED})
    except Exception as e:
        return jsonify({"success":False,"message":str(e)}),500

@app.route('/api/performance', methods=['GET'])
def get_performance_settings():
    return jsonify(PERFORMANCE_SETTINGS)

@app.route('/api/performance', methods=['POST'])
def update_performance_settings():
    try:
        data=request.get_json()
        if 'ai_skip_frames' in data: PERFORMANCE_SETTINGS["ai_skip_frames"]=max(1,min(10,int(data['ai_skip_frames'])))
        if 'yolo_imgsz' in data:     PERFORMANCE_SETTINGS["yolo_imgsz"]=max(160,min(640,int(data['yolo_imgsz'])))
        if 'jpeg_quality' in data:   PERFORMANCE_SETTINGS["jpeg_quality"]=max(30,min(100,int(data['jpeg_quality'])))
        if 'stream_fps' in data:     PERFORMANCE_SETTINGS["stream_fps"]=max(10,min(60,int(data['stream_fps'])))
        return jsonify({"success":True,"settings":PERFORMANCE_SETTINGS})
    except Exception as e:
        return jsonify({"success":False,"message":str(e)}),500

@app.route('/api/add_employee_with_faces', methods=['POST'])
def add_employee_with_faces():
    conn = None
    try:
        ho_ten=request.form.get('ho_ten'); email=request.form.get('email')
        sdt=request.form.get('sdt',''); dia_chi=request.form.get('dia_chi','')
        ten_phong=request.form.get('ten_phong',''); ten_chuc_vu=request.form.get('ten_chuc_vu','')
        trang_thai=request.form.get('trang_thai','Dang_Lam')
        if not ho_ten or not email: return jsonify({"success":False,"message":"Thieu thong tin"}),400
        conn=get_connection()
        if not conn: return jsonify({"success":False,"message":"DB fail"}),500
        cursor=conn.cursor()
        cursor.execute("INSERT INTO nhan_vien (ho_ten,email,sdt,dia_chi,ten_phong,ten_chuc_vu,trang_thai) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                       (ho_ten,email,sdt,dia_chi,ten_phong,ten_chuc_vu,trang_thai))
        conn.commit(); ma_nv=cursor.lastrowid
        face_files=request.files.getlist('faces'); embeddings=[]; rejected=[]
        if face_files:
            for idx, file in enumerate(face_files):
                if not (file and file.filename): continue
                file_bytes=np.frombuffer(file.read(),np.uint8)
                img=cv2.imdecode(file_bytes,cv2.IMREAD_COLOR)
                if img is None: rejected.append(f"Anh {idx+1}: Khong doc duoc"); continue
                faces=face_app.get(img)
                if len(faces)==0: rejected.append(f"Anh {idx+1}: Khong phat hien mat"); continue
                if len(faces)>1:  rejected.append(f"Anh {idx+1}: {len(faces)} mat"); continue
                face=faces[0]
                qi=check_face_quality(face,img)
                if qi: rejected.append(f"Anh {idx+1}: {'; '.join(qi)}"); continue
                embeddings.append(face.normed_embedding.tolist())
                bbox=face.bbox.astype(int); bx1,by1,bx2,by2=bbox
                fc=img[max(0,by1):min(img.shape[0],by2),max(0,bx1):min(img.shape[1],bx2)]
                if fc.size>0: _save_enrollment_image(ma_nv,fc,idx)
        if embeddings:
            for se in embeddings:
                cursor.execute("INSERT INTO face_embeddings (ma_nv,vector_data) VALUES (%s,%s)",(ma_nv,json.dumps(se)))
            conn.commit(); db.reload_db()
            msg=f"Da luu {len(embeddings)} khuon mat."
        else:
            msg="Chua co anh hop le."
        if rejected: msg+=f" Tu choi {len(rejected)}: "+("; ".join(rejected))
        cursor.close()
        return jsonify({"success":True,"message":msg,"ma_nv":ma_nv,"accepted":len(embeddings),"rejected":rejected})
    except Exception as e:
        return jsonify({"success":False,"message":str(e)}),500
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/training-data', methods=['GET'])
def get_training_data():
    conn=None
    try:
        conn=get_connection()
        if not conn: return jsonify({"success":False}),500
        cursor=conn.cursor(dictionary=True)
        cursor.execute("""SELECT nv.ma_nv,nv.ho_ten,nv.email,nv.ten_phong,nv.ten_chuc_vu,nv.trang_thai,
                          fe.id as embedding_id,fe.vector_data FROM nhan_vien nv
                          LEFT JOIN face_embeddings fe ON nv.ma_nv=fe.ma_nv ORDER BY nv.ma_nv""")
        rows=cursor.fetchall(); emps={}
        for row in rows:
            mv=row['ma_nv']
            if mv not in emps:
                emps[mv]={"ma_nv":mv,"ho_ten":row['ho_ten'],"email":row['email'],
                          "ten_phong":row['ten_phong'] or "N/A","ten_chuc_vu":row['ten_chuc_vu'] or "N/A",
                          "vectors":[],"vector_count":0,"has_face_data":False}
            if row['vector_data']:
                try:
                    arr=np.array(json.loads(row['vector_data']),dtype=np.float32)
                    if arr.ndim==1:
                        norm=float(np.linalg.norm(arr))
                        emps[mv]["vectors"].append({"embedding_id":row['embedding_id'],"dim":len(arr),
                                                    "norm":round(norm,4),"is_normalized":abs(norm-1.0)<0.01})
                except: pass
        for mv,emp in emps.items():
            emp["vector_count"]=len(emp["vectors"]); emp["has_face_data"]=len(emp["vectors"])>0
        cursor.close()
        te=len(emps); wf=sum(1 for e in emps.values() if e["has_face_data"])
        tv=sum(e["vector_count"] for e in emps.values())
        return jsonify({"success":True,"summary":{"total_employees":te,"with_face_data":wf,
                        "without_face_data":te-wf,"total_vectors":tv},"employees":list(emps.values())})
    except Exception as e:
        return jsonify({"success":False,"message":str(e)}),500
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/queue-stats', methods=['GET'])
def get_queue_stats():
    return jsonify({
        "ai_frame_queue_size": ai_frame_queue.qsize(),
        "ai_frame_queue_maxsize": AI_FRAME_QUEUE_SIZE,
        "face_tracks_active": len(face_state_tracker._states),
        "face_cache_size": len(_shared_face_cache),
    })


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 SERVER v4.0 — REALTIME | INSTANT RECOGNITION")
    print("")
    print("  Pipeline:   Camera → Queue(2) → AI Worker → MJPEG")
    print("  Anti-Spoof: YOLO-first (1-frame decision) + Texture + Screen")
    print("  Spoof gate: FAKE_CONFIRM=2 frames | REAL_CONFIRM=2 frames")
    print("  Recognition: Hiển thị NGAY — pin sau 2 vote đồng nhất")
    print("  Detect:     mỗi 3 frames | Track: CSRT interpolation")
    print("")
    print(f"  MJPEG:  http://localhost:5000/video_feed/0")
    print(f"  Stats:  http://localhost:5000/api/queue-stats")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)