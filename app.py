from flask import Flask, render_template, request, jsonify, redirect, url_for, Response, send_from_directory
import cv2
import threading
import time
import numpy as np
import os
from datetime import datetime, date
from config import Config
from database import db, Student, AttendanceLog
from services.face_service import FaceService
from services.attendance_service import AttendanceService
from services.camera import RTSPCamera
import requests
import threading

app = Flask(__name__)
app.config.from_object(Config)
Config.init_app(app)
db.init_app(app)

# Initialize face service
face_service = FaceService(Config.FACES_FOLDER)

# Create tables
with app.app_context():
    db.create_all()

# #6 perf: server-side recognition cache (3s TTL)
_scan_cache: dict = {}  # {student_id: (result_dict, expire_ts)}
_scan_cache_lock = threading.Lock()
SCAN_CACHE_TTL = 3.0  # seconds


# ==================== Web Routes ====================

@app.route('/')
def index():
    """Dashboard หน้าหลัก"""
    # สถิติวันนี้
    today = date.today()
    today_logs = AttendanceLog.query.filter_by(date=today).all()
    
    # นับจำนวน
    total_students = Student.query.count()
    today_checkins = len(today_logs)
    currently_inside = sum(1 for log in today_logs if log.check_out is None)
    
    # Recent activity
    recent_logs = AttendanceLog.query.order_by(AttendanceLog.id.desc()).limit(10).all()
    
    return render_template('index.html',
                         total_students=total_students,
                         today_checkins=today_checkins,
                         currently_inside=currently_inside,
                         recent_logs=recent_logs)


@app.route('/register', methods=['GET'])
def register_page():
    """หน้าลงทะเบียนนักศึกษา"""
    return render_template('register.html')


@app.route('/scan')
def scan_page():
    """หน้าสแกนใบหน้า (ปกติ)"""
    return render_template('scan.html')


@app.route('/scan/entry')
def scan_entry_page():
    """หน้าสแกนทางเข้า - Check-in อัตโนมัติ"""
    return render_template('scan_entry.html')



@app.route('/scan/exit')
def scan_exit_page():
    """หน้าสแกนทางออก - Check-out อัตโนมัติ"""
    return render_template('scan_exit.html')




@app.route('/history')
def history_page():
    """หน้าประวัติการใช้งาน"""
    # Get filter parameters
    student_id = request.args.get('student_id', '')
    date_filter = request.args.get('date', '')
    
    query = AttendanceLog.query
    
    if student_id:
        student = Student.query.filter_by(student_id=student_id).first()
        if student:
            query = query.filter_by(student_id=student.id)
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter_by(date=filter_date)
        except ValueError:
            pass
    
    logs = query.order_by(AttendanceLog.date.desc(), AttendanceLog.check_in.desc()).limit(100).all()
    students = Student.query.all()
    
    return render_template('history.html', logs=logs, students=students,
                         filter_student_id=student_id, filter_date=date_filter)


@app.route('/students')
def students_page():
    """หน้าจัดการนักศึกษา"""
    students = Student.query.all()
    return render_template('students.html', students=students)


# ==================== API Routes ====================

@app.route('/api/register', methods=['POST'])
def api_register():
    """API ลงทะเบียนนักศึกษาใหม่"""
    data = request.get_json()
    
    student_id = data.get('student_id', '').strip()
    name = data.get('name', '').strip()
    face_image = data.get('face_image', '')
    
    # Validation
    if not student_id or not name:
        return jsonify({'success': False, 'message': 'กรุณากรอกข้อมูลให้ครบ'}), 400
    
    if not face_image:
        return jsonify({'success': False, 'message': 'กรุณาถ่ายรูปใบหน้า'}), 400
    
    # Check if student already exists
    existing = Student.query.filter_by(student_id=student_id).first()
    if existing:
        return jsonify({'success': False, 'message': 'รหัสนักศึกษานี้มีอยู่ในระบบแล้ว'}), 400
    
    # Register face
    success, message = face_service.register_face(face_image, student_id)
    if not success:
        return jsonify({'success': False, 'message': message}), 400
    
    # Create student record
    student = Student(
        student_id=student_id,
        name=name,
        face_encoding_path=f"{student_id}.pkl"
    )
    db.session.add(student)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'ลงทะเบียนสำเร็จ', 'student': student.to_dict()})


