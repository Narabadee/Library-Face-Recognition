"""
ONNX Model Manager
==================
Downloads and manages ONNX models for face recognition.
Downloads the buffalo_l package from InsightFace releases.

Models included:
- det_10g.onnx (RetinaFace detection)
- w600k_r50.onnx (ArcFace embedding)
"""

import os
import urllib.request
import zipfile
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# InsightFace buffalo_l model package
BUFFALO_L_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
BUFFALO_L_SIZE_MB = 275

# Model files within the buffalo_l package
MODEL_FILES = {
    'retinaface': 'det_10g.onnx',
    'arcface': 'w600k_r50.onnx'
}

# Additional models that are not in the buffalo_l package
EXTRA_MODELS = {
    'yunet': {
        'filename': 'face_detection_yunet_2023mar.onnx',
        'url': 'https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx',
        'fallback_url': 'https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx',
        'target_folder': '.' # Root folder
    },
    'yolo': {
        'filename': 'yolov8n.pt',
        'url': 'https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8n.pt',
        'fallback_url': None,
        'target_folder': '.' # Root folder
    }
}


def get_models_folder() -> str:
    """Get the models folder path"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Models are extracted directly to models/ folder
    models_folder = os.path.join(base, 'models')
    os.makedirs(models_folder, exist_ok=True)
    return models_folder


def download_buffalo_l(force: bool = False) -> bool:
    """
    Download and extract the buffalo_l model package.
    
    Args:
        force: Re-download even if exists
        
    Returns:
        True if successful
    """
    models_folder = get_models_folder()
    
    # Check if models already exist
    if not force:
        all_exist = all(
            os.path.exists(os.path.join(models_folder, fname))
            for fname in MODEL_FILES.values()
        )
        if all_exist:
            logger.info("Models already downloaded")
            return True
    
    # Download zip
    base = os.path.dirname(models_folder)
    zip_path = os.path.join(base, 'buffalo_l.zip')
    
    logger.info(f"Downloading buffalo_l models (~{BUFFALO_L_SIZE_MB}MB)...")
    print(f"Downloading face recognition models (~{BUFFALO_L_SIZE_MB}MB)...")
    print("This may take a few minutes...")
    
    try:
        def progress_hook(block_num, block_size, total_size):
            if total_size > 0:
                progress = min(100, block_num * block_size * 100 / total_size)
                print(f"\rProgress: {progress:.1f}%", end='', flush=True)
        
        urllib.request.urlretrieve(BUFFALO_L_URL, zip_path, reporthook=progress_hook)
        print()  # New line
        
        # Extract only .onnx files directly into models/ folder
        # (zip may have a buffalo_l/ prefix — we skip it and put files in models/)
        logger.info("Extracting models...")
        print("Extracting models...")

        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.namelist():
                filename = os.path.basename(member)
                if filename.endswith('.onnx') and filename:
                    dest_path = os.path.join(models_folder, filename)
                    with zf.open(member) as src, open(dest_path, 'wb') as dst:
                        dst.write(src.read())

        # Clean up zip
        os.remove(zip_path)

        logger.info("Models downloaded successfully")
        print("Models ready!")
        return True
        
    except Exception as e:
        logger.error(f"Failed to download models: {e}")
        print(f"\nError: {e}")
        return False


def get_model_path(model_name: str) -> str:
    """Get path to a specific model file."""
    if model_name not in MODEL_FILES:
        raise ValueError(f"Unknown model: {model_name}. Available: {list(MODEL_FILES.keys())}")
    
    return os.path.join(get_models_folder(), MODEL_FILES[model_name])


def check_models() -> dict:
    """
    Check which models are available.
    
    Returns:
        Dict with model status
    """
    models_folder = get_models_folder()
    status = {}
    
    for name, filename in MODEL_FILES.items():
        path = os.path.join(models_folder, filename)
        status[name] = {
            'available': os.path.exists(path),
            'path': path if os.path.exists(path) else None,
            'filename': filename
        }
    
    return status


def ensure_models() -> bool:
    """
    Ensure all models are downloaded and ready.
    Includes InsightFace, YuNet, and YOLO.
    
    Returns:
        True if all models are ready
    """
    # 1. Check/Download InsightFace (buffalo_l)
    status = check_models()
    if not all(s['available'] for s in status.values()):
        if not download_buffalo_l():
            return False
            
    # 2. Check/Download Extra Models (YuNet, YOLO)
    base_folder = os.path.dirname(get_models_folder())
    
    for name, info in EXTRA_MODELS.items():
        target_path = os.path.join(base_folder, info['target_folder'], info['filename'])
        if not os.path.exists(target_path):
            logger.info(f"Missing extra model: {info['filename']}")
            print(f"Downloading {name} model ({info['filename']})...")
            downloaded = False
            urls_to_try = [info['url']]
            if info.get('fallback_url'):
                urls_to_try.append(info['fallback_url'])
            for attempt_url in urls_to_try:
                try:
                    def progress_hook(block_num, block_size, total_size):
                        if total_size > 0:
                            progress = min(100, block_num * block_size * 100 / total_size)
                            print(f"\rProgress: {progress:.1f}%", end='', flush=True)
                    
                    urllib.request.urlretrieve(attempt_url, target_path, reporthook=progress_hook)
                    print()
                    logger.info(f"Successfully downloaded {info['filename']}")
                    downloaded = True
                    break
                except Exception as e:
                    logger.warning(f"Failed to download from {attempt_url}: {e}")
                    print(f"\nRetrying with mirror..." if attempt_url != urls_to_try[-1] else f"\nAll download sources failed for {name} model.")
            if not downloaded:
                logger.error(f"Failed to download {info['filename']} from all sources")
                return False
                
    return True


if __name__ == '__main__':
    # Run this script directly to download models
    logging.basicConfig(level=logging.INFO)
    print("=" * 50)
    print("InsightFace Model Downloader")
    print("=" * 50)
    
    success = download_buffalo_l()
    
    print("\nModel status:")
    for name, status in check_models().items():
        icon = '✓' if status['available'] else '✗'
        print(f"  {icon} {name}: {status['filename']}")
    
    if success:
        print("\nAll models ready!")
    else:
        print("\nSome downloads failed. Check your internet connection.")
