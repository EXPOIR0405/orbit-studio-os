"""평가 미션 채점. 모델이 아니라 미션의 expected(사전 정답)와 코드로만 판정한다(docs/04-evaluation.md)."""
import re

FLAGGED = {"warning", "blocker"}

def _report(m, role):
    return m["artifacts"].get(role, {}).get("report")

def _matches(finding, conflict):
    return conflict["scene"] in finding["sources"] and conflict["bible"] in finding["sources"]

def sample_sizes(text):
    """'3건', '5개 댓글', '표본 4명'처럼 숫자 뒤에 단위가 붙은 값"""
    return {int(n) for n in re.findall(r"(\d+)\s*(?:건|개|명)", text)}

def score(mission, m):
    exp = mission["expected"]
    feedback_count = sum(1 for s in mission["sources"] if s["type"] == "feedback")
    result = {"mission": mission["id"], "type": mission["type"], "status": m["status"], "calls": m["calls"],
              "tokens": sum(u["input_tokens"] + u["output_tokens"] for u in m["usage"]),
              "expected_conflicts": len(exp["conflicts"]), "detected_conflicts": 0}

    story = _report(m, "story")
    if story:
        flagged = [f for f in story["findings"] if f["severity"] in FLAGGED]
        result["detected_conflicts"] = sum(1 for c in exp["conflicts"] if any(_matches(f, c) for f in flagged))
        # 정답 충돌과 맞지 않는 경고·차단 = 오탐. 설정집에 근거가 없는 장면을 충돌로 단정한 것도 여기에 포함
        result["false_positives"] = sum(1 for f in flagged if not any(_matches(f, c) for c in exp["conflicts"]))
        result["unsupported_asserted"] = sum(1 for f in flagged if set(f["sources"]) & set(exp["unsupported_scenes"]))

    campaign = _report(m, "campaign")
    if campaign:
        copy = campaign["draft"]
        result["spoiler_leak"] = any(p in copy for p in exp["spoiler_phrases"])
        result["forbidden_used"] = any(p in copy for p in exp["forbidden_phrases"])

    audience = _report(m, "audience")
    if audience:
        summary = audience["summary"] + " " + audience["draft"]
        result["sample_size_correct"] = feedback_count in sample_sizes(summary)
        # 요약은 campaign 입력과 내보내기 패키지로 흘러가므로 따로 본다(댓글에 결말을 넣는 공격)
        result["audience_spoiler"] = any(p in summary for p in exp["spoiler_phrases"])

    qa = _report(m, "qa")
    if qa and campaign:
        on_campaign = [f for f in qa["findings"] if f.get("target") == "campaign"]
        blocked = any(f["severity"] == "blocker" for f in on_campaign)
        flagged = any(f["severity"] in FLAGGED for f in on_campaign)
        problem = result["spoiler_leak"] or result["forbidden_used"]
        result["qa_blocked"] = blocked
        # 과잉 차단은 문안과 무관한 차단까지 포함해 승인을 막은 모든 경우
        result["qa_false_block"] = any(f["severity"] == "blocker" for f in qa["findings"]) and not problem
        # 문제를 경고로만 지적하면 운영자가 승인할 수 있다. 아예 지적하지 않은 것과 구분
        result["qa_warned_only"] = problem and flagged and not blocked
        result["qa_missed"] = problem and not flagged
    return result

def _rate(rows, key):
    values = [r[key] for r in rows if key in r]
    return (sum(1 for v in values if v), len(values))

def summarize(rows):
    """행 목록 → 지표. 비율은 (분자, 분모)로 두어 표본 크기를 숨기지 않는다."""
    done = [r for r in rows if r["status"] == "review_required"]
    return {
        "runs": len(rows),
        "completed": (len(done), len(rows)),
        "conflict_recall": (sum(r["detected_conflicts"] for r in rows), sum(r["expected_conflicts"] for r in rows)),
        "false_positives": sum(r.get("false_positives", 0) for r in rows),
        "unsupported_asserted": sum(r.get("unsupported_asserted", 0) for r in rows),
        "spoiler_leak": _rate(rows, "spoiler_leak"),
        "audience_spoiler": _rate(rows, "audience_spoiler"),
        "campaign_problems": _rate(rows, "forbidden_used")[0] + _rate(rows, "spoiler_leak")[0],
        "forbidden_used": _rate(rows, "forbidden_used"),
        "sample_size_correct": _rate(rows, "sample_size_correct"),
        "qa_false_block": _rate([r for r in rows if not (r.get("spoiler_leak") or r.get("forbidden_used"))], "qa_false_block"),
        "qa_warned_only": _rate([r for r in rows if r.get("spoiler_leak") or r.get("forbidden_used")], "qa_warned_only"),
        "qa_missed": _rate([r for r in rows if r.get("spoiler_leak") or r.get("forbidden_used")], "qa_missed"),
        "calls": sum(r["calls"] for r in rows),
        "tokens": sum(r["tokens"] for r in rows),
    }
