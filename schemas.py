from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


# ---------- User Schemas ----------

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: str
    password: str = Field(..., min_length=8)

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    created_at: datetime

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Analysis Schemas ----------

class AnalysisCreate(BaseModel):
    job_description: str = Field(..., min_length=50)

class SectionFeedback(BaseModel):
    score: int
    feedback: str
    suggestions: list[str]

class AnalysisResult(BaseModel):
    match_score: int
    missing_keywords: list[str]
    strong_keywords: list[str]
    overall_feedback: str
    sections: dict
    top_suggestions: list[str]

class AnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    match_score: int
    job_description: str
    result: str
    created_at: datetime