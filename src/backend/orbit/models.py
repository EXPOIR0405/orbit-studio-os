from typing import Literal
from pydantic import BaseModel, Field

Role = Literal["pd", "story", "audience", "campaign", "qa"]

class Finding(BaseModel):
    title: str
    detail: str
    sources: list[str]
    severity: Literal["info", "warning", "blocker"]

class Report(BaseModel):
    summary: str
    findings: list[Finding]
    draft: str
    needs_review: bool

class NewMission(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    goal: str = Field(min_length=5, max_length=2000)
    mode: Literal["mock", "live"] = "mock"
    call_limit: int = Field(default=12, ge=5, le=20)
    workflow: Literal["auto", "full", "story", "campaign"] = "auto"

class Decision(BaseModel):
    version: int
    package_hash: str

class Revision(BaseModel):
    version: int
    role: Literal["story", "campaign"]
    instruction: str = Field(min_length=3, max_length=1500)
