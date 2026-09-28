"""Structural and evidence gates, not a claim that LLM content is objectively correct."""
import re

def _norm(text):
    # 줄바꿈·공백·따옴표 차이는 무시하고 글자만 비교
    return re.sub(r"[\s'\"‘’“”「」]", "", text)

def _artifact_text(report, role):
    # campaign은 공개되는 문안(draft)만 대조. 메모(findings)에 적힌 거절한 요청 문구를 문안 문제로 인용하는 것을 막음
    if role=="campaign":
        return _norm(report.get("draft",""))
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
        if f.target not in artifacts or len(quote)<4 or quote not in _artifact_text(artifacts[f.target], f.target):
            bad.append(f.title)
    return bad

def downgrade_unverified(report,artifacts):
    """재요청 후에도 인용이 확인되지 않는 QA 경고·차단을 info로 낮춘다.
    대부분 이미 해결된 원고나 독자 의견을 산출물 문제로 올린 헛경고라(docs/08), 미션을 실패시키는 대신 표시만 남긴다."""
    bad=set(unverified_quotes(report,artifacts))
    findings=[f.model_copy(update={"severity":"info","title":"[인용 확인 불가] "+f.title}) if f.title in bad and f.severity!="info" else f
              for f in report.findings]
    needs_review=any(f.severity!="info" for f in findings)
    return report.model_copy(update={"findings":findings,"needs_review":needs_review}), sorted(bad)

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
