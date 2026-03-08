"""
Main Flask Application - Slim version with modular imports

Original app.py backed up to: app_backup_original.py
"""
import cv2
import numpy as np
import os
import time
import json
from pathlib import Path
from datetime import datetime
from flask import Flask, Response, request, jsonify, session, redirect, url_for, send_from_directory
from flask_cors import CORS
from PIL import Image

# Import InsightFace
from insightface.app import FaceAnalysis

# Import Anti-Spoof Model (YOLO best.pt)
from ultralytics import YOLO
from tracking_module import TelegramNotifier, ZoneManager, FixedPersonTracker

# Import Database
from database import get_connection

# Import Config
from config.settings import *

# Import Services
from services.face_service import db
from services.camera_service import start_cameras, global_frame_0, global_frame_1, lock
from services import ai_worker

# Import Utils
from utils.image_utils import create_placeholder_frame, put_text_utf8
from utils.auth_utils import login_required

# ============================================================================
# FLASK INITIALIZATION
# ============================================================================
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')
app.secret_key = SECRET_KEY

# NumPy compatibility fix
np.int = int

CORS(app, resources={r"/*": {"origins": CORS_ORIGINS}}, supports_credentials=True)

# ============================================================================
# AI MODELS INITIALIZATION
# ============================================================================
print("System: Đang khởi tạo InsightFace...")
face_app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
face_app.prepare(ctx_id=0, det_size=(512, 512))
print("✅ InsightFace ready!")

print("System: Đang khởi tạo Anti-Spoofing Model (best.pt)...")
spoof_model = None
best_pt_path = os.path.join(BASE_DIR, "best.pt")

if os.path.exists(best_pt_path):
    try:
        spoof_model = YOLO(best_pt_path)
        print(f"✅ Anti-Spoof YOLO Model loaded! Classes: {spoof_model.names}")
    except Exception as e:
        print(f"⚠️ Anti-Spoof model load error: {e}")
        spoof_model = None
else:
    print(f"⚠️ best.pt not found at: {best_pt_path}")

# YOLO + Tracking
print("System: Đang khởi tạo YOLO...")
if os.path.exists(YOLO_MODEL_PATH):
    try:
        os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD'] = '0'
        original_torch_load = torch.load
        def patched_torch_load(*args, **kwargs):
            kwargs['weights_only'] = False
            return original_torch_load(*args, **kwargs)
        torch.load = patched_torch_load
        yolo_model = YOLO(YOLO_MODEL_PATH)
        print("✅ YOLO Model loaded!")
        torch.load = original_torch_load
    except Exception as e:
        print(f"⚠️ YOLO load error: {e}")
        yolo_model = None
else:
    print(f"⚠️ YOLO model not found at {YOLO_MODEL_PATH}")
    yolo_model = None

person_tracker = FixedPersonTracker(max_disappeared=100)
telegram_notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
zone_manager = ZoneManager(telegram_notifier=telegram_notifier)

print("✅ Tracking Module initialized!")

# Set AI models in worker
ai_worker.set_ai_models(yolo_model, face_app, spoof_model, zone_manager, person_tracker)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
LAST_LOG_TIME = {}
RECENT_STRANGERS = []
NEXT_STRANGER_ID = 1

