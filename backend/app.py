import cv2
import numpy as np
import insightface
from insightface.app import FaceAnalysis
import os
import time
from pathlib import Path
from datetime import datetime
from flask import Flask, Response, request, jsonify, session, redirect, url_for, send_from_directory
import threading
import json
import hashlib
from PIL import Image, ImageDraw, ImageFont
from collections import Counter
from functools import wraps
from flask_cors import CORS


# Import kết nối CSDL
from database import get_connection
# Import YOLO best.pt (Anti-Spoof) + Tracking Module
import torch
from ultralytics import YOLO
from tracking_module import TelegramNotifier, ZoneManager, FixedPersonTracker


# ==============================================================================
# IMPORTS FROM MODULAR ARCHITECTURE
# ==============================================================================
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

try:
    from utils.image_utils import preprocess_face_for_spoof
except ImportError:
    def preprocess_face_for_spoof(face_crop, full_frame=None, face_bbox=None,
                                    target_size=224, padding_ratio=0.3):
        if full_frame is not None and face_bbox is not None:
            h, w = full_frame.shape[:2]
            x1, y1, x2, y2 = face_bbox
            fw, fh = x2 - x1, y2 - y1
            pad_w = int(fw * padding_ratio)
            pad_h = int(fh * padding_ratio)
            nx1 = max(0, x1 - pad_w)
            ny1 = max(0, y1 - pad_h)
            nx2 = min(w, x2 + pad_w)
            ny2 = min(h, y2 + pad_h)
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

from utils.auth_utils import login_required

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')
app.secret_key = SECRET_KEY
np.int = int
CORS(app, resources={r"/*": {"origins": CORS_ORIGINS}}, supports_credentials=True)

# ==============================================================================
# CONFIRMATION BUFFER SETTINGS
# ==============================================================================
try:
    from config.settings import CONFIRMATION_TIME_STRANGER, CONFIRMATION_TIME_SPOOF, CONFIRMATION_DISAPPEAR_TIMEOUT, SPOOF_MIN_FACE_SIZE
except ImportError:
    CONFIRMATION_TIME_STRANGER = 3.0
    CONFIRMATION_TIME_SPOOF = 3.0
    CONFIRMATION_DISAPPEAR_TIMEOUT = 1.5
    SPOOF_MIN_FACE_SIZE = 60

# ==============================================================================
# GLOBAL STATE
# ==============================================================================
lock = threading.Lock()
global_frame_0 = None
global_frame_1 = None
lock_spoof = threading.Lock()
trackers_state = {0: [], 1: []}
RECENT_STRANGERS = []
NEXT_STRANGER_ID = 1
LAST_LOG_TIME = {}
anti_spoof_state = {0: {"is_live": True, "confidence": 0.5}, 1: {"is_live": True, "confidence": 0.5}}

# ★ FIX #19: Enrollment Image Backup Directory
ENROLLMENT_BACKUP_DIR = os.path.join(BASE_DIR, "enrollment_images")
os.makedirs(ENROLLMENT_BACKUP_DIR, exist_ok=True)


