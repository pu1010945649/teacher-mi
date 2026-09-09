"""登录敏感信息传输加密：RSA 密钥对持久化在 AppSetting，前端用公钥加密，后端私钥解密。

前端加密载荷格式：RSA(base64( JSON {"p": 明文, "t": 毫秒时间戳} ))
时间戳用于防重放：超过 WINDOW_MS 的密文直接拒绝。
"""
import base64
import json
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from sqlalchemy.orm import Session

from ..models import AppSetting

RSA_KEY_SETTING = "login_rsa_private_key"
WINDOW_MS = 5 * 60 * 1000  # 密文有效期 5 分钟


def _get_private_key_pem(db: Session) -> str:
    """读取（或首次生成并保存）RSA 私钥 PEM"""
    row = db.get(AppSetting, RSA_KEY_SETTING)
    if row and row.value:
        return row.value
    key = generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    if row:
        row.value = pem
    else:
        db.add(AppSetting(key=RSA_KEY_SETTING, value=pem))
    db.commit()
    return pem


def get_public_key(db: Session) -> str:
    """返回前端加密用的公钥 PEM"""
    pem = _get_private_key_pem(db)
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    return key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def decrypt_payload(db: Session, encrypted: str) -> str:
    """解密前端加密载荷，校验时间戳防重放，返回明文"""
    pem = _get_private_key_pem(db)
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    try:
        raw = key.decrypt(base64.b64decode(encrypted), asym_padding.PKCS1v15())
        data = json.loads(raw)
        plain, ts = data["p"], int(data["t"])
    except Exception:
        raise ValueError("密文解析失败")
    if abs(time.time() * 1000 - ts) > WINDOW_MS:
        raise ValueError("登录信息已过期，请刷新页面重试")
    return plain
