"""
Configuration settings for the Face Recognition System
"""
import os
from pathlib import Path

# ============================================================================
# PATHS & DIRECTORIES
# ============================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTOR_DIR = "face_vectors"
ABS_VECTOR_DIR = os.path.join(BASE_DIR, VECTOR_DIR)

STATIC_DIR = os.path.join(BASE_DIR, "static")
STRANGER_DIR = os.path.join(STATIC_DIR, "strangers")

# Create directories if they don't exist
for directory in [ABS_VECTOR_DIR, STRANGER_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# ============================================================================
# FLASK CONFIGURATION
# ============================================================================
SECRET_KEY = 'sieubaomat_anh_trung_dep_trai'
CORS_ORIGINS = "http://localhost:3000"

# ============================================================================
# RECOGNITION THRESHOLDS
# ============================================================================
RECOGNITION_THRESHOLD = 0.50    # 30% cosine similarity để nhận là người quen
SPOOF_FAKE_THRESHOLD = 0.55     # ★ Giảm từ 0.70 → 0.55 để dễ nhận diện giả mạo hơn
SPOOF_REAL_THRESHOLD = 0.60     # ★ Giảm từ 0.75 → 0.60

SYSTEM_SETTINGS = {
    "threshold": RECOGNITION_THRESHOLD,
    "scan_duration": 1,
    "spoof_fake_threshold": SPOOF_FAKE_THRESHOLD,
    "spoof_real_threshold": SPOOF_REAL_THRESHOLD
}

# ============================================================================
# PERFORMANCE SETTINGS
# ============================================================================
PERFORMANCE_SETTINGS = {
    "ai_skip_frames": 1,        # Mỗi frame đều chạy AI (ĐỘ CHÍNH XÁC CAO NHẤT)
    "yolo_imgsz": 320,          # ★ YOLO person tracking chỉ cần 320 (detect người, không cần chi tiết)
    "spoof_imgsz": 640,         # ★ Anti-spoof tại 640 (ĐỘ CHÍNH XÁC CAO NHẤT)
    "face_det_size": (320, 320), # Face detection size (InsightFace)
    "jpeg_quality": 70,          # JPEG compression quality
    "stream_fps": 30,            # Target streaming FPS
    "async_ai": True,            # Run AI in separate thread
    "parallel_faces": False,     # ★ Tắt parallel (tránh lock contention, tăng accuracy)
    "max_faces_per_frame": 10,   # Giới hạn face/frame
}

# ============================================================================
# TRACKING & YOLO
# ============================================================================
TRACKING_ENABLED = True
YOLO_MODEL_PATH = os.path.join(BASE_DIR, "yolo11n.pt")

# ============================================================================
# TELEGRAM NOTIFICATION
# ============================================================================
TELEGRAM_BOT_TOKEN = "8097310654:AAEtu13Fmqrc9lTV4LUX6730ESaGhOmsvRg"
TELEGRAM_CHAT_ID = "7224086648"

# ============================================================================
# STRANGER DETECTION
# ============================================================================
STRANGER_MATCH_THRESHOLD = 0.006

# ============================================================================
# LOGGING
# ============================================================================
LOG_COOLDOWN = 60  # Seconds between logs for same person

# ============================================================================
# ANTI-SPOOFING
# ============================================================================
SPOOF_CHECK_ENABLED = True
SPOOF_BLOCK_FACE = True

# ============================================================================
# USERS (Authentication)
# ============================================================================
USERS = {
    "admin": {
        "name": "Admin",
        "password": "123456",
        "role": "admin",
        "dept": "all"
    }
}
# ==============================================================================
# CONFIRMATION BUFFER — chống false positive
# ==============================================================================
CONFIRMATION_TIME_STRANGER = 0      # Giây chờ xác nhận người lạ
CONFIRMATION_TIME_SPOOF = 0         # ★ Tăng từ 3s → 5s: chống false positive, cần nhiều frame hơn  
CONFIRMATION_DISAPPEAR_TIMEOUT = 1.5  # Giây mất mặt thì reset buffer
SPOOF_MIN_FACE_SIZE = 60