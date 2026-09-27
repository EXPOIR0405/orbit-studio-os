"""Structural and evidence gates, not a claim that LLM content is objectively correct."""
def evaluate(role,report,sources):
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
    return {"evaluator":"contract-evidence-v1","passed":all(gates.values()),"gates":gates,
            "reference_count":len(references),"semantic_accuracy":"requires_human_review",
            "qa_needs_revision":role=="qa" and (report.needs_review or any(f.severity in ["warning","blocker"] for f in findings))}
