"""
Image processing utilities for face recognition system
"""
import cv2
import numpy as np
import time
from PIL import Image, ImageDraw, ImageFont


def put_text_utf8(image, text, position, color=(0, 255, 0)):
    """
    Draw UTF-8 text on image using PIL (supports Vietnamese)
    
    Args:
        image: OpenCV image (BGR)
        text: Text to draw
        position: (x, y) tuple
        color: RGB color tuple
    
    Returns:
        Image with text drawn
    """
    img_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()
    
    x, y = position
    
    # Draw text shadow for better visibility
    for off in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
        draw.text((x + off[0], y + off[1]), text, font=font, fill=(0, 0, 0))
    
    draw.text(position, text, font=font, fill=color[::-1])
    
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def create_placeholder_frame(text="NO SIGNAL"):
    """
    Create a placeholder frame to display when camera is not available
    
    Args:
        text: Text to display on placeholder
    
    Returns:
        Black frame with text and timestamp
    """
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(frame, text, (160, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 2)
    cv2.putText(frame, time.strftime("%H:%M:%S"), (250, 290), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 100, 100), 1)
    return frame


def calculate_iou(boxA, boxB):
    """
    Calculate Intersection over Union (IoU) for two bounding boxes
    
    Args:
        boxA: [x1, y1, x2, y2]
        boxB: [x1, y1, x2, y2]
    
    Returns:
        IoU score (0.0 to 1.0)
    """
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    
    interArea = max(0, xB - xA) * max(0, yB - yA)
    
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    union = boxAArea + boxBArea - interArea
    
    return interArea / float(union) if union > 0 else 0


import threading as _threading
_spoof_model_lock = _threading.Lock()

# ★ EMA SMOOTHING — BỘ LỌC THỜI GIAN (Exponential Moving Average)
# Mục đích: Chống hiện tượng "bật/tắt" liên tục (false positive). 
# Nếu 1 frame bị nhiễu và báo Fake, hệ thống sẽ không tin ngay mà cần xem xét lịch sử các frame trước đó.
_spoof_ema = {}  # Lưu trữ điểm số theo format: {cam_id: {"fake_score": float, "real_score": float, "count": int}}
_SPOOF_EMA_ALPHA = 0.7  # Trọng số của frame HIỆN TẠI. 0.7 nghĩa là: Frame hiện tại quyết định 70%, lịch sử quyết định 30%. Càng cao thì càng nhạy (bắt fake lẹ hơn).
_SPOOF_MIN_FRAMES = 2   # Số frame TỐI THIỂU cần thiết để EMA bắt đầu đưa ra kết luận Fake. Dưới mức này sẽ thả cho qua (để calibrating).

def _get_spoof_ema(cam_id, face_key=None):
    """Lấy trạng thái EMA hiện tại của một khuôn mặt trên một camera cụ thể."""
    k = f"{cam_id}_{face_key}" if face_key else str(cam_id)
    if k not in _spoof_ema:
        _spoof_ema[k] = {"fake_score": 0.0, "real_score": 0.5, "count": 0}
    return _spoof_ema[k]

def _update_spoof_ema(cam_id, best_fake, best_real, face_key=None):
    """Cập nhật điểm số trung bình (EMA) dựa trên frame mới nhất."""
    ema = _get_spoof_ema(cam_id, face_key)
    a = _SPOOF_EMA_ALPHA
    # Công thức EMA: Giữ lại (1-a)% điểm cũ, cộng thêm a% điểm mới
    ema["fake_score"] = a * best_fake + (1 - a) * ema["fake_score"]
    ema["real_score"] = a * best_real + (1 - a) * ema["real_score"]
    ema["count"] = min(ema["count"] + 1, 100) # Đếm số frame đã xử lý (max 100 để tránh tràn số)
    return ema


