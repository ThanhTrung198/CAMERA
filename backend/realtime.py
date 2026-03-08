import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
import cv2
import numpy as np
import insightface
from insightface.app import FaceAnalysis
import av

# --- 1. SỬA LỖI NUMPY ---
np.int = int

# --- 2. CẤU HÌNH TRANG WEB ---
st.set_page_config(page_title="Real-time Face AI", layout="centered")
st.title("🎥 Camera AI: Nhận Diện Thời Gian Thực")

# --- 3. TẢI MODEL (Chỉ tải 1 lần duy nhất để không bị lag) ---
@st.cache_resource
def load_model():
    # Load model
    print("Đang tải model...")
    app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
    # Giảm kích thước det_size xuống (320, 320) để chạy nhanh hơn trên CPU
    app.prepare(ctx_id=0, det_size=(640, 640)) 
    return app

app = load_model()

# --- 4. XỬ LÝ VIDEO TỪNG KHUNG HÌNH ---
class FaceDetector:
    def recv(self, frame):
        # Chuyển đổi frame từ WebRTC sang ảnh OpenCV (BGR)
        img = frame.to_ndarray(format="bgr24")
        
        # Gọi InsightFace để nhận diện
        # (Lưu ý: Chạy trên CPU có thể hơi delay một chút)
        faces = app.get(img)
        
        # Vẽ kết quả lên hình
        rimg = app.draw_on(img, faces)
        
        # Trả về hình ảnh đã vẽ để hiển thị lên web
        return av.VideoFrame.from_ndarray(rimg, format="bgr24")

# --- 5. HIỂN THỊ LÊN WEB ---
st.write("Bấm **START** để bật Camera. Lần đầu chạy sẽ mất vài giây để khởi động Model.")

webrtc_streamer(
    key="example", 
    video_processor_factory=FaceDetector,
    media_stream_constraints={"video": True, "audio": False} # Chỉ lấy hình, không lấy tiếng
)