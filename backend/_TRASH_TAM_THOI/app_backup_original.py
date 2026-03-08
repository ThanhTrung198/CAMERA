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
from collections import Counter, OrderedDict
from functools import wraps
from flask_cors import CORS
import torch
import torch.nn.functional as F


# Import kết nối CSDL
from database import get_connection
# Import model Anti-Spoof
from src.model_lib.MiniFASNet import MiniFASNetV2

# Import YOLO + Tracking Module
from ultralytics import YOLO
from tracking_module import TelegramNotifier, ZoneManager, FixedPersonTracker


# --- 1. CẤU HÌNH HỆ THỐNG & ĐƯỜNG DẪN ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VECTOR_DIR = "face_vectors"
ABS_VECTOR_DIR = os.path.join(BASE_DIR, VECTOR_DIR)

STATIC_DIR = os.path.join(BASE_DIR, "static")
STRANGER_DIR = os.path.join(STATIC_DIR, "strangers")

if not os.path.exists(ABS_VECTOR_DIR): os.makedirs(ABS_VECTOR_DIR)
if not os.path.exists(STRANGER_DIR): os.makedirs(STRANGER_DIR)

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static') 
app.secret_key = 'sieubaomat_anh_trung_dep_trai' 

np.int = int

CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}}, supports_credentials=True)

RECOGNITION_THRESHOLD = 0.30    # 30% cosine similarity để nhận là người quen
SPOOF_FAKE_THRESHOLD = 0.70     
SPOOF_REAL_THRESHOLD = 0.75    

SYSTEM_SETTINGS = { 
    "threshold": RECOGNITION_THRESHOLD, 
    "scan_duration": 1,
    "spoof_fake_threshold": SPOOF_FAKE_THRESHOLD,
    "spoof_real_threshold": SPOOF_REAL_THRESHOLD
}

PERFORMANCE_SETTINGS = {
    "ai_skip_frames": 5,
    "yolo_imgsz": 256,
    "face_det_size": (256, 256),
    "jpeg_quality": 60,
    "stream_fps": 25,
    "async_ai": True,
}

lock = threading.Lock()
global_frame_0 = None
global_frame_1 = None

lock_spoof = threading.Lock()

trackers_state = {0: [], 1: []} 

RECENT_STRANGERS = []
NEXT_STRANGER_ID = 1
STRANGER_MATCH_THRESHOLD = 0.006

LAST_LOG_TIME = {} 
LOG_COOLDOWN = 60

USERS = { "admin": { "name": "Admin", "password": "123456", "role": "admin", "dept": "all" } }

anti_spoof_state = {0: {"is_live": True, "confidence": 0.5}, 1: {"is_live": True, "confidence": 0.5}}
SPOOF_CHECK_ENABLED = True
SPOOF_BLOCK_FACE = True


# --- 2. XỬ LÝ DATABASE & AI ---
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
face_app.prepare(ctx_id=0, det_size=(512, 512))
print("✅ InsightFace ready!")

# Anti-Spoof: Chỉ dùng YOLO (chonggiamao.pt)
spoof_model = None  # Không dùng MiniFASNet nữa

db = FaceDatabase()

# ==============================================================================
# KHỞI TẠO YOLO + TRACKING
# ==============================================================================
print("System: Đang khởi tạo YOLO...")
yolo_model_path = os.path.join(BASE_DIR, "yolo26n.pt")
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
# KHỞI TẠO YOLO ANTI-SPOOF (chonggiamao.pt)
# ==============================================================================
print("System: Đang khởi tạo YOLO Anti-Spoof (chonggiamao.pt)...")
yolo_spoof_model = None
yolo_spoof_path = os.path.join(BASE_DIR, "chonggiamao.pt")

if os.path.exists(yolo_spoof_path):
    try:
        os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD'] = '0'
        _orig_load = torch.load
        def _patch_load(*args, **kwargs):
            kwargs['weights_only'] = False
            return _orig_load(*args, **kwargs)
        torch.load = _patch_load
        yolo_spoof_model = YOLO(yolo_spoof_path)
        torch.load = _orig_load
        print("✅ YOLO Anti-Spoof Model (chonggiamao.pt) loaded! → Layer 3 active")
    except Exception as e:
        print(f"⚠️ YOLO Anti-Spoof load error: {e}")
        yolo_spoof_model = None
else:
    print(f"⚠️ chonggiamao.pt not found tại: {yolo_spoof_path}")


