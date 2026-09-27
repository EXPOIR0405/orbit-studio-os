# v0.3 구현 상태와 검증 경계

이 문서는 미래 설계 문서보다 현재 구현 상태를 우선 설명한다.

## 실제 모델: 기본 비활성화

사용자 요청에 따라 ORBIT_ENABLE_LIVE=false가 기본값이다. 키가 존재해도 UI, API, 미션 시작/재작업, provider와 smoke script에서 실제 호출을 차단한다. 실제 호출을 다시 켜거나 유료 테스트를 수행하려면 사용자 허락을 먼저 받는다. 공개 .env.example에는 실제 키가 없다.

비활성화 요청 이전의 연결 확인은 1회·47토큰이었다. 이후 검증은 mock만 사용한다.

## 여섯 가지 기반

| 항목 | 구현 | 현재 한계 |
| --- | --- | --- |
| Tool calling | 역할별 allowlist, 입력 스키마, search_sources/get_source/search_approved_memory. 실제 provider에는 OpenAI function-call 왕복 구현 | 외부 웹·임의 SQL·API 쓰기 없음. live 경로는 사용자 요청으로 실행 검증 안 함 |
| Routing | 목표 키워드 또는 운영자 선택 → full/story/campaign. 선택 이유·규칙 버전 기록 | rules-v1 기준선. LLM 동적 계획·병렬 분배 아님 |
| State | DB에 입력·route·역할 산출물·승인 hash·호출 예약·이벤트 저장. 실패 후 완료 역할 건너뛰기 | 단일 API 프로세스/worker. 분산 lease와 LangGraph durable checkpointer는 후속 |
| Memory | 승인된 이전 결과만 작품/데이터 버전 범위 내 검색. 결과 revision 보존 | 작은 실험용 키워드 검색. 영구 설정집 자동 갱신·벡터 검색 없음 |
| Evaluation | 출력 계약, 빈 필드, 근거 ID 존재/접근 범위, QA 미해결 항목의 승인 차단 | 사실의 의미적 정확성은 사람 검토. mock 결과를 모델 성능으로 주장하지 않음 |
| Observability | 호출 이유·역할·version·도구·결과 건수·평가·tokens·duration·실패 상태 | 가격 기준 미설정 시 비용 null. 실제 청구액 아님. 기록은 로컬 operator에게만 제공 |

실제 provider는 도구 선택 1회와 구조화 결과 1회를 요청하며 각 요청 전에 호출 예산을 예약한다. 최대 출력 토큰은 각각 500/1600이다. 자동 재시도는 없다. 실패하여 사용량을 받지 못한 요청도 호출 수에서 제외하지 않으며 unknown으로 표시한다.

## 데이터와 실행

현재 fixture는 합성 EP.12 하나다. story는 원고/설정집, audience는 댓글, campaign은 제한된 비스포일러 자료와 초안, QA는 검수 자료를 읽는다. 도구에서 존재하지 않거나 권한 밖의 source_id를 거절한다.

PostgreSQL은 계획된 기본 운영 DB이고 Docker Compose 구성이 있다. Docker/PostgreSQL이 없는 개발 환경에서는 SQLite를 명시적 로컬 fallback으로 사용한다. 둘의 동일 동작을 주장하지 않으며 PostgreSQL 통합 테스트는 별도로 수행해야 한다. Supabase는 아직 생성/연결하지 않았다.

현재 DB는 단일 JSON 미션 테이블로 저장하며 create_all을 사용한다. Alembic 마이그레이션, 정규화 테이블, 멀티테넌트 인증은 아직 구현하지 않았다. 외부 공개 서비스로 배포하지 않는다.

## 이번 검증 결과

- pytest: 15개 통과. 라우팅, 도구 권한, 근거 검사, 승인된 기억, live 차단, 호출 추적, 선택적 재작업, 오래된 승인 거절, 복구와 내보내기 포함.
- Next.js production build와 TypeScript 검사 통과.
- 브라우저 수동 검증: 합성 미션 생성 → 5개 역할 완료 → 마케팅/QA만 재작업 → 버전 2 승인 → Audit에서 도구/평가/시간/0토큰 확인.
- 테스트 DB를 애플리케이션 import 전에 분리하며 실제 운영용 파일에 쓰지 않도록 수정.
- SSE 지연 시 실행 중인 미션에 한해 상태 조회를 보완.
- 실제 모델 function-calling, PostgreSQL, Supabase, Playwright CLI 시나리오는 미실행. 실제 모델 사용 성능·비용 검증 결과로 해석하지 않는다.

## 후속 순서

1. mock 단위·API·브라우저 흐름 테스트로 기본 로직 확인.
2. PostgreSQL 통합 검증과 스키마 마이그레이션.
3. 가격 스냅샷·금액 예산 정책과 단일/고정/멀티 비교 평가.
4. 사용자 승인 후 제한된 live 평가. 실제 성능과 비용을 별도 보고.
5. 인증·권한·분산 실행·보존 정책을 보강한 뒤 공개 데모 검토.