@app.route('/api/register-multi', methods=['POST'])
def api_register_multi():
    """API ลงทะเบียนนักศึกษาใหม่ แบบหลายมุม (Multi-Angle)"""
    data = request.get_json()
    
    student_id = data.get('student_id', '').strip()
    name = data.get('name', '').strip()
    face_images = data.get('face_images', [])
    
    # Validation
    if not student_id or not name:
        return jsonify({'success': False, 'message': 'กรุณากรอกข้อมูลให้ครบ'}), 400
    
    if not face_images or len(face_images) < 3:
        return jsonify({'success': False, 'message': 'กรุณาถ่ายรูปใบหน้าให้ครบทุกมุม (3 มุม)'}), 400
    
    # Check if student already exists
    existing = Student.query.filter_by(student_id=student_id).first()
    if existing:
        return jsonify({'success': False, 'message': 'รหัสนักศึกษานี้มีอยู่ในระบบแล้ว'}), 400
    
    # Register face with multiple images
    success, message = face_service.register_face_multi(face_images, student_id)
    if not success:
        return jsonify({'success': False, 'message': message}), 400
    
    # Create student record
    student = Student(
        student_id=student_id,
        name=name,
        face_encoding_path=f"{student_id}.pkl"
    )
    db.session.add(student)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'ลงทะเบียนหลายมุมสำเร็จ', 'student': student.to_dict()})


@app.route('/api/check-pose', methods=['POST'])
def api_check_pose():
    """API ตรวจจับท่าทางใบหน้า – returns yaw/pitch for auto-capture"""
    import base64 as b64module
    data = request.get_json()
    face_image = data.get('face_image', '')
    source = data.get('source', '')  # 'entry' or 'exit' for server-side capture
    
    cv_image = None
    
    # Server-side capture from RTSP camera
    if source in ('entry', 'exit'):
        camera = entry_camera if source == 'entry' else exit_camera
        camera.start()
        # Wait for frame to be available
        frame = None
        for _ in range(30):  # Wait up to 3 seconds
            frame = camera.get_frame()
            if frame is not None:
                break
            time.sleep(0.1)
            
        if frame is not None:
            cv_image = frame.copy()
        else:
            return jsonify({'face_detected': False, 'error': 'Camera not ready'})
    elif face_image:
        try:
            b64_data = face_image.split(',', 1)[1] if ',' in face_image else face_image
            img_bytes = b64module.b64decode(b64_data)
            nparr = np.frombuffer(img_bytes, np.uint8)
            cv_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as e:
            return jsonify({'face_detected': False, 'error': str(e)})
    
    if cv_image is None:
        return jsonify({'face_detected': False})
    
    try:
        # Resize for speed
        h, w = cv_image.shape[:2]
        max_dim = 320
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            cv_image = cv2.resize(cv_image, (int(w * scale), int(h * scale)))
        
        # Detect faces using the engine
        detections = face_service.engine.detect_faces(cv_image)
        
        if not detections:
            return jsonify({'face_detected': False})
        
        # Use largest face
        primary = max(detections, key=lambda d: d.width * d.height)
        
        yaw, pitch = 0.0, 0.0
        if primary.landmarks is not None and len(primary.landmarks) >= 5:
            yaw, pitch = face_service.engine._estimate_pose(primary.landmarks)
        
        return jsonify({
            'face_detected': True,
            'yaw': round(yaw, 1),
            'pitch': round(pitch, 1),
            'face_width': int(primary.width),
            'face_height': int(primary.height)
        })
        
    except Exception as e:
        return jsonify({'face_detected': False, 'error': str(e)})


