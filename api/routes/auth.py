from fastapi import APIRouter, HTTPException, Depends
import os
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt
from datetime import datetime, timedelta
import sys
sys.path.append("/var/www/hylilabs/api")
from database import verify_user, get_user

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()

# JWT ayarları
SECRET_KEY = os.getenv("JWT_SECRET", "fallback-dev-only")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict

def create_access_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "exp": expire
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        user = get_user(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token süresi dolmuş")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Geçersiz token")

@router.post("/login")
def login(request: LoginRequest):
    user = verify_user(request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Email veya şifre hatalı")
    
    token = create_access_token(user["id"])
    
    # Hassas bilgileri çıkar
    user_info = {
        "id": user["id"],
        "email": user["email"],
        "ad_soyad": user["ad_soyad"],
        "rol": user["rol"],
        "company_id": user["company_id"]
    }
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_info
    }

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "ad_soyad": current_user["ad_soyad"],
        "rol": current_user["rol"],
        "company_id": current_user["company_id"]
    }
