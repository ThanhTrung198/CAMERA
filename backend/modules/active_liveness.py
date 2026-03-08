# ============================================================
# FILE: modules/active_liveness.py
# Active Liveness: Eye Blink (EAR) + Head Pose + Micro-expression
# ============================================================
import cv2
import numpy as np
import time
from collections import deque


class ActiveLivenessDetector:
    """
    Phát hiện sống qua:
    1. Eye Blink Detection (EAR — Eye Aspect Ratio)
    2. Head Pose Estimation (Yaw/Pitch changes)
    3. Micro-movement (bbox center shift)
    
    Chế độ PASSIVE: Không yêu cầu user action,
    nhưng giám sát blink/movement tự nhiên.
    Ảnh tĩnh (print/replay) sẽ KHÔNG có blink → FAKE.
    """
    
    EAR_THRESHOLD = 0.22
    CONSEC_FRAMES_BLINK = 2
    ANALYSIS_WINDOW = 5.0
    MIN_BLINKS_IN_WINDOW = 1
    HEAD_MOVEMENT_THRESHOLD = 3.0
    
    def __init__(self):
        self.face_histories = {}
    
    def _eye_aspect_ratio(self, eye_landmarks):
        """EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)"""
        if len(eye_landmarks) < 6:
            return 0.3
        p1, p2, p3, p4, p5, p6 = eye_landmarks[:6]
        A = np.linalg.norm(np.array(p2) - np.array(p6))
        B = np.linalg.norm(np.array(p3) - np.array(p5))
        C = np.linalg.norm(np.array(p1) - np.array(p4))
        return (A + B) / (2.0 * C) if C > 0 else 0.3
    
    def _extract_eye_landmarks(self, face):
        """Trích xuất eye landmarks từ InsightFace face object."""
        if hasattr(face, 'landmark_2d_106') and face.landmark_2d_106 is not None:
            lm = face.landmark_2d_106
            left_eye = lm[33:42].tolist() if len(lm) > 42 else []
            right_eye = lm[87:96].tolist() if len(lm) > 96 else []
            return left_eye, right_eye
        return None, None
    
    def _estimate_head_pose(self, face):
        """Ước lượng head pose từ InsightFace face object."""
        if hasattr(face, 'pose') and face.pose is not None:
            return face.pose
        
        if hasattr(face, 'kps') and face.kps is not None:
            kps = face.kps
            left_eye, right_eye, nose = kps[0], kps[1], kps[2]
            eye_center = (left_eye + right_eye) / 2.0
            dx = nose[0] - eye_center[0]
            dy = nose[1] - eye_center[1]
            eye_dist = np.linalg.norm(left_eye - right_eye)
            if eye_dist > 0:
                yaw = dx / eye_dist * 45.0
                pitch = dy / eye_dist * 30.0
            else:
                yaw, pitch = 0, 0
            return np.array([pitch, yaw, 0])
        return None
    
    def update(self, track_id, face, timestamp=None):
        """
        Cập nhật liveness state cho 1 face.
        
        Returns:
            dict: {
                "has_blinked": bool,
                "blink_count": int,
                "has_movement": bool,
                "liveness_score": float (0-1),
                "is_likely_live": bool,
                "analysis_ready": bool,
            }
        """
        if timestamp is None:
            timestamp = time.time()
        
        if track_id not in self.face_histories:
            self.face_histories[track_id] = {
                "ear_history": deque(maxlen=150),
                "pose_history": deque(maxlen=150),
                "blink_count": 0,
                "consec_below": 0,
                "first_seen": timestamp,
                "bbox_history": deque(maxlen=60),
            }
        
        hist = self.face_histories[track_id]
        
        # ── Eye Blink Detection ──
        left_eye, right_eye = self._extract_eye_landmarks(face)
        current_ear = None
        
        if left_eye and right_eye and len(left_eye) >= 6:
            left_ear = self._eye_aspect_ratio(left_eye)
            right_ear = self._eye_aspect_ratio(right_eye)
            current_ear = (left_ear + right_ear) / 2.0
            hist["ear_history"].append((timestamp, current_ear))
            
            if current_ear < self.EAR_THRESHOLD:
                hist["consec_below"] += 1
            else:
                if hist["consec_below"] >= self.CONSEC_FRAMES_BLINK:
                    hist["blink_count"] += 1
                hist["consec_below"] = 0
        
        # ── Head Pose Tracking ──
        pose = self._estimate_head_pose(face)
        has_movement = False
        
        if pose is not None:
            hist["pose_history"].append((timestamp, pose.copy()))
            if len(hist["pose_history"]) >= 10:
                recent_poses = [p[1] for p in list(hist["pose_history"])[-30:]]
                pose_array = np.array(recent_poses)
                yaw_range = np.ptp(pose_array[:, 1])
                pitch_range = np.ptp(pose_array[:, 0])
                if yaw_range > self.HEAD_MOVEMENT_THRESHOLD or \
                   pitch_range > self.HEAD_MOVEMENT_THRESHOLD:
                    has_movement = True
        
        # ── Bbox micro-movement ──
        if hasattr(face, 'bbox'):
            bbox_center = [
                (face.bbox[0] + face.bbox[2]) / 2,
                (face.bbox[1] + face.bbox[3]) / 2
            ]
            hist["bbox_history"].append((timestamp, bbox_center))
            if len(hist["bbox_history"]) >= 10 and not has_movement:
                centers = np.array([c[1] for c in list(hist["bbox_history"])[-20:]])
                if np.max(np.std(centers, axis=0)) > 1.5:
                    has_movement = True
        
        # ── Tổng hợp ──
        elapsed = timestamp - hist["first_seen"]
        analysis_ready = elapsed >= self.ANALYSIS_WINDOW
        liveness_score = 0.5
        
        if analysis_ready:
            blink_score = min(1.0, hist["blink_count"] / max(1, self.MIN_BLINKS_IN_WINDOW))
            movement_score = 1.0 if has_movement else 0.0
            
            variance_score = 0.5
            if hist["ear_history"]:
                ears = [e[1] for e in hist["ear_history"]]
                if len(ears) > 5:
                    variance_score = min(1.0, np.var(ears) / 0.001)
            
            liveness_score = (
                blink_score * 0.45 +
                movement_score * 0.30 +
                variance_score * 0.25
            )
        
        return {
            "has_blinked": hist["blink_count"] > 0,
            "blink_count": hist["blink_count"],
            "has_movement": has_movement,
            "liveness_score": round(liveness_score, 3),
            "is_likely_live": liveness_score >= 0.35 or not analysis_ready,
            "analysis_ready": analysis_ready,
            "elapsed": round(elapsed, 1),
            "ear": round(current_ear, 3) if current_ear else None,
        }
    
    def cleanup(self, max_age=10.0):
        now = time.time()
        expired = [k for k, v in self.face_histories.items()
                   if now - v.get("first_seen", 0) > max_age and
                   len(v["ear_history"]) > 0 and
                   now - v["ear_history"][-1][0] > 3.0]
        for k in expired:
            del self.face_histories[k]
