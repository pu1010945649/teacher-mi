from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..database import get_db
from ..models import User
from ..schemas import ChangePassword, LoginRequest, TokenResponse
from ..services.crypto_service import decrypt_payload, get_public_key

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/public-key", response_class=PlainTextResponse)
def public_key(db: Session = Depends(get_db)):
    """登录加密公钥（私钥保存在服务端数据库）"""
    return get_public_key(db)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    # 密码为 RSA 加密密文，在此解密后才做校验（校验完全在服务端完成）
    try:
        password = decrypt_payload(db, body.password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    token = create_access_token(user.id, user.role)
    return TokenResponse(token=token, role=user.role, real_name=user.real_name, username=user.username)


@router.post("/change-password")
def change_password(body: ChangePassword, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """验证原密码后修改为新密码，教师和学生通用；新旧密码均为加密密文"""
    try:
        old_password = decrypt_payload(db, body.old_password)
        new_password = decrypt_payload(db, body.new_password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not verify_password(old_password, user.password_hash):
        raise HTTPException(400, "原密码错误")
    if old_password == new_password:
        raise HTTPException(400, "新密码不能与原密码相同")
    user.password_hash = hash_password(new_password)
    db.commit()
    return {"ok": True}