def check_face_real(face_img, model, cam_id: int = 0,
                    full_frame=None, face_bbox=None):
    """
    HÀM CỐT LÕI: Kiểm tra khuôn mặt thật vs giả mạo dùng YOLO (best.pt)

    Model: YOLOv8n detection  |  Classes: {0: 'fake', 1: 'real'}

    Cơ chế hoạt động:
      1. Đọc ngưỡng cấu hình từ settings.py (để dễ tùy chỉnh)
      2. Chạy YOLO predict kích thước 640px trên mặt đã crop.
      3. Đưa raw score qua bộ lọc EMA để chống nhiễu.
      4. Quyết định kết quả cuối cùng dựa trên EMA và Raw Score.

    Returns:
        (is_real: bool, confidence: float) - Ví dụ: (False, 0.85) nghĩa là TIN CHẮC ĐÂY LÀ FAKE (85%)
    """
    if model is None:
        return True, 0.0 # Nếu model chưa load, mặc định thả qua (True)
    if face_img is None or face_img.size == 0:
        return True, 0.0

    # ★ LẤY NGƯỠNG TỪ SETTINGS.PY
    # Lấy ngưỡng động từ file cấu hình, nếu file lỗi thì dùng mặc định 0.65/0.60
    try:
        from config.settings import SPOOF_FAKE_THRESHOLD, SPOOF_REAL_THRESHOLD
        FAKE_THR = SPOOF_FAKE_THRESHOLD   # Ngưỡng nhỏ nhất để bị kết án "GIA MAO" (VD: 0.55)
        REAL_THR = SPOOF_REAL_THRESHOLD   # Ngưỡng tin cậy "NGƯỜI THẬT" (VD: 0.60)
    except ImportError:
        FAKE_THR = 0.65
        REAL_THR = 0.60

    # Kích thước ảnh đưa vào Model YOLO (480 = cân bằng tốc độ/độ chính xác trên CPU)
    SPOOF_IMGSZ = 480

    try:
        # ── BƯỚC 1: Chuẩn bị input (Resize nếu ảnh quá bé) ──
        h_c, w_c = face_img.shape[:2]
        if h_c < 160 or w_c < 160: # Chống lỗi ảnh crop bị biến dạng
            scale = max(160 / h_c, 160 / w_c)
            input_img = cv2.resize(face_img, (int(w_c * scale), int(h_c * scale)))
        else:
            input_img = face_img

        # ── BƯỚC 2: Gọi YOLO Model Dự Đoán (Inference) ──
        # Dùng _threading.Lock() vì model YOLO PyTorch KHÔNG Thread-Safe. 
        # Nếu 2 thread cùng predict 1 lúc, chương trình sẽ crash.
        with _spoof_model_lock:
            results = model.predict(input_img, imgsz=SPOOF_IMGSZ, conf=0.15, verbose=False)

        # Lọc ra điểm số Fake và Real cao nhất từ các boxes mà YOLO trả về
        best_fake = 0.0
        best_real = 0.0
        total_boxes = 0
        for result in results:
            if result.boxes is None or len(result.boxes) == 0:
                continue
            for box in result.boxes:
                total_boxes += 1
                cls_id = int(box.cls[0]) # 0 = fake, 1 = real
                conf   = float(box.conf[0])
                if cls_id == 0 and conf > best_fake:
                    best_fake = conf
                elif cls_id == 1 and conf > best_real:
                    best_real = conf

        # ★ DEBUG: In ra raw scores để theo dõi (XÓA SAU KHI DEBUG XONG)
        print(f"[SPOOF DEBUG] cam{cam_id} | img={face_img.shape} | boxes={total_boxes} | raw_fake={best_fake:.3f} raw_real={best_real:.3f} | THR: fake>={FAKE_THR} real>={REAL_THR}")

        # ── BƯỚC 3: Cập nhật bộ lọc EMA ──
        face_key = None
        if face_bbox is not None:
            # Tạo một cái key (tọa độ lưới 50x50) để theo dõi mặt này theo VỊ TRÍ
            # (★ Grid 50px thay vì 80px — phân biệt 2 mặt gần nhau tốt hơn)
            cx = (face_bbox[0] + face_bbox[2]) // 2
            cy = (face_bbox[1] + face_bbox[3]) // 2
            face_key = f"{cx//50}_{cy//50}" 

        ema = _update_spoof_ema(cam_id, best_fake, best_real, face_key)

        # ── BƯỚC 4: Ra Quyết Định Rút Gọn ──
        ema_fake = ema["fake_score"]
        ema_real = ema["real_score"]
        frame_count = ema["count"]

        # ★ DEBUG: In EMA state
        print(f"[SPOOF DEBUG] EMA: fake={ema_fake:.3f} real={ema_real:.3f} count={frame_count}")

        # TRƯỜNG HỢP 1: Mới xuất hiện (< 2 frame) → Mặc định cho qua là REAL để tránh giật mình báo động oan.
        if frame_count < _SPOOF_MIN_FRAMES:
            print(f"[SPOOF DEBUG] → REAL (calibrating, count={frame_count} < {_SPOOF_MIN_FRAMES})")
            return True, max(best_real, 0.5)

        # TRƯỜNG HỢP 2: Là FAKE rõ ràng 
        # (Cả Lịch sử EMA >= Ngưỡng VÀ Frame hiện tại đạt ít nhất 70% của Ngưỡng)
        if ema_fake >= FAKE_THR and best_fake >= (FAKE_THR * 0.7):
            print(f"[SPOOF DEBUG] → ★★★ FAKE ★★★ (ema_fake={ema_fake:.3f}>={FAKE_THR}, raw={best_fake:.3f}>={FAKE_THR*0.7:.3f})")
            return False, ema_fake

        # TRƯỜNG HỢP 3: LÀ REAL rõ ràng
        if ema_real >= REAL_THR:
            print(f"[SPOOF DEBUG] → REAL (ema_real={ema_real:.3f}>={REAL_THR})")
            return True, ema_real

        # TRƯỜNG HỢP 4: Không đạt cả 2 ngưỡng bự, nhưng điểm Fake cao hơn điểm Real -> châm chước bắt FAKE
        if ema_fake > ema_real and ema_fake >= (FAKE_THR * 0.85):
            print(f"[SPOOF DEBUG] → FAKE (fallback: ema_fake={ema_fake:.3f} > ema_real={ema_real:.3f})")
            return False, ema_fake

        # THEO LUẬT SUY ĐOÁN VÔ TỘI: Nếu mơ hồ không rõ ràng -> Mặc định là REAL
        print(f"[SPOOF DEBUG] → REAL (default/ambiguous)")
        return True, max(ema_real, best_real, 0.3)

    except Exception as e:
        print(f"[SPOOF CHECK] Error: {e}")
        return True, 0.0