# --- 3. TIỆN ÍCH ---
def put_text_utf8(image, text, position, color=(0, 255, 0)):
    img_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    try: font = ImageFont.truetype("arial.ttf", 24) 
    except: font = ImageFont.load_default()
    x, y = position
    for off in [(-1,-1), (1,-1), (-1,1), (1,1)]: draw.text((x+off[0], y+off[1]), text, font=font, fill=(0,0,0))
    draw.text(position, text, font=font, fill=color[::-1])
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

def create_placeholder_frame(text="NO SIGNAL"):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(frame, text, (160, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 2)
    cv2.putText(frame, time.strftime("%H:%M:%S"), (250, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 100, 100), 1)
    return frame

def calculate_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0]); yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2]); yB = min(boxA[3], boxB[3])
    interArea = max(0, xB - xA) * max(0, yB - yA)
    union = (boxA[2]-boxA[0])*(boxA[3]-boxA[1]) + (boxB[2]-boxB[0])*(boxB[3]-boxB[1]) - interArea
    return interArea / float(union) if union > 0 else 0


def check_face_real(face_img, model):
    if face_img is None or face_img.size == 0:
        return True, 0.0
    try:
        img = cv2.resize(face_img, (80, 80))
        img = img.astype(np.float32) / 255.0
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.transpose(2, 0, 1)
        img_tensor = torch.from_numpy(img).unsqueeze(0)
        model.eval()
        with torch.no_grad():
            output = model(img_tensor)
            prob = F.softmax(output, dim=1).cpu().numpy()
        fake_prob = float(prob[0][0])
        real_prob = float(prob[0][2])
        if fake_prob >= SYSTEM_SETTINGS['spoof_fake_threshold']:
            return False, fake_prob
        elif real_prob >= SYSTEM_SETTINGS['spoof_real_threshold']:
            return True, fake_prob
        else:
            return False, fake_prob
    except Exception as e:
        print(f"⚠️ Anti-Spoof Error: {e}")
        return True, 0.0


# ==============================================================================
# ✅ FIX CHÍNH: CAMERA THREAD - Webcam riêng biệt
# ==============================================================================
def camera_thread():
    global global_frame_0, global_frame_1
    
    print("=" * 60)
    print("System: Đang khởi động WEBCAM")
    print("=" * 60)

    # Mở Camera 0
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

    # Mở Camera 1 (webcam thứ 2 nếu có)
    cap1 = cv2.VideoCapture(1, cv2.CAP_DSHOW)
    use_shared_cam = False
    if cap1.isOpened():
        print("✅ Camera 1: Webcam 1 mở OK")
        cap1.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap1.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    else:
        print("⚠️ Camera 1: Dùng chung webcam 0")
        cap1.release()
        cap1 = None
        use_shared_cam = True
    
    fail_count_0 = 0
    fail_count_1 = 0
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
            
            frame1 = None
            if use_shared_cam:
                frame1 = frame0
            elif cap1 is not None and cap1.isOpened():
                ret, f = cap1.read()
                if ret and f is not None:
                    frame1 = f
                    fail_count_1 = 0
                else:
                    fail_count_1 += 1
                    if fail_count_1 >= MAX_FAIL:
                        cap1.release()
                        cap1 = cv2.VideoCapture(1, cv2.CAP_DSHOW)
                        fail_count_1 = 0

            with lock:
                global_frame_0 = frame0.copy() if frame0 is not None else None
                global_frame_1 = frame1.copy() if frame1 is not None else None
            
            time.sleep(0.025)

    except Exception as e:
        print(f"❌ Camera thread error: {e}")
    finally:
        if cap0 is not None: cap0.release()
        if cap1 is not None: cap1.release()

t = threading.Thread(target=camera_thread, daemon=True)
t.start()


# --- HÀM GHI LOG ---
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
# AI WORKER THREAD
# ==============================================================================
ai_overlay_cache = {
    0: {"boxes": [], "faces": [], "last_update": 0},
    1: {"boxes": [], "faces": [], "last_update": 0}
}
lock_overlay = threading.Lock()


