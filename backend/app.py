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

# ★ Import thêm hàm tiền xử lý mới
try:
    from utils.image_utils import preprocess_face_for_spoof
except ImportError:
    # Fallback nếu chưa thêm vào utils/image_utils.py
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
# CONFIRMATION BUFFER SETTINGS — import an toàn
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


# ==============================================================================
# DATABASE & AI
# ==============================================================================
class FaceDatabase:
    def __init__(self):
        self.known_embeddings = []
        self.stranger_embeddings = []
        self.next_stranger_id = 1
        self.reload_db()

    def reload_db(self):
        print("System: Đang tải dữ liệu khuôn mặt từ Database...")
        self.known_embeddings = []
        self.stranger_embeddings = [] 
        
        conn = None
        try:
            conn = get_connection()
            if not conn:
                print("❌ Không thể kết nối database")
                return
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("SELECT nv.ho_ten, nv.ten_phong, nv.ten_chuc_vu, fe.vector_data FROM face_embeddings fe JOIN nhan_vien nv ON fe.ma_nv = nv.ma_nv")
            for row in cursor.fetchall():
                if not row['vector_data']: continue
                try:
                    data = json.loads(row['vector_data'])
                    arr = np.array(data, dtype=np.float32)
                    
                    if arr.ndim == 1:
                        self.known_embeddings.append({
                            "name": row['ho_ten'], "dept": row['ten_phong'],
                            "role": row['ten_chuc_vu'], "embedding": arr
                        })
                    elif arr.ndim == 2:
                        for single_emb in arr:
                            self.known_embeddings.append({
                                "name": row['ho_ten'], "dept": row['ten_phong'],
                                "role": row['ten_chuc_vu'], "embedding": single_emb
                            })
                except Exception as e: 
                    print(f"⚠️ Lỗi data nhân viên {row['ho_ten']}: {e}")
            
            cursor.execute("SELECT stranger_label, vector_data FROM vector_nguoi_la")
            for row in cursor.fetchall():
                if row['vector_data']:
                    emb = np.array(json.loads(row['vector_data']), dtype=np.float32)
                    self.stranger_embeddings.append({"name": row['stranger_label'], "embedding": emb})
                    try:
                        sid = int(row['stranger_label'].split('_')[-1])
                        if sid >= self.next_stranger_id: self.next_stranger_id = sid + 1
                    except: pass

            cursor.close()
            print(f"✅ HOÀN TẤT: Đã nạp {len(self.known_embeddings)} vector NV và {len(self.stranger_embeddings)} vector người lạ.")
        except Exception as e:
            print(f"❌ Lỗi tải DB: {e}")
        finally:
            if conn:
                try: conn.close()
                except: pass

    def recognize(self, target_embedding):
        norm_target = np.linalg.norm(target_embedding)
        if norm_target != 0:
            target_embedding = target_embedding / norm_target
        
        max_score = 0
        identity = "Unknown"
        
        for face in self.known_embeddings:
            db_emb = face["embedding"]
            norm_db = np.linalg.norm(db_emb)
            if norm_db != 0:
                db_emb = db_emb / norm_db
            score = np.dot(target_embedding, db_emb)
            if score > max_score:
                max_score = score
                identity = face["name"]
        
        max_score = float(max_score)
        if max_score >= SYSTEM_SETTINGS["threshold"]:
            return identity, max_score
        return "Unknown", max_score
        
    def get_person_info(self, name):
        for f in self.known_embeddings: 
            if f["name"] == name: return {"dept": f["dept"], "role": f["role"]}
        return {"dept": "Unknown", "role": "Khách"}


# ==============================================================================
# KHỞI TẠO AI
# ==============================================================================
print("System: Đang khởi tạo InsightFace...")
face_app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
face_app.prepare(ctx_id=0, det_size=(320, 320))
print("✅ InsightFace ready!")

print("System: Đang khởi tạo Anti-Spoofing Model (best.pt)...")
best_pt_path = os.path.join(BASE_DIR, "best.pt")
spoof_model = None
spoof_model2 = None  # ★ Placeholder cho ensemble model

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
print("System: Đang khởi tạo YOLO...")
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

TELEGRAM_BOT_TOKEN = "8097310654:AAEtu13Fmqrc9lTV4LUX6730ESaGhOmsvRg"
TELEGRAM_CHAT_ID = "7224086648"
telegram_notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
zone_manager = ZoneManager(telegram_notifier=telegram_notifier)

TRACKING_ENABLED = True
print("✅ Tracking Module initialized!")


