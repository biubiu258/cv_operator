"""数据库 ORM 模型。"""
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text,
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), default="")
    phone = Column(String(30), default="")
    email = Column(String(100), default="")
    location = Column(String(100), default="")
    target_position = Column(String(100), default="")
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    educations = relationship("Education", back_populates="user", cascade="all, delete-orphan")
    skills = relationship("Skill", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    internships = relationship("Internship", back_populates="user", cascade="all, delete-orphan")
    certificates = relationship("Certificate", back_populates="user", cascade="all, delete-orphan")
    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    self_evaluations = relationship("SelfEvaluation", back_populates="user", cascade="all, delete-orphan")


class Education(Base):
    __tablename__ = "educations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    school = Column(String(200), default="")
    major = Column(String(100), default="")
    degree = Column(String(50), default="")
    start_date = Column(String(30), default="")
    end_date = Column(String(30), default="")
    courses = Column(Text, default="")
    gpa = Column(String(50), default="")
    rank = Column(String(50), default="")

    user = relationship("User", back_populates="educations")


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    category = Column(String(50), default="")
    name = Column(String(100), default="")
    proficiency = Column(String(20), default="")

    user = relationship("User", back_populates="skills")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(200), default="")
    role = Column(String(100), default="")
    tech_stack = Column(String(300), default="")
    start_date = Column(String(30), default="")
    end_date = Column(String(30), default="")
    description = Column(Text, default="")
    result = Column(Text, default="")

    user = relationship("User", back_populates="projects")


class Internship(Base):
    __tablename__ = "internships"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    company = Column(String(200), default="")
    position = Column(String(100), default="")
    start_date = Column(String(30), default="")
    end_date = Column(String(30), default="")
    description = Column(Text, default="")
    achievement = Column(Text, default="")

    user = relationship("User", back_populates="internships")


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(200), default="")
    date = Column(String(50), default="")
    description = Column(Text, default="")

    user = relationship("User", back_populates="certificates")


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    jd_text = Column(Text, default="")
    jd_summary = Column(JSON, default=dict)
    target_position = Column(String(100), default="")
    sections = Column(JSON, default=list)
    status = Column(String(20), default="draft")
    questions = Column(JSON, default=list)
    answers = Column(JSON, default=list)
    fabricated = Column(JSON, default=list)
    interview_prep = Column(JSON, default=dict)
    personal_summary = Column(Text, default="")
    self_evaluation = Column(Text, default="")
    output_path = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User", back_populates="resumes")


class SelfEvaluation(Base):
    __tablename__ = "self_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    resume_id = Column(Integer, nullable=True)
    content = Column(Text, default="")
    qa = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="self_evaluations")


class LLMConfig(Base):
    __tablename__ = "llm_config"

    id = Column(Integer, primary_key=True)
    base_url = Column(String(300), default="")
    api_key = Column(Text, default="")  # 加密存储
    model = Column(String(200), default="")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)