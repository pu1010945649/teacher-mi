from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..database import get_db
from ..models import User
from ..schemas import ChangePassword, LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    token = create_access_token(user.id, user.role)
    return TokenResponse(token=token, role=user.role, real_name=user.real_name, username=user.username)


@router.post("/change-password")
def change_password(body: ChangePassword, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """验证原密码后修改为新密码，教师和学生通用"""
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(400, "原密码错误")
    if body.old_password == body.new_password:
        raise HTTPException(400, "新密码不能与原密码相同")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}
