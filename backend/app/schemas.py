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


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    real_name: str
    student_no: str
    class_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class StudentCreate(BaseModel):
    username: str
    password: str
    real_name: str = ""
    student_no: str = ""
    class_name: str = ""


class StudentUpdate(BaseModel):
    password: str = ""
    real_name: str = ""
    student_no: str = ""
    class_name: str = ""


class AssignmentCreate(BaseModel):
    title: str
    description: str = ""
    deadline: datetime | None = None


class AssignmentOut(BaseModel):
    id: int
    title: str
    description: str
    deadline: datetime | None
    filename: str = ""
    created_at: datetime
    submission_count: int = 0
    submitted: bool = False
    assigned_to_all: bool = True
    target_count: int = 0

    class Config:
        from_attributes = True


class AssignmentDescGenerate(BaseModel):
    student_ids: list[int] = []
    hint: str = ""


class AssignmentDescOut(BaseModel):
    description: str


class FeedbackOut(BaseModel):
    id: int
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
    submitted_at: datetime
    has_file: bool = False
    assignment_title: str = ""
    student_name: str = ""
    feedback: FeedbackOut | None = None

    class Config:
        from_attributes = True


class FeedbackCreate(BaseModel):
    score: float | None = None
    content: str = ""
    ai_assisted: bool = False


class AiConfigUpdate(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    enabled: bool = False


class AiConfigOut(AiConfigUpdate):
    api_key_set: bool = False


class AiSuggestion(BaseModel):
    score: float | None = None
    comment: str = ""


class WorksheetOut(BaseModel):
    id: int
    student_id: int
    title: str
    content: str
    created_at: datetime
    student_name: str = ""
    has_pdf: bool = False

    class Config:
        from_attributes = True


class WorksheetGenerate(BaseModel):
    student_id: int
    focus: str = ""