def ai_worker_thread():
    frame_counter = 0
    skip = PERFORMANCE_SETTINGS["ai_skip_frames"]
    
    print("[AI Worker] Waiting for camera frames...")
    while True:
        with lock:
            if global_frame_0 is not None:
                break
        time.sleep(0.1)
    print("[AI Worker] ✅ Started!")
    
    while True:
        try:
            frame_counter += 1
            
            for cid in [0, 1]:
                with lock:
                    frame = global_frame_0 if cid == 0 else global_frame_1
                
                if frame is None:
                    continue
                
                h, w = frame.shape[:2]
                new_boxes = []
                new_faces = []
                
                if frame_counter % skip == 0:
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
                
                if frame_counter % (skip * 2) == 0:
                    try:
                        faces = face_app.get(frame)
                        for f in faces[:5]:
                            fbbox = f.bbox.astype(int).tolist()
                            emb = f.normed_embedding
                            name, score = db.recognize(emb)
                            
                            is_real = True
                            if SPOOF_CHECK_ENABLED and yolo_spoof_model is not None:
                                fx1, fy1, fx2, fy2 = fbbox
                                crop = frame[max(0,fy1):min(h,fy2), max(0,fx1):min(w,fx2)]
                                if crop.size > 0:
                                    try:
                                        ysr = yolo_spoof_model(crop, verbose=False, imgsz=128)
                                        for yr in ysr:
                                            if yr.boxes is not None and len(yr.boxes) > 0:
                                                top_box = max(yr.boxes, key=lambda b: float(b.conf[0]))
                                                yconf = float(top_box.conf[0])
                                                ycls  = int(top_box.cls[0])
                                                # class 0 = Fake, class 1 = Real
                                                if ycls == 0 and yconf >= 0.60:
                                                    is_real = False
                                                    print(f"[SPOOF] ❌ FAKE | YOLO conf={yconf:.2f}")
                                                else:
                                                    print(f"[SPOOF] ✅ REAL | YOLO cls={ycls} conf={yconf:.2f}")
                                    except Exception as ye:
                                        pass  # YOLO fail → giữ is_real=True
                            
                            new_faces.append({
                                "bbox": fbbox,
                                "name": "GIA MAO" if (not is_real and SPOOF_BLOCK_FACE) else name,
                                "score": score,
                                "is_real": is_real
                            })
                    except Exception as e:
                        print(f"[AI Worker] Face error cam {cid}: {e}")
                
                with lock_overlay:
                    if new_boxes:
                        ai_overlay_cache[cid]["boxes"] = new_boxes
                    if new_faces:
                        ai_overlay_cache[cid]["faces"] = new_faces
                    ai_overlay_cache[cid]["last_update"] = time.time()
            
            time.sleep(0.05)
            
        except Exception as e:
            print(f"[AI Worker] Error: {e}")
            time.sleep(0.1)

ai_thread = threading.Thread(target=ai_worker_thread, daemon=True)
ai_thread.start()


# ==============================================================================
# ✅ FIX #17 (MỚI - QUAN TRỌNG NHẤT): VIDEO FEED KHÔNG BAO GIỜ CHẾT
#
# 3 nguyên nhân gốc khiến camera tối đen khi chuyển trang:
#
# 1) Generator yield nothing khi frame=None → browser nghĩ stream chết → đen
#    FIX: LUÔN yield 1 frame (placeholder nếu cần), KHÔNG BAO GIỜ skip
#
# 2) Thiếu response headers → browser cache kết quả cũ hoặc không reconnect
#    FIX: Thêm Cache-Control, X-Accel-Buffering, Connection headers
#
# 3) Browser cache MJPEG URL → khi quay lại trang, dùng cached response (chết)
#    FIX: Frontend cần thêm ?t=timestamp (xử lý bên React)
#    Thêm header ngăn cache ở backend
# ==============================================================================

