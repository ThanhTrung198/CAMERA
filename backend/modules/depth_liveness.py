# ============================================================
# FILE: modules/depth_liveness.py
# Monocular Depth Estimation — Detect flat spoofs
# ============================================================
"""
Người thật: cấu trúc 3D (mũi nhô, mắt lõm)
Ảnh in/video: PHẲNG (depth đồng nhất)

Model: Depth-Anything-V2-Small (nhẹ, nhanh)
Install: pip install transformers torch
"""
import numpy as np
import cv2
import time

DEPTH_MODEL_AVAILABLE = False
depth_pipe = None

try:
    from transformers import pipeline as hf_pipeline
    depth_pipe = hf_pipeline(
        "depth-estimation",
        model="depth-anything/Depth-Anything-V2-Small-hf",
        device="cpu"
    )
    DEPTH_MODEL_AVAILABLE = True
    print("[Depth] ✅ Depth-Anything-V2 loaded")
except Exception as e:
    print(f"[Depth] ⚠️ Not available: {e}")


class DepthLivenessChecker:
    """
    Phân tích depth map: variance, range, nose prominence.
    Ảnh phẳng → variance ≈ 0 → FAKE.
    """
    
    MIN_DEPTH_VARIANCE = 0.02
    MIN_DEPTH_RANGE = 0.05
    MIN_NOSE_PROMINENCE = 0.01
    
    def __init__(self):
        self.cache = {}
        self.last_check_time = {}
        self.CHECK_INTERVAL = 1.0
    
    def check(self, face_crop, track_id=None):
        if not DEPTH_MODEL_AVAILABLE or face_crop is None:
            return {"is_3d": True, "confidence": 0.5}
        
        now = time.time()
        if track_id and track_id in self.last_check_time:
            if now - self.last_check_time[track_id] < self.CHECK_INTERVAL:
                return self.cache.get(track_id, {"is_3d": True, "confidence": 0.5})
        
        try:
            from PIL import Image
            small = cv2.resize(face_crop, (256, 256))
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)
            
            result = depth_pipe(pil_img)
            depth_map = np.array(result["depth"])
            
            d_min, d_max = depth_map.min(), depth_map.max()
            depth_norm = (depth_map - d_min) / (d_max - d_min) if d_max > d_min else np.zeros_like(depth_map)
            
            h, w = depth_norm.shape[:2]
            depth_var = float(np.var(depth_norm))
            depth_range = float(d_max - d_min) / max(float(d_max), 1.0)
            
            center = depth_norm[int(h*0.35):int(h*0.65), int(w*0.35):int(w*0.65)]
            border = np.concatenate([
                depth_norm[:int(h*0.2), :].flatten(),
                depth_norm[int(h*0.8):, :].flatten(),
            ])
            nose_prom = float(abs(
                (np.mean(center) if center.size else 0) -
                (np.mean(border) if border.size else 0)
            ))
            
            scores = [
                min(1.0, depth_var / self.MIN_DEPTH_VARIANCE),
                min(1.0, depth_range / self.MIN_DEPTH_RANGE),
                min(1.0, nose_prom / self.MIN_NOSE_PROMINENCE),
            ]
            confidence = float(np.mean(scores))
            
            result_dict = {
                "is_3d": confidence >= 0.45,
                "depth_variance": round(depth_var, 4),
                "depth_range": round(depth_range, 4),
                "nose_prominence": round(nose_prom, 4),
                "confidence": round(confidence, 3),
            }
            
            if track_id:
                self.cache[track_id] = result_dict
                self.last_check_time[track_id] = now
            
            return result_dict
        except Exception as e:
            print(f"[Depth] Error: {e}")
            return {"is_3d": True, "confidence": 0.5}
