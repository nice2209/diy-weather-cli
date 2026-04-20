# Deep Interview Spec: DIY 날씨 요약 CLI 에이전트 MVP

## Metadata
- Interview ID: diy-agent-mvp-001
- Rounds: 4
- Final Ambiguity Score: 17.5%
- Type: greenfield
- Generated: 2026-04-20
- Threshold: 20%
- Status: PASSED

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.90 | 0.40 | 0.36 |
| Constraint Clarity | 0.70 | 0.30 | 0.21 |
| Success Criteria | 0.85 | 0.30 | 0.255 |
| **Total Clarity** | | | **0.825** |
| **Ambiguity** | | | **0.175** |

## Goal
사용자가 개인 Windows 랩톱 CLI에서 자연어로 날씨 질문을 입력하면, wttr.in 데이터를 Ollama Cloud LLM이 해석·요약해 한국어 자연어로 응답하는 단일턴 DIY 에이전트. 현재 시점 + 단기 예보를 통합해 한 줄~한 문단 요약을 반환한다. 향후 하드웨어 이식·메모리·다중 도구는 Post-MVP.

## Constraints
- **언어/런타임:** Python (버전은 Architect 결정, 3.11+ 권장)
- **실행 환경:** Windows 개인 랩톱, CLI 전용 (`python main.py` 또는 `uv run` 스타일)
- **LLM:** Ollama Cloud API (로컬 Ollama 아님, 인터넷 필수)
- **날씨 데이터:** wttr.in (cURL/HTTP)
- **아키텍처:** 단일 파일 허용 (MVP 단계 복잡도 최소화)
- **단일턴:** 대화 컨텍스트/메모리 없음
- **출력 언어:** 한국어
- **대화 흐름:** 질문 1 → 답변 1 (follow-up 없음)
- **외부 의존성:** 인터넷 연결 필수 (wttr.in + Ollama Cloud 모두 네트워크)

## Non-Goals (명시적 제외)
- 하드웨어 이식 (Raspberry Pi 등) — Post-MVP
- 메모리/연속 대화 — Post-MVP
- 범용 툴 호출 에이전트 구조 — Post-MVP
- 웹 스크래핑 (CDP, 로그인 세션) — Post-MVP
- 논문 요약·옵시디언 통합 — Post-MVP
- 웹 UI / Flask — Post-MVP
- 멀티랭귀지 답변 — 한국어만

## Acceptance Criteria
- [ ] **Happy path:** "서울 오늘 날씨", "내일 비 와?" 등 표준 질문에 wttr.in 기반 한국어 요약 반환
- [ ] **현재+단기 통합:** 답변에 현재 기온/체감/습도/바람 + 단기 예보 코멘트 포함
- [ ] **Graceful error 1:** 인터넷 연결 끊김 시 사용자가 이해 가능한 한국어 에러 메시지
- [ ] **Graceful error 2:** wttr.in 장애/타임아웃 시 사용자가 이해 가능한 한국어 에러 메시지
- [ ] **Graceful error 3:** 지역명 불명확/미지정 시 사용자 안내 메시지 (기본 지역 사용 또는 재입력 요청)
- [ ] **Ollama Cloud 연동:** API 키 환경변수로 주입, 하드코딩 금지
- [ ] **단일 진입점:** `python main.py "질문"` 또는 REPL 스타일 중 Architect 결정
- [ ] **로그:** stderr로 에러/디버그 분리 (stdout은 사용자 답변 전용)

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| idea.md의 5+ 기능이 모두 MVP | "단 하나의 성공 시나리오는?" | 실시간 날씨 조회 에이전트만 MVP |
| 툴콜 에이전트 구조 | 요약형 vs 판단형 vs 툴콜형 | 요약형 (단일 쿼리 → 통합 요약) |
| 하드웨어·Flask·Pi 준비 필요 | "어디서 어떻게 실행?" | 개인 랩톱 CLI 전용, 이식은 Post-MVP |
| 완벽한 happy path만 필요 | Contrarian: 실패도 다뤄야 실용? | Happy + graceful error 모두 수락 테스트 |
| 연속 대화/메모리 필요 | Contrarian: MVP 가치에 진짜 필요? | 단일턴 확정, 메모리는 Post-MVP |

