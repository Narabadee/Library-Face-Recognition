import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'library-face-scanner-secret-key'
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # Database
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:1234@localhost:5432/library_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Face data storage
    FACES_FOLDER = os.path.join(BASE_DIR, 'data', 'faces')
    
    # RTSP Camera URLs
    ENTRY_CAMERA_URL = os.environ.get('ENTRY_CAMERA_URL') or 'rtsp://hcu-libraly:hculibraly123@192.168.1.197:554/stream1'
    EXIT_CAMERA_URL = os.environ.get('EXIT_CAMERA_URL') or 'rtsp://hcu-libraly:hculibraly123@192.168.1.197:554/stream1'
    
    # Gate Controller (ESP32)
    ESP32_URL = os.environ.get('ESP32_URL') or 'http://192.168.0.119'
    
    # Ensure directories exist
    @staticmethod
    def init_app(app):
        os.makedirs(Config.FACES_FOLDER, exist_ok=True)
        os.makedirs(os.path.join(Config.BASE_DIR, 'data'), exist_ok=True)
