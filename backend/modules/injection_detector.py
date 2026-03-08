# ============================================================
# FILE: modules/injection_detector.py
# Virtual Camera / Video Injection Attack Detection
# ============================================================
import cv2
import numpy as np
import platform
import subprocess
import time
from collections import deque


class InjectionDetector:
    """
    Phát hiện injection attacks:
    1. Camera device validation (tên thiết bị)
    2. Frame timing analysis (virtual cam timing đều bất thường)
    3. Sensor noise analysis (camera thật có noise pattern riêng)
    4. Duplicate frame detection (video replay có frame trùng)
    """
    
    KNOWN_VIRTUAL_CAMERAS = [
        "obs", "manycam", "snap camera", "xsplit", "virtual",
        "droidcam", "iriun", "epoccam", "ndi", "newtek",
        "streamlabs", "chromacam", "mmhmm", "camo",
    ]
    
    def __init__(self, fps_target=30):
        self.fps_target = fps_target
        self.frame_times = deque(maxlen=300)
        self.prev_frame_hash = None
        self.duplicate_count = 0
        self.total_frames = 0
        self.last_frames = deque(maxlen=5)
    
    def check_camera_name(self, cam_index=0):
        suspicious = False
        cam_name = "Unknown"
        
        if platform.system() == "Windows":
            try:
                result = subprocess.run(
                    ["powershell", "-Command",
                     "Get-PnpDevice -Class Camera | Select-Object FriendlyName"],
                    capture_output=True, text=True, timeout=5
                )
                cam_name = result.stdout.lower()
                for vc in self.KNOWN_VIRTUAL_CAMERAS:
                    if vc in cam_name:
                        suspicious = True
                        break
            except Exception:
                pass
        
        return {"camera_name": cam_name.strip(), "is_virtual": suspicious}
    
    def analyze_frame(self, frame, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
        
        self.frame_times.append(timestamp)
        self.total_frames += 1
        reasons = []
        scores = []
        
        # ── 1. Timing Analysis ──
        if len(self.frame_times) >= 60:
            diffs = np.diff(list(self.frame_times))
            jitter = np.std(diffs)
            if jitter < 0.0005:
                reasons.append("timing_too_regular")
                scores.append(0.3)
            else:
                scores.append(0.8)
        
        # ── 2. Duplicate Frame Detection ──
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (64, 64))
        frame_hash = hash(small.tobytes())
        
        if frame_hash == self.prev_frame_hash:
            self.duplicate_count += 1
        self.prev_frame_hash = frame_hash
        
        if self.total_frames > 30:
            dup_ratio = self.duplicate_count / self.total_frames
            if dup_ratio > 0.15:
                reasons.append("high_duplicate_ratio")
                scores.append(0.2)
            else:
                scores.append(0.9)
        
        # ── 3. Sensor Noise Analysis ──
        if len(self.last_frames) >= 3:
            noise_levels = []
            for f in list(self.last_frames):
                f_gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(float)
                noise_levels.append(np.var(cv2.Laplacian(f_gray, cv2.CV_64F)))
            
            if np.mean(noise_levels) < 50:
                reasons.append("low_sensor_noise")
                scores.append(0.3)
            else:
                scores.append(0.8)
        
        self.last_frames.append(frame.copy())
        
        confidence = np.mean(scores) if scores else 0.5
        is_injected = len(reasons) >= 2 or confidence < 0.4
        
        return {
            "is_injected": is_injected,
            "confidence": round(confidence, 3),
            "reasons": reasons,
            "metrics": {
                "total_frames": self.total_frames,
                "duplicate_ratio": round(self.duplicate_count / max(self.total_frames, 1), 3),
            }
        }
