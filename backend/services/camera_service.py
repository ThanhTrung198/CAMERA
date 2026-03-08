"""
Camera Service - Camera capture threads and global frame management
"""
import cv2
import threading
import time
import numpy as np

# Global state
lock = threading.Lock()
global_frame_0 = None
global_frame_1 = None


def camera_capture_thread(cam_id, source):
    """
    Continuously capture frames from camera and update global frame
    
    Args:
        cam_id: Camera ID (0 or 1)
        source: Camera source (0, 1, or RTSP URL)
    """
    global global_frame_0, global_frame_1
    
    print(f"[CAMERA] Starting capture thread for CAM {cam_id}...")
    
    cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    if cap.isOpened():
        backend = cap.getBackendName()
        print(f"✅ Camera {cam_id}: Webcam mở OK (backend={backend})")
    else:
        print(f"⚠️ Camera {cam_id}: Không mở được, sẽ dùng chung CAM 0")
        if cam_id == 1:
            # Fallback to CAM 0
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if cap.isOpened():
                print(f"⚠️ Camera 1: Dùng chung webcam 0")
    
    frame_count = 0
    
    while True:
        try:
            ret, frame = cap.read()
            
            if ret and frame is not None:
                frame_count += 1
                
                with lock:
                    if cam_id == 0:
                        global_frame_0 = frame.copy()
                    else:
                        global_frame_1 = frame.copy()
            else:
                time.sleep(0.01)
        
        except Exception as e:
            print(f"[CAMERA {cam_id}] Error: {e}")
            time.sleep(0.1)


def start_cameras():
    """
    Start camera capture threads for both cameras
    """
    print("=" * 60)
    print("System: Đang khởi động WEBCAM")
    print("=" * 60)
    
    # Start CAM 0
    t0 = threading.Thread(target=camera_capture_thread, args=(0, 0), daemon=True)
    t0.start()
    
    # Start CAM 1
    t1 = threading.Thread(target=camera_capture_thread, args=(1, 1), daemon=True)
    t1.start()
    
    # Wait a bit for cameras to initialize
    time.sleep(0.5)
