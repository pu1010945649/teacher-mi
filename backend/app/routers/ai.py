from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import ensure_ai_allowed, get_current_user, require_staff, require_teacher
from ..database import get_db
from ..models import AiConfig, Assignment, Submission, User
from ..schemas import AiConfigOut, AiConfigUpdate, AiSuggestion
from ..services.ai_service import chat, parse_suggestion
from .feedback import require_own_assignment

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _own_cfg(db: Session, user: User) -> AiConfig | None:
    return db.query(AiConfig).filter(AiConfig.user_id == user.id).first()


def _out(cfg: AiConfig | None, ai_allowed: bool) -> AiConfigOut:
    out = AiConfigOut(base_url=cfg.base_url if cfg else "", api_key="",
                      model=cfg.model if cfg else "", enabled=cfg.enabled if cfg else False)
    out.api_key_set = bool(cfg and cfg.api_key)
    out.ai_allowed = ai_allowed
    return out


@router.get("/config", response_model=AiConfigOut)
def get_config(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """配置状态查询：教师用于 AI 功能前置校验，管理员用于设置页"""
    if user.role not in ("teacher", "admin"):
        raise HTTPException(403, "无权访问")
    cfg = _own_cfg(db, user)
    if not cfg and user.role == "teacher":
        # 教师未配置时展示管理员配置（作为默认值，保存后即为自己的配置）
        admin_ids = [i for (i,) in db.query(User.id).filter(User.role == "admin").all()]
        for aid in admin_ids:
            c = db.query(AiConfig).filter(AiConfig.user_id == aid).first()
            if c:
                cfg = c
                break
    return _out(cfg, user.role == "admin" or user.ai_enabled)


@router.put("/config", response_model=AiConfigOut)
def update_config(body: AiConfigUpdate, db: Session = Depends(get_db),
                  user: User = Depends(require_staff)):
    """保存当前登录人自己的 AI 配置（管理员配置即全体教师的默认配置）"""
    cfg = _own_cfg(db, user)
    if not cfg:
        cfg = AiConfig(user_id=user.id)
        db.add(cfg)
    cfg.base_url, cfg.model, cfg.enabled = body.base_url, body.model, body.enabled
    if body.api_key:  # 为空表示保持原 Key 不变
        cfg.api_key = body.api_key
    db.commit()
    return _out(cfg, user.role == "admin" or user.ai_enabled)


PROMPT = (
    "你是一位经验丰富的教师助手。请根据作业要求批改学生提交的作业，"
    '以 JSON 格式返回：{{"score": 分数(0-100 的数字), "comment": "具体评语与改进建议"}}。'
    "只返回 JSON，不要其他内容。\n\n作业标题：{title}\n作业要求：{desc}\n\n学生提交内容：\n{content}"
)


@router.post("/test")
async def test_ai(body: AiConfigUpdate | None = None, db: Session = Depends(get_db),
                  user: User = Depends(require_staff)):
    """优先用表单当前值测试（Key 留空回退本人已保存值）；无表单值时用本人配置"""
    own = _own_cfg(db, user)
    if body and (body.base_url or body.model):
        cfg = AiConfig(
            base_url=body.base_url or (own.base_url if own else ""),
            api_key=body.api_key or (own.api_key if own else ""),
            model=body.model or (own.model if own else ""),
            enabled=True,
        )
    else:
        cfg = get_ai_config(db, user)
    result = await chat(db, [{"role": "user", "content": '请原样返回：连接成功'}], cfg=cfg)
    return {"reply": result[:50]}


@router.post("/grade/{submission_id}", response_model=AiSuggestion)
async def ai_grade(submission_id: int, db: Session = Depends(get_db),
                   user: User = Depends(require_teacher)):
    ensure_ai_allowed(user)
    sub = db.get(Submission, submission_id)
    if not sub:
        raise HTTPException(404, "提交记录不存在")
    require_own_assignment(db, user, sub.assignment_id)
    assignment = db.get(Assignment, sub.assignment_id)
    text = sub.content or f"（附件：{sub.filename}，内容需教师人工查看）"
    prompt = PROMPT.format(title=assignment.title, desc=assignment.description or "无", content=text)
    result = await chat(db, [{"role": "user", "content": prompt}], user=user)
    score, comment = parse_suggestion(result)
    return AiSuggestion(score=score, comment=comment)
