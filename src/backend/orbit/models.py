from typing import Literal
from pydantic import BaseModel, Field

Role = Literal["pd", "story", "audience", "campaign", "qa"]

class Finding(BaseModel):
    title: str
    detail: str
    sources: list[str]
    severity: Literal["info", "warning", "blocker"]
    # QA가 warning·blocker를 달 때만 채운다. quote가 target 산출물에 실제로 있는지 evaluation이 코드로 확인
    target: str = Field(default="", description="QA의 warning·blocker가 가리키는 산출물 역할(story/audience/campaign). 그 외에는 빈 문자열")
    quote: str = Field(default="", description="target 산출물에서 문제 문장을 글자 그대로 인용. 그 외에는 빈 문자열")

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
