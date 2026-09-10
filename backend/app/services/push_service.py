"""PushPlus 消息推送：统一发送方 Token，按用户好友令牌（to）定向推送"""
import logging

import httpx
from sqlalchemy.orm import Session

from ..models import AppSetting, User

SENDER_KEY = "pushplus_token"  # AppSetting 中存发送方 Token
API_URL = "https://www.pushplus.plus/send"

logger = logging.getLogger(__name__)


def get_sender_token(db: Session) -> str:
    """发送方 Token（在设置中配置，教师扫码/微信登录获取）"""
    row = db.get(AppSetting, SENDER_KEY)
    return (row.value or "").strip() if row else ""


def save_sender_token(db: Session, token: str):
    row = db.get(AppSetting, SENDER_KEY)
    if row:
        row.value = token
    else:
        db.add(AppSetting(key=SENDER_KEY, value=token))
    db.commit()


async def send_to_user(db: Session, user: User | None, title: str, content: str) -> bool:
    """以统一发送方身份推送到用户的好友令牌（to）；未配置或失败仅记日志，不影响主流程"""
    sender = get_sender_token(db)
    to = (user.pushplus_token or "").strip() if user else ""
    if not sender or not to:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(API_URL, json={
                "token": sender, "title": title, "content": content,
                "to": to, "template": "txt"})
            data = resp.json()
            if data.get("code") != 200:
                logger.warning("PushPlus 推送失败(%s): %s", user.username, data.get("msg"))
                return False
        return True
    except Exception as e:
        logger.warning("PushPlus 推送异常(%s): %s", user.username, e)
        return False


async def send_to_users(db: Session, users: list[User], title: str, content: str) -> list[str]:
    """批量推送给多个用户，返回成功收到推送的用户名列表（未配置/失败的人跳过并记日志）"""
    sent: list[str] = []
    for u in users:
        if await send_to_user(db, u, title, content):
            sent.append(u.real_name or u.username)
    return sent


async def send_to_users_detail(db: Session, users: list[User], title: str,
                               content: str) -> tuple[list[str], list[str]]:
    """批量推送并返回 (成功用户名列表, 失败原因列表)，便于上层把真实错误透出给用户"""
    sent, errors = [], []
    for u in users:
        to = (u.pushplus_token or "").strip()
        sender = get_sender_token(db)
        if not to:
            errors.append(f"{u.real_name or u.username}：未配置好友令牌")
            continue
        if not sender:
            errors.append("发送方 Token 未配置")
            continue
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(API_URL, json={
                    "token": sender, "title": title, "content": content,
                    "to": to, "template": "txt"})
                data = resp.json()
                if data.get("code") == 200:
                    sent.append(u.real_name or u.username)
                else:
                    reason = data.get("data") or data.get("msg") or "未知错误"
                    errors.append(f"{u.real_name or u.username}：{reason}（code={data.get('code')}）")
                    logger.warning("PushPlus 推送失败(%s): %s", u.username, data)
        except Exception as e:
            errors.append(f"{u.real_name or u.username}：请求异常 {e}")
            logger.warning("PushPlus 推送异常(%s): %s", u.username, e)
    return sent, errors
