from flask import Flask, request

app = Flask(__name__)
trang_thai_he_thong = "NORMAL"

@app.route('/status', methods=['GET'])
def get_status():
    # ESP32 sẽ liên tục gọi vào đây để xem có phải hú còi không
    return trang_thai_he_thong

@app.route('/set_status', methods=['POST'])
def set_status():
    global trang_thai_he_thong
    # Laptop sẽ gọi vào đây để báo cáo tình hình
    trang_thai_he_thong = request.form.get('status', 'NORMAL')
    return "OK", 200

if __name__ == '__main__':
    # Render yêu cầu port 10000
    app.run(host='0.0.0.0', port=10000)
