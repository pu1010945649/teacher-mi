from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_teacher
from ..database import get_db
from ..models import AiConfig, Assignment, Submission, User
from ..schemas import AiConfigOut, AiConfigUpdate, AiSuggestion
from ..services.ai_service import chat, parse_suggestion

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/config", response_model=AiConfigOut)
def get_config(db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    cfg = db.query(AiConfig).first()
    if not cfg:
        cfg = AiConfig()
        db.add(cfg)
        db.commit()
    out = AiConfigOut(base_url=cfg.base_url, api_key="", model=cfg.model, enabled=cfg.enabled)
    out.api_key_set = bool(cfg.api_key)
    return out


@router.put("/config", response_model=AiConfigOut)
def update_config(body: AiConfigUpdate, db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    cfg = db.query(AiConfig).first()
    if not cfg:
        cfg = AiConfig()
        db.add(cfg)
    cfg.base_url, cfg.model, cfg.enabled = body.base_url, body.model, body.enabled
    if body.api_key:  # 为空表示保持原 Key 不变
        cfg.api_key = body.api_key
    db.commit()
    out = AiConfigOut(base_url=cfg.base_url, api_key="", model=cfg.model, enabled=cfg.enabled)
    out.api_key_set = bool(cfg.api_key)
    return out


PROMPT = (
    "你是一位经验丰富的教师助手。请根据作业要求批改学生提交的作业，"
    '以 JSON 格式返回：{{"score": 分数(0-100 的数字), "comment": "具体评语与改进建议"}}。'
    "只返回 JSON，不要其他内容。\n\n作业标题：{title}\n作业要求：{desc}\n\n学生提交内容：\n{content}"
)


@router.post("/test")
async def test_ai(body: AiConfigUpdate | None = None, db: Session = Depends(get_db),
                  _: User = Depends(require_teacher)):
    """优先用表单当前值测试（Key 留空回退已保存值）；无表单值时用已保存配置"""
    if body and (body.base_url or body.model):
        saved = db.query(AiConfig).first()
        cfg = AiConfig(
            base_url=body.base_url or (saved.base_url if saved else ""),
            api_key=body.api_key or (saved.api_key if saved else ""),
            model=body.model or (saved.model if saved else ""),
            enabled=True,
        )
    else:
        cfg = get_ai_config(db)
    result = await chat(db, [{"role": "user", "content": '请原样返回：连接成功'}], cfg=cfg)
    return {"reply": result[:50]}


@router.post("/grade/{submission_id}", response_model=AiSuggestion)
async def ai_grade(submission_id: int, db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    sub = db.get(Submission, submission_id)
    if not sub:
        raise HTTPException(404, "提交记录不存在")
    assignment = db.get(Assignment, sub.assignment_id)
    text = sub.content or f"（附件：{sub.filename}，内容需教师人工查看）"
    prompt = PROMPT.format(title=assignment.title, desc=assignment.description or "无", content=text)
    result = await chat(db, [{"role": "user", "content": prompt}])
    score, comment = parse_suggestion(result)
    return AiSuggestion(score=score, comment=comment)
