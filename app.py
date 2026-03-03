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
from services.line_crossing import LineCrossingDetector, YOLO_AVAILABLE
from services.zone_access import ZoneAccessController, PersonState

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


@app.route('/line-config')
def line_config_page():
    """Line crossing configuration page"""
    return render_template('line_config.html')


@app.route('/zone-config')
def zone_config_page():
    """Interactive zone configuration page"""
    return render_template('zone_config.html')



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
    
    return jsonify({'success': False, 'message': 'Unknown face'})



@app.route('/api/checkin', methods=['POST'])
def api_checkin():
    """API บันทึกเข้าห้องสมุด"""
    data = request.get_json()
    student_id = data.get('student_id')
    
    success, message, log = AttendanceService.check_in(student_id)
    
    if not success:
        return jsonify({'success': False, 'message': message}), 400
        
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
    
    if not success:
        return jsonify({'success': False, 'message': message}), 400
        
    return jsonify({
        'success': True,
        'message': f'Check-out สำเร็จ เวลา {log.check_out.strftime("%H:%M:%S")}',
        'log': log.to_dict()
    })
    
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
    """API ลบนักศึกษา"""
    try:
        student = Student.query.filter_by(student_id=student_id).first()
        if not student:
            return jsonify({'success': False, 'message': 'ไม่พบนักศึกษา'}), 404
        
        # Delete face data
        face_service.delete_face(student_id)
        
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


@app.route('/api/settings/line', methods=['GET', 'POST'])
def api_line_settings():
    """API for getting/setting detection line ratio"""
    if request.method == 'POST':
        data = request.get_json()
        ratio = float(data.get('ratio', 0.4))
        
        # Update both detectors (simplification for user ease)
        entry_detector.set_line_ratio(ratio)
        exit_detector.set_line_ratio(ratio)
        
        return jsonify({'success': True, 'ratio': ratio})
    else:
        # Return current ratio (from entry detector)
        return jsonify({'ratio': entry_detector.line_ratio})


# ==================== Line Crossing Detection API ====================

@app.route('/api/line/<camera_id>/set', methods=['POST'])
def api_set_crossing_line(camera_id):
    """Set the virtual crossing line for a camera."""
    detector = entry_line_detector if camera_id == 'entry' else exit_line_detector
    
    if detector is None:
        return jsonify({'success': False, 'error': 'Line crossing not available'}), 400
    
    data = request.get_json()
    start = (int(data.get('start_x', 0)), int(data.get('start_y', 0)))
    end = (int(data.get('end_x', 640)), int(data.get('end_y', 480)))
    
    detector.set_line(start, end)
    
    return jsonify({
        'success': True,
        'camera_id': camera_id,
        'line': {'start': start, 'end': end}
    })


@app.route('/api/line/<camera_id>/stats', methods=['GET'])
def api_line_stats(camera_id):
    """Get line crossing statistics for a camera."""
    detector = entry_line_detector if camera_id == 'entry' else exit_line_detector
    
    if detector is None:
        return jsonify({
            'available': False,
            'yolo_installed': YOLO_AVAILABLE,
            'message': 'Install ultralytics: pip install ultralytics'
        })
    
    return jsonify(detector.get_stats())


@app.route('/api/line/<camera_id>/events', methods=['GET'])
def api_line_events(camera_id):
    """Get recent crossing events for a camera."""
    detector = entry_line_detector if camera_id == 'entry' else exit_line_detector
    
    if detector is None:
        return jsonify({'events': []})
    
    limit = request.args.get('limit', 20, type=int)
    return jsonify({
        'camera_id': camera_id,
        'events': detector.get_recent_events(limit)
    })


@app.route('/api/line/<camera_id>/reset', methods=['POST'])
def api_reset_line_counters(camera_id):
    """Reset IN/OUT counters for a camera."""
    detector = entry_line_detector if camera_id == 'entry' else exit_line_detector
    
    if detector is None:
        return jsonify({'success': False, 'error': 'Line crossing not available'}), 400
    
    detector.reset_counters()
    return jsonify({'success': True, 'camera_id': camera_id})


# ==================== Zone Access Control API ====================

@app.route('/api/zone/<camera_id>/areas', methods=['GET', 'POST'])
def api_zone_areas(camera_id):
    """Get or set zone rectangular areas."""
    controller = entry_zone_controller if camera_id == 'entry' else exit_zone_controller
    
    if request.method == 'POST':
        data = request.get_json()
        zones_data = data.get('zones', {})
        # Convert string keys back to int
        processed_stats = {int(k): v for k, v in zones_data.items() if v is not None}
        controller.set_areas(processed_stats)
        return jsonify({
            'success': True,
            'zones': controller.zone_areas
        })
    else:
        return jsonify({
            'zones': controller.zone_areas
        })


