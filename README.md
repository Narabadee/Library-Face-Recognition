# 🛡️ AI Face Recognition Library Gate System

ระบบตรวจสอบใบหน้าเข้า-ออกห้องสมุดอัตโนมัติ เชื่อมต่อกับกล้อง IP Camera (RTSP) และชุดควบคุมประตู (ESP32 Gate Controller)

## 🏗️ System Architecture

ระบบประกอบด้วย 3 ส่วนหลักทำงานร่วมกัน:
1.  **Flask Server (Central Brain)**: ประมวลผลใบหน้าด้วย AI (ArcFace + YuNet) และจัดการฐานข้อมูล PostgreSQL
2.  **RTSP Camera (Eyes)**: ส่งสัญญาณภาพผ่านโปรโตคอล UDP โดยใช้ FFmpeg เพื่อความเสถียรสูงสุด
3.  **ESP32 Controller (Hand)**: รับคำสั่งจาก Server เพื่อเปิด-ปิดประตู และแสดงสถานะผ่านไฟ LED

---

## 🔌 Hardware Setup

### 1. ESP32 Gate Controller
เชื่อมต่อ LED/Relay เข้ากับขา GPIO ดังนี้:
*   **Pin 14**: ไฟสีแดง (Red LED) - แสดงสถานะ **Waiting/Idle**
*   **Pin 13**: ไฟสีเขียว (Green LED) - แสดงสถานะ **Success/Open**

**Logic การทำงาน:**
*   **สถานะปกติ (Waiting)**: ไฟสีแดงติดค้าง (ON) / ไฟสีเขียวดับ (OFF)
*   **เมื่อสแกนผ่าน (Success)**: ไฟสีแดงดับ / ไฟสีเขียวติดค้าง 3 วินาที แล้วกลับสู่สถานะปกติ

### 2. Camera
*   ใช้กล้องที่รองรับโปรโตคอล **RTSP**
*   แนะนำให้ตั้งค่ากล้องเป็น **Sub-stream** เพื่อลดภาระการประมวลผล

---

## ⚙️ Installation Guide (แบบละเอียด)

### 1. การเตรียมระบบ Server (Windows)

#### **A. ติดตั้งซอฟต์แวร์พื้นฐาน**
1.  **Python 3.10+**: ดาวน์โหลดจาก [python.org](https://www.python.org/) (ติ๊กถูกที่ "Add Python to PATH" ตอนติดตั้งด้วย)
2.  **PostgreSQL**: ติดตั้งและสร้าง Database ชื่อ `library_db` 
3.  **FFmpeg**: 
    *   ดาวน์โหลด build จาก [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)
    *   แตกไฟล์ไว้ที่ `C:\ffmpeg`
    *   เพิ่ม `C:\ffmpeg\bin` ใน **System Environment Variables (PATH)**

#### **B. ตั้งค่าโปรเจค**
1.  **Clone โปรเจค**:
    ```bash
    git clone https://github.com/your-repo/Library-Face-Recognition.git
    cd Library-Face-Recognition
    ```
2.  **สร้าง Virtual Environment**:
    ```bash
    python -m venv .venv
    .venv\Scripts\activate
    ```
3.  **ติดตั้ง Library**:
    ```bash
    pip install -r requirements.txt
    ```

---

### 2. การเตรียมตัวควบคุมประตู (ESP32)

1.  **Arduino IDE**: ติดตั้งโปรแกรม [Arduino IDE](https://www.arduino.cc/en/software)
2.  **Board Setup**: 
    *   ไปที่ File > Preferences ใส่ URL นี้ใน "Additional Boards Manager URLs": `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
    *   ไปที่ Tools > Board > Manager ค้นหา "esp32" และกด Install
3.  **Configuration**: 
    *   เปิดไฟล์ `ESP32_Gate_Controller.ino`
    *   แก้ไข `ssid` และ `password` ให้เป็นของ Wi-Fi ที่คุณใช้
4.  **Upload**: 
    *   เชื่อมต่อ ESP32 เข้ากับคอมพิวเตอร์
    *   เลือก Board (เช่น DOIT ESP32 DEVKIT V1) และ Port ให้ถูกต้อง
    *   กดปุ่ม **Upload**
5.  **Check IP**: เปิด **Serial Monitor** (115200 baud) เพื่อดู IP Address ที่ได้รับ (เช่น `192.168.0.119`)

---

### 3. การเชื่อมต่อระบบเข้าด้วยกัน

1.  เปิดไฟล์ `config.py` และอัปเดตข้อมูล:
    *   `SQLALCHEMY_DATABASE_URI`: ใส่ user/password ของ PostgreSQL
    *   `ENTRY_CAMERA_URL`: ใส่ URL RTSP ของกล้องคุณ
    *   `ESP32_URL`: ใส่ IP ของ ESP32 (เช่น `http://192.168.0.119`)
2.  รันเซิร์ฟเวอร์:
    ```bash
    python app.py
    ```

---

## 🚀 Usage (ขั้นตอนการใช้งาน)
1.  เปิด Browser ไปที่ `http://localhost:5000`
2.  **ลงทะเบียน**: ไปที่เมนู "ลงทะเบียน" ถ่ายรูปหน้าตรงและด้านข้าง
3.  **สแกนเข้า**: ไปที่หน้า "Scan Entry" กล้อง RTSP จะเริ่มทำงาน
4.  **อัตโนมัติ**: เมื่อ AI จำใบหน้าได้:
    *   บันทึกลง Database
    *   ส่งคำสั่งไป ESP32 -> ไฟเขียวติด 3 วินาที (ประตูเปิด) -> กลับเป็นไฟแดง (ประตูปิด)

---

## 📊 Feature Highlights
*   **ONNX Acceleration**: ใช้โมเดล RetinaFace และ ArcFace ผ่าน ONNX Runtime เพื่อความเร็วสูงสุด
*   **FFmpeg Subprocess**: ดึงภาพผ่าน FFmpeg UDP โดยตรง แก้ปัญหา Delay และจอดำ
*   **Multi-angle Registration**: ระบบลงทะเบียน 3 มุมมองเพื่อความแม่นยำสูงสุด
*   **Responsive Dashboard**: ดูสถิติและประวัติการเข้าใช้งานได้แบบ Real-time