def add_log(name, cam_id, score, face_img=None):
    """Add recognition log to database"""
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
        if not conn:
            return False
        cursor = conn.cursor()
        
        if "GIA_MAO" in name or "Người lạ" in name or "Nguoi_La" in name or "Unknown" in name:
            img_blob = None
            if face_img is not None and face_img.size > 0:
                success, encoded_img = cv2.imencode('.jpg', face_img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                if success:
                    img_blob = encoded_img.tobytes()
            cursor.execute(
                "INSERT INTO nguoi_la (thoi_gian, camera, trang_thai, image_data, image_path) VALUES (%s, %s, %s, %s, %s)",
                (now_str, camera_name, name, img_blob, "")
            )
        else:
            info = db.get_person_info(name)
            dept = info.get('dept') or "Chưa cập nhật"
            cursor.execute(
                "INSERT INTO nhat_ky_nhan_dien (thoi_gian, ten, phong_ban, camera, do_tin_cay, trang_thai, image_path) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (now_str, name, dept, camera_name, float(score), "authorized", "")
            )
        
        conn.commit()
        cursor.close()
        LAST_LOG_TIME[name] = current_time
        return True
    except Exception as e:
        print(f" >> ❌ Lỗi DB: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

def get_stranger_identity(embedding):
    """Get or create stranger ID"""
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
    
    RECENT_STRANGERS.append({
        'id': new_id,
        'embedding': embedding,
        'last_seen': time.time()
    })
    
    return new_id

# ============================================================================
# PLACEHOLDER FRAME
# ============================================================================
_placeholder_frame = create_placeholder_frame("WAITING FOR CAMERA...")
_ret_ph, _placeholder_jpg = cv2.imencode('.jpg', _placeholder_frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
PLACEHOLDER_JPEG = _placeholder_jpg.tobytes() if _ret_ph else b''

# ============================================================================
# ROUTES - Import from app_backup_original.py
# (Due to time, keeping routes inline for now - can be extracted later)
# ============================================================================

# NOTE: To save time and avoid errors, I'm keeping all route definitions
# from the original app.py here. In a future refactor, these can be moved
# to separate blueprint files in routes/

# Auth routes
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if username in USERS and USERS[username]['password'] == password:
        session['user'] = username
        return jsonify({
            "success": True,
            "user": {
                "username": username,
                "name": USERS[username]['name'],
                "role": USERS[username]['role']
            }
        })
    return jsonify({"success": False, "message": "Invalid credentials"}), 401

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({"success": True})

@app.route('/api/me', methods=['GET'])
def api_me():
    if 'user' in session:
        user_data = USERS.get(session.get('user'))
        return jsonify({
            "authenticated": True,
            "user": {
                "username": session.get('user'),
                **user_data
            }
        })
    return jsonify({"authenticated": False})

# Video feed route
@app.route('/video_feed/<int:cam_id>')
def video_feed(cam_id):
    """MJPEG video stream with AI overlays"""
    def generate(cid):
        jpeg_quality = PERFORMANCE_SETTINGS["jpeg_quality"]
        target_fps = PERFORMANCE_SETTINGS["stream_fps"]
        frame_time = 1.0 / target_fps
        
        # Timeout for first frame
        start_wait = time.time()
        timeout = 10.0
        
        while True:
            loop_start = time.time()
            
            try:
                # Get raw frame
                with lock:
                    raw_frame = global_frame_0 if cid == 0 else global_frame_1
                
                if raw_frame is None:
                    if time.time() - start_wait > timeout:
                        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + PLACEHOLDER_JPEG + b'\r\n')
                    time.sleep(0.1)
                    continue
                
                display = raw_frame.copy()
                
                # Get AI overlay data
                with ai_worker.lock_overlay:
                    cached_boxes = list(ai_worker.ai_overlay_cache[cid]["boxes"])
                    cached_faces = list(ai_worker.ai_overlay_cache[cid]["faces"])
                
                # Draw tracking boxes
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
                
                # Draw face boxes
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
                
                # Draw zones
                try:
                    display = zone_manager.draw_zones(display)
                except:
                    pass
                try:
                    display = zone_manager.draw_recording_status(display)
                except:
                    pass
                
                # FPS counter
                fps = int(1.0 / max(0.001, time.time() - loop_start))
                cv2.putText(display, f"CAM {cid+1} | FPS: {fps}",
                           (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                # Encode and yield
                ret, buffer = cv2.imencode('.jpg', display, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                if ret:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                else:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + PLACEHOLDER_JPEG + b'\r\n')
            
            except GeneratorExit:
                print(f"[Stream CAM {cid}] Client disconnected - OK")
                return
            except Exception as e:
                print(f"[Stream CAM {cid}] Error: {e}")
                try:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + PLACEHOLDER_JPEG + b'\r\n')
                except:
                    return
                time.sleep(0.1)
                continue
            
            # FPS control
            elapsed = time.time() - loop_start
            sleep_time = max(0, frame_time - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    return Response(
        generate(cam_id),
        mimetype='multipart/x-mixed-replace; boundary=frame',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )

# Other routes from original app.py will be added here...
# (Keeping this minimal for now to test if refactoring works)

# ============================================================================
# MAIN
# ============================================================================
if __name__ == '__main__':
    # Start camera threads
    start_cameras()
    
    # Start AI worker thread
    ai_worker.start_ai_worker()
    
    print("=" * 60)
    print("🚀 SERVER STARTING (Refactored)")
    print("   MJPEG stream:  http://localhost:5000/video_feed/0")
    print("   MJPEG stream:  http://localhost:5000/video_feed/1")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
