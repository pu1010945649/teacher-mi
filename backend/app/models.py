from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(10))  # teacher / student
    real_name: Mapped[str] = mapped_column(String(50), default="")
    student_no: Mapped[str] = mapped_column(String(50), default="")
    class_name: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    submissions: Mapped[list["Submission"]] = relationship(back_populates="student")


class AiConfig(Base):
    __tablename__ = "ai_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    base_url: Mapped[str] = mapped_column(String(200), default="")
    api_key: Mapped[str] = mapped_column(String(200), default="")
    model: Mapped[str] = mapped_column(String(100), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    filename: Mapped[str] = mapped_column(String(255), default="")  # 作业附件
    file_path: Mapped[str] = mapped_column(String(255), default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    submissions: Mapped[list["Submission"]] = relationship(back_populates="assignment")
    targets: Mapped[list["AssignmentTarget"]] = relationship(back_populates="assignment")


class AssignmentTarget(Base):
    """作业定向下发目标；作业无目标记录时对全体学生可见"""
    __tablename__ = "assignment_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    assignment: Mapped["Assignment"] = relationship(back_populates="targets")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text, default="")
    filename: Mapped[str] = mapped_column(String(255), default="")
    file_path: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="submitted")  # submitted / graded
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    assignment: Mapped["Assignment"] = relationship(back_populates="submissions")
    student: Mapped["User"] = relationship(back_populates="submissions")
    feedback: Mapped["Feedback | None"] = relationship(back_populates="submission", uselist=False)


class Feedback(Base):
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), unique=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    annotation: Mapped[str] = mapped_column(Text, default="")  # 在线批注
    filename: Mapped[str] = mapped_column(String(255), default="")  # 批注文件
    file_path: Mapped[str] = mapped_column(String(255), default="")
    ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    submission: Mapped["Submission"] = relationship(back_populates="feedback")


class Worksheet(Base):
    __tablename__ = "worksheets"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, default="")
    pdf_path: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # 确认发布流程：pending(待确认) / published(已发送给学生) / rejected(已驳回)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_as_assignment_id: Mapped[int | None] = mapped_column(
        ForeignKey("assignments.id"), nullable=True)  # 发布后关联的学生作业条目


class Course(Base):
    """排课：教师为辅导学生安排的课程"""
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))  # 课程名 / 科目
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    location: Mapped[str] = mapped_column(String(200), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    student: Mapped["User"] = relationship(foreign_keys=[student_id])
    teacher: Mapped["User"] = relationship(foreign_keys=[teacher_id])
    feedbacks: Mapped[list["CourseFeedback"]] = relationship(back_populates="course")


class CourseFeedback(Base):
    """某节课的学习反馈，学生可回复"""
    __tablename__ = "course_feedbacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text, default="")
    reply: Mapped[str] = mapped_column(Text, default="")  # 学生回复
    replied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    course: Mapped["Course"] = relationship(back_populates="feedbacks")


class WorksheetTask(Base):
    """AI 个性化练习生成任务（后台异步执行）"""
    __tablename__ = "worksheet_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    focus: Mapped[str] = mapped_column(Text, default="")
    submission_ids: Mapped[str] = mapped_column(Text, default="[]")  # 指定参考的提交记录 id（JSON 数组）
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending/running/done/failed/canceled
    error: Mapped[str] = mapped_column(Text, default="")
    worksheet_id: Mapped[int | None] = mapped_column(ForeignKey("worksheets.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    student: Mapped["User"] = relationship(foreign_keys=[student_id])


class AppSetting(Base):
    """应用设置（键值对）"""
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(200), default="")
