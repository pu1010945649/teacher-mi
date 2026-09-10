import json

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import AiConfig, User

DEFAULT_TIMEOUT = 60.0


def _usable(cfg: AiConfig | None) -> bool:
    return bool(cfg and cfg.enabled and cfg.base_url and cfg.model)


def get_ai_config(db: Session, user: User | None = None) -> AiConfig:
    """取当前用户的 AI 配置；教师有自己的配置则用自己的（管理员配置失效），
    未配置且管理员开放权限时回退用管理员的（管理员配置即默认配置）"""
    cfg = None
    if user is not None:
        cfg = db.query(AiConfig).filter(AiConfig.user_id == user.id).first()
        if not cfg and user.role == "teacher" and user.ai_enabled:
            admin_ids = [i for (i,) in db.query(User.id).filter(User.role == "admin").all()]
            for aid in admin_ids:
                c = db.query(AiConfig).filter(AiConfig.user_id == aid).first()
                if _usable(c):
                    cfg = c
                    break
    else:
        cfg = db.query(AiConfig).first()
    if not _usable(cfg):
        raise HTTPException(400, "AI 模型未配置或未启用，请先在「设置」中完成配置")
    return cfg


async def chat(db: Session, messages: list[dict], cfg: AiConfig | None = None,
               user: User | None = None) -> str:
    """cfg 为 None 时使用已保存配置（按用户隔离）；传入 cfg 可用临时配置测试"""
    cfg = cfg or get_ai_config(db, user)
    url = cfg.base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {cfg.api_key}"}
    body = {"model": cfg.model, "messages": messages, "temperature": 0.3}
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"AI 服务返回错误：{e.response.status_code} {e.response.text[:200]}")
    except (httpx.HTTPError, KeyError, IndexError) as e:
        raise HTTPException(502, f"调用 AI 服务失败：{e}")


def parse_suggestion(text: str) -> tuple[float | None, str]:
    """从 AI 返回的 JSON 或纯文本中解析分数与评语"""
    try:
        data = json.loads(text[text.index("{"): text.rindex("}") + 1])
        return float(data.get("score")), str(data.get("comment", "")).strip()
    except (ValueError, TypeError, json.JSONDecodeError):
        return None, text.strip()


def parse_json_object(text: str) -> dict:
    """从 AI 返回文本中提取 JSON 对象，失败返回空 dict"""
    try:
        return json.loads(text[text.index("{"): text.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return {}
