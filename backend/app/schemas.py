from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePassword(BaseModel):
    old_password: str
    new_password: str


class TokenResponse(BaseModel):
    token: str
    role: str
    real_name: str
    username: str


class StudentBinding(BaseModel):
    """师生绑定项：教师 + 科目（一个学生可绑定多个教师）"""
    teacher_id: int
    subject: str = ""


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    real_name: str
    student_no: str
    class_name: str
    pushplus_token: str = ""
    teacher_id: int | None = None  # 主归属教师（第一个绑定的教师）
    teacher_name: str = ""  # 归属教师姓名（仅学生管理列表用，多个用顿号连接）
    bindings: list[StudentBinding] = []  # 全部师生绑定（含科目）
    created_at: datetime

    class Config:
        from_attributes = True


class StudentCreate(BaseModel):
    username: str
    password: str
    real_name: str = ""
    student_no: str = ""
    class_name: str = ""
    pushplus_token: str = ""
    teacher_id: int | None = None  # 归属教师（管理员分配，兼容旧单选）
    bindings: list[StudentBinding] = []  # 多教师绑定（优先于 teacher_id）


class StudentUpdate(BaseModel):
    password: str = ""
    real_name: str = ""
    student_no: str = ""
    class_name: str = ""
    pushplus_token: str = ""
    teacher_id: int | None = None  # 归属教师（仅管理员可改，兼容旧单选）
    bindings: list[StudentBinding] = []  # 多教师绑定（优先于 teacher_id）


class AssignmentCreate(BaseModel):
    title: str
    description: str = ""
    deadline: datetime | None = None


class AssignmentOut(BaseModel):
    id: int
    title: str
    subject: str = ""  # 科目
    description: str
    deadline: datetime | None
    filename: str = ""
    created_at: datetime
    submission_count: int = 0
    submitted: bool = False
    returned: bool = False  # 教师已退回，要求重新提交
    my_feedback: "FeedbackOut | None" = None
    has_video: bool = False  # 是否有讲解视频
    video_locked: bool = False  # 定向下发（含抄送）作业：老师评分后才能观看讲解视频
    video_filename: str = ""
    assigned_to_all: bool = True
    target_count: int = 0
    target_names: list[str] = []  # 下发范围的学生名字（教师视角）
    target_ids: list[int] = []  # 下发范围的学生 id（教师视角，用于抄送时排除）
    student_states: list[dict] = []  # 下发范围内学生的提交状态（danger 未提交 / warning 未批改 / success 已批改）
    created_by_name: str = ""  # 下发老师（学生端展示）

    class Config:
        from_attributes = True


class AssignmentDescGenerate(BaseModel):
    student_ids: list[int] = []
    hint: str = ""


class AssignmentDescOut(BaseModel):
    description: str


class FeedbackOut(BaseModel):
    id: int
    submission_id: int | None = None
    score: float | None
    content: str
    annotation: str = ""
    filename: str = ""
    ai_assisted: bool
    created_at: datetime
    has_annotated_file: bool = False

    class Config:
        from_attributes = True


class SubmissionOut(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    content: str
    filename: str
    status: str
    attempt: int = 1
    submitted_at: datetime
    has_file: bool = False
    assignment_title: str = ""
    student_name: str = ""
    assigned_at: datetime | None = None  # 作业下发时间
    feedback: FeedbackOut | None = None

    class Config:
        from_attributes = True


class FeedbackCreate(BaseModel):
    score: float | None = None
    content: str = ""
    ai_assisted: bool = False


class AiConfigUpdate(BaseModel):
    base_url: str = ""
    api_key: str = ""  # 传入掩码表示未修改；传空表示删除配置
    model: str = ""
    enabled: bool = False


class AiConfigOut(AiConfigUpdate):
    api_key_set: bool = False
    api_key_mask: str = ""  # 脱敏后的 API Key，不出明文
    ai_allowed: bool = True  # 当前教师是否被管理员开放 AI 使用权限


class AiSuggestion(BaseModel):
    score: float | None = None
    comment: str = ""


class WorksheetTaskCreate(BaseModel):
    student_ids: list[int]
    # 可选：指定每个学生参考哪些作业批改记录（键为学生 id 字符串），缺省用全部记录
    submission_ids: dict[str, list[int]] = {}
    # 可选：指定每个学生参考哪些课程反馈（键为学生 id 字符串），缺省用全部记录
    course_feedback_ids: dict[str, list[int]] = {}


class WorksheetTaskEdit(BaseModel):
    """教师编辑生成结果草稿（下发前）"""
    title: str
    content: str


class WorksheetTaskOut(BaseModel):
    id: int
    student_id: int
    focus: str = ""
    status: str
    error: str = ""
    title: str = ""
    content: str = ""
    assignment_id: int | None = None
    created_at: datetime
    finished_at: datetime | None = None
    student_name: str = ""

    class Config:
        from_attributes = True


class WorksheetTaskSettings(BaseModel):
    concurrency: int


# ===== 排课 =====
class CourseFeedbackOut(BaseModel):
    id: int
    course_id: int
    content: str
    reply: str = ""
    replied_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class CourseOut(BaseModel):
    id: int
    student_id: int
    title: str
    start_time: datetime
    end_time: datetime | None = None
    location: str = ""
    note: str = ""
    student_name: str = ""
    teacher_name: str = ""  # 排课老师（跨教师课表展示用）
    is_mine: bool = False  # 是否当前教师自己排的课（他人课程只读）
    feedbacks: list[CourseFeedbackOut] = []

    class Config:
        from_attributes = True


class CourseCreate(BaseModel):
    student_id: int
    title: str
    start_time: str  # YYYY-MM-DD HH:MM
    end_time: str | None = None
    location: str = ""
    note: str = ""


class CourseFeedbackCreate(BaseModel):
    content: str


class CourseFeedbackSourceOut(BaseModel):
    """AI 练习关注点来源：课程反馈扁平列表项"""
    id: int
    student_id: int
    student_name: str = ""
    course_title: str = ""
    content: str
    created_at: datetime | None = None


class CourseReplyCreate(BaseModel):
    content: str


class FeedbackPolishIn(BaseModel):
    """课程反馈 AI 润色输入"""
    content: str
    hint: str = ""  # 润色侧重提示，可空


class PolishOut(BaseModel):
    content: str


# ===== 学习周报 =====
class WeeklyReportGenerate(BaseModel):
    student_id: int
    week_start: str  # 周一日期 YYYY-MM-DD


class WeeklyReportEdit(BaseModel):
    title: str
    content: str


class WeeklyReportOut(BaseModel):
    id: int
    student_id: int
    week_start: str
    title: str
    content: str
    status: str = "draft"
    created_at: datetime
    sent_at: datetime | None = None
    student_name: str = ""
    teacher_name: str = ""  # 推送老师
    subject: str = ""  # 周报对应科目
    file_name: str = ""  # 手工上传的周报文件名，空表示纯文本周报

    class Config:
        from_attributes = True
