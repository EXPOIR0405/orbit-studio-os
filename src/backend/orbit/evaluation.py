"""Structural and evidence gates, not a claim that LLM content is objectively correct."""
import re

def _norm(text):
    # 줄바꿈·공백·따옴표·문장부호 차이는 무시하고 글자만 비교 ('…'를 '...'로 쓰는 등의 사소한 인용 오차 허용)
    return re.sub(r"[\s'\"‘’“”「」.,…!?·~\-–—()\[\]]", "", text)

def _artifact_text(report, role):
    # campaign은 공개되는 문안(draft)만 대조. 메모(findings)에 적힌 거절한 요청 문구를 문안 문제로 인용하는 것을 막음
    if role=="campaign":
        return _norm(report.get("draft",""))
    parts=[report.get("summary",""),report.get("draft","")]
    parts+=[f.get("title","")+" "+f.get("detail","") for f in report.get("findings",[])]
    return _norm(" ".join(parts))

UNVERIFIED = "[인용 확인 불가] "

def _unverified(f,artifacts):
    # 이미 한 단계 낮춘 지적은 표시가 붙어 운영자에게 보이므로 다시 게이트에 걸지 않음
    if f.severity=="info" or f.title.startswith(UNVERIFIED):
        return False
    quote=_norm(f.quote)
    return f.target not in artifacts or len(quote)<4 or quote not in _artifact_text(artifacts[f.target], f.target)

def unverified_quotes(report,artifacts):
    """QA의 warning·blocker 중 인용한 문장이 target 산출물에 없는 지적의 제목"""
    return [f.title for f in report.findings if _unverified(f,artifacts)]

def downgrade_unverified(report,artifacts):
    """재요청 후에도 인용이 확인되지 않는 QA 지적을 한 단계 낮춘다(blocker → warning, warning → info).
    대부분 이미 해결된 원고나 독자 의견을 올린 헛경고라(docs/08) 미션을 실패시키지 않는다.
    다만 인용만 어긋난 진짜 차단일 수 있어 blocker는 warning으로 남겨 운영자가 보게 한다."""
    lower={"blocker":"warning","warning":"info"}
    # 제목이 아니라 지적마다 판정. 같은 제목의 확인된 차단까지 낮추지 않게
    findings=[f.model_copy(update={"severity":lower[f.severity],"title":UNVERIFIED+f.title}) if _unverified(f,artifacts) else f
              for f in report.findings]
    needs_review=any(f.severity!="info" for f in findings)
    return report.model_copy(update={"findings":findings,"needs_review":needs_review}), unverified_quotes(report,artifacts)

def evaluate(role,report,sources,artifacts=None):
    ids={s["id"] for s in sources}
    findings=report.findings
    references=[ref for f in findings for ref in f.sources]
    gates={
        "summary_present":bool(report.summary.strip()),
        "draft_present":bool(report.draft.strip()),
        "finding_evidence_present":all(bool(f.sources) for f in findings),
        "references_in_scope":all(ref in ids for ref in references),
        # story는 충돌이 없으면 findings가 비는 게 정답. 강제하면 오류 없는 원고에서 충돌을 지어냄(docs/08)
        "analysis_has_evidence":role!="audience" or bool(findings),
    }
    unverified=unverified_quotes(report,artifacts or {}) if role=="qa" else []
    if role=="qa":
        gates["qa_quotes_verified"]=not unverified
    return {"evaluator":"contract-evidence-v1","passed":all(gates.values()),"gates":gates,
            "reference_count":len(references),"semantic_accuracy":"requires_human_review",
            "qa_needs_revision":role=="qa" and (report.needs_review or any(f.severity in ["warning","blocker"] for f in findings)),
            "unverified_quotes":unverified}
