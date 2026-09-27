"""Deterministic routing baseline: explainable, bounded, replaceable after evaluation."""
ROUTE_ROLES = {
    "full": ["pd","story","audience","campaign","qa"],
    "story": ["pd","story","qa"],
    "campaign": ["pd","audience","campaign","qa"],
}
def route(goal, workflow="auto"):
    if workflow != "auto":
        selected=workflow
        reason="운영자가 작업 범위를 직접 선택했습니다."
    elif any(word in goal for word in ["공개 준비","패키지","출시","전체"]):
        selected="full";reason="공개 준비 또는 전체 패키지 요청"
    elif any(word in goal for word in ["홍보","마케팅","캠페인"]):
        selected="campaign";reason="홍보 요청: 독자 분석과 마케팅, QA로 전달"
    elif any(word in goal for word in ["설정","대사","스토리","원고"]):
        selected="story";reason="원고·설정 검토 요청: 글작가·편집과 QA로 전달"
    else:
        selected="full";reason="명확한 단일 작업 분류가 없어 전체 계획을 제안"
    if selected not in ROUTE_ROLES:
        raise ValueError("허용되지 않은 작업 범위")
    return {"workflow":selected,"roles":ROUTE_ROLES[selected],"reason":reason,"version":"rules-v1","requires_operator_start":True}
