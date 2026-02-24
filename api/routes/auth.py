from fastapi import APIRouter, HTTPException, Depends
import os
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt
from datetime import datetime, timedelta
import sys
sys.path.append("/var/www/hylilabs/api")
from database import verify_user, get_user, get_connection

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()

# JWT ayarları
SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET environment variable zorunlu! .env dosyasinda tanimlayin.")
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

        # Kullanıcı aktif mi kontrol et
        if not user.get("aktif", 1):
            raise HTTPException(status_code=401, detail="Hesabınız pasif durumda")

        # Firma aktif mi kontrol et
        company_id = user.get("company_id")
        if company_id:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT aktif FROM companies WHERE id = ?", (company_id,))
                row = cursor.fetchone()
                if row and not row[0]:
                    raise HTTPException(status_code=403, detail="Firmanız pasif durumda")

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

    # Kullanıcı aktif mi kontrol et
    if not user.get("aktif", 1):
        raise HTTPException(status_code=403, detail="Hesabınız pasif. Yöneticinizle iletişime geçin.")

    # Firma aktif mi kontrol et
    company_id = user.get("company_id")
    if company_id:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT aktif FROM companies WHERE id = ?", (company_id,))
            row = cursor.fetchone()
            if row and not row[0]:
                raise HTTPException(status_code=403, detail="Firmanız pasif durumda.")

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


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.put("/change-password")
def change_password(request: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    """Kullanici sifresini degistir"""
    from database import verify_password, hash_password, get_connection
    
    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="Yeni sifre en az 8 karakter olmali")
    
    # Mevcut sifreyi dogrula
    stored_hash = current_user.get("password_hash")
    if not stored_hash:
        # password_hash yoksa veritabanından al
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM users WHERE id = ?", (current_user["id"],))
            row = cursor.fetchone()
            if row:
                stored_hash = row[0]
    
    if not verify_password(request.current_password, stored_hash):
        raise HTTPException(status_code=403, detail="Mevcut sifre yanlis")
    
    # Yeni sifreyi kaydet
    new_hash = hash_password(request.new_password)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, current_user["id"]))
    
    return {"success": True, "message": "Şifre başarıyla değiştirildi"}
