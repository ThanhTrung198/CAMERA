"""
AI Worker Service - Background thread for AI processing (YOLO + Face Recognition)
"""
import threading
import time
import cv2
from config.settings import PERFORMANCE_SETTINGS, TRACKING_ENABLED, SPOOF_CHECK_ENABLED, SPOOF_BLOCK_FACE
from services.camera_service import global_frame_0, global_frame_1, lock
from services.face_service import db
from utils.image_utils import check_face_real

# AI Overlay Cache - stores AI results for video stream
ai_overlay_cache = {
    0: {"boxes": [], "faces": [], "last_update": 0},
    1: {"boxes": [], "faces": [], "last_update": 0}
}
lock_overlay = threading.Lock()

# These will be initialized by app.py
yolo_model = None
face_app = None
spoof_model = None

zone_manager = None
person_tracker = None


def set_ai_models(yolo, face, spoof, zones, tracker):
    """Set AI models (called from app.py after initialization)"""
    global yolo_model, face_app, spoof_model, zone_manager, person_tracker
    yolo_model = yolo
    face_app = face
    spoof_model = spoof
    zone_manager = zones
    person_tracker = tracker


def ai_worker_thread():
    """
    Background AI processing thread
    Runs YOLO tracking and face recognition, updates cache for video stream
    """
    frame_counter = 0
    skip = PERFORMANCE_SETTINGS["ai_skip_frames"]
    
    print("[AI Worker] Waiting for camera frames...")
    
    # Wait for first frame
    while True:
        with lock:
            if global_frame_0 is not None:
                break
        time.sleep(0.1)
    
    print("[AI Worker] ✅ Started!")
    
    while True:
        try:
            frame_counter += 1
            
            # Process both cameras
            for cid in [0, 1]:
                with lock:
                    frame = global_frame_0 if cid == 0 else global_frame_1
                
                if frame is None:
                    continue
                
                h, w = frame.shape[:2]
                new_boxes = []
                new_faces = []
                
                # YOLO Tracking (every skip frames)
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
                                
                                # Zone intrusion check
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
                                
                                # End frame for recording
                                try:
                                    zone_manager.end_frame(frame, cid)
                                except TypeError:
                                    try:
                                        zone_manager.end_frame(frame)
                                    except:
                                        pass
                    
                    except Exception as e:
                        print(f"[AI Worker] YOLO error cam {cid}: {e}")
                
                # Face Recognition (every skip*2 frames)
                if frame_counter % (skip * 2) == 0:
                    try:
                        if face_app is not None:
                            faces = face_app.get(frame)
                            for f in faces[:5]:  # Limit to 5 faces
                                fbbox = f.bbox.astype(int).tolist()
                                emb = f.normed_embedding
                                name, score = db.recognize(emb)
                                
                                is_real = True
                                if SPOOF_CHECK_ENABLED and spoof_model:
                                    fx1, fy1, fx2, fy2 = fbbox
                                    crop = frame[max(0, fy1):min(h, fy2), max(0, fx1):min(w, fx2)]
                                    if crop.size > 0:
                                        is_real, _ = check_face_real(crop, spoof_model, cam_id=cid)
                                
                                new_faces.append({
                                    "bbox": fbbox,
                                    "name": "GIA MAO" if (not is_real and SPOOF_BLOCK_FACE) else name,
                                    "score": score,
                                    "is_real": is_real
                                })
                    except Exception as e:
                        print(f"[AI Worker] Face error cam {cid}: {e}")
                
                # Update cache
                with lock_overlay:
                    if new_boxes:
                        ai_overlay_cache[cid]["boxes"] = new_boxes
                    if new_faces:
                        ai_overlay_cache[cid]["faces"] = new_faces
                    ai_overlay_cache[cid]["last_update"] = time.time()
            
            time.sleep(0.01)  # Small sleep to prevent CPU overload
        
        except Exception as e:
            print(f"[AI Worker] Error: {e}")
            time.sleep(0.1)


def start_ai_worker():
    """Start AI worker thread"""
    ai_thread = threading.Thread(target=ai_worker_thread, daemon=True)
    ai_thread.start()
