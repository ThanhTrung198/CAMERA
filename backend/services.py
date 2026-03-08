import cv2
import numpy as np
import insightface
from insightface.app import FaceAnalysis
import os
import time
from datetime import datetime
import threading
import json
from PIL import Image, ImageDraw, ImageFont 
from collections import Counter





# =========================
# CẤU HÌNH HỆ THỐNG
# =========================

DB_PATH = "face_db"
LOG_FILE = "access_logs.json"
META_FILE = os.path.join(DB_PATH, "metadata.json")
SYSTEM_SETTINGS = {
    "threshold": 0.65,
    "scan_duration": 3.0
}

if not os.path.exists(DB_PATH):
    os.makedirs(DB_PATH)


# =========================
# CLASS HỆ THỐNG NHẬN DIỆN
# =========================

class FaceSystem:
    def __init__(self):
        print("System: Đang khởi động AI Model...")

        # 1. Khởi tạo insightface
        self.app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
        self.app.prepare(ctx_id=0, det_size=(640, 640))

        # 2. Database & Metadata
        self.known_embeddings = {}
        self.metadata = self.load_metadata()
        self.reload_db()

        # 3. Logs cache
        self.activity_logs = self.load_history_from_file()[:50]

        # 4. Camera
        self.lock = threading.Lock()
        self.frames = {0: None, 1: None}

        print("System: Sẵn sàng!")

    # =========================
    # DATA UTILS
    # =========================

    def load_metadata(self):
        if os.path.exists(META_FILE):
            try:
                with open(META_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_metadata(self, data):
        with open(META_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_history_from_file(self):
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_log_to_file(self, entry):
        logs = self.load_history_from_file()
        logs.insert(0, entry)
        if len(logs) > 2000:
            logs = logs[:2000]

        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)

        # Update RAM cache
        self.activity_logs.insert(0, entry)
        if len(self.activity_logs) > 50:
            self.activity_logs.pop()

    def reload_db(self):
        self.known_embeddings = {}
        if not os.path.exists(DB_PATH):
            return

        files = [f for f in os.listdir(DB_PATH) if f.endswith('.npy')]
        for f in files:
            name = os.path.splitext(f)[0]
            try:
                emb = np.load(os.path.join(DB_PATH, f))
                norm = np.linalg.norm(emb)
                if norm != 0:
                    emb = emb / norm
                self.known_embeddings[name] = emb
            except:
                pass

        self.metadata = self.load_metadata()

    def get_dept(self, name):
        return self.metadata.get(name, {}).get("dept", "Không xác định")

    # =========================
    # AI RECOGNITION
    # =========================

    def recognize(self, target_embedding):
        max_score = 0
        identity = "Unknown"

        norm = np.linalg.norm(target_embedding)
        if norm != 0:
            target_embedding = target_embedding / norm

        for name, db_emb in self.known_embeddings.items():
            score = np.dot(target_embedding, db_emb)
            if score > max_score:
                max_score = score
                identity = name

        if max_score >= SYSTEM_SETTINGS["threshold"]:
            return identity, max_score
        return "Unknown", max_score

    # =========================
    # CAMERA THREAD (KHÔNG TỰ CHẠY)
    # =========================

    def start_camera_thread(self):
        def run():
            cap0 = cv2.VideoCapture(0)

            while True:
                ret0, frame0 = cap0.read()

                with self.lock:
                    self.frames[0] = cv2.flip(frame0, 1) if ret0 else None

                time.sleep(0.03)

        t = threading.Thread(target=run, daemon=True)
        t.start()

    # =========================
    # PROCESS FRAME
    # =========================

    def put_text_utf8(self, image, text, position, color=(0, 255, 0), font_scale=1):
        img_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        font_size = int(font_scale * 20)

        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()

        draw.text(position, text, font=font, fill=color[::-1])
        return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

    def process_frame(self, cam_id):
        with self.lock:
            frame = self.frames.get(cam_id)
            if frame is None:
                return None
            display_frame = frame.copy()

        try:
            faces = self.app.get(frame)

            for face in faces:
                bbox = face.bbox.astype(int)
                name, score = self.recognize(face.embedding)

                color = (0, 0, 255) if name == "Unknown" else (0, 255, 0)
                cv2.rectangle(display_frame, (bbox[0], bbox[1]),
                              (bbox[2], bbox[3]), color, 2)

                label = f"{name} ({score:.2f})"
                display_frame = self.put_text_utf8(display_frame, label, (bbox[0], bbox[1] - 25), color)

                # Nếu cần log thực, anh add thêm logic tracking tại đây.

        except Exception as e:
            print(f"Error processing AI: {e}")

        return display_frame

    def get_logs(self):
        return self.activity_logs


# ========================================================
# QUAN TRỌNG: KHÔNG KHỞI TẠO NGAY KHI IMPORT
# ========================================================

face_system = None

def init_face_system():
    global face_system
    if face_system is None:
        face_system = FaceSystem()
        face_system.start_camera_thread()