def preprocess_face_for_spoof(face_crop, full_frame=None, face_bbox=None, 
                                target_size=None, padding_ratio=0.3):
    """
    Tiền xử lý ảnh mặt trước khi đưa vào model anti-spoof.
    1. Padding thêm viền xung quanh mặt (thêm context để thấy viền điện thoại)
    2. Light CLAHE (clipLimit=1.5 — cải thiện ảnh tối)
    
    ★ QUAN TRỌNG: KHÔNG resize về 224×224! 
      Để crop giữ kích thước tự nhiên (~200-400px từ camera).
      YOLO sẽ tự resize bên trong qua tham số imgsz.
      Resize xuống 224 khiến YOLO detect 0 boxes → spoof hoàn toàn hỏng!
    """
    import cv2
    
    # Bước 1: Crop lại từ full_frame với padding (lấy thêm context xung quanh mặt)
    if full_frame is not None and face_bbox is not None:
        h, w = full_frame.shape[:2]
        x1, y1, x2, y2 = face_bbox
        fw, fh = x2 - x1, y2 - y1
        pad_w = int(fw * padding_ratio)
        pad_h = int(fh * padding_ratio)
        nx1 = max(0, x1 - pad_w)
        ny1 = max(0, y1 - pad_h)
        nx2 = min(w, x2 + pad_w)
        ny2 = min(h, y2 + pad_h)
        face_crop = full_frame[ny1:ny2, nx1:nx2]

    if face_crop is None or face_crop.size == 0:
        return face_crop

    # Bước 2: Light CLAHE — tăng nhẹ contrast cho ảnh tối/quá sáng
    try:
        lab = cv2.cvtColor(face_crop, cv2.COLOR_BGR2LAB)
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        face_crop = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    except Exception:
        pass

    # ★ KHÔNG RESIZE — giữ kích thước tự nhiên để YOLO detect được!
    return face_crop
