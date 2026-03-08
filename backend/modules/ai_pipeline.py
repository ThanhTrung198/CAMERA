# ============================================================
# FILE: modules/ai_pipeline.py
# Multi-Thread AI Pipeline Architecture
# ============================================================
import threading
import queue
import time


class AITaskQueue:
    """
    Tách AI processing thành multiple threads:
    - Thread 1: Face Detection + Recognition
    - Thread 2: Anti-Spoof (song song với Thread 1)
    - Thread 3: Person Tracking
    - Main: Merge results + CSRT tracking
    """
    
    def __init__(self):
        self.face_queue = queue.Queue(maxsize=2)
        self.spoof_queue = queue.Queue(maxsize=2)
        self.track_queue = queue.Queue(maxsize=2)
        
        self.face_results = {}
        self.spoof_results = {}
        self.track_results = {}
        
        self.lock = threading.Lock()
    
    def submit_face_task(self, cam_id, frame):
        try:
            self.face_queue.put_nowait((cam_id, frame.copy()))
        except queue.Full:
            pass
    
    def submit_spoof_task(self, cam_id, frame):
        try:
            self.spoof_queue.put_nowait((cam_id, frame.copy()))
        except queue.Full:
            pass
    
    def submit_track_task(self, cam_id, frame):
        try:
            self.track_queue.put_nowait((cam_id, frame.copy()))
        except queue.Full:
            pass


def face_detection_worker(task_queue, face_app, db, ensemble_checker):
    """Thread chuyên Face Detection + Recognition"""
    while True:
        try:
            cam_id, frame = task_queue.face_queue.get(timeout=1.0)
            
            spoof_dets = []
            with task_queue.lock:
                if cam_id in task_queue.spoof_results:
                    spoof_dets = task_queue.spoof_results[cam_id]
            
            faces = face_app.get(frame)
            results = []
            
            for f in faces[:5]:
                fbbox = f.bbox.astype(int).tolist()
                emb = f.normed_embedding
                fx1, fy1, fx2, fy2 = fbbox
                h, w = frame.shape[:2]
                crop = frame[max(0, fy1):min(h, fy2), max(0, fx1):min(w, fx2)]
                
                spoof_result = ensemble_checker.check(
                    frame=frame, face_bbox=fbbox, face_crop=crop,
                    cam_id=cam_id, yolo_spoof_detections=spoof_dets
                )
                
                name, score = "Unknown", 0.0
                if spoof_result["is_real"]:
                    name, score = db.recognize(emb)
                else:
                    name = "GIA MAO"
                    score = 1.0 - spoof_result["confidence"]
                
                results.append({
                    "bbox": fbbox, "name": name, "score": score,
                    "is_real": spoof_result["is_real"],
                    "spoof_conf": 1.0 - spoof_result["confidence"],
                    "emb": emb,
                })
            
            with task_queue.lock:
                task_queue.face_results[cam_id] = results
        
        except queue.Empty:
            continue
        except Exception as e:
            print(f"[FaceWorker] Error: {e}")


def spoof_detection_worker(task_queue, spoof_model):
    """Thread chuyên YOLO Spoof Detection — chạy TRƯỚC face detection"""
    from utils.image_utils import _spoof_model_lock
    
    while True:
        try:
            cam_id, frame = task_queue.spoof_queue.get(timeout=1.0)
            
            if spoof_model is None:
                continue
            
            with _spoof_model_lock:
                results = spoof_model.predict(frame, imgsz=640, conf=0.15, verbose=False)
            
            detections = []
            for result in results:
                if result.boxes is None:
                    continue
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    xyxy = box.xyxy[0].cpu().numpy().astype(int).tolist()
                    if cls_id == 0 and conf < 0.50:
                        continue
                    detections.append({
                        "bbox": xyxy, "is_fake": (cls_id == 0), "conf": conf
                    })
            
            with task_queue.lock:
                task_queue.spoof_results[cam_id] = detections
        
        except queue.Empty:
            continue
        except Exception as e:
            print(f"[SpoofWorker] Error: {e}")
