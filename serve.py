from waitress import serve
from app import app
import socket
import os

if __name__ == '__main__':
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
