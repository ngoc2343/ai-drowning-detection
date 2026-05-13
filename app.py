import cv2
import numpy as np
import requests
from flask import Flask, request
from ultralytics import YOLO
import threading

# Khởi tạo mô hình YOLOv8-Pose
model = YOLO('yolov8n-pose.pt')
app = Flask(__name__)

# Cấu hình ngưỡng cảnh báo
consecutive_danger_frames = 0
ALARM_THRESHOLD = 3

# Thông tin xác thực Telegram
TELEGRAM_TOKEN = "8500045096:AAHn2BXNgeGP798VgGGY3wb7BrLG-KDXqjo"
CHAT_ID = "8691477584"

def send_telegram_alert(image_matrix):
    """Hàm gửi thông báo hình ảnh qua Telegram API."""
    try:
        _, img_encoded = cv2.imencode('.jpg', image_matrix)
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        caption_text = "🚨 CẢNH BÁO: PHÁT HIỆN ĐỐI TƯỢNG RƠI XUỐNG NƯỚC! 🚨"
        payload = {"chat_id": CHAT_ID, "caption": caption_text}
        files = {"photo": ("alert.jpg", img_encoded.tobytes(), "image/jpeg")}
        requests.post(url, data=payload, files=files)
    except Exception as e:
        print(f"Lỗi truyền tin Telegram: {e}")

@app.route('/upload', methods=['POST'])
def upload():
    global consecutive_danger_frames
    
    # Tiếp nhận dữ liệu nhị phân từ ESP32-CAM
    npimg = np.frombuffer(request.data, np.uint8)
    if npimg.size == 0:
        return "Error: Empty Image", 400
        
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    
    # Thực thi phân tích khung xương (Inference)
    results = model(img)
    danger_detected = False
    
    for r in results:
        if hasattr(r, 'keypoints') and r.keypoints is not None:
            for kpts in r.keypoints.xy:
                if len(kpts) >= 11:
                    # Tọa độ Y của mũi (index 0) và cổ tay (index 9, 10)
                    nose_y = kpts[0][1].item()
                    l_wrist_y = kpts[9][1].item()
                    r_wrist_y = kpts[10][1].item()

                    # Điều kiện logic: Cổ tay cao hơn mũi (y_wrist < y_nose)
                    if (0 < l_wrist_y < nose_y) or (0 < r_wrist_y < nose_y):
                        danger_detected = True
    
    # Kiểm soát trạng thái báo động
    if danger_detected:
        consecutive_danger_frames += 1
    else:
        consecutive_danger_frames = 0

    if consecutive_danger_frames >= ALARM_THRESHOLD:
        if consecutive_danger_frames == ALARM_THRESHOLD:
            threading.Thread(target=send_telegram_alert, args=(img,)).start()
        return "ALARM_ON"
        
    return "NORMAL"

@app.route('/')
def health_check():
    return "AI Drowning Detection Server is Running."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)