# ============================================================
# FILE: modules/ensemble_antispoof.py
# Ensemble Anti-Spoof: YOLO best.pt + MiniFASNet + ScreenDetector
# ============================================================
import os
import cv2
import numpy as np
import torch
import torch.nn.functional as F

# ── MiniFASNet Setup ──
MINIFAS_AVAILABLE = False
try:
    from silent_fas.model_lib.MiniFASNet import MiniFASNetV2SE
    from silent_fas.utility import parse_model_name
    MINIFAS_AVAILABLE = True
except ImportError:
    print("[Ensemble] MiniFASNet not found — fallback to YOLO-only")


class MiniFASNetPredictor:
    """
    Silent-Face-Anti-Spoofing — chạy trên FACE CROP.
    Lightweight (~600KB), ~98% accuracy trên CelebA-Spoof.
    """
    def __init__(self, model_dir="resources/anti_spoof_models"):
        self.models = []
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        if not os.path.exists(model_dir):
            print(f"[MiniFAS] Model dir not found: {model_dir}")
            return
        
        for model_name in os.listdir(model_dir):
            if not model_name.endswith('.pth'):
                continue
            
            h_input, w_input, model_type, _ = parse_model_name(model_name)
            kernel_size = ((h_input + 15) // 16, (w_input + 15) // 16)
            model = MiniFASNetV2SE(
                conv6_kernel=kernel_size, num_classes=3, img_channel=3
            )
            
            state_dict = torch.load(
                os.path.join(model_dir, model_name),
                map_location=self.device, weights_only=True
            )
            new_state = {}
            for k, v in state_dict.items():
                new_state[k.replace("module.", "")] = v
            model.load_state_dict(new_state)
            model.eval().to(self.device)
            
            self.models.append({
                "model": model, "h_input": h_input,
                "w_input": w_input, "name": model_name
            })
        
        print(f"[MiniFAS] Loaded {len(self.models)} models")
    
    def predict(self, face_crop):
        """
        Input: face_crop (BGR, bất kỳ size)
        Output: (is_real: bool, confidence: float)
        """
        if not self.models or face_crop is None or face_crop.size == 0:
            return True, 0.5
        
        scores = []
        for m_info in self.models:
            h, w = m_info["h_input"], m_info["w_input"]
            model = m_info["model"]
            
            resized = cv2.resize(face_crop, (w, h))
            img = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            img = img.astype(np.float32) / 255.0
            img = np.transpose(img, (2, 0, 1))
            img_tensor = torch.from_numpy(img).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                output = model(img_tensor)
                probs = F.softmax(output, dim=1).cpu().numpy()[0]
            
            # MiniFAS: [fake_1, fake_2, real] → Class 2 = Real
            real_score = probs[2] if len(probs) == 3 else probs[1]
            scores.append(float(real_score))
        
        avg_score = np.mean(scores)
        return avg_score >= 0.5, avg_score


class EnsembleAntiSpoof:
    """
    Kết hợp:
      1) YOLO best.pt (full-frame) — FAKE/REAL bbox detection
      2) MiniFASNet (face-crop) — passive liveness classifier
      3) ScreenDetector (physics-based) — moiré/reflection analysis
    
    Voting: Weighted majority vote
    """
    
    WEIGHT_YOLO = 0.35
    WEIGHT_MINIFAS = 0.40
    WEIGHT_SCREEN = 0.25
    
    def __init__(self, yolo_model=None, screen_detector_module=None):
        self.yolo_model = yolo_model
        self.screen_detector = screen_detector_module
        
        self.minifas = None
        if MINIFAS_AVAILABLE:
            try:
                self.minifas = MiniFASNetPredictor()
            except Exception as e:
                print(f"[Ensemble] MiniFAS init error: {e}")
        
        print(f"[Ensemble] Models: YOLO={'✅' if yolo_model else '❌'} "
              f"MiniFAS={'✅' if self.minifas and self.minifas.models else '❌'} "
              f"Screen={'✅' if screen_detector_module else '❌'}")
    
    def check(self, frame, face_bbox, face_crop, cam_id=0,
              yolo_spoof_detections=None):
        """
        Ensemble anti-spoof check.
        
        Returns:
            dict: {
                "is_real": bool,
                "confidence": float (0-1, real probability),
                "fake_votes": int,
                "total_votes": int,
                "methods": list[str],
                "details": dict,
            }
        """
        results = {}
        weighted_scores = []
        methods_used = []
        
        # ── 1. YOLO best.pt (từ full-frame spoof detections) ──
        yolo_is_real = True
        yolo_conf = 0.5
        
        if yolo_spoof_detections:
            try:
                from utils.image_utils import calculate_iou
            except ImportError:
                from modules.ensemble_antispoof import _simple_iou as calculate_iou
            
            matching_fakes = []
            matching_reals = []
            for det in yolo_spoof_detections:
                iou = calculate_iou(face_bbox, det["bbox"])
                if iou >= 0.15:
                    if det["is_fake"]:
                        matching_fakes.append(det)
                    else:
                        matching_reals.append(det)
            
            if matching_fakes and matching_reals:
                best_real = max(matching_reals, key=lambda x: x["conf"])
                yolo_is_real = True
                yolo_conf = best_real["conf"]
            elif matching_fakes:
                best_fake = max(matching_fakes, key=lambda x: x["conf"])
                yolo_is_real = False
                yolo_conf = best_fake["conf"]
            elif matching_reals:
                best_real = max(matching_reals, key=lambda x: x["conf"])
                yolo_is_real = True
                yolo_conf = best_real["conf"]
            
            yolo_score = yolo_conf if yolo_is_real else (1.0 - yolo_conf)
            weighted_scores.append(yolo_score * self.WEIGHT_YOLO)
            methods_used.append("YOLO")
            results["yolo"] = {"is_real": yolo_is_real, "conf": yolo_conf}
        
        # ── 2. MiniFASNet (face crop) ──
        if self.minifas and self.minifas.models and face_crop is not None:
            try:
                minifas_real, minifas_score = self.minifas.predict(face_crop)
                weighted_scores.append(minifas_score * self.WEIGHT_MINIFAS)
                methods_used.append("MiniFAS")
                results["minifas"] = {"is_real": minifas_real, "score": minifas_score}
            except Exception as e:
                print(f"[Ensemble] MiniFAS error: {e}")
        
        # ── 3. ScreenDetector (physics) ──
        if self.screen_detector and face_crop is not None:
            try:
                sd_is_screen, sd_conf, sd_details = (
                    self.screen_detector.check_screen(face_crop, cam_id=cam_id)
                )
                sd_real_score = (1.0 - sd_conf) if sd_is_screen else sd_conf
                weighted_scores.append(sd_real_score * self.WEIGHT_SCREEN)
                methods_used.append("Screen")
                results["screen"] = {"is_screen": sd_is_screen, "conf": sd_conf}
            except Exception as e:
                print(f"[Ensemble] Screen error: {e}")
        
        # ── FUSION ──
        if weighted_scores:
            total_weight = sum([
                self.WEIGHT_YOLO if "YOLO" in methods_used else 0,
                self.WEIGHT_MINIFAS if "MiniFAS" in methods_used else 0,
                self.WEIGHT_SCREEN if "Screen" in methods_used else 0,
            ])
            ensemble_score = sum(weighted_scores) / total_weight if total_weight > 0 else 0.5
        else:
            ensemble_score = 0.5
        
        # Majority vote
        fake_votes = 0
        total_votes = 0
        
        if "YOLO" in methods_used:
            total_votes += 1
            if not results["yolo"]["is_real"]:
                fake_votes += 1
        if "MiniFAS" in methods_used:
            total_votes += 1
            if not results["minifas"]["is_real"]:
                fake_votes += 1
        if "Screen" in methods_used:
            total_votes += 1
            if results["screen"]["is_screen"]:
                fake_votes += 1
        
        is_real = True
        if total_votes >= 2 and fake_votes >= 2:
            is_real = False
        elif total_votes >= 1 and fake_votes == total_votes:
            is_real = False
        elif ensemble_score < 0.40:
            is_real = False
        
        return {
            "is_real": is_real,
            "confidence": round(ensemble_score, 3),
            "fake_votes": fake_votes,
            "total_votes": total_votes,
            "methods": methods_used,
            "details": results,
        }


def _simple_iou(boxA, boxB):
    """Fallback IoU if image_utils not available"""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    areaA = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    areaB = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    union = areaA + areaB - inter
    return inter / union if union > 0 else 0
