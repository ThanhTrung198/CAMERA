# -*- coding: utf-8 -*-
"""
TRACKING MODULE - Tích hợp từ tracking4/yolov9
Các classes cho person tracking, zone intrusion, video recording và Telegram alerts
"""

import warnings
warnings.filterwarnings('ignore')

import os
import sys
import threading
import queue
import time
from pathlib import Path
from collections import deque, defaultdict
from datetime import datetime
import cv2
import numpy as np
import requests
import io
from scipy.spatial.distance import cosine


# ========== TELEGRAM NOTIFIER ==========
class TelegramNotifier:
    """Gửi thông báo qua Telegram"""
    
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.enabled = self._validate_config()
        self.last_alert_time = {}
        self.alert_cooldown = 30
        self.message_queue = queue.Queue()
        self.send_thread = None
        self.running = False
        
        if self.enabled:
            self._start_send_thread()
            print(f"[TELEGRAM] Bot initialized successfully")
        else:
            print(f"[TELEGRAM] Bot disabled - Please configure BOT_TOKEN and CHAT_ID")
    
    def _validate_config(self):
        if "YOUR_BOT_TOKEN_HERE" in self.bot_token or "YOUR_CHAT_ID_HERE" in self.chat_id:
            return False
        if not self.bot_token or not self.chat_id:
            return False
        return True
    
    def _start_send_thread(self):
        self.running = True
        self.send_thread = threading.Thread(target=self._send_worker, daemon=True)
        self.send_thread.start()
    
    def _send_worker(self):
        while self.running:
            try:
                item = self.message_queue.get(timeout=1.0)
                if item is None:
                    continue
                
                msg_type, data = item
                
                if msg_type == "text":
                    self._send_text_sync(data)
                elif msg_type == "photo":
                    text, image = data
                    self._send_photo_sync(text, image)
                elif msg_type == "video":
                    text, video_path = data
                    self._send_video_sync(text, video_path)
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[TELEGRAM] Send error: {e}")
    
    def send_message(self, text):
        if not self.enabled:
            return False
        self.message_queue.put(("text", text))
        return True
    
    def send_intrusion_alert(self, person_id, frame, bbox=None):
        if not self.enabled:
            return False
        
        current_time = time.time()
        if person_id in self.last_alert_time:
            elapsed = current_time - self.last_alert_time[person_id]
            if elapsed < self.alert_cooldown:
                return False
        
        self.last_alert_time[person_id] = current_time
        
        message = (
            "CẢNH BÁO XÂM NHẬP!\n\n"
            f"Person ID: P{person_id}\n"
            f"Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Vị trí: Vùng cấm\n"
            f"Đang ghi video...\n\n"
            "Có người lạ đã xâm nhập vùng cấm!"
        )
        
        if bbox is not None and frame is not None:
            frame_copy = frame.copy()
            x1, y1, x2, y2 = map(int, bbox)
            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), (0, 0, 255), 3)
            cv2.putText(frame_copy, f"INTRUDER P{person_id}", 
                       (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.9, (0, 0, 255), 2)
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cv2.putText(frame_copy, timestamp, 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.7, (255, 255, 255), 2)
            
            self.message_queue.put(("photo", (message, frame_copy)))
        else:
            self.message_queue.put(("text", message))
        
        print(f"[TELEGRAM] Queued alert for Person {person_id}")
        return True
    
    def send_stranger_alert(self, stranger_name, frame, face_bbox=None, cam_id=0):
        """Gửi cảnh báo Telegram khi phát hiện người lạ (cooldown 60s/stranger)"""
        if not self.enabled:
            return False
        
        cooldown_key = f"stranger_{stranger_name}"
        current_time = time.time()
        if cooldown_key in self.last_alert_time:
            if current_time - self.last_alert_time[cooldown_key] < 60:
                return False
        self.last_alert_time[cooldown_key] = current_time
        
        message = (
            "⚠️ PHÁT HIỆN NGƯỜI LẠ!\n\n"
            f"👤 ID: {stranger_name}\n"
            f"📷 Camera: CAM {cam_id + 1}\n"
            f"⏰ Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "Người không có trong cơ sở dữ liệu đã xuất hiện!"
        )
        
        if frame is not None and face_bbox is not None:
            frame_copy = frame.copy()
            x1, y1, x2, y2 = map(int, face_bbox)
            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), (0, 165, 255), 3)
            cv2.putText(frame_copy, f"STRANGER: {stranger_name}",
                       (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX,
                       0.8, (0, 165, 255), 2)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cv2.putText(frame_copy, timestamp,
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                       0.7, (255, 255, 255), 2)
            self.message_queue.put(("photo", (message, frame_copy)))
        else:
            self.message_queue.put(("text", message))
        
        print(f"[TELEGRAM] 📤 Queued stranger alert: {stranger_name} on CAM {cam_id}")
        return True
    
    def send_spoof_alert(self, frame, face_bbox=None, confidence=0.0, cam_id=0):
        """Gửi cảnh báo Telegram khi phát hiện giả mạo (cooldown 30s/camera)"""
        if not self.enabled:
            return False
        
        cooldown_key = "spoof_global"  # Đồng bộ: alert 1 lần cho cả 2 cam
        current_time = time.time()
        if cooldown_key in self.last_alert_time:
            if current_time - self.last_alert_time[cooldown_key] < 30:
                return False
        self.last_alert_time[cooldown_key] = current_time
        
        message = (
            "🚨 CẢNH BÁO GIẢ MẠO!\n\n"
            f"📷 Camera: CAM {cam_id + 1}\n"
            f"🎯 Độ tin cậy: {confidence:.0%}\n"
            f"⏰ Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "Phát hiện hành vi giả mạo khuôn mặt (ảnh/video/điện thoại)!"
        )
        
        if frame is not None and face_bbox is not None:
            frame_copy = frame.copy()
            x1, y1, x2, y2 = map(int, face_bbox)
            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), (0, 0, 255), 3)
            cv2.putText(frame_copy, f"GIA MAO ({confidence:.0%})",
                       (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX,
                       0.8, (0, 0, 255), 2)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cv2.putText(frame_copy, timestamp,
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                       0.7, (255, 255, 255), 2)
            self.message_queue.put(("photo", (message, frame_copy)))
        else:
            self.message_queue.put(("text", message))
        
        print(f"[TELEGRAM] 📤 Queued spoof alert: conf={confidence:.0%} on CAM {cam_id}")
        return True
    
    def send_video(self, video_path, caption=""):
        if not self.enabled:
            return False
        self.message_queue.put(("video", (caption, video_path)))
        return True
    
    def _send_text_sync(self, text):
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": text}
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                print(f"[TELEGRAM] Message sent successfully")
                return True
            else:
                print(f"[TELEGRAM] Failed to send: {response.text}")
                return False
                
        except Exception as e:
            print(f"[TELEGRAM] Error sending message: {e}")
            return False
    
    def _send_photo_sync(self, caption, image):
        try:
            url = f"{self.base_url}/sendPhoto"
            _, img_encoded = cv2.imencode('.jpg', image)
            img_bytes = io.BytesIO(img_encoded.tobytes())
            img_bytes.name = 'intrusion.jpg'
            
            payload = {"chat_id": self.chat_id, "caption": caption}
            files = {"photo": img_bytes}
            
            response = requests.post(url, data=payload, files=files, timeout=30)
            
            if response.status_code == 200:
                print(f"[TELEGRAM] Photo sent successfully")
                return True
            else:
                print(f"[TELEGRAM] Failed to send photo: {response.text}")
                return False
                
        except Exception as e:
            print(f"[TELEGRAM] Error sending photo: {e}")
            return False
    
    def _send_video_sync(self, caption, video_path):
        try:
            url = f"{self.base_url}/sendVideo"
            
            if not os.path.exists(video_path):
                print(f"[TELEGRAM] Video file not found: {video_path}")
                return False
            
            file_size = os.path.getsize(video_path)
            if file_size > 50 * 1024 * 1024:
                print(f"[TELEGRAM] Video too large ({file_size/1024/1024:.1f}MB)")
                return False
            
            with open(video_path, 'rb') as video_file:
                payload = {"chat_id": self.chat_id, "caption": caption}
                files = {"video": video_file}
                response = requests.post(url, data=payload, files=files, timeout=120)
            
            if response.status_code == 200:
                print(f"[TELEGRAM] Video sent successfully: {video_path}")
                return True
            else:
                print(f"[TELEGRAM] Failed to send video: {response.text}")
                return False
                
        except Exception as e:
            print(f"[TELEGRAM] Error sending video: {e}")
            return False
    
    def stop(self):
        self.running = False
        if self.send_thread:
            self.send_thread.join(timeout=2.0)


# ========== SMART VIDEO RECORDER ==========
class SmartVideoRecorder:
    """
    Quay video thông minh - MỖI CAMERA CÓ VIDEO RIÊNG:
    - Mỗi camera có video riêng biệt (cam0_xxx.mp4, cam1_xxx.mp4)
    - 1 người: Quay từ lúc phát hiện đến khi biến mất
    - Nhiều người: Quay từ người đầu tiên đến khi người cuối cùng biến mất
    """
    
    def __init__(self, output_dir="intrusion_recordings", telegram=None, db_manager=None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.telegram = telegram
        self.db_manager = db_manager
        
        # Per-camera recording states
        self.camera_states = {}
        
        # Statistics
        self.total_recordings = 0
        self.total_intruders_recorded = 0
        
        # Settings
        self.fps = 20.0
        self.min_recording_duration = 3.0
        self.max_recording_duration = 300.0
        self.seconds_after_last_intruder = 10  # 10 giây sau khi người cuối cùng rời zone
        
        print(f"[RECORDER] Multi-Camera Video Recorder initialized")
        print(f"[RECORDER] Output directory: {self.output_dir}")
    
    def _get_camera_state(self, cam_id=0):
        """Lấy hoặc tạo state cho camera"""
        if cam_id not in self.camera_states:
            self.camera_states[cam_id] = {
                'is_recording': False,
                'video_writer': None,
                'video_path': None,
                'start_time': None,
                'current_intruders': set(),
                'all_intruders': set(),
                'last_intruder_exit_time': None,  # Timestamp when last person left zone
                'frame_size': None,
                'pre_buffer': deque(maxlen=60)
            }
        return self.camera_states[cam_id]
    
    @property
    def is_recording(self):
        """Kiểm tra có camera nào đang recording không"""
        return any(state['is_recording'] for state in self.camera_states.values())
    
    def set_telegram(self, telegram):
        self.telegram = telegram
    
    def is_camera_recording(self, cam_id=0):
        """Kiểm tra camera cụ thể có đang recording không"""
        state = self._get_camera_state(cam_id)
        return state['is_recording']
    
    def add_frame_to_buffer(self, frame, cam_id=0):
        """Thêm frame vào buffer của camera cụ thể"""
        if frame is not None:
            state = self._get_camera_state(cam_id)
            state['pre_buffer'].append(frame.copy())
    
    def start_recording(self, frame, first_intruder_id, cam_id=0):
        """Bắt đầu recording cho camera cụ thể"""
        state = self._get_camera_state(cam_id)
        
        if state['is_recording']:
            return False
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Thêm cam_id vào tên file để phân biệt
        state['video_path'] = self.output_dir / f"cam{cam_id}_intrusion_{timestamp}.mp4"
        
        state['frame_size'] = (frame.shape[1], frame.shape[0])
        
        # Dùng H.264 codec qua MSMF backend (browser-compatible)
        # Fallback sang mp4v nếu H264 không khả dụng
        fourcc_h264 = cv2.VideoWriter_fourcc(*'H264')
        state['video_writer'] = cv2.VideoWriter(
            str(state['video_path']), 
            cv2.CAP_MSMF,
            fourcc_h264, 
            self.fps, 
            state['frame_size']
        )
        
        # Fallback to mp4v if H264 fails
        if not state['video_writer'].isOpened():
            print(f"[RECORDER] CAM{cam_id}: H264 failed, fallback to mp4v")
            fourcc_mp4v = cv2.VideoWriter_fourcc(*'mp4v')
            state['video_writer'] = cv2.VideoWriter(
                str(state['video_path']), 
                fourcc_mp4v, 
                self.fps, 
                state['frame_size']
            )

        
        if not state['video_writer'].isOpened():
            print(f"[RECORDER] CAM{cam_id}: Failed to create video writer")
            return False
        
        # Write pre-buffer frames
        for buffered_frame in state['pre_buffer']:
            if buffered_frame.shape[1] != state['frame_size'][0] or buffered_frame.shape[0] != state['frame_size'][1]:
                buffered_frame = cv2.resize(buffered_frame, state['frame_size'])
            state['video_writer'].write(buffered_frame)
        
        state['is_recording'] = True
        state['start_time'] = time.time()
        state['current_intruders'].add(first_intruder_id)
        state['all_intruders'].add(first_intruder_id)
        state['last_intruder_exit_time'] = None  # Reset exit timer
        self.total_recordings += 1
        
        print(f"[RECORDER] CAM{cam_id}: Started recording: {state['video_path']}")
        print(f"[RECORDER] CAM{cam_id}: First intruder: P{first_intruder_id}")
        
        return True
    
    def add_intruder(self, person_id, cam_id=0):
        """Thêm intruder cho camera cụ thể"""
        state = self._get_camera_state(cam_id)
        
        if not state['is_recording']:
            return
        
        if person_id not in state['current_intruders']:
            state['current_intruders'].add(person_id)
            state['all_intruders'].add(person_id)
            state['frames_since_last'] = 0
            print(f"[RECORDER] CAM{cam_id}: New intruder added: P{person_id}")
    
    def remove_intruder(self, person_id, cam_id=0):
        """Xóa intruder khỏi camera cụ thể"""
        state = self._get_camera_state(cam_id)
        
        if person_id in state['current_intruders']:
            state['current_intruders'].discard(person_id)
            print(f"[RECORDER] CAM{cam_id}: Intruder left zone: P{person_id}")
    
    def write_frame(self, frame, cam_id=0):
        """Ghi frame cho camera cụ thể"""
        state = self._get_camera_state(cam_id)
        
        if not state['is_recording'] or state['video_writer'] is None:
            return False
        
        if frame.shape[1] != state['frame_size'][0] or frame.shape[0] != state['frame_size'][1]:
            frame = cv2.resize(frame, state['frame_size'])
        
        display_frame = frame.copy()
        self._draw_recording_overlay(display_frame, cam_id)
        
        state['video_writer'].write(display_frame)
        
        # Track when last intruder left zone
        if len(state['current_intruders']) == 0:
            if state['last_intruder_exit_time'] is None:
                state['last_intruder_exit_time'] = time.time()
                print(f"[RECORDER] CAM{cam_id}: All intruders left zone, will stop in {self.seconds_after_last_intruder}s")
        else:
            state['last_intruder_exit_time'] = None
        
        elapsed = time.time() - state['start_time']
        if elapsed >= self.max_recording_duration:
            print(f"[RECORDER] CAM{cam_id}: Max duration reached ({self.max_recording_duration}s)")
            self.stop_recording(cam_id)
            return False
        
        return True
    
    def _draw_recording_overlay(self, frame, cam_id=0):
        """Vẽ overlay cho camera cụ thể"""
        state = self._get_camera_state(cam_id)
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        if int(time.time() * 2) % 2 == 0:
            cv2.circle(frame, (30, 30), 10, (0, 0, 255), -1)
        cv2.putText(frame, f"REC CAM{cam_id}", (50, 35), font, 0.7, (0, 0, 255), 2)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cv2.putText(frame, timestamp, (10, frame.shape[0] - 10), font, 0.5, (255, 255, 255), 1)
        
        if state['start_time']:
            elapsed = time.time() - state['start_time']
            duration_text = f"Duration: {elapsed:.1f}s"
            cv2.putText(frame, duration_text, (frame.shape[1] - 150, 30), font, 0.5, (255, 255, 255), 1)
    
    def should_stop_recording(self, cam_id=0):
        """Kiểm tra có nên dừng recording camera cụ thể không"""
        state = self._get_camera_state(cam_id)
        
        if not state['is_recording']:
            return False
        
        # Check if all intruders left and enough time has passed
        if len(state['current_intruders']) == 0 and state['last_intruder_exit_time'] is not None:
            time_since_exit = time.time() - state['last_intruder_exit_time']
            
            if time_since_exit >= self.seconds_after_last_intruder:
                elapsed = time.time() - state['start_time']
                if elapsed >= self.min_recording_duration:
                    print(f"[RECORDER] CAM{cam_id}: {self.seconds_after_last_intruder}s elapsed since last intruder, stopping...")
                    return True
        
        return False
    
    def stop_recording(self, cam_id=0):
        """Dừng recording cho camera cụ thể"""
        state = self._get_camera_state(cam_id)
        
        if not state['is_recording']:
            return None
        
        state['is_recording'] = False
        
        if state['video_writer'] is not None:
            state['video_writer'].release()
            state['video_writer'] = None
        
        duration = time.time() - state['start_time']
        num_intruders = len(state['all_intruders'])
        intruder_ids = sorted(list(state['all_intruders']))
        
        self.total_intruders_recorded += num_intruders
        
        print(f"[RECORDER] CAM{cam_id}: Stopped recording: {state['video_path']}")
        print(f"[RECORDER] CAM{cam_id}: Duration: {duration:.1f}s")
        print(f"[RECORDER] CAM{cam_id}: Total intruders in video: {num_intruders}")
        
        if self.telegram and state['video_path'] and state['video_path'].exists():
            caption = (
                f"📹 VIDEO XÂM NHẬP - CAM {cam_id}\n\n"
                f"⏰ Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"⏱️ Thời lượng: {duration:.1f}s\n"
                f"👥 Số người: {num_intruders}\n"
                f"🆔 IDs: {', '.join([f'P{pid}' for pid in intruder_ids])}"
            )
            self.telegram.send_video(str(state['video_path']), caption)
        
        video_path = state['video_path']
        
        # Reset state cho camera này
        state['video_path'] = None
        state['start_time'] = None
        state['current_intruders'].clear()
        state['all_intruders'].clear()
        state['last_intruder_exit_time'] = None
        
        return video_path
    
    def update(self, frame, intruding_person_ids, cam_id=0):
        """Update recording cho camera cụ thể"""
        state = self._get_camera_state(cam_id)
        self.add_frame_to_buffer(frame, cam_id)
        
        if intruding_person_ids:
            # Có người trong zone → bắt đầu quay ngay nếu chưa quay
            if not state['is_recording']:
                first_intruder = min(intruding_person_ids)
                self.start_recording(frame, first_intruder, cam_id)
            
            for pid in intruding_person_ids:
                self.add_intruder(pid, cam_id)
            
            for pid in list(state['current_intruders']):
                if pid not in intruding_person_ids:
                    self.remove_intruder(pid, cam_id)
        else:
            # Không có người trong zone → xóa hết current_intruders
            if state['is_recording']:
                for pid in list(state['current_intruders']):
                    self.remove_intruder(pid, cam_id)
        
        # Luôn ghi frame nếu đang recording
        if state['is_recording']:
            self.write_frame(frame, cam_id)
            
            # Kiểm tra nên dừng recording không (10s sau khi người cuối rời)
            if self.should_stop_recording(cam_id):
                self.stop_recording(cam_id)
    
    def get_stats(self, cam_id=None):
        """Lấy thống kê tổng hợp hoặc cho camera cụ thể"""
        if cam_id is not None:
            state = self._get_camera_state(cam_id)
            return {
                'cam_id': cam_id,
                'is_recording': state['is_recording'],
                'current_intruders': len(state['current_intruders']),
                'session_intruders': len(state['all_intruders']),
                'recording_duration': time.time() - state['start_time'] if state['is_recording'] and state['start_time'] else 0
            }
        else:
            return {
                'is_recording': self.is_recording,
                'total_recordings': self.total_recordings,
                'total_intruders_recorded': self.total_intruders_recorded,
                'active_cameras': [cid for cid, state in self.camera_states.items() if state['is_recording']]
            }
    
    def cleanup(self, cam_id=None):
        """Cleanup cho camera cụ thể hoặc tất cả"""
        if cam_id is not None:
            if self.is_camera_recording(cam_id):
                self.stop_recording(cam_id)
        else:
            for cid in list(self.camera_states.keys()):
                if self.is_camera_recording(cid):
                    self.stop_recording(cid)


# ========== ZONE MANAGER ==========
class ZoneManager:
    """Quản lý vùng cấm và phát hiện xâm nhập"""
    
    def __init__(self, telegram_notifier=None, db_manager=None):
        self.zones = []
        self.is_drawing = False
        self.current_zone = []
        self.intrusion_history = defaultdict(lambda: {'count': 0, 'last_frame': 0})
        
        self.recorder = SmartVideoRecorder(telegram=telegram_notifier, db_manager=db_manager)
        self.telegram = telegram_notifier
        self.alerted_persons = set()
        
        self.current_frame_intruders = set()
        self.pending_snapshots = []
        
        # Create snapshots directory
        self.snapshot_dir = Path("intrusion_snapshots")
        self.snapshot_dir.mkdir(exist_ok=True)
    
    def set_telegram(self, telegram_notifier):
        self.telegram = telegram_notifier
        self.recorder.set_telegram(telegram_notifier)
    
    def add_zone(self, points):
        """Thêm zone từ list of points [(x1,y1), (x2,y2), ...]"""
        if len(points) >= 3:
            self.zones.append(points)
            print(f"[ZONE] Zone {len(self.zones)} created with {len(points)} points")
            return True
        return False
    
    def clear_all_zones(self):
        self.zones = []
        self.current_zone = []
        self.is_drawing = False
        self.alerted_persons.clear()
        print("[ZONE] All zones cleared")
    
    def get_zones(self):
        return self.zones
    
    def point_in_polygon(self, point, polygon):
        x, y = point
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def check_intrusion(self, person_id, bbox, frame):
        if not self.zones:
            return False, None
        
        x1, y1, x2, y2 = bbox
        center = ((x1 + x2) / 2, (y1 + y2) / 2)
        
        for idx, zone in enumerate(self.zones):
            if self.point_in_polygon(center, zone):
                self.current_frame_intruders.add(person_id)
                
                if self.telegram and person_id not in self.alerted_persons:
                    self.save_snapshot(person_id, frame, bbox)
                    self.telegram.send_intrusion_alert(person_id, frame, bbox)
                    self.alerted_persons.add(person_id)
                
                return True, idx
        
        if person_id in self.alerted_persons:
            self.alerted_persons.discard(person_id)
        
        return False, None
    
    def begin_frame(self, cam_id=0):
        """Bắt đầu frame mới cho camera cụ thể"""
        self.current_frame_intruders.clear()
        self.pending_snapshots.clear()
    
    def end_frame(self, frame, cam_id=0):
        """Kết thúc frame và update recorder - chỉ quay video trên CAM 0"""
        # Chỉ record trên CAM 0 để tránh gửi video trùng lặp
        if cam_id == 0:
            self.recorder.update(frame, self.current_frame_intruders, cam_id)
    
    def save_snapshot(self, person_id, frame, bbox):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.snapshot_dir / f"intruder_P{person_id}_{timestamp}.jpg"
            
            snapshot = frame.copy()
            x1, y1, x2, y2 = map(int, bbox)
            cv2.rectangle(snapshot, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(snapshot, f"P{person_id}", (x1, y1-5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            cv2.imwrite(str(filename), snapshot)
            print(f"[ZONE] Snapshot saved: {filename}")
            
            self.pending_snapshots.append((person_id, filename))
            
        except Exception as e:
            print(f"[ZONE] Failed to save snapshot: {e}")

    def draw_zones(self, frame, flash=False):
        overlay = frame.copy()
        
        for idx, zone in enumerate(self.zones):
            pts = np.array(zone, np.int32).reshape((-1, 1, 2))
            color = (0, 0, 255) if flash else (0, 255, 255)
            
            cv2.fillPoly(overlay, [pts], color)
            cv2.polylines(frame, [pts], True, color, 3)
            
            center_x = int(np.mean([p[0] for p in zone]))
            center_y = int(np.mean([p[1] for p in zone]))
            cv2.putText(frame, f"ZONE {idx+1}", (center_x-40, center_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
        
        return frame
    
    def draw_intrusion_alert(self, frame, person_id, bbox):
        x1, y1, x2, y2 = map(int, bbox)
        
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 4)
        
        label = f"INTRUDER P{person_id}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        (text_w, text_h), _ = cv2.getTextSize(label, font, 0.7, 2)
        
        cv2.rectangle(frame, (x1, y1 - text_h - 15), 
                     (x1 + text_w + 10, y1), (0, 0, 255), -1)
        cv2.putText(frame, label, (x1 + 5, y1 - 5), 
                   font, 0.7, (255, 255, 255), 2)
        
        return frame
    
    def draw_recording_status(self, frame):
        if self.recorder.is_recording:
            font = cv2.FONT_HERSHEY_SIMPLEX
            stats = self.recorder.get_stats()
            
            if int(time.time() * 2) % 2 == 0:
                cv2.circle(frame, (frame.shape[1] - 30, 80), 8, (0, 0, 255), -1)
            cv2.putText(frame, "REC", (frame.shape[1] - 70, 85), font, 0.5, (0, 0, 255), 2)
            
            duration_text = f"{stats.get('recording_duration', 0):.1f}s"
            cv2.putText(frame, duration_text, (frame.shape[1] - 70, 105), font, 0.4, (255, 255, 255), 1)
        
        return frame
    
    def get_zone_count(self):
        return len(self.zones)
    
    def cleanup(self):
        self.recorder.cleanup()


# ========== APPEARANCE EXTRACTOR ==========
class AppearanceExtractor:
    def __init__(self, device='cpu'):
        self.device = device
        self.use_simple_features = True
        print("[FEATURE] Using simple color-based features")
    
    def extract_features(self, frame, bbox):
        x1, y1, x2, y2 = map(int, bbox)
        
        person_img = frame[y1:y2, x1:x2]
        if person_img.size == 0:
            return None
        
        features = []
        
        avg_color = cv2.mean(person_img)[:3]
        features.extend([c/255.0 for c in avg_color])
        
        height = y2 - y1
        width = x2 - x1
        aspect_ratio = height / max(width, 1)
        features.append(aspect_ratio / 3.0)
        
        small_img = cv2.resize(person_img, (32, 64))
        for i in range(3):
            hist = cv2.calcHist([small_img], [i], None, [4], [0, 256])
            hist = hist.flatten() / (small_img.size / 3)
            features.extend(hist)
        
        return np.array(features, dtype=np.float32)
    
    def similarity(self, feat1, feat2):
        if feat1 is None or feat2 is None:
            return 0.0
        return 1.0 - cosine(feat1, feat2)


# ========== PERSON TRACKER ==========
class FixedPersonTracker:
    def __init__(self, max_disappeared=100):
        self.next_person_id = 1
        self.max_disappeared = max_disappeared
        self.min_confidence_for_new = 0.15
        
        self.active_persons = {}
        self.disappeared_persons = {}
        self.all_persons_ever = set()
        self.tentative_persons = {}
        
        self.feature_extractor = AppearanceExtractor()
        self.min_frames_to_confirm = 3
        
        self.total_unique_people = 0
        self.frame_count = 0
        self.matches_count = 0
        self.new_person_count = 0
        self.reid_success_count = 0
        
        print(f"[TRACKER] Initialized with min_frames_to_confirm: {self.min_frames_to_confirm}")
    
    def update(self, frame, yolo_results):
        self.frame_count += 1
        
        current_detections = self._parse_yolo_results(yolo_results)
        
        if not current_detections:
            self._update_disappeared()
            self._cleanup_old_tentative()
            return [], {}
        
        matches, unmatched_detections, unmatched_persons = self._match_detections(
            frame, current_detections
        )
        
        for det_idx, person_id in matches:
            bbox, yolo_id = current_detections[det_idx]
            features = self.feature_extractor.extract_features(frame, bbox)
            
            self.active_persons[person_id] = {
                'bbox': bbox,
                'yolo_id': yolo_id,
                'features': features,
                'last_seen': self.frame_count,
                'first_seen': self.active_persons[person_id]['first_seen'],
                'total_frames': self.active_persons[person_id].get('total_frames', 0) + 1,
                'consecutive_frames': self.active_persons[person_id].get('consecutive_frames', 0) + 1,
                'confirmed': True
            }
            self.matches_count += 1
        
        for det_idx in unmatched_detections:
            bbox, yolo_id = current_detections[det_idx]
            self._handle_new_detection(frame, bbox, yolo_id)
        
        for person_id in unmatched_persons:
            self._handle_disappeared_person(person_id)
        
        self._cleanup_old_disappeared()
        self._cleanup_old_tentative()
        
        # Return both IDs and their bboxes
        tracked_persons = {}
        for pid, info in self.active_persons.items():
            tracked_persons[pid] = info['bbox']
        
        return list(self.active_persons.keys()), tracked_persons
    
    def _parse_yolo_results(self, results):
        detections = []
        
        if results.boxes is not None and results.boxes.id is not None:
            boxes = results.boxes.xyxy.cpu().numpy()
            track_ids = results.boxes.id.cpu().numpy().astype(int)
            
            for box, track_id in zip(boxes, track_ids):
                detections.append((box, track_id))
        
        return detections
    
    def _match_detections(self, frame, current_detections):
        if not self.active_persons:
            return [], list(range(len(current_detections))), []
        
        matches = []
        unmatched_detections = list(range(len(current_detections)))
        unmatched_persons = list(self.active_persons.keys())
        
        similarity_matrix = np.zeros((len(current_detections), len(self.active_persons)))
        
        for i, (bbox, yolo_id) in enumerate(current_detections):
            det_features = self.feature_extractor.extract_features(frame, bbox)
            
            for j, person_id in enumerate(self.active_persons.keys()):
                person_info = self.active_persons[person_id]
                
                iou = self._calculate_iou(bbox, person_info['bbox'])
                
                if det_features is not None and person_info['features'] is not None:
                    appearance_sim = self.feature_extractor.similarity(
                        det_features, person_info['features']
                    )
                else:
                    appearance_sim = 0.0
                
                similarity_score = (iou * 0.7) + (appearance_sim * 0.3)
                similarity_matrix[i, j] = similarity_score
        
        while True:
            max_score = np.max(similarity_matrix)
            if max_score < 0.4:
                break
            
            i, j = np.unravel_index(np.argmax(similarity_matrix), similarity_matrix.shape)
            matches.append((i, list(self.active_persons.keys())[j]))
            
            similarity_matrix[i, :] = -1
            similarity_matrix[:, j] = -1
        
        matched_det_indices = [m[0] for m in matches]
        matched_person_indices = [m[1] for m in matches]
        
        unmatched_detections = [i for i in range(len(current_detections)) 
                               if i not in matched_det_indices]
        unmatched_persons = [pid for pid in self.active_persons.keys() 
                            if pid not in matched_person_indices]
        
        return matches, unmatched_detections, unmatched_persons
    
    def _calculate_iou(self, boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])
        
        interArea = max(0, xB - xA) * max(0, yB - yA)
        
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        
        iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)
        return iou
    
    def _handle_new_detection(self, frame, bbox, yolo_id):
        features = self.feature_extractor.extract_features(frame, bbox)
        
        matched_person_id, confidence = self._find_reid_match(features, bbox)
        
        if matched_person_id is not None and confidence >= self.min_confidence_for_new:
            person_info = self.disappeared_persons.pop(matched_person_id)
            
            self.active_persons[matched_person_id] = {
                'bbox': bbox,
                'yolo_id': yolo_id,
                'features': features,
                'last_seen': self.frame_count,
                'first_seen': person_info['first_seen'],
                'total_frames': person_info.get('total_frames', 0) + 1,
                'consecutive_frames': 1,
                'confirmed': True
            }
            
            self.reid_success_count += 1
            print(f"[TRACKER] Person {matched_person_id} REAPPEARED")
        else:
            tentative_match = self._find_tentative_match(features, bbox)
            
            if tentative_match is not None:
                self.tentative_persons[tentative_match]['consecutive_frames'] += 1
                self.tentative_persons[tentative_match]['bbox'] = bbox
                self.tentative_persons[tentative_match]['last_seen'] = self.frame_count
                self.tentative_persons[tentative_match]['features'] = features
                
                if self.tentative_persons[tentative_match]['consecutive_frames'] >= self.min_frames_to_confirm:
                    self._confirm_tentative_person(tentative_match, bbox, yolo_id)
            else:
                person_id = self._get_next_available_id()
                
                self.tentative_persons[person_id] = {
                    'bbox': bbox,
                    'yolo_id': yolo_id,
                    'features': features,
                    'last_seen': self.frame_count,
                    'first_seen': self.frame_count,
                    'total_frames': 1,
                    'consecutive_frames': 1,
                    'confirmed': False
                }
    
    def _get_next_available_id(self):
        person_id = self.next_person_id
        self.next_person_id += 1
        return person_id
    
    def _find_tentative_match(self, features, bbox):
        if features is None:
            return None
        
        best_match_id = None
        best_similarity = 0.0
        
        for person_id, person_info in self.tentative_persons.items():
            frames_gone = self.frame_count - person_info['last_seen']
            
            if frames_gone <= 10:
                if person_info['features'] is not None:
                    appearance_sim = self.feature_extractor.similarity(
                        features, person_info['features']
                    )
                    
                    iou = self._calculate_iou(bbox, person_info['bbox'])
                    combined_score = (appearance_sim * 0.6) + (iou * 0.4)
                    
                    if combined_score > best_similarity and combined_score > 0.5:
                        best_similarity = combined_score
                        best_match_id = person_id
        
        return best_match_id
    
    def _confirm_tentative_person(self, person_id, bbox, yolo_id):
        person_info = self.tentative_persons.pop(person_id)
        
        self.total_unique_people += 1
        self.new_person_count += 1
        self.all_persons_ever.add(person_id)
        
        self.active_persons[person_id] = {
            'bbox': bbox,
            'yolo_id': yolo_id,
            'features': person_info['features'],
            'last_seen': self.frame_count,
            'first_seen': person_info['first_seen'],
            'total_frames': person_info['total_frames'],
            'consecutive_frames': person_info['consecutive_frames'],
            'confirmed': True
        }
        
        print(f"[TRACKER] Person {person_id} CONFIRMED | Total: {self.total_unique_people}")
    
    def _handle_disappeared_person(self, person_id):
        if person_id in self.active_persons:
            person_info = self.active_persons.pop(person_id)
            self.disappeared_persons[person_id] = person_info
    
    def _update_disappeared(self):
        for person_id in list(self.active_persons.keys()):
            self._handle_disappeared_person(person_id)
    
    def _cleanup_old_disappeared(self):
        to_remove = []
        current_time = self.frame_count
        
        for person_id, person_info in self.disappeared_persons.items():
            frames_gone = current_time - person_info['last_seen']
            if frames_gone > self.max_disappeared:
                to_remove.append(person_id)
        
        for person_id in to_remove:
            del self.disappeared_persons[person_id]
    
    def _cleanup_old_tentative(self):
        to_remove = []
        current_time = self.frame_count
        
        for person_id, person_info in self.tentative_persons.items():
            frames_gone = current_time - person_info['last_seen']
            if frames_gone > 30:
                to_remove.append(person_id)
        
        for person_id in to_remove:
            del self.tentative_persons[person_id]
    
    def _find_reid_match(self, features, bbox):
        if features is None:
            return None, 0.0
        
        best_match_id = None
        best_confidence = 0.0
        
        for person_id, person_info in self.disappeared_persons.items():
            frames_gone = self.frame_count - person_info['last_seen']
            
            if frames_gone <= self.max_disappeared:
                if person_info['features'] is not None:
                    appearance_sim = self.feature_extractor.similarity(
                        features, person_info['features']
                    )
                    
                    if appearance_sim > best_confidence and appearance_sim > 0.6:
                        best_confidence = appearance_sim
                        best_match_id = person_id
        
        return best_match_id, best_confidence
    
    def get_stats(self):
        return {
            'total_unique_people': self.total_unique_people,
            'current_active': len(self.active_persons),
            'tentative_count': len(self.tentative_persons),
            'disappeared_count': len(self.disappeared_persons),
            'matches_count': self.matches_count,
            'reid_success_count': self.reid_success_count
        }