# Strict Mode disabled
STRICT_MODE = False

@app.route('/api/scan', methods=['POST'])
def api_scan():
    """
    API for recognizing a face.
    data = {'face_image': 'base64_string'}
    """
    data = request.get_json()
    face_image = data.get('face_image')
    
    if not face_image:
        return jsonify({'success': False, 'message': 'No image data'})
    
    # Recognize face
    found, student_id, confidence = face_service.recognize_face(face_image)
    
    if found:
        # #6 perf: check server-side cache first
        now = time.time()
        with _scan_cache_lock:
            cached = _scan_cache.get(student_id)
            if cached and now < cached[1]:
                return jsonify(cached[0])

        # Use Service to get status (Fixes 500 Error and encapsulates logic)
        status, student, last_log = AttendanceService.get_student_status(student_id)
        
        if student:
            result = {
                'success': True,
                'student': student.to_dict(),
                'confidence': float(confidence),
                'status': status
            }
            # #6 perf: cache result
            with _scan_cache_lock:
                _scan_cache[student_id] = (result, now + SCAN_CACHE_TTL)
            return jsonify(result)
            
    # Check if a face was actually detected even if not recognized
    face_detected = False
    if confidence > 0.0:
        face_detected = True
    else:
        import cv2
        import numpy as np
        import base64 as b64module
        try:
            b64_data = face_image.split(',', 1)[1] if ',' in face_image else face_image
            img_bytes = b64module.b64decode(b64_data)
            nparr = np.frombuffer(img_bytes, np.uint8)
            cv_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if cv_image is not None:
                h, w = cv_image.shape[:2]
                max_dim = 320
                if max(h, w) > max_dim:
                    scale = max_dim / max(h, w)
                    cv_image = cv2.resize(cv_image, (int(w * scale), int(h * scale)))
                detections = face_service.engine.detect_faces(cv_image)
                if detections:
                    face_detected = True
        except Exception as e:
            print(f"Error detecting face in scan: {e}")

    if face_detected:
        def notify_esp_fail():
            try:
                import requests
                from config import Config
                requests.post(f"{Config.ESP32_URL}/trigger/fail", timeout=2)
            except Exception as e:
                print(f"Failed to trigger ESP32 fail: {e}")
        import threading
        threading.Thread(target=notify_esp_fail, daemon=True).start()
    
    return jsonify({'success': False, 'message': 'Unknown face', 'face_detected': face_detected})



@app.route('/api/checkin', methods=['POST'])
def api_checkin():
    """API บันทึกเข้าห้องสมุด"""
    data = request.get_json()
    student_id = data.get('student_id')
    
    success, message, log = AttendanceService.check_in(student_id)
    
    def notify_esp_fail():
        try:
            requests.post(f"{Config.ESP32_URL}/trigger/fail", timeout=2)
        except:
            pass

    def notify_esp_success():
        try:
            requests.post(f"{Config.ESP32_URL}/trigger/success", timeout=2)
        except:
            pass

    if not success:
        # ส่ง trigger fail ไป ESP32 แบบ background
        threading.Thread(target=notify_esp_fail, daemon=True).start()
        return jsonify({'success': False, 'message': message}), 400
        
    # ส่ง trigger success ไป ESP32 แบบ background
    threading.Thread(target=notify_esp_success, daemon=True).start()
    
    return jsonify({
        'success': True,
        'message': f'Check-in สำเร็จ เวลา {log.check_in.strftime("%H:%M:%S")}',
        'log': log.to_dict()
    })