# Tạo 1 placeholder JPEG sẵn để dùng khi chưa có frame (tránh tạo mới mỗi lần)
_placeholder_frame = create_placeholder_frame("WAITING FOR CAMERA...")
_ret_ph, _placeholder_jpg = cv2.imencode('.jpg', _placeholder_frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
PLACEHOLDER_JPEG = _placeholder_jpg.tobytes() if _ret_ph else b''


@app.route('/video_feed/<int:cam_id>')
def video_feed(cam_id):
    """
    ✅ FIX #17: Stream LUÔN yield frame, KHÔNG BAO GIỜ dừng.
    - Nếu có frame từ camera → yield frame + AI overlay
    - Nếu chưa có frame → yield placeholder (không phải đen)
    - Response headers ngăn cache
    """
    def generate(cid):
        jpeg_quality = PERFORMANCE_SETTINGS["jpeg_quality"]
        target_fps = PERFORMANCE_SETTINGS["stream_fps"]
        frame_time = 1.0 / target_fps
        
        while True:
            loop_start = time.time()
            
            try:
                # Lấy frame - có thể None
                with lock: 
                    raw_frame = global_frame_0 if cid == 0 else global_frame_1
                
                # ✅ FIX: LUÔN có frame để yield - không bao giờ skip
                if raw_frame is None:
                    # Chưa có camera → yield placeholder thay vì continue (gây đen)
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' 
                           + PLACEHOLDER_JPEG + b'\r\n')
                    time.sleep(0.1)
                    continue
                
                display = raw_frame.copy()
                
                # Đọc AI cache (rất nhanh)
                with lock_overlay:
                    cached_boxes = list(ai_overlay_cache[cid]["boxes"])
                    cached_faces = list(ai_overlay_cache[cid]["faces"])
                
                # Vẽ tracking boxes
                for item in cached_boxes:
                    pid, bbox, is_intruding = item
                    x1, y1, x2, y2 = map(int, bbox)
                    if is_intruding:
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), 3)
                        cv2.putText(display, f"INTRUDER P{pid}", (x1, y1-10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    else:
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(display, f"P{pid}", (x1, y1-5), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # Vẽ face boxes
                for face_data in cached_faces:
                    x1, y1, x2, y2 = face_data["bbox"]
                    fname = face_data["name"]
                    fscore = face_data["score"]
                    freal = face_data["is_real"]
                    
                    if not freal:
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        cv2.putText(display, "GIA MAO", (x1, y1-10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    elif fname != "Unknown":
                        cv2.rectangle(display, (x1, y1), (x2, y2), (255, 200, 0), 2)
                        cv2.putText(display, f"{fname} ({int(fscore*100)}%)", (x1, y1-10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
                    else:
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 165, 255), 2)
                        cv2.putText(display, "Unknown", (x1, y1-10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
                
                # Zones
                try: display = zone_manager.draw_zones(display)
                except: pass
                try: display = zone_manager.draw_recording_status(display)
                except: pass
                
                # FPS
                fps = int(1.0 / max(0.001, time.time() - loop_start))
                cv2.putText(display, f"CAM {cid+1} | FPS: {fps}", 
                           (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                # Encode & yield
                ret, buffer = cv2.imencode('.jpg', display, 
                                          [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                if ret: 
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' 
                           + buffer.tobytes() + b'\r\n')
                else:
                    # Encode fail → yield placeholder
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' 
                           + PLACEHOLDER_JPEG + b'\r\n')
                
            except GeneratorExit:
                print(f"[Stream CAM {cid}] Client disconnected - OK")
                return
            except Exception as e:
                print(f"[Stream CAM {cid}] Error: {e}")
                # ✅ FIX: Khi lỗi vẫn yield placeholder, KHÔNG để stream chết
                try:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' 
                           + PLACEHOLDER_JPEG + b'\r\n')
                except:
                    return
                time.sleep(0.1)
                continue
            
            # FPS control
            elapsed = time.time() - loop_start
            sleep_time = max(0, frame_time - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    # ✅ FIX #17: Response headers ngăn cache
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


# ✅ FIX #18: Endpoint snapshot - React dùng polling thay MJPEG khi cần
@app.route('/snapshot/<int:cam_id>')
def snapshot(cam_id):
    """
    Trả về 1 ảnh JPEG duy nhất (không stream).
    React có thể polling endpoint này mỗi 200ms nếu MJPEG bị lỗi.
    Ưu điểm: Không bao giờ bị "stream chết" vì mỗi request là độc lập.
    """
    with lock:
        frame = global_frame_0 if cam_id == 0 else global_frame_1
    
    if frame is None:
        return Response(PLACEHOLDER_JPEG, mimetype='image/jpeg',
                       headers={'Cache-Control': 'no-cache'})
    
    # Vẽ AI overlay
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
                           'Pragma': 'no-cache',
                           'Expires': '0'})


# Test raw stream
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


# --- API ROUTES ---

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
            for vf in sorted(recordings_dir.glob("*.mp4"), reverse=True)[:50]:
                stat = vf.stat()
                recordings.append({"filename": vf.name, "size_mb": round(stat.st_size/(1024*1024), 2),
                    "created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")})
        return jsonify({"recordings": recordings, "count": len(recordings)})
    except Exception as e:
        return jsonify({"recordings": [], "error": str(e)})

@app.route('/api/tracking/video/<filename>')
def stream_recording(filename):
    return send_from_directory(str(Path(BASE_DIR) / "intrusion_recordings"), filename)

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


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 SERVER STARTING")
    print("   MJPEG stream:  http://localhost:5000/video_feed/0")
    print("   MJPEG stream:  http://localhost:5000/video_feed/1") 
    print("   Snapshot:      http://localhost:5000/snapshot/0")
    print("   Test raw:      http://localhost:5000/test_video/0")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
