# Source

- backend/orbit/api.py: 로컬 FastAPI와 SSE, 미션·승인 API.
- backend/orbit/service.py: LangGraph 실행, 산출물 버전, 재작업과 승인.
- backend/orbit/routing.py: 설명 가능한 규칙 라우팅.
- backend/orbit/tools.py: 역할별 읽기 전용 도구와 입력 검증.
- backend/orbit/memory.py: 같은 작품의 승인 결과 검색.
- backend/orbit/evaluation.py: 구조·근거 평가.
- backend/orbit/provider.py: mock과 잠긴 OpenAI function-calling 경로.
- backend/orbit/storage.py: SQLAlchemy 저장.
- web/: Next.js 운영 화면, 조직 그래프, 감사 기록.

루트 .env를 서버만 읽는다. 실제 호출은 ORBIT_ENABLE_LIVE=false로 차단된다.
[현재 상태와 한계](../docs/07-implementation-status.md)를 참고한다.
