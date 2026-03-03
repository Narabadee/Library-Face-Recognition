import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'library-face-scanner-secret-key'
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # Database
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'data', 'library.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Face data storage
    FACES_FOLDER = os.path.join(BASE_DIR, 'data', 'faces')
    
    # RTSP Camera URLs
    ENTRY_CAMERA_URL = os.environ.get('ENTRY_CAMERA_URL') or 'rtsp://rtsp:7qinrvdb@192.168.1.177:554/av_stream/ch0'
    EXIT_CAMERA_URL = os.environ.get('EXIT_CAMERA_URL') or 'rtsp://rtsp:ODGMLBqh@192.168.1.179:554/av_stream/ch0'
    
    # Ensure directories exist
    @staticmethod
    def init_app(app):
        os.makedirs(Config.FACES_FOLDER, exist_ok=True)
        os.makedirs(os.path.join(Config.BASE_DIR, 'data'), exist_ok=True)
