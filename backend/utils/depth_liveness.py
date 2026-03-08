# -*- coding: utf-8 -*-
"""
Depth-Based Liveness Detection Module
=====================================
Module phân tích chiều sâu để chống giả mạo khuôn mặt.

Hỗ trợ 2 chế độ:
1. REAL DEPTH: Sử dụng depth map từ camera RGB-D (Intel RealSense, Azure Kinect)
2. PSEUDO DEPTH: Ước lượng depth từ RGB bằng monocular depth estimation
                 (MiDaS/DPT model) khi chưa có depth camera

Nguyên lý:
- Khuôn mặt thật có cấu trúc 3D: mũi nhô ra, mắt lõm, trán cong
- Ảnh in/video/màn hình phẳng: depth gần như đồng nhất
- Mặt nạ 3D: thiếu vi cấu trúc da, gradient depth không tự nhiên
"""

import cv2
import numpy as np
from collections import deque
from typing import Tuple, Optional, Dict
import time
import threading


class DepthLivenessAnalyzer:
    """Phân tích depth map để phát hiện giả mạo"""
    
    # Thresholds (calibrated for typical face at 0.5-1.0m distance)
    DEPTH_VARIANCE_MIN = 8.0        # Minimum depth variance for real face
    NOSE_PROTRUSION_MIN = 3.0       # Minimum nose protrusion (mm/units)
    SURFACE_NORMAL_VAR_MIN = 0.02   # Minimum surface normal variance
    CURVATURE_MIN = 0.005           # Minimum mean curvature
    FLAT_RATIO_MAX = 0.65           # Max ratio of flat pixels
    
    # Multi-frame voting
    HISTORY_SIZE = 5
    VOTE_THRESHOLD = 3  # Need >= 3/5 FAKE votes to classify as FAKE
    
    def __init__(self):
        self.history: Dict[int, deque] = {}  # cam_id -> deque of results
        self.depth_model = None
        self.depth_model_type = None
        self._lock = threading.Lock()
        
    def _get_history(self, cam_id: int) -> deque:
        if cam_id not in self.history:
            self.history[cam_id] = deque(maxlen=self.HISTORY_SIZE)
        return self.history[cam_id]

    # ==========================================================================
    # CORE: Depth Analysis Functions
    # ==========================================================================
    
    def analyze_depth_variance(self, depth_roi: np.ndarray) -> Tuple[bool, float]:
        """
        Kiểm tra phương sai độ sâu trong vùng khuôn mặt.
        
        Ảnh phẳng → variance ≈ 0 → FAKE
        Mặt thật → variance > threshold → REAL
        
        Args:
            depth_roi: Depth map đã crop theo face bbox
            
        Returns:
            (is_real, variance_score)
        """
        if depth_roi is None or depth_roi.size == 0:
            return True, 0.0  # Không có data → skip
        
        # Loại bỏ invalid depth (0 hoặc NaN)
        valid_mask = (depth_roi > 0) & np.isfinite(depth_roi)
        valid_depth = depth_roi[valid_mask]
        
        if len(valid_depth) < 100:  # Quá ít pixel hợp lệ
            return True, 0.0
        
        variance = np.var(valid_depth)
        is_real = variance >= self.DEPTH_VARIANCE_MIN
        
        return is_real, float(variance)
    
    def analyze_nose_protrusion(self, depth_roi: np.ndarray) -> Tuple[bool, float]:
        """
        Phân tích độ nhô của mũi.
        
        Khuôn mặt thật: mũi gần camera hơn (depth nhỏ hơn) so với viền mặt.
        Ảnh phẳng: không có sự khác biệt depth giữa mũi và viền.
        
        Args:
            depth_roi: Depth map đã crop, shape (H, W)
            
        Returns:
            (is_real, protrusion_score)
        """
        if depth_roi is None or depth_roi.size == 0:
            return True, 0.0
            
        h, w = depth_roi.shape[:2]
        
        # Vùng mũi: trung tâm, ~20% kích thước
        nose_y1, nose_y2 = int(h * 0.35), int(h * 0.65)
        nose_x1, nose_x2 = int(w * 0.35), int(w * 0.65)
        nose_region = depth_roi[nose_y1:nose_y2, nose_x1:nose_x2]
        
        # Vùng viền mặt: rìa trái + phải
        edge_left = depth_roi[:, :int(w * 0.15)]
        edge_right = depth_roi[:, int(w * 0.85):]
        edge_region = np.concatenate([edge_left.flatten(), edge_right.flatten()])
        
        # Filter invalid
        nose_valid = nose_region[(nose_region > 0) & np.isfinite(nose_region)]
        edge_valid = edge_region[(edge_region > 0) & np.isfinite(edge_region)]
        
        if len(nose_valid) < 20 or len(edge_valid) < 20:
            return True, 0.0
        
        # Mũi gần camera hơn → depth value nhỏ hơn → protrusion > 0
        protrusion = float(np.median(edge_valid) - np.median(nose_valid))
        is_real = protrusion >= self.NOSE_PROTRUSION_MIN
        
        return is_real, protrusion
    
    def analyze_surface_normals(self, depth_roi: np.ndarray) -> Tuple[bool, float]:
        """
        Tính vector pháp tuyến bề mặt từ depth map.
        
        Mặt thật: normal vectors biến thiên liên tục (bề mặt cong)
        Ảnh phẳng: normal vectors gần như song song (bề mặt phẳng)
        
        Args:
            depth_roi: Depth map đã crop
            
        Returns:
            (is_real, normal_variance)
        """
        if depth_roi is None or depth_roi.size < 100:
            return True, 0.0
        
        # Smooth depth để giảm noise
        depth_smooth = cv2.GaussianBlur(depth_roi.astype(np.float32), (5, 5), 1.0)
        
        # Tính gradient (xấp xỉ partial derivatives)
        dz_dx = cv2.Sobel(depth_smooth, cv2.CV_32F, 1, 0, ksize=3)
        dz_dy = cv2.Sobel(depth_smooth, cv2.CV_32F, 0, 1, ksize=3)
        
        # Normal vector n = (-dz/dx, -dz/dy, 1) (đã normalize)
        magnitude = np.sqrt(dz_dx**2 + dz_dy**2 + 1.0)
        nx = -dz_dx / magnitude
        ny = -dz_dy / magnitude
        # nz = 1.0 / magnitude
        
        # Tính variance của normal components
        nx_var = np.var(nx[np.isfinite(nx)])
        ny_var = np.var(ny[np.isfinite(ny)])
        normal_var = float(nx_var + ny_var)
        
        is_real = normal_var >= self.SURFACE_NORMAL_VAR_MIN
        
        return is_real, normal_var
    
    def analyze_curvature(self, depth_roi: np.ndarray) -> Tuple[bool, float]:
        """
        Tính độ cong (curvature) của bề mặt khuôn mặt.
        
        Công thức Mean Curvature:
            H = (∂²z/∂x² + ∂²z/∂y²) / 2
            
        Mặt thật: curvature cao ở mũi, quanh mắt, gò má
        Ảnh phẳng: curvature ≈ 0
        
        Args:
            depth_roi: Depth map đã crop
        
        Returns:
            (is_real, mean_curvature)
        """
        if depth_roi is None or depth_roi.size < 100:
            return True, 0.0
        
        depth_f = cv2.GaussianBlur(depth_roi.astype(np.float32), (7, 7), 1.5)
        
        # 2nd derivatives (Laplacian ≈ mean curvature)
        laplacian = cv2.Laplacian(depth_f, cv2.CV_32F, ksize=5)
        
        # Filter valid
        valid = laplacian[np.isfinite(laplacian)]
        if len(valid) < 50:
            return True, 0.0
        
        mean_curvature = float(np.mean(np.abs(valid)))
        is_real = mean_curvature >= self.CURVATURE_MIN
        
        return is_real, mean_curvature
    
    def analyze_flat_ratio(self, depth_roi: np.ndarray) -> Tuple[bool, float]:
        """
        Tính tỷ lệ pixel "phẳng" (gradient ≈ 0).
        
        Ảnh in: hầu hết pixel phẳng → flat_ratio > 0.65
        Mặt thật: nhiều vùng có gradient → flat_ratio < 0.65
        
        Returns:
            (is_real, flat_ratio)
        """
        if depth_roi is None or depth_roi.size < 100:
            return True, 0.0
        
        depth_f = depth_roi.astype(np.float32)
        grad_x = cv2.Sobel(depth_f, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(depth_f, cv2.CV_32F, 0, 1, ksize=3)
        
        grad_magnitude = np.sqrt(grad_x**2 + grad_y**2)
        
        # "Flat" = gradient magnitude < threshold
        flat_threshold = 0.5  # Tuned for normalized depth
        flat_pixels = np.sum(grad_magnitude < flat_threshold)
        total_pixels = grad_magnitude.size
        
        flat_ratio = float(flat_pixels / total_pixels) if total_pixels > 0 else 1.0
        is_real = flat_ratio <= self.FLAT_RATIO_MAX
        
        return is_real, flat_ratio

    # ==========================================================================
    # COMBINED Analysis
    # ==========================================================================
    
    def check_depth_liveness(
        self, 
        depth_map: np.ndarray, 
        face_bbox: list, 
        cam_id: int = 0
    ) -> Tuple[bool, float, Dict]:
        """
        Kiểm tra tổng hợp liveness từ depth map.
        
        Sử dụng ensemble của 5 metrics:
        1. Depth Variance — phương sai chiều sâu
        2. Nose Protrusion — độ nhô mũi
        3. Surface Normals — biến thiên pháp tuyến
        4. Curvature — độ cong bề mặt
        5. Flat Ratio — tỷ lệ pixel phẳng
        
        Kết hợp multi-frame voting để giảm false alarm.
        
        Args:
            depth_map: Full depth map từ camera, shape (H, W) float32
            face_bbox: [x1, y1, x2, y2] bounding box
            cam_id: Camera ID cho multi-frame tracking
            
        Returns:
            (is_real, confidence, details_dict)
        """
        x1, y1, x2, y2 = face_bbox
        h, w = depth_map.shape[:2]
        
        # Clamp bbox
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        
        depth_roi = depth_map[y1:y2, x1:x2]
        
        if depth_roi.size == 0:
            return True, 0.5, {"error": "empty ROI"}
        
        # Run all analyses
        var_real, var_score = self.analyze_depth_variance(depth_roi)
        nose_real, nose_score = self.analyze_nose_protrusion(depth_roi)
        normal_real, normal_score = self.analyze_surface_normals(depth_roi)
        curv_real, curv_score = self.analyze_curvature(depth_roi)
        flat_real, flat_score = self.analyze_flat_ratio(depth_roi)
        
        # Weighted voting
        checks = [
            (var_real, 0.25, "depth_variance"),
            (nose_real, 0.25, "nose_protrusion"),
            (normal_real, 0.20, "surface_normals"),
            (curv_real, 0.15, "curvature"),
            (flat_real, 0.15, "flat_ratio"),
        ]
        
        weighted_score = sum(w for real, w, _ in checks if real)
        frame_is_real = weighted_score >= 0.55  # Need >55% weighted vote
        
        # Multi-frame voting
        history = self._get_history(cam_id)
        history.append(frame_is_real)
        
        if len(history) >= 3:
            fake_votes = sum(1 for r in history if not r)
            final_is_real = fake_votes < self.VOTE_THRESHOLD
        else:
            final_is_real = frame_is_real
        
        details = {
            "depth_variance": {"real": var_real, "score": round(var_score, 4)},
            "nose_protrusion": {"real": nose_real, "score": round(nose_score, 4)},
            "surface_normals": {"real": normal_real, "score": round(normal_score, 4)},
            "curvature": {"real": curv_real, "score": round(curv_score, 4)},
            "flat_ratio": {"real": flat_real, "score": round(flat_score, 4)},
            "weighted_score": round(weighted_score, 3),
            "frame_result": frame_is_real,
            "multi_frame_result": final_is_real,
            "history_length": len(history),
        }
        
        confidence = weighted_score if final_is_real else (1.0 - weighted_score)
        
        return final_is_real, float(confidence), details

    # ==========================================================================
    # PSEUDO DEPTH (RGB-only estimate for current hardware)
    # ==========================================================================
    
    def estimate_pseudo_depth(self, rgb_frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Ước lượng pseudo-depth từ RGB frame bằng face geometry heuristics.
        
        Phương pháp đơn giản (không cần MiDaS):
        - Dùng luminance gradient + face landmark heuristics
        - Giả định: vùng sáng hơn gần camera hơn (ambient lighting)
        - Estimate nose prominence từ brightness profile
        
        Returns:
            Pseudo depth map (float32), hoặc None nếu thất bại
        """
        if rgb_frame is None or rgb_frame.size == 0:
            return None
        
        try:
            # Convert to grayscale
            if len(rgb_frame.shape) == 3:
                gray = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = rgb_frame
            
            # Normalize to float
            gray_f = gray.astype(np.float32) / 255.0
            
            # Simple pseudo-depth: invert brightness (brighter = closer = smaller depth)
            # This is a gross simplification but catches completely flat images
            pseudo_depth = 1.0 - gray_f
            
            # Apply Gaussian to smooth
            pseudo_depth = cv2.GaussianBlur(pseudo_depth, (11, 11), 3.0)
            
            # Scale to reasonable depth range (arbitrary units)
            pseudo_depth = pseudo_depth * 100.0
            
            return pseudo_depth
            
        except Exception as e:
            print(f"[DEPTH] Pseudo depth error: {e}")
            return None
    
    def check_liveness_rgb_only(
        self,
        face_crop: np.ndarray,
        cam_id: int = 0
    ) -> Tuple[bool, float, Dict]:
        """
        Kiểm tra liveness chỉ dùng RGB (pseudo-depth).
        
        Dùng khi chưa có depth camera. Kém chính xác hơn depth thật
        nhưng bổ sung thêm signal cho MiniFASNet.
        
        Returns:
            (is_real, confidence, details)
        """
        pseudo_depth = self.estimate_pseudo_depth(face_crop)
        if pseudo_depth is None:
            return True, 0.5, {"error": "pseudo depth failed"}
        
        h, w = pseudo_depth.shape[:2]
        bbox = [0, 0, w, h]  # Full ROI since already cropped
        
        return self.check_depth_liveness(pseudo_depth, bbox, cam_id)


# ==============================================================================
# Singleton instance
# ==============================================================================
depth_analyzer = DepthLivenessAnalyzer()
