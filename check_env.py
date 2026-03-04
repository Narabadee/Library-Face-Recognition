import sys
import os

def check_dependencies():
    packages = [
        'flask', 
        'flask_sqlalchemy', 
        'cv2', 
        'numpy', 
        'PIL', 
        'onnxruntime', 
        'ultralytics'
    ]
    
    print("📋 Checking Project Dependencies...")
    print("-" * 30)
    
    all_ok = True
    for pkg in packages:
        try:
            if pkg == 'cv2':
                import cv2
                print(f"✅ OpenCV: {cv2.__version__}")
            elif pkg == 'PIL':
                from PIL import Image
                print(f"✅ Pillow: {Image.__version__}")
            else:
                module = __import__(pkg)
                version = getattr(module, '__version__', 'unknown')
                print(f"✅ {pkg}: {version}")
        except ImportError:
            print(f"❌ {pkg}: NOT INSTALLED")
            all_ok = False
            
    return all_ok

def check_models():
    print("\n🧠 Checking Model Files...")
    print("-" * 30)
    
    required_files = [
        'face_detection_yunet_2023mar.onnx',
        'models/w600k_r50.onnx',
        'yolov8n.pt'
    ]
    
    all_ok = True
    for f in required_files:
        if os.path.exists(f):
            print(f"✅ {f}: FOUND")
        else:
            print(f"⚠️ {f}: MISSING (Some features may be limited)")
            all_ok = False
            
    return all_ok

if __name__ == "__main__":
    print(f"🐍 Python Version: {sys.version}")
    print(f"📂 Project Path: {os.getcwd()}")
    print("-" * 30)
    
    dep_ok = check_dependencies()
    mod_ok = check_models()
    
    print("\n" + "="*30)
    if dep_ok and mod_ok:
        print("🌟 Everything is CORRECT! ready to run.")
    elif dep_ok:
        print("⚠️ Dependencies OK, but some models are missing.")
    else:
        print("❌ Missing dependencies. Please close this and run RUN_WINDOWS.bat (or START_MAC.command) again.")
    print("="*30)