# ==============================================================================
# CAMERA THREAD
# ==============================================================================
def camera_thread():
    global global_frame_0, global_frame_1
    
    print("=" * 60)
    print("System: Đang khởi động WEBCAM")
    print("=" * 60)

    cap0 = None
    for backend in [cv2.CAP_DSHOW, cv2.CAP_ANY]:
        cap0 = cv2.VideoCapture(0, backend)
        if cap0.isOpened():
            print(f"✅ Camera 0: Webcam mở OK (backend={backend})")
            break
        cap0.release()
        cap0 = None
    
    if cap0 is None:
        print("❌ CRITICAL: Không mở được webcam 0!")
    else:
        cap0.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap0.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap0.set(cv2.CAP_PROP_FPS, 30)

    # ★ CAM 1 TẠM TẮT
    # cap1 = cv2.VideoCapture(1, cv2.CAP_DSHOW)
    # use_shared_cam = False
    # if cap1.isOpened():
    #     print("✅ Camera 1: Webcam 1 mở OK")
    #     cap1.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    #     cap1.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    # else:
    #     print("⚠️ Camera 1: Dùng chung webcam 0")
    #     cap1.release()
    #     cap1 = None
    #     use_shared_cam = True
    
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
            
            # ★ CAM 1 TẠM TẮT
            # frame1 = None
            # if use_shared_cam:
            #     frame1 = frame0
            # elif cap1 is not None and cap1.isOpened():
            #     ret, f = cap1.read()
            #     if ret and f is not None:
            #         frame1 = f
            #         fail_count_1 = 0
            #     else:
            #         fail_count_1 += 1
            #         if fail_count_1 >= MAX_FAIL:
            #             cap1.release()
            #             cap1 = cv2.VideoCapture(1, cv2.CAP_DSHOW)
            #             fail_count_1 = 0

            with lock:
                global_frame_0 = frame0.copy() if frame0 is not None else None
                global_frame_1 = None
            
            time.sleep(0.025)

    except Exception as e:
        print(f"❌ Camera thread error: {e}")
    finally:
        if cap0 is not None: cap0.release()
        # if cap1 is not None: cap1.release()

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
    camera_name = f"CAM {cam_id+1}"
    
    conn = None
    try:
        conn = get_connection()
        if not conn: return False
        cursor = conn.cursor()
        
        if "GIA_MAO" in name or "Người lạ" in name or "Nguoi_La" in name or "Unknown" in name:
            img_blob = None
            if face_img is not None and face_img.size > 0:
                success, encoded_img = cv2.imencode('.jpg', face_img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                if success: img_blob = encoded_img.tobytes()
            cursor.execute("INSERT INTO nguoi_la (thoi_gian, camera, trang_thai, image_data, image_path) VALUES (%s, %s, %s, %s, %s)",
                          (now_str, camera_name, name, img_blob, ""))
        else:
            info = db.get_person_info(name)
            dept = info.get('dept') or "Chưa cập nhật"
            cursor.execute("INSERT INTO nhat_ky_nhan_dien (thoi_gian, ten, phong_ban, camera, do_tin_cay, trang_thai, image_path) VALUES (%s, %s, %s, %s, %s, %s, %s)", 
                        (now_str, name, dept, camera_name, float(score), "authorized", ""))
            
        conn.commit(); cursor.close()
        LAST_LOG_TIME[name] = current_time
        return True
    except Exception as e: 
        print(f" >> ❌ Lỗi DB: {e}")
        return False
    finally:
        if conn:
            try: conn.close()
            except: pass


def get_stranger_identity(embedding):
    global RECENT_STRANGERS, NEXT_STRANGER_ID
    max_score = 0; match_idx = -1
    for i, stranger in enumerate(RECENT_STRANGERS):
        score = np.dot(embedding, stranger['embedding'])
        if score > max_score: max_score = score; match_idx = i
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
# CSRT FACE TRACKER (giữ nguyên)
# ==============================================================================
class FaceCSRTTracker:
    DETECT_INTERVAL = 5
    EMA_ALPHA = 0.35
    MAX_TRACK_AGE = 15
    
    def __init__(self):
        self.trackers = {}
        self.frame_count = {0: 0, 1: 0}
    
    def should_detect(self, cam_id):
        return self.frame_count.get(cam_id, 0) % self.DETECT_INTERVAL == 0
    
    def on_detection(self, cam_id, frame, detected_faces):
        h, w = frame.shape[:2]
        old_trackers = self.trackers.get(cam_id, [])
        new_trackers = []
        
        for det in detected_faces:
            x1, y1, x2, y2 = det["bbox"]
            x1 = max(0, min(x1, w-1))
            y1 = max(0, min(y1, h-1))
            x2 = max(x1+1, min(x2, w))
            y2 = max(y1+1, min(y2, h))
            bw, bh = x2 - x1, y2 - y1
            if bw < 10 or bh < 10:
                continue
            
            cx, cy = (x1+x2)/2, (y1+y2)/2
            old_ema = 0.0
            for old in old_trackers:
                ocx = (old["bbox"][0] + old["bbox"][2]) / 2
                ocy = (old["bbox"][1] + old["bbox"][3]) / 2
                if ((cx-ocx)**2 + (cy-ocy)**2) ** 0.5 < 120:
                    old_ema = old.get("spoof_ema", 0.0)
                    break
            
            raw_conf = det.get("spoof_conf", 0)
            is_fake = not det.get("is_real", True)
            raw_score = raw_conf if is_fake else (1.0 - raw_conf)
            new_ema = self.EMA_ALPHA * raw_score + (1 - self.EMA_ALPHA) * old_ema
            
            try:
                tracker = cv2.TrackerCSRT_create()
                tracker.init(frame, (x1, y1, bw, bh))
            except Exception:
                tracker = None
            
            new_trackers.append({
                "tracker": tracker,
                "bbox": [x1, y1, x2, y2],
                "name": det.get("name", "..."),
                "score": det.get("score", 0),
                "is_real": new_ema < 0.55,
                "spoof_conf": raw_conf,
                "spoof_ema": new_ema,
                "alert_level": det.get("alert_level", 0),
                "age": 0,
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
                rx = max(0, min(rx, w-1))
                ry = max(0, min(ry, h-1))
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
        
        return [
            {
                "bbox": t["bbox"], "name": t["name"], "score": t["score"],
                "is_real": t["is_real"], "spoof_conf": t["spoof_conf"],
                "spoof_ema": t.get("spoof_ema", 0.5), "alert_level": t["alert_level"],
            }
            for t in alive
        ]
    
    def get_faces(self, cam_id):
        return [
            {
                "bbox": t["bbox"], "name": t["name"], "score": t["score"],
                "is_real": t["is_real"], "spoof_conf": t["spoof_conf"],
                "spoof_ema": t.get("spoof_ema", 0.5), "alert_level": t["alert_level"],
            }
            for t in self.trackers.get(cam_id, [])
            if t["age"] < self.MAX_TRACK_AGE
        ]

face_csrt_tracker = FaceCSRTTracker()


# ==============================================================================
# PRO ANTI-SPOOF STATE
# ==============================================================================
from collections import deque as _deque

spoof_history      = {0: _deque(maxlen=200), 1: _deque(maxlen=200)}
consecutive_fake   = {0: 0, 1: 0}
last_fake_capture  = {0: 0.0, 1: 0.0}
spoof_session_stats = {
    0: {"real": 0, "fake": 0, "alert_level": 0, "start": time.time()},
    1: {"real": 0, "fake": 0, "alert_level": 0, "start": time.time()},
}

os.makedirs(os.path.join(BASE_DIR, "fake_captures"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "screenshots"),   exist_ok=True)

_spoof_log = os.path.join(BASE_DIR, f"spoof_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
with open(_spoof_log, 'w', encoding='utf-8') as _f:
    _f.write(f"Anti-Spoofing Detection Log\nStarted: {datetime.now()}\nModel: best.pt\n{'='*50}\n\n")


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
                print(f"[SPOOF] 📸 Fake saved: {fname}")
            except Exception:
                pass

    if st["alert_level"] >= 2:
        print(f"[SPOOF] 🚨 ALERT LVL {st['alert_level']} cam{cid} | consecutive={cf}")


# ==============================================================================
# SHARED FACE CACHE
# ==============================================================================
_shared_face_cache = {}
_shared_cache_lock = threading.Lock()

def _cache_face_identity(emb, name, score):
    key = tuple(emb[:8].round(3))
    with _shared_cache_lock:
        _shared_face_cache[key] = {"name": name, "score": score, "time": time.time()}

def _lookup_face_cache(emb):
    key = tuple(emb[:8].round(3))
    now = time.time()
    with _shared_cache_lock:
        expired = [k for k, v in _shared_face_cache.items() if now - v["time"] > 5.0]
        for k in expired:
            del _shared_face_cache[k]
        if key in _shared_face_cache:
            entry = _shared_face_cache[key]
            return entry["name"], entry["score"]
    return None, None


# ==============================================================================
# ★ FULL-FRAME SPOOF DETECTION (YOLO best.pt)
# ==============================================================================
def _run_spoof_on_full_frame(frame, cid):
    """
    Chạy YOLO best.pt trên TOÀN BỘ frame camera (không crop).
    Model được train trên full-frame → phải chạy trên full-frame.
    """
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
                conf = float(box.conf[0])
                xyxy = box.xyxy[0].cpu().numpy().astype(int).tolist()
                # Chỉ giữ FAKE khi conf >= 0.50
                if cls_id == 0 and conf < 0.50:
                    continue
                spoof_detections.append({
                    "bbox": xyxy, "is_fake": (cls_id == 0), "conf": conf,
                })
        
        # Debug log
        fakes = [d for d in spoof_detections if d["is_fake"]]
        reals = [d for d in spoof_detections if not d["is_fake"]]
        if fakes or reals:
            parts = []
            for d in fakes: parts.append(f"FAKE={d['conf']:.2f}")
            for d in reals: parts.append(f"REAL={d['conf']:.2f}")
            print(f"[SPOOF] cam{cid} | {' '.join(parts)}")
        
        return spoof_detections
    except Exception as e:
        print(f"[SPOOF] Error: {e}")
        return []


def _match_spoof_to_face(face_bbox, spoof_detections, crop=None, cid=0):
    """
    Ghép YOLO spoof ↔ InsightFace bằng IoU.
    + Uncertainty: cả FAKE+REAL cùng vùng → REAL (model phân vân)
    + ScreenDetector VETO: FAKE bị huỷ nếu ScreenDetector nói không phải màn hình
    """
    matching_fakes = []
    matching_reals = []
    
    for det in spoof_detections:
        iou = calculate_iou(face_bbox, det["bbox"])
        if iou >= 0.15:
            if det["is_fake"]:
                matching_fakes.append((det, iou))
            else:
                matching_reals.append((det, iou))
    
    # Uncertainty: cả FAKE và REAL cho cùng mặt → REAL
    if matching_fakes and matching_reals:
        best_real = max(matching_reals, key=lambda x: x[0]["conf"])
        return False, best_real[0]["conf"], best_real[1]
    
    # Chỉ FAKE → kiểm tra ScreenDetector VETO
    if matching_fakes:
        best = max(matching_fakes, key=lambda x: x[0]["conf"])
        # ScreenDetector VETO: kiểm tra lại bằng phân tích vật lý
        if crop is not None and crop.size > 0:
            sd_is_screen, sd_conf, _ = screen_detector.check_screen(crop, cam_id=cid)
            if not sd_is_screen:
                print(f"[SPOOF] ✅ VETO: YOLO=FAKE({best[0]['conf']:.2f}) but Screen=REAL({sd_conf:.2f}) → REAL")
                return False, 0.5, best[1]
        return True, best[0]["conf"], best[1]
    
    # Chỉ REAL → REAL
    if matching_reals:
        best = max(matching_reals, key=lambda x: x[0]["conf"])
        return False, best[0]["conf"], best[1]
    
    return False, 0.0, 0.0


# ==============================================================================
# ★ CONFIRMATION BUFFER — chống false positive
# ==============================================================================
class IdentityConfirmationBuffer:
    """
    Yêu cầu kết quả nhận diện phải ỔN ĐỊNH LIÊN TỤC trước khi trigger alert.
    - Nhân viên (name != Unknown, is_real=True): confirm NGAY LẬP TỨC
    - Người lạ (Unknown): cần liên tục >= CONFIRMATION_TIME_STRANGER giây
    - Giả mạo (is_real=False): cần liên tục >= CONFIRMATION_TIME_SPOOF giây
    """

    def __init__(self):
        self.tracked = {}
        self._next_key = 0

    def _cosine_sim(self, a, b):
        dot = float(np.dot(a[:16], b[:16]))  # Dùng 16 giá trị đầu cho nhanh
        na = float(np.linalg.norm(a[:16]))
        nb = float(np.linalg.norm(b[:16]))
        return dot / (na * nb) if na > 0 and nb > 0 else 0

    def _find_match(self, emb):
        """Tìm face đã track có cosine similarity > 0.6"""
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

        # ── Nhân viên đã biết → confirm NGAY ──
        if name != "Unknown" and is_real:
            if key is not None and key in self.tracked:
                state = self.tracked[key]
                state.update({
                    "emb": emb, "last_seen": now,
                    "confirmed": True, "confirmed_name": name,
                    "confirmed_is_real": True, "current_name": name,
                })
                should_alert = not state.get("alert_sent", False)
            else:
                key = self._next_key
                self._next_key += 1
                self.tracked[key] = {
                    "emb": emb, "first_seen": now, "last_seen": now,
                    "confirmed": True, "confirmed_name": name,
                    "confirmed_is_real": True, "current_name": name,
                    "pending_type": None, "pending_start": None,
                    "alert_sent": False,
                }
                should_alert = True

            return {
                "confirmed": True, "display_name": name,
                "should_alert": should_alert, "is_real": True,
                "score": score, "spoof_conf": spoof_conf,
            }

        # ── Stranger hoặc Spoof → cần xác minh ──
        if name == "Unknown" and is_real:
            pending_type = "stranger"
            confirm_time = CONFIRMATION_TIME_STRANGER
        else:
            pending_type = "spoof"
            confirm_time = CONFIRMATION_TIME_SPOOF

        if key is None:
            key = self._next_key
            self._next_key += 1
            self.tracked[key] = {
                "emb": emb, "first_seen": now, "last_seen": now,
                "confirmed": False, "confirmed_name": None,
                "confirmed_is_real": None, "current_name": name,
                "pending_type": pending_type, "pending_start": now,
                "alert_sent": False,
            }
            return {
                "confirmed": False, "display_name": "Dang xac minh...",
                "should_alert": False, "is_real": is_real,
                "score": score, "spoof_conf": spoof_conf,
            }

        state = self.tracked[key]
        state["emb"] = emb
        state["last_seen"] = now
        state["current_name"] = name

        # Nếu đã confirmed trước đó
        if state["confirmed"]:
            return {
                "confirmed": True,
                "display_name": state["confirmed_name"] or name,
                "should_alert": not state.get("alert_sent", False),
                "is_real": is_real,
                "score": score, "spoof_conf": spoof_conf,
            }

        # Kiểm tra pending type thay đổi → RESET timer
        if state["pending_type"] != pending_type:
            state["pending_type"] = pending_type
            state["pending_start"] = now
            return {
                "confirmed": False, "display_name": "Dang xac minh...",
                "should_alert": False, "is_real": is_real,
                "score": score, "spoof_conf": spoof_conf,
            }

        # Check đủ thời gian chưa
        elapsed = now - state["pending_start"]
        if elapsed >= confirm_time:
            state["confirmed"] = True
            state["alert_sent"] = False  # Cho phép gửi alert lần đầu
            if pending_type == "spoof":
                state["confirmed_name"] = "GIA MAO"
                state["confirmed_is_real"] = False
            else:
                state["confirmed_name"] = name
                state["confirmed_is_real"] = is_real
            print(f"[CONFIRM] ✅ Confirmed {pending_type}: {state['confirmed_name']} after {elapsed:.1f}s")
            return {
                "confirmed": True,
                "display_name": state["confirmed_name"],
                "should_alert": True,
                "is_real": is_real,
                "score": score, "spoof_conf": spoof_conf,
            }

        # Chưa đủ thời gian — đang chờ
        remaining = confirm_time - elapsed
        return {
            "confirmed": False,
            "display_name": f"Xac minh ({remaining:.0f}s)...",
            "should_alert": False, "is_real": is_real,
            "score": score, "spoof_conf": spoof_conf,
        }

    def mark_alert_sent(self, emb):
        """Đánh dấu đã gửi alert cho face này — tránh gửi lặp"""
        key = self._find_match(emb)
        if key is not None and key in self.tracked:
            self.tracked[key]["alert_sent"] = True

    def cleanup(self):
        now = time.time()
        expired = [k for k, v in self.tracked.items()
                   if now - v["last_seen"] > CONFIRMATION_DISAPPEAR_TIMEOUT]
        for k in expired:
            del self.tracked[k]

confirm_buffer = IdentityConfirmationBuffer()


# ==============================================================================
# ★ NMS + DEDUP — Loại bỏ duplicate faces
# ==============================================================================
def _nms_faces(faces, iou_threshold=0.4):
    """
    Non-Maximum Suppression cho InsightFace output.
    Loại bỏ bounding box trùng — giữ box có det_score cao nhất.
    """
    if len(faces) <= 1:
        return faces
    
    # Sắp theo det_score giảm dần
    scored = sorted(faces, key=lambda f: getattr(f, 'det_score', 0), reverse=True)
    keep = []
    
    for f in scored:
        bbox = f.bbox.astype(int).tolist()
        is_dup = False
        for kept in keep:
            kbbox = kept.bbox.astype(int).tolist()
            iou = calculate_iou(bbox, kbbox)
            if iou > iou_threshold:
                is_dup = True
                break
        if not is_dup:
            keep.append(f)
    
    return keep


def _dedup_faces_by_embedding(face_results, threshold=0.85):
    """
    Merge faces có cùng embedding (cosine > threshold).
    Giữ face có score cao nhất, loại duplicate.
    """
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
            # So sánh nhanh embedding (16 phần tử đầu)
            emb_i = r.get("_emb")
            emb_j = face_results[j].get("_emb")
            if emb_i is not None and emb_j is not None:
                dot = float(np.dot(emb_i[:16], emb_j[:16]))
                ni = float(np.linalg.norm(emb_i[:16]))
                nj = float(np.linalg.norm(emb_j[:16]))
                sim = dot / (ni * nj) if ni > 0 and nj > 0 else 0
                if sim > threshold:
                    used.add(j)
                    if face_results[j].get("score", 0) > best.get("score", 0):
                        best = face_results[j]
        kept.append(best)
        used.add(i)
    
    return kept


# ==============================================================================
# ★ AI WORKER THREAD — DETECT/TRACK PIPELINE
# ==============================================================================
DETECT_EVERY_N = 3  # Full detect mỗi 3 frame, track giữa các frame

def ai_worker_thread():
    frame_counter = 0
    
    print("[AI Worker] Waiting for camera frames...")
    while True:
        with lock:
            if global_frame_0 is not None:
                break
        time.sleep(0.1)
    print(f"[AI Worker] ✅ Started! DETECT every {DETECT_EVERY_N} frames, TRACK between")
    
    while True:
        try:
            frame_counter += 1
            confirm_buffer.cleanup()
            t_start = time.time()
            
            for cid in [0]:  # ★ Chỉ cam 0
                with lock:
                    frame = global_frame_0 if cid == 0 else global_frame_1
                
                if frame is None:
                    continue
                
                h, w = frame.shape[:2]
                new_boxes = []
                new_faces = []
                is_detect_frame = (frame_counter % DETECT_EVERY_N == 0)
                
                # ── YOLO Person Tracking (mỗi DETECT frame) ──
                if is_detect_frame:
                    try:
                        if TRACKING_ENABLED and yolo_model is not None:
                            yolo_results = yolo_model.track(
                                frame, conf=0.25, iou=0.5, persist=True,
                                tracker="bytetrack.yaml", verbose=False,
                                max_det=10, classes=[0],
                                imgsz=PERFORMANCE_SETTINGS["yolo_imgsz"]
                            )
                            
                            if yolo_results and len(yolo_results) > 0:
                                person_ids, tracked_persons = person_tracker.update(frame, yolo_results[0])
                                
                                try: zone_manager.begin_frame(cid)
                                except TypeError:
                                    try: zone_manager.begin_frame()
                                    except: pass
                                
                                for pid, bbox in tracked_persons.items():
                                    is_intruding = False
                                    try: is_intruding, _ = zone_manager.check_intrusion(pid, bbox, frame)
                                    except: pass
                                    new_boxes.append((pid, bbox, is_intruding))
                                
                                try: zone_manager.end_frame(frame, cid)
                                except TypeError:
                                    try: zone_manager.end_frame(frame)
                                    except: pass
                    except Exception as e:
                        print(f"[AI Worker] YOLO error cam {cid}: {e}")
                
                # ═════════════════════════════════════════════════════
                # ★ DETECT FRAME: Full pipeline (mỗi N frame)
                # ═════════════════════════════════════════════════════
                if is_detect_frame:
                    try:
                        # Bước 1: YOLO SPOOF trên FULL FRAME
                        spoof_detections = _run_spoof_on_full_frame(frame, cid)
                        
                        # Bước 2: InsightFace detect + NMS
                        raw_faces = face_app.get(frame)
                        faces = _nms_faces(raw_faces, iou_threshold=0.4)
                        
                        pre_dedup = []
                        for f in faces[:5]:
                            fbbox = f.bbox.astype(int).tolist()
                            emb = f.normed_embedding
                            fx1, fy1, fx2, fy2 = fbbox
                            
                            # Lọc mặt quá nhỏ
                            face_w = fx2 - fx1
                            face_h = fy2 - fy1
                            if face_w < SPOOF_MIN_FACE_SIZE or face_h < SPOOF_MIN_FACE_SIZE:
                                new_faces.append({
                                    "bbox": fbbox, "name": "...",
                                    "score": 0, "is_real": True,
                                    "spoof_conf": 0, "alert_level": 0,
                                })
                                continue
                            
                            # Bước 3: Ghép YOLO spoof ↔ InsightFace bằng IoU
                            crop = frame[max(0, fy1):min(h, fy2), max(0, fx1):min(w, fx2)]
                            is_fake, conf, match_iou = _match_spoof_to_face(
                                fbbox, spoof_detections, crop=crop, cid=cid
                            )
                            is_real = not is_fake
                            spoof_conf = conf
                            _update_spoof_stats(cid, is_real, spoof_conf, crop)
                            
                            # Bước 4: RECOGNITION — CHỈ khi là mặt thật
                            name = "Unknown"
                            score = 0.0
                            
                            if is_real:
                                cached_name, cached_score = _lookup_face_cache(emb)
                                if cached_name is not None:
                                    name, score = cached_name, cached_score
                                else:
                                    name, score = db.recognize(emb)
                                    _cache_face_identity(emb, name, score)
                            else:
                                name = "GIA MAO"
                                score = spoof_conf
                            
                            # Bước 5: CONFIRMATION BUFFER
                            buf = confirm_buffer.update(
                                emb, name, is_real, score, spoof_conf, cid
                            )
                            
                            if buf["confirmed"]:
                                final_name = buf["display_name"]
                                if not is_real and SPOOF_BLOCK_FACE:
                                    final_name = "GIA MAO"
                                alert_lvl = spoof_session_stats[cid]["alert_level"]
                            else:
                                final_name = buf["display_name"]
                                alert_lvl = 0
                            
                            # Bước 6: Alert/Log CHỈ sau confirm
                            if buf["should_alert"]:
                                alert_sent_ok = False
                                
                                if not is_real and SPOOF_BLOCK_FACE and spoof_conf >= 0.45:
                                    try:
                                        telegram_notifier.send_spoof_alert(
                                            frame, face_bbox=fbbox,
                                            confidence=spoof_conf, cam_id=cid
                                        )
                                        add_log("GIA_MAO", cid, spoof_conf, crop)
                                        alert_sent_ok = True
                                    except Exception as tg_e:
                                        print(f"[AI Worker] Telegram spoof error: {tg_e}")
                                
                                elif name == "Unknown" and is_real:
                                    try:
                                        stranger_id = get_stranger_identity(emb)
                                        stranger_label = f"Nguoi_La_{stranger_id}"
                                        telegram_notifier.send_stranger_alert(
                                            stranger_label, frame,
                                            face_bbox=fbbox, cam_id=cid
                                        )
                                        add_log(stranger_label, cid, score, crop)
                                        alert_sent_ok = True
                                    except Exception as tg_e:
                                        print(f"[AI Worker] Telegram stranger error: {tg_e}")
                                
                                elif name != "Unknown" and is_real:
                                    try:
                                        add_log(name, cid, score)
                                        alert_sent_ok = True
                                    except Exception as log_e:
                                        print(f"[AI Worker] Log error: {log_e}")
                                
                                if alert_sent_ok:
                                    confirm_buffer.mark_alert_sent(emb)
                            
                            # Collect for dedup
                            result = {
                                "bbox": fbbox,
                                "name": final_name,
                                "score": score,
                                "is_real": is_real if buf["confirmed"] else True,
                                "spoof_conf": round(spoof_conf, 3),
                                "alert_level": alert_lvl,
                                "_emb": emb,  # Tạm giữ cho dedup
                            }
                            pre_dedup.append(result)
                        
                        # Bước 7: Embedding dedup — loại duplicate
                        deduped = _dedup_faces_by_embedding(pre_dedup, threshold=0.85)
                        for r in deduped:
                            r.pop("_emb", None)  # Xóa embedding trước khi lưu overlay
                            new_faces.append(r)
                        
                        # Bước 8: CSRT init — khởi tạo tracker cho frame tiếp
                        if new_faces:
                            face_csrt_tracker.on_detection(cid, frame, new_faces)
                        
                    except Exception as e:
                        print(f"[AI Worker] Face detect error cam {cid}: {e}")
                
                else:
                    # ═══════════════════════════════════════════════
                    # ★ TRACK FRAME: CSRT update only (~5ms)
                    # ═══════════════════════════════════════════════
                    tracked = face_csrt_tracker.update_frame(cid, frame)
                    if tracked:
                        new_faces = tracked
                
                # ── Cập nhật overlay cache ──
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
                print(f"[AI] {mode} frame {frame_counter}: {elapsed*1000:.0f}ms (FPS≈{fps:.0f})")
            
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
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' 
                           + PLACEHOLDER_JPEG + b'\r\n')
                    time.sleep(0.1)
                    continue
                
                display = raw_frame.copy()
                
                with lock_overlay:
                    cached_boxes = list(ai_overlay_cache[cid]["boxes"])
                    cached_faces = list(ai_overlay_cache[cid]["faces"])
                
                # Vẽ tracking boxes
                for item in cached_boxes:
                    pid, bbox, is_intruding = item
                    x1, y1, x2, y2 = map(int, bbox)
                    if is_intruding:
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), 3)
                        label = f"INTRUDER P{pid}"
                        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                        cv2.rectangle(display, (x1, y1 - th - 10), (x1 + tw + 10, y1), (0, 0, 200), -1)
                        cv2.putText(display, label, (x1 + 5, y1 - 5),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
                    else:
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(display, f"P{pid}", (x1, y1-5), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # ★ Vẽ face boxes
                for face_data in cached_faces:
                    x1, y1, x2, y2 = face_data["bbox"]
                    fname = face_data["name"]
                    fscore = face_data["score"]
                    freal = face_data["is_real"]
                    spf_conf = face_data.get("spoof_conf", 0)
                    
                    if not freal:
                        # ═══ GIẢ MẠO ═══
                        pulse = 3 if int(time.time() * 4) % 2 == 0 else 2
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), pulse)
                        corner_len = min(20, (x2-x1)//4, (y2-y1)//4)
                        for cx, cy, dx, dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
                            cv2.line(display, (cx, cy), (cx + corner_len*dx, cy), (0, 0, 255), 3)
                            cv2.line(display, (cx, cy), (cx, cy + corner_len*dy), (0, 0, 255), 3)
                        label = f"GIA MAO ({int(spf_conf*100)}%)"
                        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                        lw = tw + 16
                        overlay_label = display.copy()
                        cv2.rectangle(overlay_label, (x1, y1 - th - 14), (x1 + lw, y1), (0, 0, 180), -1)
                        cv2.addWeighted(overlay_label, 0.85, display, 0.15, 0, display)
                        cv2.putText(display, label, (x1 + 8, y1 - 6),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 200, 255), 2)
                        cv2.putText(display, "!", (x1 + 3, y1 - 5),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

                    elif "xac minh" in fname.lower() or "Dang xac minh" in fname:
                        # ═══ ĐANG XÁC MINH ═══
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 220, 255), 1)
                        corner_len = min(14, (x2-x1)//4, (y2-y1)//4)
                        for cx, cy, dx, dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
                            cv2.line(display, (cx, cy), (cx + corner_len*dx, cy), (0, 230, 255), 2)
                            cv2.line(display, (cx, cy), (cx, cy + corner_len*dy), (0, 230, 255), 2)
                        cv2.putText(display, fname, (x1 + 4, y1 - 6),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 230, 255), 1)

                    elif fname not in ("Unknown", "...", "Scanning...") and fname != "GIA MAO":
                        # ═══ NHÂN VIÊN ═══
                        cv2.rectangle(display, (x1, y1), (x2, y2), (255, 180, 0), 2)
                        corner_len = min(15, (x2-x1)//4, (y2-y1)//4)
                        for cx, cy, dx, dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
                            cv2.line(display, (cx, cy), (cx + corner_len*dx, cy), (255, 220, 50), 2)
                            cv2.line(display, (cx, cy), (cx, cy + corner_len*dy), (255, 220, 50), 2)
                        display = put_text_utf8(display, f"{fname} ({int(fscore*100)}%)", (x1, y1-30), (255, 220, 50))

                    elif fname in ("...", "Scanning..."):
                        # ═══ ĐANG QUÉT ═══
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 200, 100), 1)
                        corner_len = min(12, (x2-x1)//4, (y2-y1)//4)
                        for cx, cy, dx, dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
                            cv2.line(display, (cx, cy), (cx + corner_len*dx, cy), (0, 220, 120), 2)
                            cv2.line(display, (cx, cy), (cx, cy + corner_len*dy), (0, 220, 120), 2)
                        cv2.putText(display, "Scanning...", (x1 + 4, y1 - 6),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 120), 1)

                    else:
                        # ═══ NGƯỜI LẠ ═══
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 140, 255), 2)
                        corner_len = min(18, (x2-x1)//4, (y2-y1)//4)
                        for cx, cy, dx, dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
                            cv2.line(display, (cx, cy), (cx + corner_len*dx, cy), (0, 165, 255), 3)
                            cv2.line(display, (cx, cy), (cx, cy + corner_len*dy), (0, 165, 255), 3)
                        label = "NGUOI LA"
                        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                        lw = tw + 16
                        overlay_label = display.copy()
                        cv2.rectangle(overlay_label, (x1, y1 - th - 14), (x1 + lw, y1), (0, 100, 200), -1)
                        cv2.addWeighted(overlay_label, 0.8, display, 0.2, 0, display)
                        cv2.putText(display, label, (x1 + 8, y1 - 6),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                        score_label = f"{int(fscore*100)}%"
                        (sw, sh), _ = cv2.getTextSize(score_label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
                        cv2.rectangle(display, (x1, y2), (x1 + sw + 10, y2 + sh + 8), (0, 100, 200), -1)
                        cv2.putText(display, score_label, (x1 + 5, y2 + sh + 4),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 220, 255), 1)
                
                # Zones
                try: display = zone_manager.draw_zones(display)
                except: pass
                try: display = zone_manager.draw_recording_status(display)
                except: pass
                
                # FPS + Status bar
                fps = int(1.0 / max(0.001, time.time() - loop_start))
                status_overlay = display.copy()
                cv2.rectangle(status_overlay, (0, 0), (220, 32), (40, 40, 40), -1)
                cv2.addWeighted(status_overlay, 0.6, display, 0.4, 0, display)
                cv2.putText(display, f"CAM {cid+1} | FPS: {fps}",
                           (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 120), 2)

                # Alert overlay
                al = spoof_session_stats[cid]["alert_level"]
                if al >= 1:
                    h_d, w_d = display.shape[:2]
                    overlay = display.copy()
                    cv2.rectangle(overlay, (0, 0), (w_d, h_d), (0, 0, 180), 8)
                    cv2.addWeighted(overlay, 0.25, display, 0.75, 0, display)
                if al >= 2:
                    h_d, w_d = display.shape[:2]
                    banner = f"!! PHAT HIEN GIA MAO !! [L{al}]"
                    (tw, _th), _ = cv2.getTextSize(banner, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                    ban_overlay = display.copy()
                    cv2.rectangle(ban_overlay, (0, h_d - 45), (w_d, h_d), (0, 0, 160), -1)
                    cv2.addWeighted(ban_overlay, 0.75, display, 0.25, 0, display)
                    cv2.putText(display, banner, ((w_d - tw) // 2, h_d - 12),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                
                ret, buffer = cv2.imencode('.jpg', display, 
                                          [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                if ret: 
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' 
                           + buffer.tobytes() + b'\r\n')
                else:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' 
                           + PLACEHOLDER_JPEG + b'\r\n')
                
            except GeneratorExit:
                print(f"[Stream CAM {cid}] Client disconnected - OK")
                return
            except Exception as e:
                print(f"[Stream CAM {cid}] Error: {e}")
                try:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' 
                           + PLACEHOLDER_JPEG + b'\r\n')
                except:
                    return
                time.sleep(0.1)
                continue
            
            elapsed = time.time() - loop_start
            sleep_time = max(0, frame_time - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    response = Response(
        generate(cam_id), 
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )
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
        return Response(PLACEHOLDER_JPEG, mimetype='image/jpeg',
                       headers={'Cache-Control': 'no-cache'})
    
    display = frame.copy()
    with lock_overlay:
        cached_faces = list(ai_overlay_cache[cam_id]["faces"])
        cached_boxes = list(ai_overlay_cache[cam_id]["boxes"])
    
    for item in cached_boxes:
        pid, bbox, is_intruding = item
        x1, y1, x2, y2 = map(int, bbox)
        color = (0, 0, 255) if is_intruding else (0, 255, 0)
        cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
    
    for face_data in cached_faces:
        x1, y1, x2, y2 = face_data["bbox"]
        fname = face_data["name"]
        fscore = face_data["score"]
        if not face_data["is_real"]:
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(display, "FAKE", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        elif fname != "Unknown":
            cv2.rectangle(display, (x1, y1), (x2, y2), (255, 200, 0), 2)
            cv2.putText(display, f"{fname} ({int(fscore*100)}%)", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
    
    cv2.putText(display, f"CAM {cam_id+1}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    
    ret, buffer = cv2.imencode('.jpg', display, [cv2.IMWRITE_JPEG_QUALITY, 65])
    if not ret:
        return Response(PLACEHOLDER_JPEG, mimetype='image/jpeg')
    
    return Response(buffer.tobytes(), mimetype='image/jpeg',
                   headers={'Cache-Control': 'no-cache, no-store, must-revalidate',
                           'Pragma': 'no-cache', 'Expires': '0'})


@app.route('/test_video/<int:cam_id>')
def test_video(cam_id):
    def generate_raw(cid):
        while True:
            with lock:
                frame = global_frame_0 if cid == 0 else global_frame_1
            if frame is None:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' 
                       + PLACEHOLDER_JPEG + b'\r\n')
                time.sleep(0.1)
                continue
            display = frame.copy()
            cv2.putText(display, f"RAW CAM {cid} - NO AI", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            ret, buffer = cv2.imencode('.jpg', display, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ret:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' 
                       + buffer.tobytes() + b'\r\n')
            time.sleep(0.033)
    
    response = Response(generate_raw(cam_id), mimetype='multipart/x-mixed-replace; boundary=frame')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


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
            "consecutive_fake": consecutive_fake[cid],
            "alert_level": st["alert_level"],
            "uptime_s": round(elapsed, 0),
            "history_tail": hist[-20:],
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
    return jsonify({"success": True, "message": "Stats reset!"})


@app.route('/api/spoof-stats/captures', methods=['GET'])
def list_fake_captures():
    cap_dir = os.path.join(BASE_DIR, "fake_captures")
    files = []
    if os.path.exists(cap_dir):
        for f in sorted(os.listdir(cap_dir), reverse=True)[:50]:
            if f.endswith('.jpg'):
                fpath = os.path.join(cap_dir, f)
                files.append({
                    "filename": f,
                    "size_kb": round(os.path.getsize(fpath) / 1024, 1),
                    "url": f"/api/spoof-stats/capture/{f}"
                })
    return jsonify({"count": len(files), "captures": files})


@app.route('/api/spoof-stats/capture/<filename>')
def serve_fake_capture(filename):
    return send_from_directory(os.path.join(BASE_DIR, "fake_captures"), filename)


@app.route('/login', methods=['POST'])
def login():
    try: data = request.get_json(force=True)
    except: data = request.form.to_dict()
    user = USERS.get(data.get('username', '').split('@')[0])
    if user and user['password'] == data.get('password'):
        session['user'] = user['name']; return jsonify({"success": True, "user": user})
    return jsonify({"success": False}), 401

@app.route('/api/logout', methods=['POST'])
def api_logout(): 
    session.clear(); return jsonify({"success": True})

@app.route('/api/me', methods=['GET'])
def api_me():
    return jsonify({"authenticated": True, "user": USERS.get(session.get('user'))} if 'user' in session else {"authenticated": False})

@app.route('/nguoi_dung', methods=['GET'])
def get_user_all():
    conn = None
    try:
        conn = get_connection()
        if not conn: return jsonify({"status": "error", "message": "DB fail"}), 500
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
                    (d.get('ho_ten'), d.get('email'), d.get('sdt'), d.get('dia_chi'), d.get('ten_phong'), d.get('ten_chuc_vu'), d.get('trang_thai'), d.get('ma_nv')))
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
                stats['logs'].append({
                    "id": row['id'], "name": row['ten'], "dept": row['phong_ban'], 
                    "loc": row['camera'], "time": row['thoi_gian'].strftime("%H:%M:%S %d/%m"), 
                    "status": "Hợp lệ", "image": ""
                })
            cur.close()
    except Exception as e: 
        print(f"Dashboard Error: {e}")
    finally:
        if conn:
            try: conn.close()
            except: pass
    import random; stats.update({"gpu_load": random.randint(10, 40), "temp": random.randint(45, 65)})
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
            detail = { "time": dt.strftime("%H:%M:%S"), "img": img_url }
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
    except Exception as e: 
        return jsonify([])
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
        grouped_blacklist = []; processed_names = {} 
        for r in rows:
            name = r['name']
            img = r['image_path'] or "https://placehold.co/400"
            date_str = r['created_at'].strftime("%d/%m/%Y")
            time_str = r['created_at'].strftime("%H:%M:%S")
            detail_item = { "time": time_str, "img": img, "reason": r['reason'] }
            if name in processed_names:
                idx = processed_names[name]
                grouped_blacklist[idx]['count'] += 1
                grouped_blacklist[idx]['details'].append(detail_item)
            else:
                grouped_blacklist.append({
                    "id": r['id'], "name": name, "reason": r['reason'], "date": date_str, "img": img,
                    "status": "Dangerous", "count": 1, "location": "Trong danh sách đen", "cam": "Cơ sở dữ liệu",
                    "details": [detail_item]
                })
                processed_names[name] = len(grouped_blacklist) - 1
        cursor.close()
        return jsonify(grouped_blacklist)
    except Exception as e: 
        return jsonify([])
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/security/blacklist/add', methods=['POST'])
def add_to_blacklist():
    conn = None
    try:
        d = request.get_json()
        conn = get_connection()
        if not conn: return jsonify({"success": False}), 500
        cursor = conn.cursor()
        cursor.execute("INSERT INTO blacklist (name, reason, image_path, created_at) VALUES (%s, %s, %s, %s)", 
                    (d.get('name'), d.get('reason'), d.get('image'), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit(); cursor.close()
        return jsonify({"success": True, "message": "Đã thêm vào danh sách đen!"})
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
        conn.commit()
        affected = cursor.rowcount; cursor.close()
        if affected > 0:
            return jsonify({"success": True, "message": "Đã xóa khỏi danh sách đen!"})
        return jsonify({"success": False, "message": "Không tìm thấy ID"}), 404
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
        cursor.execute("UPDATE nguoi_la SET trang_thai = 'Đã xác minh' WHERE id = %s", (alert_id,))
        conn.commit(); cursor.close()
        return jsonify({"success": True, "message": "Đã xác minh!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            try: conn.close()
            except: pass

@app.route('/api/security/intrusion-events', methods=['GET'])
def get_intrusion_events():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 12))
        date_filter = request.args.get('date', None)
        
        recordings_dir = Path(BASE_DIR) / "intrusion_recordings"
        snapshots_dir = Path(BASE_DIR) / "intrusion_snapshots"
        events = []
        
        if recordings_dir.exists():
            for vf in sorted(recordings_dir.glob("*.mp4"), reverse=True):
                stat = vf.stat()
                created = datetime.fromtimestamp(stat.st_ctime)
                if date_filter:
                    try:
                        filter_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
                        if created.date() != filter_date: continue
                    except: pass
                
                parts = vf.stem.split('_')
                cam_id = parts[0] if parts else "cam0"
                matched_snapshots = []
                if snapshots_dir.exists():
                    for sf in snapshots_dir.glob("*.jpg"):
                        s_stat = sf.stat()
                        s_time = datetime.fromtimestamp(s_stat.st_ctime)
                        if abs((s_time - created).total_seconds()) < 300:
                            matched_snapshots.append({
                                "filename": sf.name,
                                "url": f"http://localhost:5000/api/security/snapshot/{sf.name}",
                                "time": s_time.strftime("%Y-%m-%d %H:%M:%S"),
                                "person_id": sf.stem.split('_P')[1].split('_')[0] if '_P' in sf.stem else None
                            })
                
                alert_level = "high" if len(matched_snapshots) > 2 else "medium"
                events.append({
                    "id": len(events) + 1, "video_filename": vf.name,
                    "video_url": f"http://localhost:5000/api/tracking/video/{vf.name}",
                    "cam_id": cam_id,
                    "timestamp": created.strftime("%Y-%m-%d %H:%M:%S"),
                    "date": created.strftime("%Y-%m-%d"), "time": created.strftime("%H:%M:%S"),
                    "duration_s": round(stat.st_size / (20 * 640 * 480 * 3 / 50), 1),
                    "size_mb": round(stat.st_size / (1024*1024), 2),
                    "alert_level": alert_level,
                    "snapshots": matched_snapshots[:5],
                    "snapshot_count": len(matched_snapshots),
                    "thumbnail": matched_snapshots[0]["url"] if matched_snapshots else None
                })
        
        total = len(events)
        start = (page - 1) * per_page
        paginated = events[start:start + per_page]
        return jsonify({
            "events": paginated, "total": total, "page": page, "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page if total > 0 else 0
        })
    except Exception as e:
        print(f"[ERROR] intrusion-events: {e}")
        return jsonify({"events": [], "total": 0, "page": 1, "total_pages": 0, "error": str(e)})

@app.route('/api/security/intrusion-events/<int:event_id>', methods=['GET'])
def get_intrusion_event_detail(event_id):
    try:
        recordings_dir = Path(BASE_DIR) / "intrusion_recordings"
        snapshots_dir = Path(BASE_DIR) / "intrusion_snapshots"
        videos = sorted(recordings_dir.glob("*.mp4"), reverse=True) if recordings_dir.exists() else []
        if event_id < 1 or event_id > len(videos):
            return jsonify({"error": "Event not found"}), 404
        
        vf = videos[event_id - 1]
        stat = vf.stat()
        created = datetime.fromtimestamp(stat.st_ctime)
        all_snapshots = []
        if snapshots_dir.exists():
            for sf in sorted(snapshots_dir.glob("*.jpg"), reverse=True):
                s_stat = sf.stat()
                s_time = datetime.fromtimestamp(s_stat.st_ctime)
                if abs((s_time - created).total_seconds()) < 300:
                    all_snapshots.append({
                        "filename": sf.name,
                        "url": f"http://localhost:5000/api/security/snapshot/{sf.name}",
                        "time": s_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "person_id": sf.stem.split('_P')[1].split('_')[0] if '_P' in sf.stem else None
                    })
        
        return jsonify({
            "id": event_id, "video_filename": vf.name,
            "video_url": f"http://localhost:5000/api/tracking/video/{vf.name}",
            "cam_id": vf.stem.split('_')[0],
            "timestamp": created.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_s": round(stat.st_size / (1024*1024) * 2, 1),
            "size_mb": round(stat.st_size / (1024*1024), 2),
            "snapshots": all_snapshots, "snapshot_count": len(all_snapshots)
        })
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
        if row and row[0]:
            return Response(row[0], mimetype='image/jpeg')
        return Response(b'', mimetype='image/jpeg')
    except Exception as e:
        return "Lỗi Server", 500
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

# --- TRACKING API ---
@app.route('/api/tracking/stats', methods=['GET'])
def get_tracking_stats():
    try: tracker_stats = person_tracker.get_stats()
    except: tracker_stats = {}
    try: recorder_stats = zone_manager.recorder.get_stats()
    except: recorder_stats = {}
    try: zones_count = zone_manager.get_zone_count()
    except: zones_count = 0
    return jsonify({
        "tracking_enabled": TRACKING_ENABLED,
        "total_unique_people": tracker_stats.get('total_unique_people', 0),
        "current_active": tracker_stats.get('current_active', 0),
        "tentative_count": tracker_stats.get('tentative_count', 0),
        "zones_count": zones_count,
        "is_recording": recorder_stats.get('is_recording', False),
        "total_recordings": recorder_stats.get('total_recordings', 0),
        "total_intruders_recorded": recorder_stats.get('total_intruders_recorded', 0),
        "active_cameras": recorder_stats.get('active_cameras', [])
    })

@app.route('/api/tracking/zones', methods=['GET'])
def get_zones():
    zones = zone_manager.get_zones()
    return jsonify({"zones": zones, "count": len(zones)})

@app.route('/api/tracking/zones', methods=['POST'])
def add_zone():
    try:
        data = request.get_json()
        points = data.get('points', [])
        if len(points) < 3: return jsonify({"success": False, "message": "Zone cần ít nhất 3 điểm"}), 400
        zone_manager.add_zone([(p['x'], p['y']) for p in points])
        return jsonify({"success": True, "zones_count": zone_manager.get_zone_count()})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/tracking/zones', methods=['DELETE'])
def clear_zones():
    zone_manager.clear_all_zones()
    return jsonify({"success": True})

@app.route('/api/tracking/recordings', methods=['GET'])
def get_recordings():
    try:
        recordings_dir = Path(BASE_DIR) / "intrusion_recordings"
        recordings = []
        if recordings_dir.exists():
            for vf in sorted(recordings_dir.glob("*.mp4"), reverse=True)[:100]:
                stat = vf.stat()
                if stat.st_size < 1024: continue
                try:
                    with open(vf, 'rb') as f:
                        head = f.read(min(stat.st_size, 64 * 1024))
                        has_moov = b'moov' in head
                        if not has_moov and stat.st_size > 64 * 1024:
                            f.seek(max(0, stat.st_size - 64 * 1024))
                            has_moov = b'moov' in f.read()
                    if not has_moov: continue
                except: continue
                recordings.append({"filename": vf.name, "size_mb": round(stat.st_size/(1024*1024), 2),
                    "created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")})
        return jsonify({"recordings": recordings, "count": len(recordings)})
    except Exception as e:
        return jsonify({"recordings": [], "error": str(e)})

@app.route('/api/tracking/video/<filename>')
def stream_recording(filename):
    video_dir = Path(BASE_DIR) / "intrusion_recordings"
    video_path = video_dir / filename
    if not video_path.exists():
        return jsonify({"error": "Video không tồn tại"}), 404
    file_size = video_path.stat().st_size
    if file_size < 1024:
        return jsonify({"error": "Video bị hỏng (file rỗng)", "size": file_size}), 422
    try:
        with open(video_path, 'rb') as f:
            data = f.read(min(file_size, 64 * 1024))
            if b'moov' not in data:
                if file_size > 64 * 1024:
                    f.seek(max(0, file_size - 64 * 1024))
                    tail = f.read()
                    if b'moov' not in tail:
                        return jsonify({"error": "Video bị hỏng (thiếu moov atom)", "size": file_size}), 422
    except Exception: pass
    return send_from_directory(str(video_dir), filename, mimetype='video/mp4', conditional=True)

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

@app.route('/api/add_employee_with_faces', methods=['POST'])
def add_employee_with_faces():
    conn = None
    try:
        ho_ten = request.form.get('ho_ten')
        email = request.form.get('email')
        sdt = request.form.get('sdt', '')
        dia_chi = request.form.get('dia_chi', '')
        ten_phong = request.form.get('ten_phong', '')
        ten_chuc_vu = request.form.get('ten_chuc_vu', '')
        trang_thai = request.form.get('trang_thai', 'Dang_Lam')
        if not ho_ten or not email:
            return jsonify({"success": False, "message": "Thiếu họ tên hoặc email"}), 400
        conn = get_connection()
        if not conn: return jsonify({"success": False, "message": "DB fail"}), 500
        cursor = conn.cursor()
        cursor.execute("INSERT INTO nhan_vien (ho_ten, email, sdt, dia_chi, ten_phong, ten_chuc_vu, trang_thai) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                      (ho_ten, email, sdt, dia_chi, ten_phong, ten_chuc_vu, trang_thai))
        conn.commit()
        ma_nv = cursor.lastrowid
        
        face_files = request.files.getlist('faces')
        embeddings = []
        if face_files:
            for file in face_files:
                if file and file.filename:
                    file_bytes = np.frombuffer(file.read(), np.uint8)
                    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                    if img is None: continue
                    faces = face_app.get(img)
                    if len(faces) > 0:
                        embeddings.append(faces[0].normed_embedding.tolist())
        
        if embeddings:
            for single_emb in embeddings:
                cursor.execute("INSERT INTO face_embeddings (ma_nv, vector_data) VALUES (%s, %s)",
                              (ma_nv, json.dumps(single_emb)))
            conn.commit()
            db.reload_db()
            message = f"Thêm thành công! Đã lưu {len(embeddings)} khuôn mặt."
        else:
            message = "Thêm thành công (chưa có ảnh khuôn mặt)."
        
        cursor.close()
        return jsonify({"success": True, "message": message, "ma_nv": ma_nv})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            try: conn.close()
            except: pass


# ==============================================================================
# ★ TRAINING DATA VIEWER API
# ==============================================================================
@app.route('/api/training-data', methods=['GET'])
def get_training_data():
    """Trả về dữ liệu training: thông tin nhân viên + vectors + metadata"""
    conn = None
    try:
        conn = get_connection()
        if not conn:
            return jsonify({"success": False, "message": "DB fail"}), 500
        
        cursor = conn.cursor(dictionary=True)
        
        # Lấy tất cả nhân viên + embeddings
        cursor.execute("""
            SELECT 
                nv.ma_nv, nv.ho_ten, nv.email, nv.ten_phong, nv.ten_chuc_vu, nv.trang_thai,
                fe.id as embedding_id, fe.vector_data
            FROM nhan_vien nv
            LEFT JOIN face_embeddings fe ON nv.ma_nv = fe.ma_nv
            ORDER BY nv.ma_nv
        """)
        rows = cursor.fetchall()
        
        # Group theo nhân viên
        employees = {}
        for row in rows:
            ma_nv = row['ma_nv']
            if ma_nv not in employees:
                employees[ma_nv] = {
                    "ma_nv": ma_nv,
                    "ho_ten": row['ho_ten'],
                    "email": row['email'],
                    "ten_phong": row['ten_phong'] or "N/A",
                    "ten_chuc_vu": row['ten_chuc_vu'] or "N/A",
                    "trang_thai": row['trang_thai'] or "N/A",
                    "vectors": [],
                    "vector_count": 0,
                    "has_face_data": False,
                }
            
            if row['vector_data']:
                try:
                    vec = json.loads(row['vector_data'])
                    arr = np.array(vec, dtype=np.float32)
                    
                    if arr.ndim == 1:
                        norm = float(np.linalg.norm(arr))
                        employees[ma_nv]["vectors"].append({
                            "embedding_id": row['embedding_id'],
                            "dim": len(arr),
                            "norm": round(norm, 4),
                            "is_normalized": abs(norm - 1.0) < 0.01,
                            "preview": arr[:8].tolist(),  # 8 phần tử đầu
                            "stats": {
                                "min": round(float(arr.min()), 4),
                                "max": round(float(arr.max()), 4),
                                "mean": round(float(arr.mean()), 4),
                                "std": round(float(arr.std()), 4),
                            }
                        })
                    elif arr.ndim == 2:
                        for i, single in enumerate(arr):
                            norm = float(np.linalg.norm(single))
                            employees[ma_nv]["vectors"].append({
                                "embedding_id": f"{row['embedding_id']}_{i}",
                                "dim": len(single),
                                "norm": round(norm, 4),
                                "is_normalized": abs(norm - 1.0) < 0.01,
                                "preview": single[:8].tolist(),
                                "stats": {
                                    "min": round(float(single.min()), 4),
                                    "max": round(float(single.max()), 4),
                                    "mean": round(float(single.mean()), 4),
                                    "std": round(float(single.std()), 4),
                                }
                            })
                except Exception as e:
                    print(f"[Training Data] Parse error for NV{ma_nv}: {e}")
        
        # Tính similarity giữa các vectors cùng nhân viên
        for ma_nv, emp in employees.items():
            vecs = emp["vectors"]
            emp["vector_count"] = len(vecs)
            emp["has_face_data"] = len(vecs) > 0
            
            if len(vecs) >= 2:
                # Tính pairwise cosine similarity
                similarities = []
                for i in range(len(vecs)):
                    for j in range(i + 1, len(vecs)):
                        vi = np.array(vecs[i]["preview"][:8])
                        vj = np.array(vecs[j]["preview"][:8])
                        ni = np.linalg.norm(vi)
                        nj = np.linalg.norm(vj)
                        if ni > 0 and nj > 0:
                            sim = float(np.dot(vi, vj) / (ni * nj))
                            similarities.append(round(sim, 4))
                
                emp["intra_similarity"] = {
                    "min": min(similarities) if similarities else 0,
                    "max": max(similarities) if similarities else 0,
                    "avg": round(sum(similarities) / len(similarities), 4) if similarities else 0,
                }
            else:
                emp["intra_similarity"] = None
        
        # Summary stats
        total_employees = len(employees)
        with_face = sum(1 for e in employees.values() if e["has_face_data"])
        without_face = total_employees - with_face
        total_vectors = sum(e["vector_count"] for e in employees.values())
        
        cursor.close()
        
        return jsonify({
            "success": True,
            "summary": {
                "total_employees": total_employees,
                "with_face_data": with_face,
                "without_face_data": without_face,
                "total_vectors": total_vectors,
                "avg_vectors_per_person": round(total_vectors / max(with_face, 1), 1),
            },
            "employees": list(employees.values()),
        })
    
    except Exception as e:
        print(f"[Training Data API] Error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            try: conn.close()
            except: pass


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 SERVER STARTING — PIPELINE TỐI ƯU")
    print("   Pipeline: Detect → Spoof Check → Recognition")
    print("   Confirmation Buffer: 3s cho stranger/spoof")
    print("   MJPEG stream:  http://localhost:5000/video_feed/0")
    print("   MJPEG stream:  http://localhost:5000/video_feed/1") 
    print("   Snapshot:      http://localhost:5000/snapshot/0")
    print("   Test raw:      http://localhost:5000/test_video/0")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)