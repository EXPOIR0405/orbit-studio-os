"""Structural and evidence gates, not a claim that LLM content is objectively correct."""
import re

def _norm(text):
    # 줄바꿈·공백·따옴표 차이는 무시하고 글자만 비교
    return re.sub(r"[\s'\"‘’“”「」]", "", text)

def _artifact_text(report):
    parts=[report.get("summary",""),report.get("draft","")]
    parts+=[f.get("title","")+" "+f.get("detail","") for f in report.get("findings",[])]
    return _norm(" ".join(parts))

def unverified_quotes(report,artifacts):
    """QA의 warning·blocker 중 인용한 문장이 target 산출물에 없는 지적의 제목"""
    bad=[]
    for f in report.findings:
        if f.severity=="info":
            continue
        quote=_norm(f.quote)
        if f.target not in artifacts or len(quote)<4 or quote not in _artifact_text(artifacts[f.target]):
            bad.append(f.title)
    return bad

def evaluate(role,report,sources,artifacts=None):
    ids={s["id"] for s in sources}
    findings=report.findings
    references=[ref for f in findings for ref in f.sources]
    gates={
        "summary_present":bool(report.summary.strip()),
        "draft_present":bool(report.draft.strip()),
        "finding_evidence_present":all(bool(f.sources) for f in findings),
        "references_in_scope":all(ref in ids for ref in references),
        "analysis_has_evidence":role not in ["story","audience"] or bool(findings),
    }
    unverified=unverified_quotes(report,artifacts or {}) if role=="qa" else []
    if role=="qa":
        gates["qa_quotes_verified"]=not unverified
    return {"evaluator":"contract-evidence-v1","passed":all(gates.values()),"gates":gates,
            "reference_count":len(references),"semantic_accuracy":"requires_human_review",
            "qa_needs_revision":role=="qa" and (report.needs_review or any(f.severity in ["warning","blocker"] for f in findings)),
            "unverified_quotes":unverified}
