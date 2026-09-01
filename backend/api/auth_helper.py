import hmac
import hashlib
import json
import base64
import time
import os
import bcrypt
from fastapi import Header, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import db_config

# Load secret key from environment or fallback to a default secure key
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "meridian_hospital_secure_jwt_secret_key_2026")

security = HTTPBearer(auto_error=False)

# ─── JWT Helper Operations ───────────────────────────────────────────────────

def base64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b'=').decode('utf-8')

def base64url_decode(payload_str: str) -> bytes:
    padding = '=' * (4 - (len(payload_str) % 4))
    return base64.urlsafe_b64decode(payload_str + padding)

def encode_token(payload: dict) -> str:
    """Create standard signed JWT (HS256) token."""
    if "exp" not in payload:
        # Default 4 hours expiration (14400 seconds)
        payload["exp"] = int(time.time()) + 14400
        
    header = {"alg": "HS256", "typ": "JWT"}
    
    header_b64 = base64url_encode(json.dumps(header).encode('utf-8'))
    payload_b64 = base64url_encode(json.dumps(payload).encode('utf-8'))
    
    message = f"{header_b64}.{payload_b64}".encode('utf-8')
    signature = hmac.new(SECRET_KEY.encode('utf-8'), message, hashlib.sha256).digest()
    signature_b64 = base64url_encode(signature)
    
    return f"{header_b64}.{payload_b64}.{signature_b64}"

def decode_token(token: str) -> dict | None:
    """Verify and decode signed JWT token."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
            
        header_b64, payload_b64, signature_b64 = parts
        
        # Verify signature
        message = f"{header_b64}.{payload_b64}".encode('utf-8')
        expected_sig = hmac.new(SECRET_KEY.encode('utf-8'), message, hashlib.sha256).digest()
        expected_sig_b64 = base64url_encode(expected_sig)
        
        if not hmac.compare_digest(signature_b64, expected_sig_b64):
            return None
            
        payload = json.loads(base64url_decode(payload_b64).decode('utf-8'))
        
        # Verify expiration
        if payload.get("exp", 0) < time.time():
            return None
            
        return payload
    except Exception:
        return None

# ─── Password Cryptography ─────────────────────────────────────────────────────

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_hashed_password(plain_password: str) -> str:
    """Generate bcrypt hash for password."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode('utf-8'), salt).decode('utf-8')

# ─── FastAPI Dependencies ──────────────────────────────────────────────────────

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Dependency injection to authenticate requests via JWT."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication credentials missing")
    
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token or expired session")
        
    return payload

def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependency injection to enforce ADMIN role."""
    if user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin authorization required")
    return user

def require_doctor_or_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependency injection to allow either ADMIN or DOCTOR role."""
    if user.get("role") not in ["ADMIN", "DOCTOR"]:
        raise HTTPException(status_code=403, detail="Admin or Doctor authorization required")
    return user
