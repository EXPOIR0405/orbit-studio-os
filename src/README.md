# Source layout

현재 실행 코드는 없다. 아래는 구현 시 만들 모듈의 계획이다.

| 예정 경로 | 책임 |
| --- | --- |
| web/ | Next.js 운영 콘솔, React Flow 그래프, SSE 구독 |
| backend/orbit/api/ | FastAPI 라우트, 인증·권한, 입력 검증 |
| backend/orbit/orchestration/ | LangGraph 상태, 계획 검증, worker, 재작업 |
| backend/orbit/agents/ | 역할별 지시문과 버전이 고정된 설정 |
| backend/orbit/tools/ | 자료 조회, 모델 어댑터, 도구 허용 목록 |
| backend/orbit/storage/ | 업무 레코드, 체크포인트 연동, 이벤트 |
| backend/orbit/evaluation/ | 단일·고정·멀티 비교 실험과 지표 집계 |

모델 키와 실행 권한은 서버에서만 사용한다. UI 상태를 승인 근거로 신뢰하지 않는다. 실제 구현 순서는 mock → 단일 에이전트 기준선 → 역할 분리 → 복구·승인 → 비교 평가다.

루트 .env.example은 환경변수 설계 초안이다. 현재 로더가 없으며, 구현 시 backend가 루트 .env를 명시적으로 읽도록 정하고 frontend에는 공개 설정만 전달한다. .env 전체를 클라이언트 번들로 넘기지 않는다.

[전체 아키텍처](../architecture.md) · [상세 실행 계약](../docs/03-architecture.md).
