# ============================================================
# FILE: config/security.py
# Token management, Rate Limiting, Safe torch.load
# ============================================================
import os
import time
import hashlib
from functools import wraps
from collections import defaultdict
from flask import request, jsonify

# ★ 1. Token từ environment variable
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

if not TELEGRAM_BOT_TOKEN:
    print("⚠️ WARNING: TELEGRAM_BOT_TOKEN not set — using fallback from settings.py")
    try:
        from config.settings import TELEGRAM_BOT_TOKEN as _FB_TOKEN, TELEGRAM_CHAT_ID as _FB_CHAT
        TELEGRAM_BOT_TOKEN = _FB_TOKEN
        TELEGRAM_CHAT_ID = _FB_CHAT
    except ImportError:
        pass


# ★ 2. Rate Limiter
class SimpleRateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)
    
    def is_allowed(self, key, max_requests=60, window=60):
        now = time.time()
        self.requests[key] = [t for t in self.requests[key] if now - t < window]
        if len(self.requests[key]) >= max_requests:
            return False
        self.requests[key].append(now)
        return True

rate_limiter = SimpleRateLimiter()


def rate_limit(max_per_minute=60):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            client_ip = request.remote_addr
            if not rate_limiter.is_allowed(client_ip, max_per_minute, 60):
                return jsonify({"error": "Rate limit exceeded", "retry_after": 60}), 429
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ★ 3. Secure torch.load wrapper
def safe_torch_load(path, map_location=None):
    """Load model weights safely with optional checksum verification"""
    import torch
    
    if not os.path.exists(path):
        raise FileNotFoundError(f"Model not found: {path}")
    
    # Verify checksum if available
    checksum_file = path + ".sha256"
    if os.path.exists(checksum_file):
        with open(checksum_file, 'r') as f:
            expected_hash = f.read().strip()
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        if sha256.hexdigest() != expected_hash:
            raise ValueError(f"Checksum mismatch for {path}")
    
    try:
        return torch.load(path, map_location=map_location, weights_only=True)
    except Exception:
        print(f"⚠️ Loading {path} with weights_only=False (YOLO format)")
        return torch.load(path, map_location=map_location, weights_only=False)
