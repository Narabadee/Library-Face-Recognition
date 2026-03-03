from waitress import serve
from app import app
from services.model_manager import ensure_models
import socket
import os

if __name__ == '__main__':
    # Ensure all AI models are downloaded before starting
    print("Checking system requirements and AI models...")
    if not ensure_models():
        print("\n[ERROR] Failed to ensure AI models are present.")
        print("Please check your internet connection and try again.")
        input("Press Enter to exit...")
        exit(1)
        
    # Get local IP for convenience
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "localhost"

    port = 5000
    
    print("\n" + "="*50)
    print(f"🚀 PRODUCTION SERVER STARTING")
    print(f"🏠 Local:   http://localhost:{port}")
    print(f"🌐 Network: http://{local_ip}:{port}")
    print("="*50 + "\n")
    print("NOTE: Press Ctrl+C to stop the server.")
    
    # Run production server
    # threads=12 allows handling multiple simultaneous requests efficiently
    serve(app, host='0.0.0.0', port=port, threads=12)
