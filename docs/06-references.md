# 참고 자료와 설계 결정

확인일: 2026-09-27. 아래는 아키텍처 참고 자료이며 이 제품의 시장성이나 성능을 입증하는 자료가 아니다.

## 외부 참고

- [Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents): 단순한 구성부터 시작하고 작업 특성에 맞춰 orchestrator/worker와 evaluator 패턴을 선택하는 관점. 여기서는 제한된 계획과 기준선 비교를 설계하는 데 참고했다.
- [Anthropic — How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system): 역할 분담과 병렬 연구에 관한 구현 사례. 웹툰 운영에서 동일한 효율을 보장하지 않으므로 직접 평가한다.
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence): 실행 단위 체크포인트와 실행 간 저장소의 구분. 여기서는 미션 복구 상태와 승인된 작품 설정을 분리한다.
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts): 중단·재개와 영속 체크포인터의 사용, 재개 시 노드 시작부터 실행되는 동작. 승인 단계 전 부작용을 피하고 멱등 실행을 설계하는 근거다.

## 결정 기록

| 결정 | 이유 | 재검토 조건 |
| --- | --- | --- |
| 운영자 중심 UI | 사람이 결과와 예외를 판단하는 업무가 핵심 | CEO 직접 사용 수요가 검증될 때 |
| 회차 공개 준비부터 시작 | 입력·출력·검수 기준을 구체화할 수 있음 | 도메인 인터뷰가 다른 우선 업무를 보여줄 때 |
| 제한된 동적 작업 그래프 | 자율 계획과 예측 가능한 운영을 함께 검증 | 기준선 대비 효익이 없으면 고정 흐름으로 축소 |
| LangGraph 후보 | 영속 실행과 사람 개입 구조를 검토하기 쉬움 | 구현 실험에서 복잡성이 이점을 넘을 때 |
| DB에 버전과 감사 이력 | 재작업·승인·복구에 같은 기준 필요 | 보존량과 처리량이 커질 때 |
| 외부 게시 제외 | 첫 평가의 끝점을 명확히 정의 | 패키지 품질과 실제 운영 수요 검증 후 |
| 공개 원문 대신 합성 데이터 | 재현 가능한 검수 시나리오 제공 | 정식 사용 허가와 데이터 관리 체계 확보 후 |

기술 선택은 잠정안이다. 이 설계에서 제안한 비용 상한·타임아웃·평가 목표·역할 수는 외부 자료의 권장 수치를 인용한 것이 아니라 프로젝트 검증을 위한 초기값이다.