# ==============================================================================
# ★ FIX #5 + #12: FACE QUALITY GATE FUNCTION
# ==============================================================================
def _get_quality_embedding(face, frame):
    emb = face.normed_embedding
    bbox = face.bbox.astype(int)
    x1, y1, x2, y2 = bbox
    h, w = frame.shape[:2]
    det_score = getattr(face, 'det_score', 0)
    if det_score < 0.5:
        return None, 0
    face_w = x2 - x1
    face_h = y2 - y1
    if face_w < 40 or face_h < 40:
        return None, 0
    ratio = face_w / max(face_h, 1)
    if ratio < 0.4 or ratio > 1.5:
        return None, 0
    border_margin = 10
    quality = det_score
    if x1 < border_margin or y1 < border_margin or \
       x2 > w - border_margin or y2 > h - border_margin:
        quality = det_score * 0.8
    face_crop = frame[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
    if face_crop.size > 0:
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        if blur_score < 20:
            return None, 0
    return emb, quality


# ==============================================================================
# ★ FIX #4: ENROLLMENT QUALITY CHECK
# ==============================================================================
def check_face_quality(face, img):
    issues = []
    bbox = face.bbox.astype(int)
    x1, y1, x2, y2 = bbox
    face_w = x2 - x1
    face_h = y2 - y1
    if face_w < 80 or face_h < 80:
        issues.append(f"Mat qua nho ({face_w}x{face_h}px, can >=80x80)")
    det_score = getattr(face, 'det_score', 0)
    if det_score < 0.7:
        issues.append(f"Do tin cay phat hien thap ({det_score:.2f}, can >=0.70)")
    if hasattr(face, 'pose') and face.pose is not None:
        try:
            yaw, pitch, roll = face.pose
            if abs(yaw) > 30:
                issues.append(f"Mat quay ngang qua nhieu (yaw={yaw:.0f})")
            if abs(pitch) > 25:
                issues.append(f"Mat ngang/cui qua nhieu (pitch={pitch:.0f})")
        except Exception:
            pass
    emb = face.normed_embedding
    norm = np.linalg.norm(emb)
    if abs(norm - 1.0) > 0.05:
        issues.append(f"Embedding bat thuong (norm={norm:.3f})")
    face_crop = img[max(0, y1):min(img.shape[0], y2), max(0, x1):min(img.shape[1], x2)]
    if face_crop.size > 0:
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if laplacian_var < 50:
            issues.append(f"Anh qua mo (blur={laplacian_var:.0f}, can >=50)")
    if face_crop.size > 0:
        hsv = cv2.cvtColor(face_crop, cv2.COLOR_BGR2HSV)
        brightness = hsv[:, :, 2].mean()
        if brightness < 40:
            issues.append(f"Anh qua toi (brightness={brightness:.0f})")
        elif brightness > 240:
            issues.append(f"Anh qua sang (brightness={brightness:.0f})")
    return issues


# ==============================================================================
# ★ FIX #19: ENROLLMENT IMAGE BACKUP
# ==============================================================================
def _save_enrollment_image(ma_nv, face_crop, img_index):
    try:
        person_dir = os.path.join(ENROLLMENT_BACKUP_DIR, f"nv_{ma_nv}")
        os.makedirs(person_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"face_{img_index}_{ts}.jpg"
        filepath = os.path.join(person_dir, filename)
        cv2.imwrite(filepath, face_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return filepath
    except Exception as e:
        print(f"[Enrollment] Save image error: {e}")
        return None


# ==============================================================================
# ★ FIX #17: ADAPTIVE RECOGNITION THRESHOLD
# ==============================================================================
class AdaptiveThresholdManager:
    MIN_THRESHOLD = 0.40
    MAX_THRESHOLD = 0.70
    HISTORY_SIZE = 50
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
        if len(self.score_history) < 20:
            return
        recognized = [h for h in self.score_history if h["recognized"]]
        if not recognized:
            return
        rec_scores = [h["score"] for h in recognized]
        avg_rec = np.mean(rec_scores)
        std_rec = np.std(rec_scores)
        new_threshold = avg_rec - 2 * std_rec
        new_threshold = max(self.MIN_THRESHOLD, min(self.MAX_THRESHOLD, new_threshold))
        self.current = 0.8 * self.current + 0.2 * new_threshold
        self.current = max(self.MIN_THRESHOLD, min(self.MAX_THRESHOLD, self.current))
        if abs(self.current - self.base) > 0.05:
            print(f"[AdaptiveThreshold] {self.base:.3f} -> {self.current:.3f} "
                  f"(avg={avg_rec:.3f}, std={std_rec:.3f})")

    def get_threshold(self):
        return self.current


adaptive_threshold = AdaptiveThresholdManager(
    base_threshold=SYSTEM_SETTINGS.get("threshold", 0.50)
)


# ==============================================================================
# ★ FIX #2 + IMPROVED FACE DATABASE
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
                print("❌ Khong the ket noi database")
                return
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT nv.ho_ten, nv.ten_phong, nv.ten_chuc_vu, fe.vector_data
                FROM face_embeddings fe
                JOIN nhan_vien nv ON fe.ma_nv = nv.ma_nv
            """)
            for row in cursor.fetchall():
                if not row['vector_data']:
                    continue
                try:
                    data = json.loads(row['vector_data'])
                    arr = np.array(data, dtype=np.float32)
                    name = row['ho_ten']
                    entries = []
                    if arr.ndim == 1:
                        entries = [arr]
                    elif arr.ndim == 2:
                        entries = list(arr)
                    for emb in entries:
                        norm = np.linalg.norm(emb)
                        if norm > 0:
                            emb = emb / norm
                        self.known_embeddings.append({
                            "name": name, "dept": row['ten_phong'],
                            "role": row['ten_chuc_vu'], "embedding": emb
                        })
                        if name not in self._person_groups:
                            self._person_groups[name] = []
                        self._person_groups[name].append(emb)
                except Exception as e:
                    print(f"⚠️ Loi data nhan vien {row['ho_ten']}: {e}")
            for name, embs in self._person_groups.items():
                centroid = np.mean(embs, axis=0)
                c_norm = np.linalg.norm(centroid)
                if c_norm > 0:
                    centroid = centroid / c_norm
                self._person_centroids[name] = centroid
            cursor.execute("SELECT stranger_label, vector_data FROM vector_nguoi_la")
            for row in cursor.fetchall():
                if row['vector_data']:
                    emb = np.array(json.loads(row['vector_data']), dtype=np.float32)
                    norm = np.linalg.norm(emb)
                    if norm > 0:
                        emb = emb / norm
                    self.stranger_embeddings.append({"name": row['stranger_label'], "embedding": emb})
                    try:
                        sid = int(row['stranger_label'].split('_')[-1])
                        if sid >= self.next_stranger_id:
                            self.next_stranger_id = sid + 1
                    except:
                        pass
            cursor.close()
            print(f"✅ HOAN TAT: {len(self.known_embeddings)} vectors, "
                  f"{len(self._person_groups)} nguoi, "
                  f"{len(self.stranger_embeddings)} nguoi la.")
        except Exception as e:
            print(f"❌ Loi tai DB: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

    def recognize(self, target_embedding, method="hybrid"):
        norm_target = np.linalg.norm(target_embedding)
        if norm_target != 0:
            target_embedding = target_embedding / norm_target
        if method == "simple" or not self._person_groups:
            return self._recognize_simple(target_embedding)

        # ★ FIX #17: Dùng adaptive threshold
        threshold = adaptive_threshold.get_threshold()
        MARGIN = 0.08

        centroid_scores = {}
        for name, centroid in self._person_centroids.items():
            score = float(np.dot(target_embedding, centroid))
            centroid_scores[name] = score
        top_candidates = sorted(centroid_scores.items(), key=lambda x: x[1], reverse=True)[:5]

        detailed_scores = {}
        for name, _ in top_candidates:
            embs = self._person_groups[name]
            scores = [float(np.dot(target_embedding, e)) for e in embs]
            scores.sort(reverse=True)
            if len(scores) == 1:
                detailed_scores[name] = scores[0]
            elif len(scores) == 2:
                detailed_scores[name] = (scores[0] + scores[1]) / 2
            else:
                k = max(2, len(scores) // 2)
                detailed_scores[name] = sum(scores[:k]) / k

        ranked = sorted(detailed_scores.items(), key=lambda x: x[1], reverse=True)
        if not ranked:
            return "Unknown", 0.0

        best_name, best_score = ranked[0]
        if best_score < threshold:
            adaptive_threshold.record_score(best_score, False)
            return "Unknown", best_score

        if len(ranked) >= 2:
            second_name, second_score = ranked[1]
            margin = best_score - second_score
            if margin < MARGIN and second_score >= threshold * 0.8:
                print(f"[RECOGNIZE] ⚠️ Ambiguous: {best_name}={best_score:.3f} vs "
                      f"{second_name}={second_score:.3f} (margin={margin:.3f})")
                adaptive_threshold.record_score(best_score, False)
                return "Unknown", best_score

        adaptive_threshold.record_score(best_score, True)
        return best_name, best_score

    def _recognize_simple(self, target_embedding):
        max_score = 0
        identity = "Unknown"
        for face in self.known_embeddings:
            score = float(np.dot(target_embedding, face["embedding"]))
            if score > max_score:
                max_score = score
                identity = face["name"]
        threshold = adaptive_threshold.get_threshold()
        if max_score >= threshold:
            adaptive_threshold.record_score(max_score, True)
            return identity, max_score
        adaptive_threshold.record_score(max_score, False)
        return "Unknown", max_score

    def get_person_info(self, name):
        for f in self.known_embeddings:
            if f["name"] == name:
                return {"dept": f["dept"], "role": f["role"]}
        return {"dept": "Unknown", "role": "Khách"}


# ==============================================================================
# ★ FIX #1: KHỞI TẠO AI — det_size 640×640
# ==============================================================================
print("System: Dang khoi tao InsightFace...")
face_app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
face_app.prepare(ctx_id=0, det_size=(640, 640))
print("✅ InsightFace ready! (det_size=640x640)")

print("System: Dang khoi tao Anti-Spoofing Model (best.pt)...")
best_pt_path = os.path.join(BASE_DIR, "best.pt")
spoof_model = None
spoof_model2 = None

if os.path.exists(best_pt_path):
    try:
        spoof_model = YOLO(best_pt_path)
        print(f"✅ Anti-Spoof YOLO (best.pt) loaded! Classes: {spoof_model.names}")
    except Exception as e:
        print(f"⚠️ best.pt load error: {e}")
        spoof_model = None
else:
    print(f"⚠️ best.pt not found: {best_pt_path}")

db = FaceDatabase()


# ==============================================================================
# KHỞI TẠO YOLO + TRACKING
# ==============================================================================
print("System: Dang khoi tao YOLO...")
yolo_model_path = os.path.join(BASE_DIR, "yolo11n.pt")
yolo_model = None

if os.path.exists(yolo_model_path):
    try:
        os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD'] = '0'
        original_torch_load = torch.load
        def patched_torch_load(*args, **kwargs):
            kwargs['weights_only'] = False
            return original_torch_load(*args, **kwargs)
        torch.load = patched_torch_load
        yolo_model = YOLO(yolo_model_path)
        print("✅ YOLO Model loaded!")
        torch.load = original_torch_load
    except Exception as e:
        print(f"⚠️ YOLO load error: {e}")
        yolo_model = None

person_tracker = FixedPersonTracker(max_disappeared=100)
TELEGRAM_BOT_TOKEN_VAL = "8097310654:AAEtu13Fmqrc9lTV4LUX6730ESaGhOmsvRg"
TELEGRAM_CHAT_ID_VAL = "7224086648"
telegram_notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN_VAL, TELEGRAM_CHAT_ID_VAL)
zone_manager = ZoneManager(telegram_notifier=telegram_notifier)
TRACKING_ENABLED = True
print("✅ Tracking Module initialized!")


# ==============================================================================
# ★ FIX #14: MULTI-SCALE FACE DETECTION
# ==============================================================================
class MultiScaleFaceDetector:
    def __init__(self, face_app_main):
        self.face_app = face_app_main
        try:
            self.face_app_fast = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
            self.face_app_fast.prepare(ctx_id=0, det_size=(320, 320))
            self.has_fast = True
            print("✅ Multi-scale detector: 640 + 320")
        except Exception:
            self.has_fast = False
            print("⚠️ Multi-scale: fallback to single 640")

    def detect(self, frame, use_multi_scale=True):
        faces_main = self.face_app.get(frame)
        if not use_multi_scale or not self.has_fast:
            return faces_main
        if len(faces_main) >= 1:
            return faces_main
        faces_fast = self.face_app_fast.get(frame)
        if not faces_fast:
            return faces_main
        all_faces = list(faces_main)
        for f_fast in faces_fast:
            bbox_fast = f_fast.bbox.astype(int).tolist()
            is_dup = False
            for f_main in faces_main:
                bbox_main = f_main.bbox.astype(int).tolist()
                iou = calculate_iou(bbox_fast, bbox_main)
                if iou > 0.3:
                    is_dup = True
                    break
            if not is_dup:
                all_faces.append(f_fast)
        return all_faces


multi_scale_detector = MultiScaleFaceDetector(face_app)


# ==============================================================================
# ★ FIX #15: AUTO-CALIBRATING ANTI-SPOOF THRESHOLDS
# ==============================================================================
class AdaptiveAntiSpoofCalibrator:
    CALIBRATION_FRAMES = 100

    def __init__(self):
        self.calibrated = False
        self.frame_count = 0
        self.lbp_scores = []
        self.fft_scores = []
        self.color_scores = []
        self.edge_scores = []
        self.thresholds = {"lbp": 0.3, "fft": 0.3, "color": 0.3, "edge": 0.3, "total": 0.45}
        self.stats = {}

    def record_sample(self, lbp, fft, color, edge):
        if self.calibrated:
            return
        self.frame_count += 1
        self.lbp_scores.append(lbp)
        self.fft_scores.append(fft)
        self.color_scores.append(color)
        self.edge_scores.append(edge)
        if self.frame_count >= self.CALIBRATION_FRAMES:
            self._compute_thresholds()

    def _compute_thresholds(self):
        def calc_th(scores, sigma=2.0, min_val=0.15):
            arr = np.array(scores)
            return max(min_val, float(arr.mean() - sigma * arr.std())), float(arr.mean()), float(arr.std())

        lbp_th, lm, ls = calc_th(self.lbp_scores)
        fft_th, fm, fs = calc_th(self.fft_scores)
        color_th, cm, cs = calc_th(self.color_scores)
        edge_th, em, es = calc_th(self.edge_scores)
        self.thresholds = {
            "lbp": lbp_th, "fft": fft_th, "color": color_th, "edge": edge_th,
            "total": max(0.30, (lbp_th + fft_th + color_th + edge_th) / 4 * 0.9),
        }
        self.calibrated = True
        print(f"[AntiSpoof] ✅ Auto-calibrated! total_th={self.thresholds['total']:.3f}")
        self.lbp_scores.clear()
        self.fft_scores.clear()
        self.color_scores.clear()
        self.edge_scores.clear()

    def get_total_threshold(self):
        return self.thresholds["total"]

    def is_calibrated(self):
        return self.calibrated


spoof_calibrator = AdaptiveAntiSpoofCalibrator()


# ==============================================================================
# ★ FIX #20: SPOOF CONFIDENCE CALIBRATION (Temperature Scaling)
# ==============================================================================
class SpoofConfidenceCalibrator:
    def __init__(self, temperature=1.0):
        self.temperature = temperature
        self.history = []

    def calibrate(self, raw_conf):
        if self.temperature == 1.0:
            return raw_conf
        raw_conf = max(0.001, min(0.999, raw_conf))
        logit = np.log(raw_conf / (1 - raw_conf))
        scaled_logit = logit / self.temperature
        calibrated = 1.0 / (1.0 + np.exp(-scaled_logit))
        return float(calibrated)

    def set_temperature(self, temp):
        self.temperature = max(0.1, min(5.0, temp))
        print(f"[SpoofCalibrator] Temperature set to {self.temperature:.2f}")

    def record_outcome(self, raw_conf, was_correct):
        self.history.append({"conf": raw_conf, "correct": was_correct})
        if len(self.history) > 500:
            self.history = self.history[-500:]


spoof_conf_calibrator = SpoofConfidenceCalibrator(temperature=1.0)


# ==============================================================================
# ★ FIX #18: ENHANCED DEPTH CUE DETECTION
# ==============================================================================
class DepthCueAnalyzer:
    def analyze(self, face_crop):
        if face_crop is None or face_crop.size == 0:
            return True, 0.5, {}
        try:
            gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (96, 96))
            shadow_score = self._analyze_shadow_gradient(gray)
            specular_score = self._analyze_specular(gray)
            texture_density = self._analyze_micro_texture(gray)
            region_contrast = self._analyze_region_contrast(gray)
            total = (shadow_score * 0.25 + specular_score * 0.25 +
                     texture_density * 0.25 + region_contrast * 0.25)
            is_real = total > 0.40
            return is_real, total, {"shadow": shadow_score, "specular": specular_score,
                                    "texture": texture_density, "region": region_contrast, "total": total}
        except Exception as e:
            return True, 0.5, {"error": str(e)}

    def _analyze_shadow_gradient(self, gray):
        h, w = gray.shape
        q1 = gray[:h // 2, :w // 2].mean()
        q2 = gray[:h // 2, w // 2:].mean()
        q3 = gray[h // 2:, :w // 2].mean()
        q4 = gray[h // 2:, w // 2:].mean()
        max_diff = max(abs(q1 - q2), abs(q1 - q3), abs(q2 - q4), abs(q3 - q4),
                       abs(q1 - q4), abs(q2 - q3))
        return min(1.0, max_diff / 30.0)

    def _analyze_specular(self, gray):
        _, bright = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        bright_ratio = bright.sum() / (gray.size * 255)
        if 0.005 < bright_ratio < 0.05:
            return 0.8
        elif 0.001 < bright_ratio < 0.10:
            return 0.5
        return 0.2

    def _analyze_micro_texture(self, gray):
        lap1 = cv2.Laplacian(gray, cv2.CV_64F, ksize=1).var()
        lap3 = cv2.Laplacian(gray, cv2.CV_64F, ksize=3).var()
        lap5 = cv2.Laplacian(gray, cv2.CV_64F, ksize=5).var()
        multi_scale_var = (lap1 + lap3 + lap5) / 3
        fine_coarse_ratio = lap5 / max(lap1, 0.01) if lap1 > 0 else 0
        density_score = min(1.0, multi_scale_var / 300.0)
        ratio_score = min(1.0, fine_coarse_ratio / 2.0)
        return (density_score + ratio_score) / 2

    def _analyze_region_contrast(self, gray):
        h, w = gray.shape
        regions = []
        for i in range(3):
            for j in range(3):
                r = gray[i * h // 3:(i + 1) * h // 3, j * w // 3:(j + 1) * w // 3]
                regions.append(float(r.std()))
        return min(1.0, np.std(regions) / 15.0)


depth_analyzer = DepthCueAnalyzer()


# ==============================================================================
# ★ FIX #6: MULTI-LAYER ANTI-SPOOF (with #15, #18, #20 integrated)
# ==============================================================================
class MultiLayerAntiSpoof:
    def __init__(self, yolo_model=None):
        self.yolo_model = yolo_model

    def check_texture_liveness(self, face_crop):
        if face_crop is None or face_crop.size == 0:
            return True, 0.5
        try:
            gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (128, 128))
            lbp_score = self._compute_lbp_variance(gray)
            fft_score = self._compute_fft_score(gray)
            color_score = self._compute_color_distribution(face_crop)
            edge_score = self._compute_edge_sharpness(gray)
            # ★ FIX #15: Record for auto-calibration
            spoof_calibrator.record_sample(lbp_score, fft_score, color_score, edge_score)
            total = (lbp_score * 0.3 + fft_score * 0.25 + color_score * 0.2 + edge_score * 0.25)
            # ★ FIX #15: Use adaptive threshold
            threshold = spoof_calibrator.get_total_threshold()
            is_real = total > threshold
            return is_real, total
        except Exception as e:
            print(f"[TextureLiveness] Error: {e}")
            return True, 0.5

    def _compute_lbp_variance(self, gray):
        center = gray[1:-1, 1:-1].astype(np.int16)
        lbp = np.zeros_like(center, dtype=np.uint8)
        lbp |= ((gray[0:-2, 0:-2] >= center).astype(np.uint8) << 7)
        lbp |= ((gray[0:-2, 1:-1] >= center).astype(np.uint8) << 6)
        lbp |= ((gray[0:-2, 2:] >= center).astype(np.uint8) << 5)
        lbp |= ((gray[1:-1, 2:] >= center).astype(np.uint8) << 4)
        lbp |= ((gray[2:, 2:] >= center).astype(np.uint8) << 3)
        lbp |= ((gray[2:, 1:-1] >= center).astype(np.uint8) << 2)
        lbp |= ((gray[2:, 0:-2] >= center).astype(np.uint8) << 1)
        lbp |= ((gray[1:-1, 0:-2] >= center).astype(np.uint8) << 0)
        hist = np.histogram(lbp, bins=256, range=(0, 256))[0]
        hist = hist.astype(np.float32) / max(hist.sum(), 1)
        return min(1.0, np.var(hist) / 0.003)

    def _compute_fft_score(self, gray):
        f = np.fft.fft2(gray.astype(np.float32))
        fshift = np.fft.fftshift(f)
        magnitude = np.log1p(np.abs(fshift))
        h, w = magnitude.shape
        cy, cx = h // 2, w // 2
        low_freq = magnitude[cy - 10:cy + 10, cx - 10:cx + 10].sum()
        high_freq = magnitude.sum() - low_freq
        ratio = high_freq / max(low_freq, 1)
        if ratio < 0.5:
            score = ratio / 0.5
        elif ratio > 5.0:
            score = max(0, 1.0 - (ratio - 5.0) / 10.0)
        else:
            score = 0.7 + 0.3 * min(1, ratio / 3.0)
        return min(1.0, max(0.0, score))

    def _compute_color_distribution(self, face_crop):
        hsv = cv2.cvtColor(face_crop, cv2.COLOR_BGR2HSV)
        sat_score = min(1.0, float(hsv[:, :, 1].std()) / 40.0)
        val_score = min(1.0, float(hsv[:, :, 2].std()) / 50.0)
        return (sat_score + val_score) / 2

    def _compute_edge_sharpness(self, gray):
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        sx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        edge_mean = np.sqrt(sx ** 2 + sy ** 2).mean()
        return (min(1.0, lap_var / 500.0) + min(1.0, edge_mean / 30.0)) / 2

    def full_check(self, frame, face_bbox, face_crop, cam_id=0, spoof_detections=None):
        results = {}
        # Layer 1: YOLO
        yolo_is_real = True
        yolo_conf = 0.5
        if spoof_detections is not None:
            is_fake, conf, match_iou = _match_spoof_to_face(face_bbox, spoof_detections, crop=face_crop, cid=cam_id)
            yolo_is_real = not is_fake
            yolo_conf = conf
            results["yolo"] = {"is_real": yolo_is_real, "conf": conf}
        elif self.yolo_model is not None:
            spoof_dets = _run_spoof_on_full_frame(frame, cam_id)
            is_fake, conf, match_iou = _match_spoof_to_face(face_bbox, spoof_dets, crop=face_crop, cid=cam_id)
            yolo_is_real = not is_fake
            yolo_conf = conf
            results["yolo"] = {"is_real": yolo_is_real, "conf": conf}

        # Layer 2: Texture
        tex_is_real, tex_score = self.check_texture_liveness(face_crop)
        results["texture"] = {"is_real": tex_is_real, "score": tex_score}

        # Layer 3: Screen detector
        sd_is_screen = False
        sd_conf = 0.5
        if face_crop is not None and face_crop.size > 0:
            try:
                sd_is_screen, sd_conf, _ = screen_detector.check_screen(face_crop, cam_id=cam_id)
            except Exception:
                pass
        results["screen"] = {"is_screen": sd_is_screen, "conf": sd_conf}

        # ★ FIX #18: Layer 4 — Depth cue
        depth_is_real, depth_score, depth_details = depth_analyzer.analyze(face_crop)
        results["depth"] = {"is_real": depth_is_real, "score": depth_score}

        # Voting: 4 layers, cần >= 2 FAKE
        fake_votes = sum([not yolo_is_real, not tex_is_real, sd_is_screen, not depth_is_real])

        if fake_votes >= 2:
            is_real = False
            confidence = max(yolo_conf, 1.0 - tex_score, sd_conf, 1.0 - depth_score)
        else:
            is_real = True
            confidence = (0.40 * (1.0 if yolo_is_real else 0.0) +
                          0.20 * (1.0 if tex_is_real else 0.0) +
                          0.20 * (0.0 if sd_is_screen else 1.0) +
                          0.20 * (1.0 if depth_is_real else 0.0))

        results["final"] = {"is_real": is_real, "confidence": confidence, "fake_votes": fake_votes, "layers": 4}
        return is_real, confidence, results


multi_spoof = MultiLayerAntiSpoof(yolo_model=spoof_model)
print("✅ Multi-Layer Anti-Spoof initialized! (4 layers)")


# ==============================================================================
# ★ FIX #13: TEMPORAL IDENTITY STABILIZER
# ==============================================================================
class TemporalIdentityStabilizer:
    WINDOW_SIZE = 7
    MIN_CONSISTENCY = 0.6
    MATCH_THRESHOLD = 0.55
    MAX_TRACK_AGE = 5.0

    def __init__(self):
        self.tracks = {}
        self._next_id = 0

    def _cosine_sim(self, a, b):
        N = 64
        a_s, b_s = a[:N], b[:N]
        dot = float(np.dot(a_s, b_s))
        na = float(np.linalg.norm(a_s))
        nb = float(np.linalg.norm(b_s))
        return dot / (na * nb) if na > 0 and nb > 0 else 0

    def _find_track(self, emb):
        best_id, best_sim = None, self.MATCH_THRESHOLD
        for tid, state in self.tracks.items():
            sim = self._cosine_sim(emb, state["emb"])
            if sim > best_sim:
                best_sim = sim
                best_id = tid
        return best_id

    def update(self, emb, raw_name, raw_score):
        now = time.time()
        tid = self._find_track(emb)
        if tid is None:
            tid = self._next_id
            self._next_id += 1
            self.tracks[tid] = {"emb": emb, "history": [], "last_seen": now,
                                "stable_name": None, "stable_score": 0}
        track = self.tracks[tid]
        track["emb"] = emb
        track["last_seen"] = now
        track["history"].append({"name": raw_name, "score": raw_score, "time": now})
        if len(track["history"]) > self.WINDOW_SIZE:
            track["history"] = track["history"][-self.WINDOW_SIZE:]

        names = [h["name"] for h in track["history"]]
        scores = [h["score"] for h in track["history"]]
        if not names:
            return raw_name, raw_score, False

        counter = Counter(names)
        most_common_name, most_common_count = counter.most_common(1)[0]
        consistency = most_common_count / len(names)
        winning_scores = [s for n, s in zip(names, scores) if n == most_common_name]
        avg_score = sum(winning_scores) / len(winning_scores)
        is_stable = consistency >= self.MIN_CONSISTENCY

        if is_stable:
            track["stable_name"] = most_common_name
            track["stable_score"] = avg_score
            return most_common_name, avg_score, True
        else:
            if track["stable_name"] is not None:
                return track["stable_name"], track["stable_score"], False
            return raw_name, raw_score, False

    def cleanup(self):
        now = time.time()
        expired = [tid for tid, s in self.tracks.items() if now - s["last_seen"] > self.MAX_TRACK_AGE]
        for tid in expired:
            del self.tracks[tid]


identity_stabilizer = TemporalIdentityStabilizer()


# ==============================================================================
# ★ FIX #16: FACE TRACK ID LINKING
# ==============================================================================
class FaceTrackLinker:
    MATCH_THRESHOLD = 0.65
    SKIP_RECOGNIZE_SIM = 0.75
    MAX_AGE = 10.0

    def __init__(self):
        self.active_tracks = {}
        self._next_id = 0

    def _cos_sim(self, a, b):
        N = 64
        dot = float(np.dot(a[:N], b[:N]))
        na = float(np.linalg.norm(a[:N]))
        nb = float(np.linalg.norm(b[:N]))
        return dot / (na * nb) if na > 0 and nb > 0 else 0

    def match_and_update(self, emb, bbox):
        now = time.time()
        best_tid = None
        best_sim = self.MATCH_THRESHOLD
        for tid, track in self.active_tracks.items():
            sim = self._cos_sim(emb, track["emb"])
            if sim > best_sim:
                best_sim = sim
                best_tid = tid
        if best_tid is not None:
            track = self.active_tracks[best_tid]
            track["emb"] = emb
            track["bbox"] = bbox
            track["last_seen"] = now
            track["match_count"] += 1
            if best_sim > self.SKIP_RECOGNIZE_SIM and track.get("name"):
                return best_tid, {"name": track["name"], "score": track["score"],
                                  "skipped": True, "sim": best_sim}
            return best_tid, None
        tid = self._next_id
        self._next_id += 1
        self.active_tracks[tid] = {"emb": emb, "bbox": bbox, "name": None,
                                   "score": 0, "last_seen": now, "match_count": 0}
        return tid, None

    def update_result(self, track_id, name, score):
        if track_id in self.active_tracks:
            self.active_tracks[track_id]["name"] = name
            self.active_tracks[track_id]["score"] = score

    def cleanup(self):
        now = time.time()
        expired = [tid for tid, t in self.active_tracks.items() if now - t["last_seen"] > self.MAX_AGE]
        for tid in expired:
            del self.active_tracks[tid]


face_track_linker = FaceTrackLinker()


# ==============================================================================
# CAMERA THREAD
# ==============================================================================
def camera_thread():
    global global_frame_0, global_frame_1
    print("=" * 60)
    print("System: Dang khoi dong WEBCAM")
    print("=" * 60)
    cap0 = None
    for backend in [cv2.CAP_DSHOW, cv2.CAP_ANY]:
        cap0 = cv2.VideoCapture(0, backend)
        if cap0.isOpened():
            print(f"✅ Camera 0: Webcam mo OK (backend={backend})")
            break
        cap0.release()
        cap0 = None
    if cap0 is None:
        print("❌ CRITICAL: Khong mo duoc webcam 0!")
    else:
        cap0.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap0.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap0.set(cv2.CAP_PROP_FPS, 30)
    fail_count_0 = 0
    MAX_FAIL = 30
    try:
        while True:
            frame0 = None
            if cap0 is not None and cap0.isOpened():
                ret, f = cap0.read()
                if ret and f is not None:
                    frame0 = f
                    fail_count_0 = 0
                else:
                    fail_count_0 += 1
                    if fail_count_0 >= MAX_FAIL:
                        cap0.release()
                        cap0 = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                        fail_count_0 = 0
            else:
                fail_count_0 += 1
                if fail_count_0 >= MAX_FAIL:
                    cap0 = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                    fail_count_0 = 0
            with lock:
                global_frame_0 = frame0.copy() if frame0 is not None else None
                global_frame_1 = None
            time.sleep(0.025)
    except Exception as e:
        print(f"❌ Camera thread error: {e}")
    finally:
        if cap0 is not None:
            cap0.release()

t = threading.Thread(target=camera_thread, daemon=True)
t.start()


# ==============================================================================
# HÀM GHI LOG
# ==============================================================================
def add_log(name, cam_id, score, face_img=None):
    global LAST_LOG_TIME
    current_time = time.time()
    if name in LAST_LOG_TIME:
        if current_time - LAST_LOG_TIME[name] < LOG_COOLDOWN:
            return True
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    camera_name = f"CAM {cam_id + 1}"
    conn = None
    try:
        conn = get_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        if "GIA_MAO" in name or "Nguoi_La" in name or "Unknown" in name:
            img_blob = None
            if face_img is not None and face_img.size > 0:
                success, encoded_img = cv2.imencode('.jpg', face_img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                if success:
                    img_blob = encoded_img.tobytes()
            cursor.execute(
                "INSERT INTO nguoi_la (thoi_gian, camera, trang_thai, image_data, image_path) VALUES (%s,%s,%s,%s,%s)",
                (now_str, camera_name, name, img_blob, ""))
        else:
            info = db.get_person_info(name)
            dept = info.get('dept') or "Chua cap nhat"
            cursor.execute(
                "INSERT INTO nhat_ky_nhan_dien (thoi_gian, ten, phong_ban, camera, do_tin_cay, trang_thai, image_path) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (now_str, name, dept, camera_name, float(score), "authorized", ""))
        conn.commit()
        cursor.close()
        LAST_LOG_TIME[name] = current_time
        return True
    except Exception as e:
        print(f" >> ❌ Loi DB: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_stranger_identity(embedding):
    global RECENT_STRANGERS, NEXT_STRANGER_ID
    max_score = 0
    match_idx = -1
    for i, stranger in enumerate(RECENT_STRANGERS):
        score = np.dot(embedding, stranger['embedding'])
        if score > max_score:
            max_score = score
            match_idx = i
    if max_score > STRANGER_MATCH_THRESHOLD:
        RECENT_STRANGERS[match_idx]['last_seen'] = time.time()
        return RECENT_STRANGERS[match_idx]['id']
    new_id = NEXT_STRANGER_ID
    NEXT_STRANGER_ID += 1
    if len(RECENT_STRANGERS) >= 50:
        RECENT_STRANGERS.pop(0)
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
# ★ FIX #8: CSRT FACE TRACKER — Adaptive EMA
# ==============================================================================
class FaceCSRTTracker:
    DETECT_INTERVAL = 5
    EMA_ALPHA_NORMAL = 0.20
    EMA_ALPHA_FAST = 0.40
    EMA_THRESHOLD_HIGH = 0.60
    MAX_TRACK_AGE = 15

    def __init__(self):
        self.trackers = {}
        self.frame_count = {0: 0, 1: 0}

    def _compute_ema(self, old_ema, raw_score, raw_conf):
        if raw_conf > 0.8:
            alpha = self.EMA_ALPHA_FAST
        elif raw_conf > 0.5:
            alpha = self.EMA_ALPHA_NORMAL
        else:
            alpha = 0.10
        return alpha * raw_score + (1 - alpha) * old_ema

    def on_detection(self, cam_id, frame, detected_faces):
        h, w = frame.shape[:2]
        old_trackers = self.trackers.get(cam_id, [])
        new_trackers = []
        for det in detected_faces:
            x1, y1, x2, y2 = det["bbox"]
            x1 = max(0, min(x1, w - 1))
            y1 = max(0, min(y1, h - 1))
            x2 = max(x1 + 1, min(x2, w))
            y2 = max(y1 + 1, min(y2, h))
            bw, bh = x2 - x1, y2 - y1
            if bw < 10 or bh < 10:
                continue
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            old_ema = 0.0
            for old in old_trackers:
                ocx = (old["bbox"][0] + old["bbox"][2]) / 2
                ocy = (old["bbox"][1] + old["bbox"][3]) / 2
                if ((cx - ocx) ** 2 + (cy - ocy) ** 2) ** 0.5 < 120:
                    old_ema = old.get("spoof_ema", 0.0)
                    break
            raw_conf = det.get("spoof_conf", 0)
            is_fake = not det.get("is_real", True)
            raw_score = raw_conf if is_fake else (1.0 - raw_conf)
            new_ema = self._compute_ema(old_ema, raw_score, raw_conf)
            try:
                tracker = cv2.TrackerCSRT_create()
                tracker.init(frame, (x1, y1, bw, bh))
            except Exception:
                tracker = None
            new_trackers.append({
                "tracker": tracker, "bbox": [x1, y1, x2, y2],
                "name": det.get("name", "..."), "score": det.get("score", 0),
                "is_real": new_ema < self.EMA_THRESHOLD_HIGH,
                "spoof_conf": raw_conf, "spoof_ema": new_ema,
                "alert_level": det.get("alert_level", 0), "age": 0,
            })
        self.trackers[cam_id] = new_trackers

    def update_frame(self, cam_id, frame):
        self.frame_count[cam_id] = self.frame_count.get(cam_id, 0) + 1
        h, w = frame.shape[:2]
        alive = []
        for t in self.trackers.get(cam_id, []):
            if t["tracker"] is None:
                t["age"] += 1
                if t["age"] < self.MAX_TRACK_AGE:
                    alive.append(t)
                continue
            ok, roi = t["tracker"].update(frame)
            if ok:
                rx, ry, rw, rh = [int(v) for v in roi]
                rx = max(0, min(rx, w - 1))
                ry = max(0, min(ry, h - 1))
                rw = max(10, min(rw, w - rx))
                rh = max(10, min(rh, h - ry))
                t["bbox"] = [rx, ry, rx + rw, ry + rh]
                t["age"] = 0
                alive.append(t)
            else:
                t["age"] += 1
                if t["age"] < self.MAX_TRACK_AGE:
                    alive.append(t)
        self.trackers[cam_id] = alive
        return [{"bbox": t["bbox"], "name": t["name"], "score": t["score"],
                 "is_real": t["is_real"], "spoof_conf": t["spoof_conf"],
                 "spoof_ema": t.get("spoof_ema", 0.5), "alert_level": t["alert_level"]}
                for t in alive]


face_csrt_tracker = FaceCSRTTracker()


# ==============================================================================
# PRO ANTI-SPOOF STATE
# ==============================================================================
from collections import deque as _deque

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
    _f.write(f"Anti-Spoofing Log v3.0\nStarted: {datetime.now()}\nModel: best.pt + 4-Layer\n{'=' * 50}\n\n")


def _update_spoof_stats(cid, is_real, conf, face_crop):
    global consecutive_fake, last_fake_capture
    spoof_history[cid].append(1 if is_real else 0)
    st = spoof_session_stats[cid]
    if is_real:
        st["real"] += 1
        consecutive_fake[cid] = 0
    else:
        st["fake"] += 1
        consecutive_fake[cid] += 1
    cf = consecutive_fake[cid]
    if cf >= 20:
        st["alert_level"] = 3
    elif cf >= 10:
        st["alert_level"] = 2
    elif cf >= 5:
        st["alert_level"] = 1
    else:
        st["alert_level"] = 0
    if (not is_real) and conf >= 0.60:
        now = time.time()
        if now - last_fake_capture[cid] >= 3.0:
            last_fake_capture[cid] = now
            try:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fname = os.path.join(BASE_DIR, "fake_captures", f"fake_cam{cid}_{ts}.jpg")
                if face_crop is not None and face_crop.size > 0:
                    cv2.imwrite(fname, face_crop)
                with open(_spoof_log, 'a', encoding='utf-8') as _lf:
                    _lf.write(f"[{ts}] FAKE cam{cid} | conf={conf:.0%}\n")
            except Exception:
                pass
    if st["alert_level"] >= 2:
        print(f"[SPOOF] 🚨 ALERT LVL {st['alert_level']} cam{cid} | consecutive={cf}")


# ==============================================================================
# ★ FIX #3: SHARED FACE CACHE — Hash 32 + verify
# ==============================================================================
_shared_face_cache = {}
_shared_cache_lock = threading.Lock()


def _make_cache_key(emb, n_elements=32):
    key_data = emb[:n_elements].round(4).tobytes()
    return hashlib.md5(key_data).hexdigest()


def _cache_face_identity(emb, name, score):
    key = _make_cache_key(emb)
    with _shared_cache_lock:
        _shared_face_cache[key] = {"name": name, "score": score, "time": time.time(),
                                   "emb_norm": float(np.linalg.norm(emb))}


def _lookup_face_cache(emb):
    key = _make_cache_key(emb)
    now = time.time()
    with _shared_cache_lock:
        expired = [k for k, v in _shared_face_cache.items() if now - v["time"] > 3.0]
        for k in expired:
            del _shared_face_cache[k]
        if key in _shared_face_cache:
            entry = _shared_face_cache[key]
            current_norm = float(np.linalg.norm(emb))
            if abs(current_norm - entry["emb_norm"]) < 0.05:
                return entry["name"], entry["score"]
            else:
                del _shared_face_cache[key]
    return None, None


# ==============================================================================
# FULL-FRAME SPOOF DETECTION (YOLO best.pt) + FIX #20
# ==============================================================================
def _run_spoof_on_full_frame(frame, cid):
    if spoof_model is None or not SPOOF_CHECK_ENABLED:
        return []
    try:
        from utils.image_utils import _spoof_model_lock
        with _spoof_model_lock:
            results = spoof_model.predict(frame, imgsz=640, conf=0.15, verbose=False)
        spoof_detections = []
        for result in results:
            if result.boxes is None or len(result.boxes) == 0:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                raw_conf = float(box.conf[0])
                # ★ FIX #20: Calibrate confidence
                conf = spoof_conf_calibrator.calibrate(raw_conf)
                xyxy = box.xyxy[0].cpu().numpy().astype(int).tolist()
                if cls_id == 0 and conf < 0.50:
                    continue
                spoof_detections.append({"bbox": xyxy, "is_fake": (cls_id == 0),
                                         "conf": conf, "raw_conf": raw_conf})
        fakes = [d for d in spoof_detections if d["is_fake"]]
        reals = [d for d in spoof_detections if not d["is_fake"]]
        if fakes or reals:
            parts = [f"FAKE={d['conf']:.2f}" for d in fakes] + [f"REAL={d['conf']:.2f}" for d in reals]
            print(f"[SPOOF] cam{cid} | {' '.join(parts)}")
        return spoof_detections
    except Exception as e:
        print(f"[SPOOF] Error: {e}")
        return []


# ==============================================================================
# ★ FIX #7 + #9: IMPROVED SPOOF-TO-FACE MATCHING
# ==============================================================================
def _match_spoof_to_face(face_bbox, spoof_detections, crop=None, cid=0):
    matching_fakes = []
    matching_reals = []
    face_cx = (face_bbox[0] + face_bbox[2]) / 2
    face_cy = (face_bbox[1] + face_bbox[3]) / 2
    face_diag = ((face_bbox[2] - face_bbox[0]) ** 2 + (face_bbox[3] - face_bbox[1]) ** 2) ** 0.5
    for det in spoof_detections:
        iou = calculate_iou(face_bbox, det["bbox"])
        det_cx = (det["bbox"][0] + det["bbox"][2]) / 2
        det_cy = (det["bbox"][1] + det["bbox"][3]) / 2
        center_dist = ((face_cx - det_cx) ** 2 + (face_cy - det_cy) ** 2) ** 0.5
        is_match = (iou >= 0.25) or (center_dist < face_diag * 0.5 and iou >= 0.10)
        if is_match:
            if det["is_fake"]:
                matching_fakes.append((det, iou))
            else:
                matching_reals.append((det, iou))
    if matching_fakes and matching_reals:
        best_fake = max(matching_fakes, key=lambda x: x[0]["conf"])
        best_real = max(matching_reals, key=lambda x: x[0]["conf"])
        fake_conf = best_fake[0]["conf"]
        real_conf = best_real[0]["conf"]
        if fake_conf > real_conf + 0.15:
            return True, fake_conf, best_fake[1]
        elif real_conf > fake_conf + 0.15:
            return False, real_conf, best_real[1]
        else:
            return False, (fake_conf + real_conf) / 2, max(best_fake[1], best_real[1])
    if matching_fakes:
        best = max(matching_fakes, key=lambda x: x[0]["conf"])
        if crop is not None and crop.size > 0:
            try:
                sd_is_screen, sd_conf, _ = screen_detector.check_screen(crop, cam_id=cid)
                if not sd_is_screen:
                    return False, 0.5, best[1]
            except:
                pass
        return True, best[0]["conf"], best[1]
    if matching_reals:
        best = max(matching_reals, key=lambda x: x[0]["conf"])
        return False, best[0]["conf"], best[1]
    return False, 0.0, 0.0


# ==============================================================================
# ★ FIX #11: CONFIRMATION BUFFER — cosine_sim 64
# ==============================================================================
class IdentityConfirmationBuffer:
    def __init__(self):
        self.tracked = {}
        self._next_key = 0

    def _cosine_sim(self, a, b):
        N = 64
        a_s, b_s = a[:N], b[:N]
        dot = float(np.dot(a_s, b_s))
        na = float(np.linalg.norm(a_s))
        nb = float(np.linalg.norm(b_s))
        return dot / (na * nb) if na > 0 and nb > 0 else 0

    def _find_match(self, emb):
        best_key, best_sim = None, 0.6
        for key, state in self.tracked.items():
            sim = self._cosine_sim(emb, state["emb"])
            if sim > best_sim:
                best_sim = sim
                best_key = key
        return best_key

    def update(self, emb, name, is_real, score, spoof_conf, cam_id):
        now = time.time()
        key = self._find_match(emb)
        if name != "Unknown" and is_real and "GIA" not in name:
            if key is not None and key in self.tracked:
                state = self.tracked[key]
                state.update({"emb": emb, "last_seen": now, "confirmed": True,
                              "confirmed_name": name, "confirmed_is_real": True, "current_name": name})
                should_alert = not state.get("alert_sent", False)
            else:
                key = self._next_key
                self._next_key += 1
                self.tracked[key] = {"emb": emb, "first_seen": now, "last_seen": now,
                                     "confirmed": True, "confirmed_name": name,
                                     "confirmed_is_real": True, "current_name": name,
                                     "pending_type": None, "pending_start": None, "alert_sent": False}
                should_alert = True
            return {"confirmed": True, "display_name": name, "should_alert": should_alert,
                    "is_real": True, "score": score, "spoof_conf": spoof_conf}

        if name == "Unknown" and is_real:
            pending_type = "stranger"
            confirm_time = CONFIRMATION_TIME_STRANGER
        else:
            pending_type = "spoof"
            confirm_time = CONFIRMATION_TIME_SPOOF

        if key is None:
            key = self._next_key
            self._next_key += 1
            self.tracked[key] = {"emb": emb, "first_seen": now, "last_seen": now,
                                 "confirmed": False, "confirmed_name": None,
                                 "confirmed_is_real": None, "current_name": name,
                                 "pending_type": pending_type, "pending_start": now, "alert_sent": False}
            return {"confirmed": False, "display_name": "Dang xac minh...",
                    "should_alert": False, "is_real": is_real, "score": score, "spoof_conf": spoof_conf}

        state = self.tracked[key]
        state["emb"] = emb
        state["last_seen"] = now
        state["current_name"] = name
        if state["confirmed"]:
            return {"confirmed": True, "display_name": state["confirmed_name"] or name,
                    "should_alert": not state.get("alert_sent", False),
                    "is_real": is_real, "score": score, "spoof_conf": spoof_conf}
        if state["pending_type"] != pending_type:
            state["pending_type"] = pending_type
            state["pending_start"] = now
            return {"confirmed": False, "display_name": "Dang xac minh...",
                    "should_alert": False, "is_real": is_real, "score": score, "spoof_conf": spoof_conf}
        elapsed = now - state["pending_start"]
        if elapsed >= confirm_time:
            state["confirmed"] = True
            state["alert_sent"] = False
            if pending_type == "spoof":
                state["confirmed_name"] = "GIA MAO"
                state["confirmed_is_real"] = False
            else:
                state["confirmed_name"] = name
                state["confirmed_is_real"] = is_real
            return {"confirmed": True, "display_name": state["confirmed_name"],
                    "should_alert": True, "is_real": is_real, "score": score, "spoof_conf": spoof_conf}
        remaining = confirm_time - elapsed
        return {"confirmed": False, "display_name": f"Xac minh ({remaining:.0f}s)...",
                "should_alert": False, "is_real": is_real, "score": score, "spoof_conf": spoof_conf}

    def mark_alert_sent(self, emb):
        key = self._find_match(emb)
        if key is not None and key in self.tracked:
            self.tracked[key]["alert_sent"] = True

    def cleanup(self):
        now = time.time()
        expired = [k for k, v in self.tracked.items() if now - v["last_seen"] > CONFIRMATION_DISAPPEAR_TIMEOUT]
        for k in expired:
            del self.tracked[k]


confirm_buffer = IdentityConfirmationBuffer()


# ==============================================================================
# NMS + DEDUP
# ==============================================================================
def _nms_faces(faces, iou_threshold=0.4):
    if len(faces) <= 1:
        return faces
    scored = sorted(faces, key=lambda f: getattr(f, 'det_score', 0), reverse=True)
    keep = []
    for f in scored:
        bbox = f.bbox.astype(int).tolist()
        is_dup = False
        for kept in keep:
            if calculate_iou(bbox, kept.bbox.astype(int).tolist()) > iou_threshold:
                is_dup = True
                break
        if not is_dup:
            keep.append(f)
    return keep


def _dedup_faces_by_embedding(face_results, threshold=0.85):
    if len(face_results) <= 1:
        return face_results
    kept = []
    used = set()
    for i, r in enumerate(face_results):
        if i in used:
            continue
        best = r
        for j in range(i + 1, len(face_results)):
            if j in used:
                continue
            emb_i = r.get("_emb")
            emb_j = face_results[j].get("_emb")
            if emb_i is not None and emb_j is not None:
                N = 64
                dot = float(np.dot(emb_i[:N], emb_j[:N]))
                ni = float(np.linalg.norm(emb_i[:N]))
                nj = float(np.linalg.norm(emb_j[:N]))
                sim = dot / (ni * nj) if ni > 0 and nj > 0 else 0
                if sim > threshold:
                    used.add(j)
                    if face_results[j].get("score", 0) > best.get("score", 0):
                        best = face_results[j]
        kept.append(best)
        used.add(i)
    return kept


# ==============================================================================
# ★ AI WORKER THREAD — ALL 20 FIXES INTEGRATED
# ==============================================================================
DETECT_EVERY_N = 3


def ai_worker_thread():
    frame_counter = 0
    print("[AI Worker] Waiting for camera frames...")
    while True:
        with lock:
            if global_frame_0 is not None:
                break
        time.sleep(0.1)
    print(f"[AI Worker] ✅ Started! v3.0 — 20 FIXES — DETECT every {DETECT_EVERY_N} frames")

    while True:
        try:
            frame_counter += 1
            confirm_buffer.cleanup()
            identity_stabilizer.cleanup()
            face_track_linker.cleanup()
            t_start = time.time()

            for cid in [0]:
                with lock:
                    frame = global_frame_0 if cid == 0 else global_frame_1
                if frame is None:
                    continue
                h, w = frame.shape[:2]
                new_boxes = []
                new_faces = []
                is_detect_frame = (frame_counter % DETECT_EVERY_N == 0)

                # YOLO Person Tracking
                if is_detect_frame:
                    try:
                        if TRACKING_ENABLED and yolo_model is not None:
                            yolo_results = yolo_model.track(
                                frame, conf=0.25, iou=0.5, persist=True,
                                tracker="bytetrack.yaml", verbose=False,
                                max_det=10, classes=[0], imgsz=PERFORMANCE_SETTINGS["yolo_imgsz"])
                            if yolo_results and len(yolo_results) > 0:
                                person_ids, tracked_persons = person_tracker.update(frame, yolo_results[0])
                                try:
                                    zone_manager.begin_frame(cid)
                                except TypeError:
                                    try:
                                        zone_manager.begin_frame()
                                    except:
                                        pass
                                for pid, bbox in tracked_persons.items():
                                    is_intruding = False
                                    try:
                                        is_intruding, _ = zone_manager.check_intrusion(pid, bbox, frame)
                                    except:
                                        pass
                                    new_boxes.append((pid, bbox, is_intruding))
                                try:
                                    zone_manager.end_frame(frame, cid)
                                except TypeError:
                                    try:
                                        zone_manager.end_frame(frame)
                                    except:
                                        pass
                    except Exception as e:
                        print(f"[AI Worker] YOLO error cam {cid}: {e}")

                # ═══ DETECT FRAME ═══
                if is_detect_frame:
                    try:
                        spoof_detections = _run_spoof_on_full_frame(frame, cid)

                        # ★ FIX #14: Multi-scale detection
                        raw_faces = multi_scale_detector.detect(frame, use_multi_scale=True)
                        faces = _nms_faces(raw_faces, iou_threshold=0.4)

                        pre_dedup = []
                        for f in faces[:5]:
                            fbbox = f.bbox.astype(int).tolist()
                            fx1, fy1, fx2, fy2 = fbbox
                            face_w = fx2 - fx1
                            face_h = fy2 - fy1
                            det_score = getattr(f, 'det_score', 0)

                            # ★ FIX #12: Quality gates
                            if face_w < SPOOF_MIN_FACE_SIZE or face_h < SPOOF_MIN_FACE_SIZE:
                                new_faces.append({"bbox": fbbox, "name": "...", "score": 0,
                                                  "is_real": True, "spoof_conf": 0, "alert_level": 0})
                                continue
                            if det_score < 0.5:
                                new_faces.append({"bbox": fbbox, "name": "...", "score": 0,
                                                  "is_real": True, "spoof_conf": 0, "alert_level": 0})
                                continue
                            crop_blur = frame[max(0, fy1):min(h, fy2), max(0, fx1):min(w, fx2)]
                            if crop_blur.size > 0:
                                blur_var = cv2.Laplacian(cv2.cvtColor(crop_blur, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
                                if blur_var < 15:
                                    new_faces.append({"bbox": fbbox, "name": "...", "score": 0,
                                                      "is_real": True, "spoof_conf": 0, "alert_level": 0})
                                    continue

                            # ★ FIX #5: Quality embedding
                            emb, quality = _get_quality_embedding(f, frame)
                            if emb is None:
                                new_faces.append({"bbox": fbbox, "name": "...", "score": 0,
                                                  "is_real": True, "spoof_conf": 0, "alert_level": 0})
                                continue

                            crop = frame[max(0, fy1):min(h, fy2), max(0, fx1):min(w, fx2)]

                            # ★ FIX #6 + #18: Multi-layer anti-spoof (4 layers)
                            is_real, spoof_conf, spoof_details = multi_spoof.full_check(
                                frame, fbbox, crop, cam_id=cid, spoof_detections=spoof_detections)
                            _update_spoof_stats(cid, is_real, spoof_conf, crop)

                            # ★ FIX #16: Track linking — skip recognize if same person
                            track_id, cached_result = face_track_linker.match_and_update(emb, fbbox)

                            name = "Unknown"
                            score = 0.0

                            if cached_result is not None and cached_result.get("skipped") and is_real:
                                name = cached_result["name"]
                                score = cached_result["score"]
                            elif is_real:
                                cached_name, cached_score = _lookup_face_cache(emb)
                                if cached_name is not None:
                                    name, score = cached_name, cached_score
                                else:
                                    name, score = db.recognize(emb, method="hybrid")
                                    _cache_face_identity(emb, name, score)
                                face_track_linker.update_result(track_id, name, score)
                            else:
                                # ★ FIX #10: Recognize when fake
                                spoofed_name, spoofed_score = db.recognize(emb, method="hybrid")
                                if spoofed_score >= adaptive_threshold.get_threshold():
                                    name = f"GIA_MAO_{spoofed_name}"
                                    print(f"[SPOOF] 🚨 Gia mao: {spoofed_name} (sim={spoofed_score:.2f})")
                                else:
                                    name = "GIA_MAO"
                                score = spoof_conf
                                face_track_linker.update_result(track_id, name, score)

                            # ★ FIX #13: Temporal stabilizer
                            if is_real and name != "Unknown":
                                name, score, is_stable = identity_stabilizer.update(emb, name, score)

                            # Confirmation buffer
                            buf = confirm_buffer.update(emb, name, is_real, score, spoof_conf, cid)
                            if buf["confirmed"]:
                                final_name = buf["display_name"]
                                alert_lvl = spoof_session_stats[cid]["alert_level"]
                            else:
                                final_name = buf["display_name"]
                                alert_lvl = 0

                            # Alert/Log
                            if buf["should_alert"]:
                                alert_sent_ok = False
                                if not is_real and SPOOF_BLOCK_FACE and spoof_conf >= 0.45:
                                    try:
                                        telegram_notifier.send_spoof_alert(frame, face_bbox=fbbox,
                                                                           confidence=spoof_conf, cam_id=cid)
                                        add_log(name, cid, spoof_conf, crop)
                                        alert_sent_ok = True
                                    except Exception as tg_e:
                                        print(f"[AI] Telegram spoof error: {tg_e}")
                                elif name == "Unknown" and is_real:
                                    try:
                                        stranger_id = get_stranger_identity(emb)
                                        stranger_label = f"Nguoi_La_{stranger_id}"
                                        telegram_notifier.send_stranger_alert(stranger_label, frame,
                                                                              face_bbox=fbbox, cam_id=cid)
                                        add_log(stranger_label, cid, score, crop)
                                        alert_sent_ok = True
                                    except Exception as tg_e:
                                        print(f"[AI] Telegram stranger error: {tg_e}")
                                elif name != "Unknown" and is_real and "GIA" not in name:
                                    try:
                                        add_log(name, cid, score)
                                        alert_sent_ok = True
                                    except Exception as log_e:
                                        print(f"[AI] Log error: {log_e}")
                                if alert_sent_ok:
                                    confirm_buffer.mark_alert_sent(emb)

                            pre_dedup.append({
                                "bbox": fbbox, "name": final_name, "score": score,
                                "is_real": is_real if buf["confirmed"] else True,
                                "spoof_conf": round(spoof_conf, 3), "alert_level": alert_lvl, "_emb": emb,
                            })

                        deduped = _dedup_faces_by_embedding(pre_dedup, threshold=0.85)
                        for r in deduped:
                            r.pop("_emb", None)
                            new_faces.append(r)
                        if new_faces:
                            face_csrt_tracker.on_detection(cid, frame, new_faces)
                    except Exception as e:
                        print(f"[AI Worker] Face detect error cam {cid}: {e}")
                else:
                    tracked = face_csrt_tracker.update_frame(cid, frame)
                    if tracked:
                        new_faces = tracked

                with lock_overlay:
                    if new_boxes:
                        ai_overlay_cache[cid]["boxes"] = new_boxes
                    if new_faces:
                        ai_overlay_cache[cid]["faces"] = new_faces
                    ai_overlay_cache[cid]["last_update"] = time.time()

            elapsed = time.time() - t_start
            if frame_counter % 30 == 0:
                fps = 1.0 / elapsed if elapsed > 0 else 0
                mode = "DETECT" if (frame_counter % DETECT_EVERY_N == 0) else "TRACK"
                print(f"[AI] {mode} #{frame_counter}: {elapsed * 1000:.0f}ms (FPS~{fps:.0f})")
            time.sleep(0.005)
        except Exception as e:
            print(f"[AI Worker] Error: {e}")
            time.sleep(0.1)


ai_thread = threading.Thread(target=ai_worker_thread, daemon=True)
ai_thread.start()


# ==============================================================================
# VIDEO FEED
# ==============================================================================
_placeholder_frame = create_placeholder_frame("WAITING FOR CAMERA...")
_ret_ph, _placeholder_jpg = cv2.imencode('.jpg', _placeholder_frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
PLACEHOLDER_JPEG = _placeholder_jpg.tobytes() if _ret_ph else b''


@app.route('/video_feed/<int:cam_id>')
def video_feed(cam_id):
    def generate(cid):
        jpeg_quality = PERFORMANCE_SETTINGS["jpeg_quality"]
        target_fps = PERFORMANCE_SETTINGS["stream_fps"]
        frame_time = 1.0 / target_fps
        while True:
            loop_start = time.time()
            try:
                with lock:
                    raw_frame = global_frame_0 if cid == 0 else global_frame_1
                if raw_frame is None:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + PLACEHOLDER_JPEG + b'\r\n')
                    time.sleep(0.1)
                    continue
                display = raw_frame.copy()
                with lock_overlay:
                    cached_boxes = list(ai_overlay_cache[cid]["boxes"])
                    cached_faces = list(ai_overlay_cache[cid]["faces"])
                for item in cached_boxes:
                    pid, bbox, is_intruding = item
                    x1, y1, x2, y2 = map(int, bbox)
                    if is_intruding:
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), 3)
                        label = f"INTRUDER P{pid}"
                        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                        cv2.rectangle(display, (x1, y1 - th - 10), (x1 + tw + 10, y1), (0, 0, 200), -1)
                        cv2.putText(display, label, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
                    else:
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(display, f"P{pid}", (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                for face_data in cached_faces:
                    x1, y1, x2, y2 = face_data["bbox"]
                    fname = face_data["name"]
                    fscore = face_data["score"]
                    freal = face_data["is_real"]
                    spf_conf = face_data.get("spoof_conf", 0)
                    if not freal:
                        pulse = 3 if int(time.time() * 4) % 2 == 0 else 2
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), pulse)
                        cl = min(20, (x2 - x1) // 4, (y2 - y1) // 4)
                        for cx, cy, dx, dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
                            cv2.line(display, (cx, cy), (cx + cl * dx, cy), (0, 0, 255), 3)
                            cv2.line(display, (cx, cy), (cx, cy + cl * dy), (0, 0, 255), 3)
                        label = f"GIA MAO ({int(spf_conf * 100)}%)"
                        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                        ol = display.copy()
                        cv2.rectangle(ol, (x1, y1 - th - 14), (x1 + tw + 16, y1), (0, 0, 180), -1)
                        cv2.addWeighted(ol, 0.85, display, 0.15, 0, display)
                        cv2.putText(display, label, (x1 + 8, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 200, 255), 2)
                    elif "xac minh" in fname.lower():
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 220, 255), 1)
                        cl = min(14, (x2 - x1) // 4, (y2 - y1) // 4)
                        for cx, cy, dx, dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
                            cv2.line(display, (cx, cy), (cx + cl * dx, cy), (0, 230, 255), 2)
                            cv2.line(display, (cx, cy), (cx, cy + cl * dy), (0, 230, 255), 2)
                        cv2.putText(display, fname, (x1 + 4, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 230, 255), 1)
                    elif fname not in ("Unknown", "...", "Scanning...", "Dang nhan dien...") and "GIA" not in fname:
                        cv2.rectangle(display, (x1, y1), (x2, y2), (255, 180, 0), 2)
                        cl = min(15, (x2 - x1) // 4, (y2 - y1) // 4)
                        for cx, cy, dx, dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
                            cv2.line(display, (cx, cy), (cx + cl * dx, cy), (255, 220, 50), 2)
                            cv2.line(display, (cx, cy), (cx, cy + cl * dy), (255, 220, 50), 2)
                        display = put_text_utf8(display, f"{fname} ({int(fscore * 100)}%)", (x1, y1 - 30), (255, 220, 50))
                    elif fname in ("...", "Scanning...", "Dang nhan dien..."):
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 200, 100), 1)
                        cv2.putText(display, "Scanning...", (x1 + 4, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 120), 1)
                    else:
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 140, 255), 2)
                        cl = min(18, (x2 - x1) // 4, (y2 - y1) // 4)
                        for cx, cy, dx, dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
                            cv2.line(display, (cx, cy), (cx + cl * dx, cy), (0, 165, 255), 3)
                            cv2.line(display, (cx, cy), (cx, cy + cl * dy), (0, 165, 255), 3)
                        ol = display.copy()
                        (tw, th), _ = cv2.getTextSize("NGUOI LA", cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                        cv2.rectangle(ol, (x1, y1 - th - 14), (x1 + tw + 16, y1), (0, 100, 200), -1)
                        cv2.addWeighted(ol, 0.8, display, 0.2, 0, display)
                        cv2.putText(display, "NGUOI LA", (x1 + 8, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                try:
                    display = zone_manager.draw_zones(display)
                except:
                    pass
                try:
                    display = zone_manager.draw_recording_status(display)
                except:
                    pass
                fps = int(1.0 / max(0.001, time.time() - loop_start))
                so = display.copy()
                cv2.rectangle(so, (0, 0), (240, 32), (40, 40, 40), -1)
                cv2.addWeighted(so, 0.6, display, 0.4, 0, display)
                cv2.putText(display, f"CAM {cid + 1} | FPS: {fps}", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 120), 2)
                al = spoof_session_stats[cid]["alert_level"]
                if al >= 1:
                    h_d, w_d = display.shape[:2]
                    o = display.copy()
                    cv2.rectangle(o, (0, 0), (w_d, h_d), (0, 0, 180), 8)
                    cv2.addWeighted(o, 0.25, display, 0.75, 0, display)
                if al >= 2:
                    h_d, w_d = display.shape[:2]
                    banner = f"!! PHAT HIEN GIA MAO !! [L{al}]"
                    (tw, _th), _ = cv2.getTextSize(banner, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                    bo = display.copy()
                    cv2.rectangle(bo, (0, h_d - 45), (w_d, h_d), (0, 0, 160), -1)
                    cv2.addWeighted(bo, 0.75, display, 0.25, 0, display)
                    cv2.putText(display, banner, ((w_d - tw) // 2, h_d - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                ret, buffer = cv2.imencode('.jpg', display, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                if ret:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                else:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + PLACEHOLDER_JPEG + b'\r\n')
            except GeneratorExit:
                return
            except Exception as e:
                print(f"[Stream CAM {cid}] Error: {e}")
                try:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + PLACEHOLDER_JPEG + b'\r\n')
                except:
                    return
                time.sleep(0.1)
                continue
            elapsed = time.time() - loop_start
            sl = max(0, frame_time - elapsed)
            if sl > 0:
                time.sleep(sl)
    response = Response(generate(cam_id), mimetype='multipart/x-mixed-replace; boundary=frame')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Connection'] = 'keep-alive'
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'
    return response


@app.route('/snapshot/<int:cam_id>')
def snapshot(cam_id):
    with lock:
        frame = global_frame_0 if cam_id == 0 else global_frame_1
    if frame is None:
        return Response(PLACEHOLDER_JPEG, mimetype='image/jpeg', headers={'Cache-Control': 'no-cache'})
    display = frame.copy()
    with lock_overlay:
        cached_faces = list(ai_overlay_cache[cam_id]["faces"])
        cached_boxes = list(ai_overlay_cache[cam_id]["boxes"])
    for item in cached_boxes:
        pid, bbox, is_intruding = item
        x1, y1, x2, y2 = map(int, bbox)
        color = (0, 0, 255) if is_intruding else (0, 255, 0)
        cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
    for fd in cached_faces:
        x1, y1, x2, y2 = fd["bbox"]
        fn = fd["name"]
        fs = fd["score"]
        if not fd["is_real"]:
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(display, "FAKE", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        elif fn != "Unknown":
            cv2.rectangle(display, (x1, y1), (x2, y2), (255, 200, 0), 2)
            cv2.putText(display, f"{fn} ({int(fs * 100)}%)", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
    ret, buffer = cv2.imencode('.jpg', display, [cv2.IMWRITE_JPEG_QUALITY, 65])
    if not ret:
        return Response(PLACEHOLDER_JPEG, mimetype='image/jpeg')
    return Response(buffer.tobytes(), mimetype='image/jpeg',
                    headers={'Cache-Control': 'no-cache, no-store', 'Pragma': 'no-cache'})


@app.route('/test_video/<int:cam_id>')
def test_video(cam_id):
    def gen(cid):
        while True:
            with lock:
                frame = global_frame_0 if cid == 0 else global_frame_1
            if frame is None:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + PLACEHOLDER_JPEG + b'\r\n')
                time.sleep(0.1)
                continue
            d = frame.copy()
            cv2.putText(d, f"RAW CAM {cid}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            ret, buf = cv2.imencode('.jpg', d, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ret:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')
            time.sleep(0.033)
    resp = Response(gen(cam_id), mimetype='multipart/x-mixed-replace; boundary=frame')
    resp.headers['Cache-Control'] = 'no-cache, no-store'
    resp.headers['X-Accel-Buffering'] = 'no'
    return resp


# ==============================================================================
# API ROUTES
# ==============================================================================
@app.route('/api/spoof-stats', methods=['GET'])
def get_spoof_stats():
    result = {}
    for cid in [0, 1]:
        st = spoof_session_stats[cid]
        hist = list(spoof_history[cid])
        total = st["real"] + st["fake"]
        elapsed = time.time() - st["start"]
        result[f"cam{cid}"] = {
            "real": st["real"], "fake": st["fake"], "total": total,
            "real_pct": round(st["real"] / max(total, 1) * 100, 1),
            "fake_pct": round(st["fake"] / max(total, 1) * 100, 1),
            "consecutive_fake": consecutive_fake[cid], "alert_level": st["alert_level"],
            "uptime_s": round(elapsed, 0), "history_tail": hist[-20:],
        }
    result["fake_captures_dir"] = os.path.join(BASE_DIR, "fake_captures")
    result["log_file"] = _spoof_log
    return jsonify(result)

@app.route('/api/spoof-stats/reset', methods=['POST'])
def reset_spoof_stats():
    for cid in [0, 1]:
        spoof_session_stats[cid].update({"real": 0, "fake": 0, "alert_level": 0, "start": time.time()})
        consecutive_fake[cid] = 0
        spoof_history[cid].clear()
    return jsonify({"success": True})

@app.route('/api/spoof-stats/captures', methods=['GET'])
def list_fake_captures():
    cap_dir = os.path.join(BASE_DIR, "fake_captures")
    files = []
    if os.path.exists(cap_dir):
        for f in sorted(os.listdir(cap_dir), reverse=True)[:50]:
            if f.endswith('.jpg'):
                fpath = os.path.join(cap_dir, f)
                files.append({"filename": f, "size_kb": round(os.path.getsize(fpath) / 1024, 1),
                               "url": f"/api/spoof-stats/capture/{f}"})
    return jsonify({"count": len(files), "captures": files})

@app.route('/api/spoof-stats/capture/<filename>')
def serve_fake_capture(filename):
    return send_from_directory(os.path.join(BASE_DIR, "fake_captures"), filename)

# ★ FIX #20: Spoof calibration API
@app.route('/api/spoof-calibration', methods=['GET'])
def get_spoof_calibration():
    return jsonify({
        "temperature": spoof_conf_calibrator.temperature,
        "history_size": len(spoof_conf_calibrator.history),
        "anti_spoof_calibrated": spoof_calibrator.is_calibrated(),
        "adaptive_recognition_threshold": adaptive_threshold.get_threshold(),
        "spoof_texture_threshold": spoof_calibrator.get_total_threshold(),
    })

@app.route('/api/spoof-calibration', methods=['POST'])
def update_spoof_calibration():
    try:
        data = request.get_json()
        if 'temperature' in data:
            spoof_conf_calibrator.set_temperature(float(data['temperature']))
        return jsonify({"success": True, "temperature": spoof_conf_calibrator.temperature})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json(force=True)
    except:
        data = request.form.to_dict()
    user = USERS.get(data.get('username', '').split('@')[0])
    if user and user['password'] == data.get('password'):
        session['user'] = user['name']
        return jsonify({"success": True, "user": user})
    return jsonify({"success": False}), 401

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({"success": True})

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
        if not conn: return jsonify({"status": "error"}), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM nhan_vien ORDER BY ma_nv DESC")
        data = cursor.fetchall(); cursor.close()
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
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
        if not conn: return jsonify({"success": False}), 500
        cursor = conn.cursor()
        cursor.execute("DELETE FROM face_embeddings WHERE ma_nv=%s", (ma_nv,))
        cursor.execute("DELETE FROM nhan_vien WHERE ma_nv=%s", (ma_nv,))
        conn.commit(); cursor.close(); db.reload_db()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/update_employee', methods=['POST'])
def update_employee():
    conn = None
    try:
        d = request.get_json()
        conn = get_connection()
        if not conn: return jsonify({"success": False}), 500
        cursor = conn.cursor()
        cursor.execute("UPDATE nhan_vien SET ho_ten=%s, email=%s, sdt=%s, dia_chi=%s, ten_phong=%s, ten_chuc_vu=%s, trang_thai=%s WHERE ma_nv=%s",
                       (d.get('ho_ten'), d.get('email'), d.get('sdt'), d.get('dia_chi'),
                        d.get('ten_phong'), d.get('ten_chuc_vu'), d.get('trang_thai'), d.get('ma_nv')))
        conn.commit(); cursor.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/dashboard-stats', methods=['GET'])
def get_dashboard_stats():
    stats = {"present_count": 0, "total_employees": 0, "warning_count": 0, "logs": []}
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
                stats['logs'].append({"id": row['id'], "name": row['ten'], "dept": row['phong_ban'],
                                      "loc": row['camera'], "time": row['thoi_gian'].strftime("%H:%M:%S %d/%m"),
                                      "status": "Hop le"})
            cur.close()
    except Exception as e:
        print(f"Dashboard Error: {e}")
    finally:
        if conn:
            try: conn.close()
            except: pass
    import random
    stats.update({"gpu_load": random.randint(10, 40), "temp": random.randint(45, 65)})
    return jsonify(stats)

@app.route('/api/security/alerts', methods=['GET'])
def get_security_alerts():
    conn = None
    try:
        conn = get_connection()
        if not conn: return jsonify([])
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, thoi_gian, camera, trang_thai FROM nguoi_la ORDER BY thoi_gian DESC LIMIT 100")
        rows = cursor.fetchall(); cursor.close()
        grouped = []
        for row in rows:
            dt = row['thoi_gian']
            img_url = f"http://localhost:5000/api/image/view/{row['id']}"
            detail = {"time": dt.strftime("%H:%M:%S"), "img": img_url}
            name = row['trang_thai']; cam = row['camera']
            found = False
            for g in grouped:
                if g['location'] == name and g['cam'] == cam:
                    g['count'] += 1; g['details'].append(detail); g['img'] = img_url; found = True; break
            if not found:
                grouped.append({"id": row['id'], "location": name, "cam": cam,
                                "date": dt.strftime("%d/%m/%Y"), "time": dt.strftime("%H:%M:%S"),
                                "img": img_url, "count": 1, "details": [detail]})
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
        rows = cursor.fetchall()
        gl = []; pn = {}
        for r in rows:
            name = r['name']; img = r['image_path'] or "https://placehold.co/400"
            ds = r['created_at'].strftime("%d/%m/%Y"); ts = r['created_at'].strftime("%H:%M:%S")
            di = {"time": ts, "img": img, "reason": r['reason']}
            if name in pn:
                gl[pn[name]]['count'] += 1; gl[pn[name]]['details'].append(di)
            else:
                gl.append({"id": r['id'], "name": name, "reason": r['reason'], "date": ds, "img": img,
                           "status": "Dangerous", "count": 1, "location": "Blacklist", "cam": "DB", "details": [di]})
                pn[name] = len(gl) - 1
        cursor.close()
        return jsonify(gl)
    except: return jsonify([])
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/security/blacklist/add', methods=['POST'])
def add_to_blacklist():
    conn = None
    try:
        d = request.get_json(); conn = get_connection()
        if not conn: return jsonify({"success": False}), 500
        cursor = conn.cursor()
        cursor.execute("INSERT INTO blacklist (name, reason, image_path, created_at) VALUES (%s,%s,%s,%s)",
                       (d.get('name'), d.get('reason'), d.get('image'), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit(); cursor.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/security/blacklist/<int:bl_id>', methods=['DELETE'])
def delete_from_blacklist(bl_id):
    conn = None
    try:
        conn = get_connection()
        if not conn: return jsonify({"success": False}), 500
        cursor = conn.cursor()
        cursor.execute("DELETE FROM blacklist WHERE id = %s", (bl_id,))
        conn.commit(); af = cursor.rowcount; cursor.close()
        if af > 0: return jsonify({"success": True})
        return jsonify({"success": False}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/security/alerts/<int:alert_id>/verify', methods=['PUT'])
def verify_alert(alert_id):
    conn = None
    try:
        conn = get_connection()
        if not conn: return jsonify({"success": False}), 500
        cursor = conn.cursor()
        cursor.execute("UPDATE nguoi_la SET trang_thai = 'Da xac minh' WHERE id = %s", (alert_id,))
        conn.commit(); cursor.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/security/intrusion-events', methods=['GET'])
def get_intrusion_events():
    try:
        page = int(request.args.get('page', 1)); per_page = int(request.args.get('per_page', 12))
        date_filter = request.args.get('date', None)
        rdir = Path(BASE_DIR) / "intrusion_recordings"; sdir = Path(BASE_DIR) / "intrusion_snapshots"; events = []
        if rdir.exists():
            for vf in sorted(rdir.glob("*.mp4"), reverse=True):
                stat = vf.stat(); created = datetime.fromtimestamp(stat.st_ctime)
                if date_filter:
                    try:
                        if created.date() != datetime.strptime(date_filter, "%Y-%m-%d").date(): continue
                    except: pass
                ms = []
                if sdir.exists():
                    for sf in sdir.glob("*.jpg"):
                        st2 = sf.stat(); st2t = datetime.fromtimestamp(st2.st_ctime)
                        if abs((st2t - created).total_seconds()) < 300:
                            ms.append({"filename": sf.name, "url": f"http://localhost:5000/api/security/snapshot/{sf.name}",
                                       "time": st2t.strftime("%Y-%m-%d %H:%M:%S")})
                events.append({"id": len(events) + 1, "video_filename": vf.name,
                               "video_url": f"http://localhost:5000/api/tracking/video/{vf.name}",
                               "cam_id": vf.stem.split('_')[0], "timestamp": created.strftime("%Y-%m-%d %H:%M:%S"),
                               "date": created.strftime("%Y-%m-%d"), "time": created.strftime("%H:%M:%S"),
                               "size_mb": round(stat.st_size / (1024 * 1024), 2),
                               "snapshots": ms[:5], "snapshot_count": len(ms),
                               "thumbnail": ms[0]["url"] if ms else None})
        total = len(events); start = (page - 1) * per_page
        return jsonify({"events": events[start:start + per_page], "total": total, "page": page,
                        "total_pages": (total + per_page - 1) // per_page if total > 0 else 0})
    except Exception as e:
        return jsonify({"events": [], "total": 0, "error": str(e)})

@app.route('/api/security/intrusion-events/<int:event_id>', methods=['GET'])
def get_intrusion_event_detail(event_id):
    try:
        rdir = Path(BASE_DIR) / "intrusion_recordings"; sdir = Path(BASE_DIR) / "intrusion_snapshots"
        videos = sorted(rdir.glob("*.mp4"), reverse=True) if rdir.exists() else []
        if event_id < 1 or event_id > len(videos): return jsonify({"error": "Not found"}), 404
        vf = videos[event_id - 1]; stat = vf.stat(); created = datetime.fromtimestamp(stat.st_ctime)
        snaps = []
        if sdir.exists():
            for sf in sorted(sdir.glob("*.jpg"), reverse=True):
                st2 = sf.stat(); st2t = datetime.fromtimestamp(st2.st_ctime)
                if abs((st2t - created).total_seconds()) < 300:
                    snaps.append({"filename": sf.name, "url": f"http://localhost:5000/api/security/snapshot/{sf.name}",
                                  "time": st2t.strftime("%Y-%m-%d %H:%M:%S")})
        return jsonify({"id": event_id, "video_filename": vf.name,
                        "video_url": f"http://localhost:5000/api/tracking/video/{vf.name}",
                        "timestamp": created.strftime("%Y-%m-%d %H:%M:%S"),
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "snapshots": snaps, "snapshot_count": len(snaps)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/security/snapshot/<filename>')
def serve_snapshot(filename):
    return send_from_directory(str(Path(BASE_DIR) / "intrusion_snapshots"), filename)

@app.route('/api/image/view/<int:log_id>')
def view_image_from_db(log_id):
    conn = None
    try:
        conn = get_connection()
        if not conn: return "DB fail", 500
        cursor = conn.cursor()
        cursor.execute("SELECT image_data FROM nguoi_la WHERE id = %s", (log_id,))
        row = cursor.fetchone(); cursor.close()
        if row and row[0]: return Response(row[0], mimetype='image/jpeg')
        return Response(b'', mimetype='image/jpeg')
    except: return "Error", 500
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/door-status', methods=['GET'])
def get_door_status():
    return jsonify({"door_status": "CLOSED", "last_user": None, "time": None})

@app.route('/api/anti-spoof-status', methods=['GET'])
def get_anti_spoof_status():
    with lock_spoof:
        return jsonify({"enabled": SPOOF_CHECK_ENABLED, "camera_0": anti_spoof_state[0], "camera_1": anti_spoof_state[1]})

@app.route('/api/tracking/stats', methods=['GET'])
def get_tracking_stats():
    try: ts = person_tracker.get_stats()
    except: ts = {}
    try: rs = zone_manager.recorder.get_stats()
    except: rs = {}
    try: zc = zone_manager.get_zone_count()
    except: zc = 0
    return jsonify({"tracking_enabled": TRACKING_ENABLED, "total_unique_people": ts.get('total_unique_people', 0),
                    "current_active": ts.get('current_active', 0), "zones_count": zc,
                    "is_recording": rs.get('is_recording', False), "total_recordings": rs.get('total_recordings', 0)})

@app.route('/api/tracking/zones', methods=['GET'])
def get_zones():
    return jsonify({"zones": zone_manager.get_zones(), "count": zone_manager.get_zone_count()})

@app.route('/api/tracking/zones', methods=['POST'])
def add_zone():
    try:
        data = request.get_json(); points = data.get('points', [])
        if len(points) < 3: return jsonify({"success": False}), 400
        zone_manager.add_zone([(p['x'], p['y']) for p in points])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/tracking/zones', methods=['DELETE'])
def clear_zones():
    zone_manager.clear_all_zones()
    return jsonify({"success": True})

@app.route('/api/tracking/recordings', methods=['GET'])
def get_recordings():
    try:
        rdir = Path(BASE_DIR) / "intrusion_recordings"; recs = []
        if rdir.exists():
            for vf in sorted(rdir.glob("*.mp4"), reverse=True)[:100]:
                stat = vf.stat()
                if stat.st_size < 1024: continue
                recs.append({"filename": vf.name, "size_mb": round(stat.st_size / (1024 * 1024), 2),
                             "created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")})
        return jsonify({"recordings": recs, "count": len(recs)})
    except Exception as e:
        return jsonify({"recordings": [], "error": str(e)})

@app.route('/api/tracking/video/<filename>')
def stream_recording(filename):
    vdir = Path(BASE_DIR) / "intrusion_recordings"; vp = vdir / filename
    if not vp.exists(): return jsonify({"error": "Not found"}), 404
    return send_from_directory(str(vdir), filename, mimetype='video/mp4', conditional=True)

@app.route('/api/tracking/config', methods=['GET'])
def get_tracking_config():
    return jsonify({"tracking_enabled": TRACKING_ENABLED,
                    "telegram_enabled": telegram_notifier.enabled if telegram_notifier else False,
                    "zones_count": zone_manager.get_zone_count()})

@app.route('/api/tracking/config', methods=['POST'])
def update_tracking_config():
    global TRACKING_ENABLED
    try:
        data = request.get_json()
        if 'tracking_enabled' in data: TRACKING_ENABLED = bool(data['tracking_enabled'])
        return jsonify({"success": True, "tracking_enabled": TRACKING_ENABLED})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/performance', methods=['GET'])
def get_performance_settings():
    return jsonify(PERFORMANCE_SETTINGS)

@app.route('/api/performance', methods=['POST'])
def update_performance_settings():
    try:
        data = request.get_json()
        if 'ai_skip_frames' in data: PERFORMANCE_SETTINGS["ai_skip_frames"] = max(1, min(10, int(data['ai_skip_frames'])))
        if 'yolo_imgsz' in data: PERFORMANCE_SETTINGS["yolo_imgsz"] = max(160, min(640, int(data['yolo_imgsz'])))
        if 'jpeg_quality' in data: PERFORMANCE_SETTINGS["jpeg_quality"] = max(30, min(100, int(data['jpeg_quality'])))
        if 'stream_fps' in data: PERFORMANCE_SETTINGS["stream_fps"] = max(10, min(60, int(data['stream_fps'])))
        return jsonify({"success": True, "settings": PERFORMANCE_SETTINGS})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ★ FIX #4 + #19: ADD EMPLOYEE WITH QUALITY CHECK + IMAGE BACKUP
@app.route('/api/add_employee_with_faces', methods=['POST'])
def add_employee_with_faces():
    conn = None
    try:
        ho_ten = request.form.get('ho_ten'); email = request.form.get('email')
        sdt = request.form.get('sdt', ''); dia_chi = request.form.get('dia_chi', '')
        ten_phong = request.form.get('ten_phong', ''); ten_chuc_vu = request.form.get('ten_chuc_vu', '')
        trang_thai = request.form.get('trang_thai', 'Dang_Lam')
        if not ho_ten or not email: return jsonify({"success": False, "message": "Thieu thong tin"}), 400
        conn = get_connection()
        if not conn: return jsonify({"success": False, "message": "DB fail"}), 500
        cursor = conn.cursor()
        cursor.execute("INSERT INTO nhan_vien (ho_ten, email, sdt, dia_chi, ten_phong, ten_chuc_vu, trang_thai) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                       (ho_ten, email, sdt, dia_chi, ten_phong, ten_chuc_vu, trang_thai))
        conn.commit(); ma_nv = cursor.lastrowid
        face_files = request.files.getlist('faces'); embeddings = []; rejected = []
        if face_files:
            for idx, file in enumerate(face_files):
                if not (file and file.filename): continue
                file_bytes = np.frombuffer(file.read(), np.uint8)
                img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                if img is None: rejected.append(f"Anh {idx + 1}: Khong doc duoc"); continue
                faces = face_app.get(img)
                if len(faces) == 0: rejected.append(f"Anh {idx + 1}: Khong phat hien mat"); continue
                if len(faces) > 1: rejected.append(f"Anh {idx + 1}: {len(faces)} mat, chi nen 1"); continue
                face = faces[0]
                qi = check_face_quality(face, img)
                if qi: rejected.append(f"Anh {idx + 1}: {'; '.join(qi)}"); continue
                embeddings.append(face.normed_embedding.tolist())
                # ★ FIX #19: Save enrollment image
                bbox = face.bbox.astype(int); bx1, by1, bx2, by2 = bbox
                fc = img[max(0, by1):min(img.shape[0], by2), max(0, bx1):min(img.shape[1], bx2)]
                if fc.size > 0: _save_enrollment_image(ma_nv, fc, idx)
        if embeddings:
            for se in embeddings:
                cursor.execute("INSERT INTO face_embeddings (ma_nv, vector_data) VALUES (%s, %s)", (ma_nv, json.dumps(se)))
            conn.commit(); db.reload_db()
            msg = f"Da luu {len(embeddings)} khuon mat."
        else:
            msg = "Chua co anh hop le."
        if rejected: msg += f" Tu choi {len(rejected)}: " + "; ".join(rejected)
        cursor.close()
        return jsonify({"success": True, "message": msg, "ma_nv": ma_nv, "accepted": len(embeddings), "rejected": rejected})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/training-data', methods=['GET'])
def get_training_data():
    conn = None
    try:
        conn = get_connection()
        if not conn: return jsonify({"success": False}), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""SELECT nv.ma_nv, nv.ho_ten, nv.email, nv.ten_phong, nv.ten_chuc_vu, nv.trang_thai,
                          fe.id as embedding_id, fe.vector_data FROM nhan_vien nv
                          LEFT JOIN face_embeddings fe ON nv.ma_nv = fe.ma_nv ORDER BY nv.ma_nv""")
        rows = cursor.fetchall(); emps = {}
        for row in rows:
            mv = row['ma_nv']
            if mv not in emps:
                emps[mv] = {"ma_nv": mv, "ho_ten": row['ho_ten'], "email": row['email'],
                            "ten_phong": row['ten_phong'] or "N/A", "ten_chuc_vu": row['ten_chuc_vu'] or "N/A",
                            "vectors": [], "vector_count": 0, "has_face_data": False}
            if row['vector_data']:
                try:
                    arr = np.array(json.loads(row['vector_data']), dtype=np.float32)
                    if arr.ndim == 1:
                        norm = float(np.linalg.norm(arr))
                        emps[mv]["vectors"].append({"embedding_id": row['embedding_id'], "dim": len(arr),
                                                    "norm": round(norm, 4), "is_normalized": abs(norm - 1.0) < 0.01})
                except: pass
        for mv, emp in emps.items():
            emp["vector_count"] = len(emp["vectors"]); emp["has_face_data"] = len(emp["vectors"]) > 0
        cursor.close()
        te = len(emps); wf = sum(1 for e in emps.values() if e["has_face_data"])
        tv = sum(e["vector_count"] for e in emps.values())
        return jsonify({"success": True, "summary": {"total_employees": te, "with_face_data": wf,
                        "without_face_data": te - wf, "total_vectors": tv},
                        "employees": list(emps.values())})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            try: conn.close()
            except: pass


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 SERVER v3.0 — 20 FIXES")
    print("  Recognition: #1 det640 #2 hybrid #3 cache32 #4 enrollment-QC")
    print("               #5 quality-gate #13 temporal-stabilizer")
    print("               #14 multi-scale #16 track-linking #17 adaptive-th")
    print("  Anti-Spoof:  #6 4-layer #7 iou25 #8 adaptive-ema #9 uncertainty")
    print("               #10 recognize-fake #15 auto-calibrate #18 depth-cue")
    print("               #20 conf-calibration")
    print("  Infra:       #11 cos64 #12 quality-gate #19 enrollment-backup")
    print(f"  MJPEG:  http://localhost:5000/video_feed/0")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)