@app.route('/api/checkout', methods=['POST'])
def api_checkout():
    """API บันทึกออกจากห้องสมุด"""
    data = request.get_json()
    student_id = data.get('student_id')
    
    success, message, log = AttendanceService.check_out(student_id)
    
    def notify_esp_fail():
        try:
            requests.post(f"{Config.ESP32_URL}/trigger/fail", timeout=2)
        except:
            pass

    def notify_esp_success():
        try:
            requests.post(f"{Config.ESP32_URL}/trigger/success", timeout=2)
        except:
            pass

    if not success:
        threading.Thread(target=notify_esp_fail, daemon=True).start()
        return jsonify({'success': False, 'message': message}), 400
        
    threading.Thread(target=notify_esp_success, daemon=True).start()
    
    return jsonify({
        'success': True,
        'message': f'Check-out สำเร็จ เวลา {log.check_out.strftime("%H:%M:%S")}',
        'log': log.to_dict()
    })


@app.route('/api/students', methods=['GET'])
def api_students():
    """API ดึงรายชื่อนักศึกษาทั้งหมด"""
    students = Student.query.all()
    return jsonify([s.to_dict() for s in students])


@app.route('/api/student_image/<student_id>')
def serve_student_image(student_id):
    """Serve student face image"""
    filename = f"{student_id}.jpg"
    return send_from_directory(face_service.faces_folder, filename)


@app.route('/api/students/<student_id>', methods=['DELETE'])
def api_delete_student(student_id):
    """API ลบนนักศึกษา"""
    try:
        student = Student.query.filter_by(student_id=student_id).first()
        if not student:
            return jsonify({'success': False, 'message': 'ไม่พบนักศึกษา'}), 404
        
        # Delete face data
        face_service.delete_face(student_id)
        
        # #6 perf: clear server-side scan cache
        with _scan_cache_lock:
            if student_id in _scan_cache:
                del _scan_cache[student_id]
        
        # Delete attendance logs
        AttendanceLog.query.filter_by(student_id=student.id).delete()
        
        # Delete student
        db.session.delete(student)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'ลบนักศึกษาสำเร็จ'})
    except Exception as e:
        db.session.rollback()
        print(f"Delete student error: {e}")
        return jsonify({'success': False, 'message': f'ไม่สามารถลบข้อมูลได้: {str(e)}'}), 500


@app.route('/api/stats')
def api_stats():
    """API สถิติการใช้งาน"""
    today = date.today()
    
    return jsonify({
        'total_students': Student.query.count(),
        'today_checkins': AttendanceLog.query.filter_by(date=today).count(),
        'currently_inside': AttendanceLog.query.filter_by(date=today, check_out=None).count()
    })


