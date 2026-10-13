"""Pydantic 请求/响应模型。"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ---------- 子实体 ----------
class EducationBase(BaseModel):
    school: str = ""
    major: str = ""
    degree: str = ""
    start_date: str = ""
    end_date: str = ""
    courses: str = ""
    gpa: str = ""
    rank: str = ""


class EducationOut(EducationBase):
    id: int
    user_id: int
    model_config = ConfigDict(from_attributes=True)


class SkillBase(BaseModel):
    category: str = ""
    name: str = ""
    proficiency: str = ""


class SkillOut(SkillBase):
    id: int
    user_id: int
    model_config = ConfigDict(from_attributes=True)


class ProjectBase(BaseModel):
    title: str = ""
    role: str = ""
    tech_stack: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""
    result: str = ""


class ProjectOut(ProjectBase):
    id: int
    user_id: int
    model_config = ConfigDict(from_attributes=True)


class InternshipBase(BaseModel):
    company: str = ""
    position: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""
    achievement: str = ""


class InternshipOut(InternshipBase):
    id: int
    user_id: int
    model_config = ConfigDict(from_attributes=True)


class CertificateBase(BaseModel):
    name: str = ""
    date: str = ""
    description: str = ""


class CertificateOut(CertificateBase):
    id: int
    user_id: int
    model_config = ConfigDict(from_attributes=True)


# ---------- 用户 ----------
class UserCreate(BaseModel):
    name: str = ""
    phone: str = ""
    email: str = ""
    location: str = ""
    target_position: str = ""
    expected_salary: str = ""
    hobbies: str = ""


class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    location: Optional[str] = None
    target_position: Optional[str] = None
    expected_salary: Optional[str] = None
    hobbies: Optional[str] = None


class UserOut(BaseModel):
    id: int
    name: str
    phone: str
    email: str
    location: str
    target_position: str
    expected_salary: str = ""
    hobbies: str = ""
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

    @field_validator("name", "phone", "email", "location", "target_position",
                     "expected_salary", "hobbies", mode="before")
    @classmethod
    def _coerce_str(cls, v):
        return v if isinstance(v, str) else ""


class UserDetail(UserOut):
    educations: List[EducationOut] = []
    skills: List[SkillOut] = []
    projects: List[ProjectOut] = []
    internships: List[InternshipOut] = []
    certificates: List[CertificateOut] = []


# ---------- LLM 配置 ----------
class LLMConfigIn(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""


class LLMConfigOut(BaseModel):
    base_url: str = ""
    api_key_masked: str = ""
    model: str = ""


class ModelsRequest(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None


# ---------- 简历 / 自我评价 ----------
class ResumeCreate(BaseModel):
    jd_text: str
    target_position: str = ""
    expected_salary: str = ""
    include_salary: bool = True
    sections: List[str] = []
    template: str = "classic"


class RebuildIn(BaseModel):
    template: str = ""


class FabricateIn(BaseModel):
    fabricate: bool = True
    types: List[str] = []
    count: int = 3
    extra_jd: str = ""


class FabricateReviseIn(BaseModel):
    experiences: List[dict] = []
    feedback: str = ""


class AnswerItem(BaseModel):
    id: str = ""
    question: str = ""
    answer: str = ""


class AnswersIn(BaseModel):
    answers: List[AnswerItem] = []


class SeAnswersIn(BaseModel):
    answers: List[AnswerItem] = []
    supplement: str = ""


class SelfEvalGenerateIn(BaseModel):
    resume_id: Optional[int] = None
    answers: List[AnswerItem] = []
    supplement: str = ""


class SelfEvalRecordIn(BaseModel):
    content: str
    resume_id: Optional[int] = None
    qa: List[AnswerItem] = []


class SelfEvalRecordUpdate(BaseModel):
    content: Optional[str] = None


class SelfEvalRecordOut(BaseModel):
    id: int
    user_id: int
    resume_id: Optional[int] = None
    content: str
    qa: list = []
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class ResumeOut(BaseModel):
    id: int
    user_id: int
    jd_text: str
    jd_summary: dict = {}
    target_position: str
    expected_salary: str = ""
    include_salary: bool = True
    sections: list = []
    template: str
    status: str
    questions: list = []
    answers: list = []
    fabricated: list = []
    interview_prep: dict = {}
    se_questions: list = []
    se_answers: list = []
    skills_curated: list = []
    progress: str = ""
    personal_summary: str
    self_evaluation: str
    output_path: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

    @field_validator("jd_summary", "interview_prep", mode="before")
    @classmethod
    def _coerce_dict(cls, v):
        return v if isinstance(v, dict) else {}

    @field_validator(
        "questions", "answers", "fabricated", "sections",
        "se_questions", "se_answers", "skills_curated", mode="before")
    @classmethod
    def _coerce_list(cls, v):
        return v if isinstance(v, list) else []

    @field_validator(
        "jd_text", "target_position", "expected_salary", "status", "personal_summary",
        "self_evaluation", "output_path", "progress", "template", mode="before")
    @classmethod
    def _coerce_str(cls, v):
        return v if isinstance(v, str) else ""

    @field_validator("include_salary", mode="before")
    @classmethod
    def _coerce_bool(cls, v):
        return v if isinstance(v, bool) else (bool(v) if v is not None else True)