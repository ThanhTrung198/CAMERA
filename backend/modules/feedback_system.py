# ============================================================
# FILE: modules/feedback_system.py
# Feedback Loop — Collect false positives/negatives for retraining
# ============================================================
import json
import os
import cv2
import time
from datetime import datetime


class FeedbackCollector:
    """
    Thu thập feedback từ operator để cải thiện model.
    Lưu: ảnh + label + metadata → dùng cho training set.
    """
    
    def __init__(self, feedback_dir="feedback_data"):
        self.feedback_dir = feedback_dir
        for cat in ["false_positive", "false_negative", "confirmed_real", "confirmed_fake"]:
            os.makedirs(os.path.join(feedback_dir, cat), exist_ok=True)
        self.log_file = os.path.join(feedback_dir, "feedback_log.jsonl")
    
    def submit_feedback(self, image, predicted_label, true_label,
                         confidence, cam_id=0, notes=""):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        if predicted_label == "fake" and true_label == "real":
            category = "false_positive"
        elif predicted_label == "real" and true_label == "fake":
            category = "false_negative"
        elif true_label == "real":
            category = "confirmed_real"
        else:
            category = "confirmed_fake"
        
        img_filename = f"{category}_{timestamp}_cam{cam_id}.jpg"
        img_path = os.path.join(self.feedback_dir, category, img_filename)
        
        if image is not None and image.size > 0:
            cv2.imwrite(img_path, image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        
        entry = {
            "timestamp": timestamp, "category": category,
            "predicted": predicted_label, "true_label": true_label,
            "confidence": confidence, "cam_id": cam_id,
            "image_path": img_path, "notes": notes,
        }
        
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
        
        print(f"[Feedback] ✅ {category}: {img_filename}")
        return entry
    
    def get_stats(self):
        stats = {"false_positive": 0, "false_negative": 0,
                 "confirmed_real": 0, "confirmed_fake": 0}
        for cat in stats:
            cat_dir = os.path.join(self.feedback_dir, cat)
            if os.path.exists(cat_dir):
                stats[cat] = len([f for f in os.listdir(cat_dir) if f.endswith('.jpg')])
        stats["total"] = sum(stats.values())
        stats["ready_for_retrain"] = stats["total"] >= 100
        return stats