## Technical Context (Greenfield)
- **빈 프로젝트:** `idea.md` + 빈 `.omc/` 디렉토리만 존재
- **원본 영감:** 홍정모 "나의 에이전트 From Scratch" 튜토리얼 스타일 (main.py 기반 단일파일 시작)
- **참고 링크:** wttr.in (cURL 날씨), Ollama Cloud API 문서
- **개발 OS:** Windows 11, bash 셸 (Claude Code)

## Ontology (Key Entities) — Final
| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| User | core | query_text, preferred_language=ko | issues WeatherQuery |
| Agent | core | ollama_model, wttr_endpoint | processes WeatherQuery → WeatherSummary |
| WeatherQuery | core | raw_text, parsed_location, parsed_timeframe | handled by Agent |
| WeatherSummary | core | current_conditions, short_term_forecast, ko_summary | produced by Agent |
| ErrorResponse | supporting | error_type, user_message_ko | returned by Agent on failure |
| CLI | supporting | entry_point, args | hosts User ↔ Agent |
| wttr.in | external | http endpoint | queried by Agent |
| OllamaCloud | external | api_endpoint, api_key_env | invoked by Agent |

## Ontology Convergence
| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 5 | 5 | - | - | N/A |
| 2 | 6 | 1 (WeatherSummary) | 0 | 5 | 83% |
| 3 | 7 | 1 (CLI) | 0 | 6 | 86% |
| 4 | 8 | 1 (ErrorResponse) | 0 | 7 | 88% |

엔티티가 단조 증가하면서도 기존 엔티티는 모두 보존됨 → 도메인 모델 안정화 중. 코어 엔티티(User/Agent/WeatherQuery/WeatherSummary)는 Round 2부터 불변.

## Open Questions (Architect 단계에서 결정)
- Python 버전 (3.11/3.12) 및 의존성 도구 (uv vs pip + requirements.txt)
- 디폴트 지역 처리 (인자 필수 / 환경변수 / "서울" 하드코딩)
- 답변 길이 목표 (1문장 / 2-3문장 / 문단)
- 단일파일 vs 간단한 모듈 분리 (main.py / agent.py / weather.py)
- Ollama Cloud 모델명 (gpt-oss?, 다른 모델?)
- 프롬프트 설계 (시스템 프롬프트 한국어 강제 방식)

## Interview Transcript
<details>
<summary>Full Q&A (4 rounds)</summary>

### Round 1 — Goal Clarity
**Q:** MVP가 성공했다고 말할 때, '가장 먼저 완벽하게 동작해야 할' 단 하나의 시나리오는 무엇인가요?
**A:** 실시간 날씨 조회 에이전트
**Ambiguity:** 59% (Goal 0.65, Constraints 0.30, Criteria 0.20)

### Round 2 — Success Criteria
**Q:** 'MVP 완성'을 누가 봐도 인정하려면 어떤 질문→답변 쌍이 동작해야 하나요?
**A:** 요약형 (현재~단기 통합 요약)
**Ambiguity:** 41% (Goal 0.80, Constraints 0.35, Criteria 0.55)

### Round 3 — Constraints
**Q:** MVP를 '어디서 어떻게' 실행할 계획인가요?
**A:** 개인 랩톱 CLI 전용 (현재 더 진행)
**Ambiguity:** 30% (Goal 0.85, Constraints 0.65, Criteria 0.55)

### Round 4 — Success Criteria (Contrarian mode)
**Q:** 세 가지 시나리오가 모두 동작해야 MVP '완성'입니까, 하나만 완벽하면 충분해요?
**A:** 행복 + 실패 서사적 처리
**Ambiguity:** 17.5% (Goal 0.90, Constraints 0.70, Criteria 0.85) ✅ Threshold met

</details>
