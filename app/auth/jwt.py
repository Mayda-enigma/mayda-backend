from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Check token type
        if payload.get("type") != token_type:
            return None
            
        # Check expiration
        exp = payload.get("exp")
        if exp is None:
            return None
            
        if datetime.utcnow() > datetime.fromtimestamp(exp):
            return None
            
        return payload
    except JWTError:
        return None


def create_temp_token(user_id: int, purpose: str = "2fa") -> str:
    """Create a temporary token for 2FA verification (5 minutes)."""
    expire = datetime.utcnow() + timedelta(minutes=5)
    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "type": "temp",
        "purpose": purpose
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_temp_token(token: str, purpose: str = "2fa") -> Optional[dict]:
    """Verify and decode a temporary token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Check token type and purpose
        if payload.get("type") != "temp" or payload.get("purpose") != purpose:
            return None
            
        # Check expiration
        exp = payload.get("exp")
        if exp is None:
            return None
            
        if datetime.utcnow() > datetime.fromtimestamp(exp):
            return None
            
        return payload
    except JWTError:
        return None


def get_user_id_from_token(token: str) -> Optional[int]:
    """Extract user ID from JWT token."""
    payload = verify_token(token)
    if payload:
        return payload.get("sub")
    return None
