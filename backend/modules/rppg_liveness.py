# ============================================================
# FILE: modules/rppg_liveness.py
# rPPG Liveness Detection — Phát hiện nhịp tim từ camera RGB
# ============================================================
"""
Nguyên lý:
- Người thật: da thay đổi màu nhẹ theo nhịp tim (60-150 BPM)
- Ảnh in, video replay, mặt nạ 3D: KHÔNG có tín hiệu nhịp tim

Method: CHROM (De Haan & Jeanne, 2013)
"""
import numpy as np
import cv2
import time
from collections import deque

SCIPY_AVAILABLE = False
try:
    from scipy.signal import butter, filtfilt
    SCIPY_AVAILABLE = True
except ImportError:
    print("[rPPG] ⚠️ scipy not installed — pip install scipy")


class ManualCHROM_rPPG:
    """CHROM method — trích xuất nhịp tim từ video RGB. Không cần GPU."""
    
    BUFFER_SIZE = 150   # ~5s at 30fps
    MIN_SAMPLES = 45    # ~1.5s minimum
    HR_LOW = 0.7        # 42 BPM
    HR_HIGH = 3.5       # 210 BPM
    
    def __init__(self, fps=30):
        self.fps = fps
        self.signal_buffer = deque(maxlen=self.BUFFER_SIZE)
        self.timestamps = deque(maxlen=self.BUFFER_SIZE)
    
    def extract_roi_signal(self, face_crop):
        """Trích xuất tín hiệu RGB trung bình từ vùng da (trán + má)."""
        if face_crop is None or face_crop.size == 0:
            return None
        h, w = face_crop.shape[:2]
        
        forehead = face_crop[int(h*0.15):int(h*0.35), int(w*0.25):int(w*0.75)]
        left_cheek = face_crop[int(h*0.45):int(h*0.70), int(w*0.10):int(w*0.40)]
        right_cheek = face_crop[int(h*0.45):int(h*0.70), int(w*0.60):int(w*0.90)]
        
        signals = []
        for roi in [forehead, left_cheek, right_cheek]:
            if roi.size > 0:
                signals.append(roi.mean(axis=(0, 1)))
        
        return np.mean(signals, axis=0) if signals else None
    
    def process_frame(self, face_crop, timestamp=None):
        """
        Xử lý 1 frame, tích lũy signal.
        Returns: dict with hr, signal_strength, has_pulse, ready, buffer_fill
        """
        if timestamp is None:
            timestamp = time.time()
        
        signal = self.extract_roi_signal(face_crop)
        if signal is None:
            return {"hr": None, "signal_strength": 0, "has_pulse": False,
                    "ready": False, "buffer_fill": 0}
        
        self.signal_buffer.append(signal)
        self.timestamps.append(timestamp)
        buffer_fill = len(self.signal_buffer) / self.BUFFER_SIZE
        
        if len(self.signal_buffer) < self.MIN_SAMPLES or not SCIPY_AVAILABLE:
            return {"hr": None, "signal_strength": 0, "has_pulse": False,
                    "ready": False, "buffer_fill": buffer_fill}
        
        # ── CHROM Method ──
        rgb_array = np.array(list(self.signal_buffer))
        R, G, B = rgb_array[:, 2], rgb_array[:, 1], rgb_array[:, 0]
        
        mean_R = max(np.mean(R), 1)
        mean_G = max(np.mean(G), 1)
        mean_B = max(np.mean(B), 1)
        Rn, Gn, Bn = R / mean_R, G / mean_G, B / mean_B
        
        Xs = 3 * Rn - 2 * Gn
        Ys = 1.5 * Rn + Gn - 1.5 * Bn
        
        # Actual FPS from timestamps
        actual_fps = self.fps
        if len(self.timestamps) >= 2:
            dt = np.mean(np.diff(list(self.timestamps)))
            if dt > 0:
                actual_fps = 1.0 / dt
        
        nyq = actual_fps / 2.0
        if nyq <= self.HR_LOW:
            return {"hr": None, "signal_strength": 0, "has_pulse": False,
                    "ready": True, "buffer_fill": buffer_fill}
        
        low = self.HR_LOW / nyq
        high = min(self.HR_HIGH / nyq, 0.99)
        
        if low >= high or low <= 0:
            return {"hr": None, "signal_strength": 0, "has_pulse": False,
                    "ready": True, "buffer_fill": buffer_fill}
        
        try:
            b, a = butter(2, [low, high], btype='band')
            Xs_f = filtfilt(b, a, Xs)
            Ys_f = filtfilt(b, a, Ys)
            
            alpha = np.std(Xs_f) / (np.std(Ys_f) + 1e-8)
            pulse = Xs_f - alpha * Ys_f
            
            N = len(pulse)
            fft_vals = np.fft.rfft(pulse * np.hanning(N))
            fft_freqs = np.fft.rfftfreq(N, d=1.0 / actual_fps)
            magnitude = np.abs(fft_vals)
            
            valid = (fft_freqs >= self.HR_LOW) & (fft_freqs <= self.HR_HIGH)
            if not np.any(valid):
                return {"hr": None, "signal_strength": 0, "has_pulse": False,
                        "ready": True, "buffer_fill": buffer_fill}
            
            valid_mag = magnitude[valid]
            valid_freq = fft_freqs[valid]
            
            peak_idx = np.argmax(valid_mag)
            hr = valid_freq[peak_idx] * 60.0
            signal_strength = float(valid_mag[peak_idx] / (np.sum(valid_mag) + 1e-8))
            has_pulse = 45 <= hr <= 180 and signal_strength > 0.15
            
            return {
                "hr": round(hr, 1) if has_pulse else None,
                "signal_strength": round(signal_strength, 3),
                "has_pulse": has_pulse,
                "ready": True,
                "buffer_fill": buffer_fill,
            }
        except Exception:
            return {"hr": None, "signal_strength": 0, "has_pulse": False,
                    "ready": True, "buffer_fill": buffer_fill}
    
    def reset(self):
        self.signal_buffer.clear()
        self.timestamps.clear()


class RPPGLivenessChecker:
    """Quản lý rPPG cho nhiều face cùng lúc."""
    
    def __init__(self, fps=30):
        self.fps = fps
        self.face_rppgs = {}
    
    def update(self, track_id, face_crop, timestamp=None):
        if track_id not in self.face_rppgs:
            self.face_rppgs[track_id] = ManualCHROM_rPPG(fps=self.fps)
        return self.face_rppgs[track_id].process_frame(face_crop, timestamp)
    
    def cleanup(self, active_ids=None):
        if active_ids is not None:
            for k in [k for k in self.face_rppgs if k not in active_ids]:
                del self.face_rppgs[k]