@app.route('/api/zone/<camera_id>/stats', methods=['GET'])
def api_zone_stats(camera_id):
    """Get zone controller statistics."""
    controller = entry_zone_controller if camera_id == 'entry' else exit_zone_controller
    return jsonify(controller.get_stats())


# ==================== Camera Streaming with Face Detection ====================

class FaceDetectionOverlay:
    """Robust face detection using OpenCV YuNet (Deep Learning)"""
    
    def __init__(self):
        # Load YuNet model (Deep Learning based, high accuracy)
        model_path = 'face_detection_yunet_2023mar.onnx'
        if not os.path.exists(model_path):
            print("Warning: YuNet model not found, downloading...")
            # Fallback or strict error handling could go here
        
        self.detector = cv2.FaceDetectorYN.create(
            model=model_path,
            config="",
            input_size=(320, 320), # Initial size, updated per frame
            score_threshold=0.6,   # High confidence to avoid walls/curtains
            nms_threshold=0.3,
            top_k=5000,
            backend_id=cv2.dnn.DNN_BACKEND_OPENCV,
            target_id=cv2.dnn.DNN_TARGET_CPU
        )
        self.last_faces = []
        
        # Load line position from config
        self.config_file = 'line_config.json'
        self.line_ratio = self.load_line_ratio()

    def load_line_ratio(self):
        """Load line ratio from config file"""
        import json
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    return config.get('line_ratio', 0.4)
        except Exception as e:
            print(f"Error loading line config: {e}")
        return 0.4

    def set_line_ratio(self, ratio):
        """Update line ratio and save to config"""
        import json
        self.line_ratio = max(0.1, min(0.9, ratio)) # Clamp between 10% and 90%
        try:
            with open(self.config_file, 'w') as f:
                json.dump({'line_ratio': self.line_ratio}, f)
        except Exception as e:
            print(f"Error saving line config: {e}")
    
    def detect_faces(self, frame):
        """Detect faces using YuNet"""
        height, width, _ = frame.shape
        
        # YuNet requires updating input size if frame size changes
        self.detector.setInputSize((width, height))
        
        # Detect
        # results = (1, faces_array) where faces_array is [x, y, w, h,...]
        _, faces_data = self.detector.detect(frame)
        
        faces = []
        if faces_data is not None:
            for face in faces_data:
                # YuNet returns bounding box as first 4 elements: x, y, w, h
                # Also returns confidence at index 14
                confidence = face[14]
                if confidence >= 0.6:
                    x, y, w, h = map(int, face[:4])
                    faces.append((x, y, w, h))
        
        self.last_faces = faces
        return faces
    def draw_overlay(self, frame, is_entry=True, zone_controller=None):
        """Draw face detection boxes and zone areas on frame"""
        height, width = frame.shape[:2]
        
        # Detect faces
        faces = self.detect_faces(frame)
        
        # Draw bounding boxes around faces
        for (x, y, w, h) in faces:
            # Green box for detected face
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 3)
            
            # Face label
            cv2.putText(frame, "FACE DETECTED", (x, y-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Draw Zone Areas
        if zone_controller:
            colors = {
                1: (128, 128, 128), # Gray - Detection
                2: (255, 255, 0),   # Cyan - Intent
                3: (0, 255, 255)    # Yellow - Auth
            }
            names = {1: "DETECTION", 2: "INTENT", 3: "AUTH"}
            
            for zone_id, points in zone_controller.zone_areas.items():
                if points and isinstance(points, list) and len(points) >= 2:
                    # points is list of [x, y] normalized
                    # Convert to pixel coordinates
                    pts = np.array([
                        [int(p[0] * width), int(p[1] * height)] 
                        for p in points
                    ], np.int32)
                    pts = pts.reshape((-1, 1, 2))
                    
                    color = colors.get(zone_id, (255, 255, 255))
                    # Draw polygon
                    cv2.polylines(frame, [pts], True, color, 2)
                    
                    # Label at the first point
                    lx, ly = pts[0][0]
                    cv2.putText(frame, f"ZONE {zone_id}: {names.get(zone_id)}", (lx + 5, ly + 20),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Status text
        status_text = f"Faces: {len(faces)}"
        cv2.putText(frame, status_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        return frame


# Face detection overlays for each camera
entry_detector = FaceDetectionOverlay()
exit_detector = FaceDetectionOverlay()

# Line crossing detectors for each camera
entry_line_detector = None
exit_line_detector = None
if YOLO_AVAILABLE:
    try:
        entry_line_detector = LineCrossingDetector("entry", model_path="yolov8n.pt")
        exit_line_detector = LineCrossingDetector("exit", model_path="yolov8n.pt")
    except Exception as e:
        print(f"Line crossing detector initialization failed: {e}")

# Zone-based access controllers for each camera
entry_zone_controller = ZoneAccessController("entry")
exit_zone_controller = ZoneAccessController("exit")


class CameraStream:
    """RTSP camera stream handler - fixed for FFmpeg threading issues"""
    def __init__(self, url):
        self.url = url
        self.lock = threading.Lock()
        self.frame = None
        self.running = False
        self.thread = None
        
    def start(self):
        with self.lock:
            if self.running:
                return
            self.running = True
        
        def capture_loop():
            # Use CAP_FFMPEG with specific options to avoid async issues
            import os
            os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp'
            
            cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            while self.running:
                try:
                    if cap.isOpened():
                        ret, frame = cap.read()
                        if ret:
                            with self.lock:
                                self.frame = frame
                        else:
                            # Reconnect on failure
                            cap.release()
                            time.sleep(1)
                            cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
                            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    else:
                        time.sleep(1)
                        cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception as e:
                    print(f"Camera error: {e}")
                    time.sleep(1)
            
            cap.release()
        
        self.thread = threading.Thread(target=capture_loop, daemon=True)
        self.thread.start()
        
    def get_frame(self):
        with self.lock:
            if self.frame is not None:
                return self.frame.copy()
        return None
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)

# Initialize camera streams (lazy - will start when first accessed)
entry_camera = CameraStream(Config.ENTRY_CAMERA_URL)
exit_camera = CameraStream(Config.EXIT_CAMERA_URL)


def generate_frames_with_detection(camera, detector, zone_controller, is_entry=True):
    """Generate MJPEG frames with face detection and zone overlay"""
    camera.start()
    # Wait for camera to start and get first frame
    for _ in range(50):  # Wait up to 5 seconds
        if camera.get_frame() is not None:
            break
        time.sleep(0.1)
    
    frame_count = 0
    MAX_WIDTH = 800
    
    while True:
        frame = camera.get_frame()
        if frame is not None:
            # Resize if too big (reduces bandwidth usage significantly)
            h, w = frame.shape[:2]
            if w > MAX_WIDTH:
                scale = MAX_WIDTH / w
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
            
            # Only run detection every 3 frames for better performance
            if frame_count % 3 == 0:
                # Update zone controller with detections
                h, w = frame.shape[:2]
                faces = detector.detect_faces(frame)
                
                # Use faces as person detections (for now, until YOLO is fully integrated here)
                # BBoxes are (x, y, w, h) -> convert to (x1, y1, x2, y2)
                bboxes = [(x, y, x+w, y+h) for (x, y, w, h) in faces]
                
                # Update zone state machine
                auth_needed = zone_controller.update(bboxes, w, h, frame)
                
                # Handle Auth Trigger (Zone 3)
                for person in auth_needed:
                    if not person.auth_completed and person.state == PersonState.AUTH:
                        # Try to recognize face from buffered frames
                        if person.face_frames:
                            # Use last frame for recognition
                            top_frame = person.face_frames[-1]
                            found, student_id, confidence = face_service.recognize_face_image(top_frame)
                            if found and confidence >= 0.75:
                                # Successful recognition -> Trigger Check-in/out
                                zone_controller.complete_auth(person, student_id, confidence)
                                
                                # Call AttendanceService
                                with app.app_context():
                                    if is_entry:
                                        AttendanceService.check_in(student_id)
                                    else:
                                        AttendanceService.check_out(student_id)
                
                # Draw overlay
                frame = detector.draw_overlay(frame, is_entry, zone_controller)
            else:
                # Draw cached overlays for performance
                # Draw zones
                frame = detector.draw_overlay(frame, is_entry, zone_controller)
            
            frame_count += 1
            # Reduce JPEG quality to 70 for performance
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        
        time.sleep(0.05)  # ~20 FPS (Stable)


@app.route('/video/entry')
def video_entry():
    """Stream entry camera feed with face detection overlay"""
    return Response(generate_frames_with_detection(entry_camera, entry_detector, entry_zone_controller, is_entry=True),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/video/exit')
def video_exit():
    """Stream exit camera feed with face detection overlay"""
    return Response(generate_frames_with_detection(exit_camera, exit_detector, exit_zone_controller, is_entry=False),
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
        print(f"🚀 Face Scanner is running!")
        print(f"🏠 Local:   http://localhost:5000")
        print(f"🌐 Network: http://{local_ip}:5000")
        print("="*50 + "\n")
    except Exception:
        print("🚀 Face Scanner is running on http://localhost:5000")

    # use_reloader=False prevents duplicate processes that cause FFmpeg issues
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False, threaded=True)

