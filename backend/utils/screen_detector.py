# -*- coding: utf-8 -*-
"""
Screen Detection Module - Phát hiện giả mạo qua màn hình điện thoại/tablet
===========================================================================

Phát hiện replay attack từ các loại màn hình (LCD, OLED, AMOLED).

Nguyên lý vật lý:
- Màn hình phát ánh sáng đều (emit) — da người phản chiếu ánh sáng (reflect)
- Màn hình có color gamut khác biệt (sRGB/P3 vs Munsell skin tones)
- Màn hình không có micro-texture của da (lỗ chân lông, nếp nhăn vi mô)
- Màn hình hiển thị qua camera: thêm beat frequency patterns giữa 2 grids
- Màn hình có màu blue channel cao hơn do LED backlight

4 detector chính:
1. Color Gamut Analysis (màu screen vs da)
2. LBP Texture (micro-texture da vs màn hình)
3. Frequency Domain (moiré artifacts)
4. Specular Reflection (glass screen vs matte skin)
"""

import cv2
import numpy as np
from collections import deque
from typing import Tuple, Dict


class ScreenDetector:
    """Phát hiện face crop đến từ màn hình điện thoại/tablet"""
    
    def __init__(self):
        # Per-camera frame history cho temporal voting
        self._history: Dict[int, deque] = {
            0: deque(maxlen=8),
            1: deque(maxlen=8),
        }
    
    # ------------------------------------------------------------------
    # Detector 1: Color Gamut Analysis
    # ------------------------------------------------------------------
    def _color_gamut_analysis(self, bgr: np.ndarray) -> Tuple[bool, float]:
        """
        Màu da người tuân theo Munsell skin tone gamut:
        - Hue: ~10-50° trong Hue-Saturation (H in HSV roughly 0-30)
        - Da: R > G > B thường xuyên
        
        Màn hình có thể show bất cứ màu nào nhưng thường:
        - Cool tone (blue/white balance)
        - Wider gamut, bão hòa màu hơn
        
        Score cao → khả năng screen cao hơn
        """
        if bgr is None or bgr.size == 0:
            return False, 0.0
        try:
            b = bgr[:, :, 0].astype(np.float32)
            g = bgr[:, :, 1].astype(np.float32)
            r = bgr[:, :, 2].astype(np.float32)
            
            total = r + g + b + 1e-6
            r_ratio = r / total
            g_ratio = g / total
            b_ratio = b / total
            
            # Skin: r_ratio > 0.33, b_ratio < 0.30
            # Screen (cool): b_ratio tends higher
            mean_r = float(np.mean(r_ratio))
            mean_b = float(np.mean(b_ratio))
            
            # Skin-tone pixel ratio
            is_skin_pixel = (r > g) & (g > b) & (r > 80) & (b < 200)
            skin_ratio = float(np.mean(is_skin_pixel))
            
            # Screen signature: low skin ratio + high blue
            screen_score = (1.0 - skin_ratio) * 0.5 + (mean_b - 0.28) * 2.0
            screen_score = float(np.clip(screen_score, 0, 1))
            
            is_screen = screen_score > 0.45
            return is_screen, screen_score
        except Exception:
            return False, 0.0
    
    # ------------------------------------------------------------------
    # Detector 2: LBP Texture Analysis
    # ------------------------------------------------------------------
    def _lbp_texture_analysis(self, bgr: np.ndarray) -> Tuple[bool, float]:
        """
        Local Binary Pattern (LBP) texture analysis.
        
        Da người có:
        - High local variance (lỗ chân lông, sắc)
        - LBP histogram phân bố rộng (nhiều pattern)
        
        Màn hình có:
        - Pixel grid regularPattern (ít variety)  
        - LBP histogram tập trung (ít pattern types)
        
        Dùng: variance of LBP histogram entropy
        """
        if bgr is None or bgr.size == 0:
            return False, 0.5
        try:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (64, 64))
            
            # Compute simplified LBP
            center = gray[1:-1, 1:-1]
            lbp = np.zeros_like(center, dtype=np.uint8)
            
            neighbors = [
                gray[:-2, :-2], gray[:-2, 1:-1], gray[:-2, 2:],
                gray[1:-1, 2:], gray[2:, 2:], gray[2:, 1:-1],
                gray[2:, :-2], gray[1:-1, :-2],
            ]
            for i, nb in enumerate(neighbors):
                lbp += ((nb >= center).astype(np.uint8) << i)
            
            # LBP histogram
            hist, _ = np.histogram(lbp.ravel(), bins=32, range=(0, 256))
            hist = hist.astype(np.float32)
            hist /= (hist.sum() + 1e-6)
            
            # Shannon entropy of histogram
            entropy = -np.sum(hist * np.log2(hist + 1e-10))
            max_entropy = np.log2(32)
            norm_entropy = float(entropy / max_entropy)
            
            # High entropy = diverse texture = more likely real skin
            # Low entropy = uniform/regular texture = more likely screen
            screen_score = 1.0 - norm_entropy
            is_screen = screen_score > 0.35
            
            return is_screen, float(screen_score)
        except Exception:
            return False, 0.5
    
    # ------------------------------------------------------------------
    # Detector 3: Frequency Domain (Moiré)
    # ------------------------------------------------------------------
    def _frequency_analysis(self, bgr: np.ndarray) -> Tuple[bool, float]:
        """
        FFT Moiré Analysis – JPEG-artifact immune.
        
        Camera + Screen pixel grids → beat frequency = periodic moiré pattern.
        
        JPEG 8×8 DCT also creates periodic peaks → must NOT confuse.
        
        Distinguishing features of SCREEN moiré vs JPEG artifacts:
        1. Screen moiré peaks are SYMMETRIC (appear as opposed pairs ±freq)
        2. Screen moiré creates coherence across R, G, B channels simultaneously
        3. Screen pixel grid creates HIGH-freq peaks (PPI 400+ → fine grid)
        4. JPEG artifacts are at a fixed spatial freq (1/8 of image = coarse)
        
        Method:
        - Analyse cross-channel peak correlation (R∩G∩B)
        - JPEG peaks appear in only 1-2 channels; screen in all 3
        - Require symmetric peak pairs
        """
        if bgr is None or bgr.size == 0:
            return False, 0.0
        try:
            h_orig, w_orig = bgr.shape[:2]
            # Use native resolution (avoid resize that creates aliasing artifacts)
            size = 128
            img = cv2.resize(bgr, (size, size))
            
            channel_peaks = []
            
            for ch in range(3):  # B, G, R
                plane = img[:, :, ch].astype(np.float32)
                
                # Remove mean (suppress DC)
                plane -= plane.mean()
                
                # 2D FFT + shift
                fft_shift = np.fft.fftshift(np.fft.fft2(plane))
                mag = np.abs(fft_shift)
                
                cy, cx = size // 2, size // 2
                Y, X = np.ogrid[:size, :size]
                dist = np.sqrt((Y - cy) ** 2 + (X - cx) ** 2)
                
                # Focus on HIGH-frequency band (fine screen pixel grid)
                # JPEG artifacts are in lower freq (size/8 = 16px → dist~8-20)
                # Screen fine grid can be 30-60 px from center
                hi_band = mag.copy()
                hi_band[dist < size * 0.20] = 0   # Remove low/JPEG freq
                hi_band[dist >= size * 0.48] = 0  # Remove noise
                
                if hi_band.max() == 0:
                    channel_peaks.append(0.0)
                    continue
                
                # Robust peak detection above 99th percentile
                p99 = np.percentile(hi_band[hi_band > 0], 99)
                p50 = np.percentile(hi_band[hi_band > 0], 50)
                
                # Peak sharpness: ratio of top-1% energy vs median
                sharpness = float(p99 / (p50 + 1e-6))
                
                # Count symmetric peak pairs (screen-specific)
                peak_mask = hi_band > p99
                peak_yx = np.column_stack(np.where(peak_mask))
                
                sym_pairs = 0
                for py, px in peak_yx:
                    # Mirror point across center
                    my, mx = 2*cy - py, 2*cx - px
                    if 0 <= my < size and 0 <= mx < size:
                        if peak_mask[my, mx]:
                            sym_pairs += 1
                
                # Normalize: score based on sharpness + symmetric pairs
                pair_score = min(sym_pairs / 6.0, 1.0)  # Expect 2-6 pairs for screen
                score = float(np.clip((sharpness - 3.0) / 20.0 * 0.5 + pair_score * 0.5, 0, 1))
                channel_peaks.append(score)
            
            # Cross-channel coherence: screen creates peaks in ALL 3 channels
            # JPEG artifacts are channel-specific (YCbCr → less coherent in RGB)
            ch_min = min(channel_peaks)
            ch_max = max(channel_peaks)
            ch_mean = float(np.mean(channel_peaks))
            
            # Require coherence across channels (all 3 elevated, not just 1-2)
            coherence = ch_min / (ch_max + 1e-6)  # 1.0 = perfectly coherent
            
            # Final score: mean across channels weighted by coherence
            moire_score = ch_mean * (0.5 + 0.5 * coherence)
            moire_score = float(np.clip(moire_score, 0, 1))
            
            is_screen = moire_score > 0.45
            return is_screen, moire_score
        except Exception:
            return False, 0.0

    
    # ------------------------------------------------------------------
    # Detector 4: Specular Reflection
    # ------------------------------------------------------------------
    def _specular_reflection(self, bgr: np.ndarray) -> Tuple[bool, float]:
        """
        Glass screens có specular (specular=mirror-like) reflection.
        Da người có diffuse reflection.
        
        Method: tìm overexposed hotspot pixels bất đối xứng.
        """
        if bgr is None or bgr.size == 0:
            return False, 0.0
        try:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            h, w = gray.shape
            
            # Overexposed pixels
            oex = (gray > 235).astype(np.float32)
            bright_ratio = float(np.mean(oex))
            
            # Check if bright spots are clustered (specular) vs diffuse
            if bright_ratio > 0.005:
                kernel = np.ones((5, 5), np.float32) / 25
                smoothed = cv2.filter2D(oex, -1, kernel)
                cluster_strength = float(np.max(smoothed))
                score = bright_ratio * 2.0 + cluster_strength * 0.5
            else:
                score = 0.0
            
            score = float(np.clip(score, 0, 1))
            is_screen = score > 0.20
            return is_screen, score
        except Exception:
            return False, 0.0
    
    # ------------------------------------------------------------------
    # Main check
    # ------------------------------------------------------------------
    def check_screen(self, face_crop: np.ndarray, cam_id: int = 0) -> Tuple[bool, float, Dict]:
        """
        Kiểm tra tổng hợp: face crop từ màn hình không?
        
        Args:
            face_crop: BGR face crop
            cam_id: Camera ID (cho temporal voting)
            
        Returns:
            (is_screen, confidence, details)
        """
        if face_crop is None or face_crop.size == 0:
            return False, 0.0, {}
        
        # Run 4 detectors
        c1, s1 = self._color_gamut_analysis(face_crop)
        c2, s2 = self._lbp_texture_analysis(face_crop)
        c3, s3 = self._frequency_analysis(face_crop)
        c4, s4 = self._specular_reflection(face_crop)
        
        # Weighted ensemble
        # After JPEG-immune FFT redesign (2026-02-20):
        # - FFT (moiré) now JPEG-immune → reliable signal, weight 0.40
        # - Color gamut: 0.25 (warm face shown on phone → less effective)
        # - LBP texture: 0.25 (face on phone has real texture → moderate)
        # - Specular: 0.10
        weighted = (
            s1 * 0.25 +   # Color gamut
            s2 * 0.25 +   # LBP texture
            s3 * 0.40 +   # FFT moiré (JPEG-immune)
            s4 * 0.10     # Specular reflection
        )
        weighted = float(np.clip(weighted, 0, 1))
        
        # Temporal smoothing — accumulate over frames
        history = self._history.get(cam_id, deque(maxlen=10))
        history.append(weighted)
        self._history[cam_id] = history
        
        # Rolling average (need sustained elevation, not single-frame spike)
        temporal_score = float(np.mean(history))
        
        # is_screen requires TEMPORAL evidence (not single-frame)
        # Threshold 0.35 requires multiple consecutive frames of screen signal
        is_screen = temporal_score >= 0.35
        
        details = {
            "color_gamut": {"detected": c1, "score": round(s1, 4)},
            "lbp_texture":  {"detected": c2, "score": round(s2, 4)},
            "moire_fft":    {"detected": c3, "score": round(s3, 4)},
            "specular":     {"detected": c4, "score": round(s4, 4)},
            "frame_score":  round(weighted, 4),
            "temporal_score": round(temporal_score, 4),
            "is_screen": is_screen,
        }
        
        return is_screen, temporal_score, details
    
    def reset(self, cam_id: int = 0):
        """Reset temporal history for a camera"""
        self._history[cam_id] = deque(maxlen=8)


# Singleton
screen_detector = ScreenDetector()
