import cv2
import numpy as np
import requests
from flask import Flask, request
from ultralytics import YOLO
import threading
import os

# Khởi tạo mô hình AI
model = YOLO('yolov8n-pose.pt')
app = Flask(__name__)

# --- BIẾN ĐIỀU KHIỂN LOGIC ---
consecutive_danger_frames = 0
ALARM_THRESHOLD = 3      # Nhịp 3: Gửi Telegram & ESP32 bật còi
CALL_THRESHOLD = 5       # Nhịp 5: Gọi điện IFTTT
telegram_sent = False    
call_made = False        

# --- BẢO MẬT API (Lấy từ biến môi trường của Render) ---
# Nếu trên Render chưa cài biến, nó sẽ tự động lấy thông số dự phòng ở vế sau
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8500045096:AAHn2BXNgeGP798VgGGY3wb7BrLG-KDXqjo")
CHAT_ID = os.getenv("CHAT_ID", "8691477584")
IFTTT_KEY = os.getenv("IFTTT_KEY", "NMGdOo9ym6WkUV4-wunLERHR_SMM4D78k1onpn6T8q")
EVENT_NAME = "canh_bao_co_nguoi_duoi_nuoc"

def make_voice_call():
    """Kích hoạt cuộc gọi VoIP khẩn cấp qua IFTTT"""
    try:
        url = f"https://maker.ifttt.com/trigger/{EVENT_NAME}/with/key/{IFTTT_KEY}"
        requests.get(url)
        print("Đã phát lệnh gọi điện IFTTT!")
    except Exception as e:
        print(f"Lỗi gọi IFTTT: {e}")

def send_telegram_alert(image_matrix):
    """Gửi ảnh hiện trường qua Telegram"""
    try:
        _, img_encoded = cv2.imencode('.jpg', image_matrix)
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        caption = "🚨 CẢNH BÁO TỐI KHẨN: PHÁT HIỆN ĐUỐI NƯỚC! 🚨\nHệ thống đang kích hoạt còi hú tại hiện trường."
        data = {"chat_id": CHAT_ID, "caption": caption}
        files = {"photo": ("alert.jpg", img_encoded.tobytes(), "image/jpeg")}
        requests.post(url, data=data, files=files)
        print("Đã gửi ảnh Telegram.")
    except Exception as e:
        print(f"Lỗi gửi Telegram: {e}")

@app.route('/upload', methods=['POST'])
def upload():
    global consecutive_danger_frames, telegram_sent, call_made
    
    # Nhận ảnh nhị phân từ mạch ESP32-CAM
    npimg = np.frombuffer(request.data, np.uint8)
    if npimg.size == 0: return "Error", 400
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    
    results = model(img)
    danger_detected = False
    
    for r in results:
        if hasattr(r, 'keypoints') and r.keypoints is not None:
            for kpts in r.keypoints.xy:
                if len(kpts) >= 13:
                    nose_y = kpts[0][1].item()
                    l_eye_y, r_eye_y = kpts[1][1].item(), kpts[2][1].item()
                    l_shoulder_y, r_shoulder_y = kpts[5][1].item(), kpts[6][1].item()
                    mid_shoulder_y = (l_shoulder_y + r_shoulder_y) / 2
                    l_wrist_y, r_wrist_y = kpts[9][1].item(), kpts[10][1].item()
                    
                    # Logic nhận diện hành vi vung vẩy chới với
                    is_flailing = (0 < l_wrist_y < mid_shoulder_y) or (0 < r_wrist_y < mid_shoulder_y)
                    is_head_tilted = (nose_y < l_eye_y) and (nose_y < r_eye_y)

                    if is_flailing or is_head_tilted:
                        danger_detected = True

    # Quản lý nhịp độ
    if danger_detected:
        consecutive_danger_frames += 1
    else:
        consecutive_danger_frames = 0
        telegram_sent = False
        call_made = False 
        return "NORMAL"

    # Xử lý các cấp độ cảnh báo
    if consecutive_danger_frames == ALARM_THRESHOLD and not telegram_sent:
        threading.Thread(target=send_telegram_alert, args=(img.copy(),)).start()
        telegram_sent = True

    if consecutive_danger_frames == CALL_THRESHOLD and not call_made:
        threading.Thread(target=make_voice_call).start()
        call_made = True
        
    # Trả lệnh về cho ESP32-CAM nếu chạm ngưỡng hú còi
    if consecutive_danger_frames >= ALARM_THRESHOLD:
        return "ALARM_ON"

    return "NORMAL"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
