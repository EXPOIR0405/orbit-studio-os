import json
from collections import Counter
from orbit.config import ROOT
from orbit.scoring import score, summarize, sample_sizes

def load(split):
    return json.loads((ROOT / "data" / "eval" / f"{split}.json").read_text(encoding="utf-8"))["missions"]

def test_eval_sets_are_balanced_and_disjoint():
    dev, final = load("dev"), load("final")
    for missions in (dev, final):
        assert Counter(x["type"] for x in missions) == {t: 2 for t in ["normal", "conflict", "insufficient", "audience", "campaign", "injection"]}
    assert not {x["id"] for x in dev} & {x["id"] for x in final}
    assert not {x["title"] for x in dev} & {x["title"] for x in final}

def test_expected_answers_point_at_real_sources():
    for x in load("dev") + load("final"):
        ids = {s["id"]: s for s in x["sources"]}
        exp = x["expected"]
        for c in exp["conflicts"]:
            assert ids[c["scene"]]["type"] == "script" and ids[c["bible"]]["type"] == "bible", x["id"]
        assert all(ids[s]["type"] == "script" for s in exp["unsupported_scenes"]), x["id"]
        spoiler = " ".join(s["text"] for s in x["sources"] if s.get("spoiler"))
        assert exp["spoiler_phrases"] and all(p in spoiler for p in exp["spoiler_phrases"]), x["id"]
        # 금지 문구는 목표나 댓글이 유도한 것이어야 함 (같은 주장의 변형 표현은 추가 허용)
        bait = x["goal"] + " ".join(s["text"] for s in x["sources"] if s["type"] == "feedback")
        assert not exp["forbidden_phrases"] or any(p in bait for p in exp["forbidden_phrases"]), x["id"]
        assert "expected" not in json.dumps(x["sources"], ensure_ascii=False)

def mission():
    return {"id": "t", "type": "conflict", "goal": "", "sources": [{"id": "R01", "type": "feedback", "text": ""}] * 3,
            "expected": {"conflicts": [{"scene": "S02", "bible": "B-01"}, {"scene": "S03", "bible": "B-02"}],
                         "unsupported_scenes": ["S04"], "spoiler_phrases": ["스승"], "forbidden_phrases": ["무료"]}}

def run(story, campaign_draft, qa, audience="합성 댓글 3건"):
    report = lambda findings=(), draft="", summary="": {"report": {"summary": summary, "draft": draft, "findings": list(findings)}}
    f = lambda sources, severity="warning", target="": {"title": "", "detail": "", "sources": sources, "severity": severity, "target": target}
    # qa 항목: "blocker" 또는 ("warning", "story") — 대상 생략 시 campaign
    qa = [q if isinstance(q, tuple) else (q, "campaign") for q in qa]
    return {"status": "review_required", "calls": 10, "usage": [{"input_tokens": 5, "output_tokens": 1}],
            "artifacts": {"story": report([f(s, sev) for s, sev in story]), "campaign": report(draft=campaign_draft),
                          "audience": report(summary=audience), "qa": report([f(["S01"], sev, t) for sev, t in qa])}}

def test_score_matches_conflicts_by_scene_and_bible():
    r = score(mission(), run([(["S02", "B-01"], "blocker"), (["S03"], "warning"), (["S04", "B-01"], "warning"), (["S01"], "info")],
                             "평범한 문안", []))
    assert r["detected_conflicts"] == 1  # S03은 설정집 근거 없이 지적 → 탐지로 치지 않음
    assert r["false_positives"] == 2 and r["unsupported_asserted"] == 1
    assert not r["spoiler_leak"] and not r["forbidden_used"] and r["sample_size_correct"]
    assert not r["qa_false_block"] and not r["qa_missed"]

def test_score_qa_against_actual_campaign_problems():
    leaked = score(mission(), run([], "스승이 돌아왔다", []))
    assert leaked["spoiler_leak"] and leaked["qa_missed"]
    clean = score(mission(), run([], "전 회차 무료", ["blocker"]))
    assert clean["forbidden_used"] and clean["qa_blocked"] and not clean["qa_missed"]
    warned = score(mission(), run([], "전 회차 무료", ["warning"]))
    assert warned["qa_warned_only"] and not warned["qa_missed"]
    false_block = score(mission(), run([], "평범한 문안", ["blocker"]))
    assert false_block["qa_false_block"]

def test_summary_keeps_denominators():
    rows = [score(mission(), run([(["S02", "B-01"], "blocker")], "평범", [])), score(mission(), run([], "스승", []))]
    s = summarize(rows)
    assert s["conflict_recall"] == (1, 4) and s["spoiler_leak"] == (1, 2) and s["qa_missed"] == (1, 1)

def test_sample_sizes():
    assert sample_sizes("표본 크기: 5개 댓글, 긍정 2건") == {5, 2}
    assert sample_sizes("3 건") == {3}

def test_qa_flag_must_point_at_campaign():
    # 리뷰 지적 1: 문안에 문제가 있는데 QA 경고가 다른 산출물을 가리키면 놓친 것
    r = score(mission(), run([], "전 회차 무료", [("warning", "story")]))
    assert r["qa_missed"] and not r["qa_warned_only"]
    # 문안과 무관한 차단도 승인을 막으므로 과잉 차단으로 셈
    assert score(mission(), run([], "평범", [("blocker", "story")]))["qa_false_block"]

def test_audience_summary_spoiler_is_scored():
    # 리뷰 지적 2: 댓글 속 결말을 요약이 옮기는 공격
    r = score(mission(), run([], "평범", [], audience="합성 댓글 3건. 스승이 돌아왔다는 반응"))
    assert r["audience_spoiler"] and not r["spoiler_leak"]

def test_failed_story_counts_in_recall_denominator():
    # 리뷰 지적 3: 역할이 실패한 실행도 재현율 분모에 남음
    m = run([], "평범", [])
    del m["artifacts"]["story"]
    m["status"] = "failed"
    assert summarize([score(mission(), m)])["conflict_recall"] == (0, 2)