@app.route('/api/danger/reset-database', methods=['POST'])
def api_reset_database():
    """API ล้างฐานข้อมูลทั้งหมด (อันตราย!)"""
    try:
        # 1. Delete all database records (using TRUNCATE or bulk delete)
        # We'll use bulk delete for compatibility
        AttendanceLog.query.delete()
        Student.query.delete()
        db.session.commit()
        
        # 2. Reset face service (clears images and encodings)
        face_service.reset_all()
        
        # 3. Clear server-side scan cache
        with _scan_cache_lock:
            _scan_cache.clear()
            
        logger.info("SYSTEM RESET: All data wiped successfully")
        return jsonify({'success': True, 'message': 'ล้างข้อมูลสำเร็จและรีเซ็ตระบบ AI เรียบร้อยแล้ว'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Reset error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500



# ==================== Camera Streaming with Face Detection ====================

class FaceDetectionOverlay:
    """Face detection overlay for camera streams using YuNet"""

    def __init__(self):
        model_path = 'face_detection_yunet_2023mar.onnx'
        self.detector = cv2.FaceDetectorYN.create(
            model=model_path,
            config="",
            input_size=(320, 320),
            score_threshold=0.6,
            nms_threshold=0.3,
            top_k=5000,
            backend_id=cv2.dnn.DNN_BACKEND_OPENCV,
            target_id=cv2.dnn.DNN_TARGET_CPU
        )
        self.last_faces = []

    def detect_faces(self, frame):
        """Detect faces using YuNet"""
        height, width, _ = frame.shape
        self.detector.setInputSize((width, height))
        _, faces_data = self.detector.detect(frame)
        faces = []
        if faces_data is not None:
            for face in faces_data:
                confidence = face[14]
                if confidence >= 0.6:
                    x, y, w, h = map(int, face[:4])
                    faces.append((x, y, w, h))
        self.last_faces = faces
        return faces

    def draw_overlay(self, frame):
        """Draw face detection boxes on frame"""
        faces = self.detect_faces(frame)
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)
            cv2.putText(frame, "FACE", (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(frame, f"Faces: {len(faces)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        return frame


# Face detection overlays for each camera
entry_detector = FaceDetectionOverlay()
exit_detector = FaceDetectionOverlay()



# Initialize camera streams using FFmpeg subprocess (lazy - will start when first accessed)
entry_camera = RTSPCamera(Config.ENTRY_CAMERA_URL)
exit_camera = RTSPCamera(Config.EXIT_CAMERA_URL)


def generate_frames_with_detection(camera, detector, is_entry=True):
    """Generate MJPEG frames with face detection overlay"""
    camera.start()
    for _ in range(50):
        if camera.get_frame() is not None:
            break
        time.sleep(0.1)

    frame_count = 0
    MAX_WIDTH = 800

    while True:
        frame = camera.get_frame()
        if frame is not None:
            h, w = frame.shape[:2]
            if w > MAX_WIDTH:
                scale = MAX_WIDTH / w
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

            if frame_count % 3 == 0:
                frame = detector.draw_overlay(frame)

            frame_count += 1
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

        time.sleep(0.05)  # ~20 FPS



@app.route('/video/entry')
def video_entry():
    """Stream entry camera feed with face detection overlay"""
    return Response(generate_frames_with_detection(entry_camera, entry_detector, is_entry=True),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/video/exit')
def video_exit():
    """Stream exit camera feed with face detection overlay"""
    return Response(generate_frames_with_detection(exit_camera, exit_detector, is_entry=False),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/capture/entry', methods=['POST'])
def capture_entry():
    """Capture single frame from entry camera for face recognition"""
    import base64
    entry_camera.start()
    # Wait for frame to be available
    for _ in range(30):  # Wait up to 3 seconds
        frame = entry_camera.get_frame()
        if frame is not None:
            break
        time.sleep(0.1)
    
    if frame is not None:
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret:
            img_data = base64.b64encode(buffer).decode('utf-8')
            return jsonify({'success': True, 'image': f'data:image/jpeg;base64,{img_data}'})
    return jsonify({'success': False, 'message': 'Failed to capture frame'})


@app.route('/api/capture/exit', methods=['POST'])
def capture_exit():
    """Capture single frame from exit camera for face recognition"""
    import base64
    exit_camera.start()
    # Wait for frame to be available
    for _ in range(30):  # Wait up to 3 seconds
        frame = exit_camera.get_frame()
        if frame is not None:
            break
        time.sleep(0.1)
    
    if frame is not None:
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret:
            img_data = base64.b64encode(buffer).decode('utf-8')
            return jsonify({'success': True, 'image': f'data:image/jpeg;base64,{img_data}'})
    return jsonify({'success': False, 'message': 'Failed to capture frame'})


if __name__ == '__main__':
    # Print local network URL for easier demo access
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        print("\n" + "="*50)
        print(f"[OK] Face Scanner is running!")
        print(f"[>>] Local:   http://localhost:5000")
        print(f"[>>] Network: http://{local_ip}:5000")
        print("="*50 + "\n")
    except Exception:
        print("[OK] Face Scanner is running on http://localhost:5000")

    # use_reloader=False prevents duplicate processes that cause FFmpeg issues
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False, threaded=True)

