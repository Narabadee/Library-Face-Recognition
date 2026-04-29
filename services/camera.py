"""
RTSPCamera - FFmpeg subprocess-based RTSP stream reader
========================================================
ใช้ FFmpeg subprocess แทน cv2.VideoCapture เพราะกล้อง UDP stream
บางรุ่นไม่รองรับ OpenCV built-in FFmpeg decoder
"""

import os
import subprocess
import threading
import numpy as np
import time
import shutil
import logging

logger = logging.getLogger(__name__)

# Auto-detect resolution from stream (default fallback)
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720


def find_ffmpeg():
    """Find ffmpeg executable path"""
    path = shutil.which("ffmpeg")
    if path:
        return path
    
    # Common install paths on Windows
    candidates = [
        r"C:\Program Files\FFmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ]
    
    # Add WinGet path dynamically for the current user
    user_home = os.path.expanduser("~")
    winget_path = os.path.join(
        user_home, 
        r"AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffmpeg.exe"
    )
    candidates.append(winget_path)
    
    for c in candidates:
        if os.path.isfile(c):
            return c
            
    return "ffmpeg"  # fallback, hope it's in PATH


FFMPEG_BIN = find_ffmpeg()


class RTSPCamera:
    """
    RTSP Camera reader using FFmpeg subprocess.
    Interface-compatible with the old CameraStream class.
    """

    def __init__(self, url: str, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT):
        self.url = url
        self.width = width
        self.height = height
        self.frame = None
        self.running = False
        self._lock = threading.Lock()
        self._process = None
        self._thread = None
        self._connected = False

    # ── public API (same as CameraStream) ──────────────────────────────────

    def start(self):
        """Start background capture thread (idempotent)."""
        with self._lock:
            if self.running:
                return
            self.running = True

        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        logger.info(f"[Camera] Starting stream: {self.url}")

    def get_frame(self):
        """Return latest frame (numpy BGR array) or None."""
        with self._lock:
            return self.frame.copy() if self.frame is not None else None

    def stop(self):
        """Stop capture thread."""
        self.running = False
        self._kill_process()
        if self._thread:
            self._thread.join(timeout=3)

    # ── alias so old code that calls camera.start() still works ────────────
    def is_connected(self):
        return self._connected

    # ── internal ────────────────────────────────────────────────────────────

    def _build_process(self):
        """Spawn ffmpeg -> stdout raw BGR frames."""
        cmd = [
            FFMPEG_BIN,
            "-loglevel", "error",
            "-rtsp_transport", "udp",   # กล้องใช้ UDP
            "-i", self.url,
            "-vf", f"scale={self.width}:{self.height}",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-vcodec", "rawvideo",
            "-an",                        # ไม่เอา audio
            "-"
        ]
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=10 ** 8
        )

    def _kill_process(self):
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
        self._process = None

    def _read_loop(self):
        frame_size = self.width * self.height * 3  # bytes per frame (BGR24)

        while self.running:
            try:
                logger.info("[Camera] Connecting via FFmpeg subprocess...")
                self._process = self._build_process()
                self._connected = False

                while self.running:
                    raw = self._process.stdout.read(frame_size)

                    if len(raw) != frame_size:
                        # Stream ended or connection dropped
                        logger.warning("[Camera] Stream lost, reconnecting in 2s...")
                        self._connected = False
                        break

                    frame = np.frombuffer(raw, dtype=np.uint8).reshape(
                        (self.height, self.width, 3)
                    )
                    with self._lock:
                        self.frame = frame.copy()

                    if not self._connected:
                        self._connected = True
                        logger.info(f"[Camera] Connected! {self.width}x{self.height}")

            except Exception as e:
                logger.error(f"[Camera] Error: {e}")
                self._connected = False
            finally:
                self._kill_process()

            if self.running:
                time.sleep(2)  # รอก่อน reconnect
