# ============================================================
# FILE: tests/test_antispoof.py
# ISO 30107 Anti-Spoof Benchmark Framework
# ============================================================
"""
Đo APCER, BPCER, ACER cho anti-spoof system.
ISO 30107:
  APCER = Attack Presentation Classification Error Rate (Fake→Real)
  BPCER = Bona Fide Presentation Classification Error Rate (Real→Fake)
  ACER  = (APCER + BPCER) / 2
"""
import os
import cv2
import numpy as np
import json
from pathlib import Path


class AntiSpoofBenchmark:
    
    def __init__(self, ensemble_checker, test_data_dir="test_datasets"):
        self.checker = ensemble_checker
        self.test_dir = test_data_dir
        self.results = []
    
    def run_benchmark(self, dataset_name="custom"):
        """
        Dataset structure:
        test_datasets/<name>/
        ├── real/  (*.jpg)
        └── fake/  (*.jpg, subdirs: print/, replay/, mask3d/)
        """
        real_dir = os.path.join(self.test_dir, dataset_name, "real")
        fake_dir = os.path.join(self.test_dir, dataset_name, "fake")
        
        real_correct, real_total = 0, 0
        fake_correct, fake_total = 0, 0
        
        # Test REAL
        if os.path.exists(real_dir):
            for img_file in Path(real_dir).glob("*.jpg"):
                img = cv2.imread(str(img_file))
                if img is None:
                    continue
                result = self.checker.check(
                    frame=img,
                    face_bbox=[0, 0, img.shape[1], img.shape[0]],
                    face_crop=img, cam_id=0
                )
                real_total += 1
                if result["is_real"]:
                    real_correct += 1
                self.results.append({
                    "file": str(img_file), "true": "real",
                    "predicted": "real" if result["is_real"] else "fake",
                    "confidence": result["confidence"],
                })
        
        # Test FAKE
        if os.path.exists(fake_dir):
            for img_file in Path(fake_dir).rglob("*.jpg"):
                img = cv2.imread(str(img_file))
                if img is None:
                    continue
                result = self.checker.check(
                    frame=img,
                    face_bbox=[0, 0, img.shape[1], img.shape[0]],
                    face_crop=img, cam_id=0
                )
                fake_total += 1
                if not result["is_real"]:
                    fake_correct += 1
                self.results.append({
                    "file": str(img_file), "true": "fake",
                    "predicted": "real" if result["is_real"] else "fake",
                    "confidence": result["confidence"],
                })
        
        # Metrics
        BPCER = 1.0 - (real_correct / max(real_total, 1))
        APCER = 1.0 - (fake_correct / max(fake_total, 1))
        ACER = (APCER + BPCER) / 2.0
        
        report = {
            "dataset": dataset_name,
            "real_total": real_total, "real_correct": real_correct,
            "fake_total": fake_total, "fake_correct": fake_correct,
            "BPCER": round(BPCER * 100, 2),
            "APCER": round(APCER * 100, 2),
            "ACER": round(ACER * 100, 2),
            "accuracy": round(
                (real_correct + fake_correct) / max(real_total + fake_total, 1) * 100, 2
            ),
        }
        
        print(f"\n{'='*50}")
        print(f"BENCHMARK: {dataset_name}")
        print(f"  Real: {real_correct}/{real_total}")
        print(f"  Fake: {fake_correct}/{fake_total}")
        print(f"  APCER (FAR): {report['APCER']}%")
        print(f"  BPCER (FRR): {report['BPCER']}%")
        print(f"  ACER: {report['ACER']}%")
        print(f"  Accuracy: {report['accuracy']}%")
        print(f"{'='*50}\n")
        
        return report
    
    def save_results(self, filepath="benchmark_results.json"):
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"[Benchmark] Results saved to {filepath}")
