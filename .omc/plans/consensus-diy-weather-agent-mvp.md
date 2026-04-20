# Consensus Plan: DIY Weather Agent MVP

**Source spec:** `.omc/specs/deep-interview-diy-weather-agent-mvp.md` (ambiguity 17.5%)
**Pipeline:** deep-interview → ralplan (this doc) → autopilot Phase 2
**Consensus:** 1 iteration (Planner → Architect → Critic APPROVE)
**Generated:** 2026-04-20

---

## RALPLAN-DR Summary

### Principles
1. Single-file simplicity first (MVP fits in one `main.py`; modularize only if confusion-reducing)
2. Explicit Korean-facing errors (stdout=answer only, stderr=debug/logs)
3. No secret leaks (`OLLAMA_API_KEY` via env var only; never logged)
4. Tutorial-legibility > cleverness (홍정모 "main.py From Scratch" style)
5. Network honesty (wttr.in + Ollama Cloud are hard deps; fail loud in Korean)

### Decision Drivers
1. MVP speed — end-to-end today on Windows 11, bash, Python
2. Beginner tutorial audience legibility
3. Windows + Ollama Cloud compat (no Unix shims, no local ollama daemon)

### Locked Decisions
| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| Q1 | Python version | **3.11** | Broadest Windows wheel coverage, matches spec "3.11+ 권장" |
| Q2 | Dep management | **pip + requirements.txt** | Zero extra install; beginner-legible |
| Q3 | Default location | **env `DEFAULT_LOCATION`=서울 + `--location` CLI arg + blocklist** | Works out-of-box; honors Graceful Error 3; blocklist (`오늘/내일/지금/현재/요즘`) prevents regex false-matches |
| Q4 | Answer length | **1~3문장** | Matches spec wording "한 줄~한 문단"; reduces sentence-count drift on small models |
| Q5 | Ollama model | **`gpt-oss:20b` default, `OLLAMA_MODEL` override** | Cost/latency fit for personal tutorial; 120b documented as override |
| Q6 | File structure | **single `main.py`** | Tutorial fit; 200-line rule comfortably met |
| Q7 | wttr.in Korean field | **`current_condition[0].lang_ko[0].value`** | Verified: `weatherDesc` stays English even with `lang=ko` param |

---

## ADR: DIY Weather Agent MVP Architecture

### Decision
Build a single-file Python 3.11 CLI (`main.py`) that accepts a Korean query, fetches wttr.in JSON (lang_ko), sends it with a Korean system prompt to Ollama Cloud (`gpt-oss:20b`), and prints a 1–3 sentence Korean summary to stdout.

### Drivers
- Personal tutorial audience (홍정모 스타일)
- MVP speed — runs today
- Windows 11 + bash under Claude Code
- No stack proliferation

### Alternatives Considered
- **`uv` over pip** — rejected: adds install step; documented as optional in README
- **`gpt-oss:120b` default** — rejected: cost/latency not justified for short summaries; kept as override
- **Modular split (`weather.py`+`agent.py`)** — rejected at MVP; revisit with Post-MVP memory/tools
- **Required `--location` arg (no default)** — rejected: spec permits "기본 지역 사용" on unclear input
- **OpenAI-compat `/v1/chat/completions`** — rejected: native Ollama `/api/chat` verified simpler and correct for `message.content` parsing

### Why Chosen
Each rejection preserves one of the 5 principles (simplicity, tutorial-legibility, MVP speed). Flipping model default to 20b came from Architect review — better fit for "personal tutorial" driver.

### Consequences
- ✅ Runs end-to-end on a fresh Windows machine with only `pip install -r requirements.txt` + API key env
- ✅ Every error user sees is Korean
- ✅ No secret surface beyond env var
- ⚠️ Small models may occasionally emit 4+ sentences (relaxed "1~3문장" mitigates)
- ⚠️ Regex location parser is heuristic; blocklist covers the obvious ambiguous tokens
- ⚠️ `requests.RequestException` catch-all for unexpected exceptions (SSLError, ChunkedEncodingError) maps to exit 6

### Follow-ups (Post-MVP, explicitly deferred)
- Raspberry Pi port
- Memory / multi-turn
- CDP-based web scraping (separate project)
- Flask UI
- Paper summarization / Obsidian sync
- `pytest` suite / CI

---

## Implementation Plan

### Files to create
| Path | Purpose | ~LOC |
|------|---------|------|
| `main.py` | Entry point; argparse → env → location → wttr → ollama → stdout | ~150 |
| `requirements.txt` | `requests>=2.32` only | 1 |
| `.env.example` | `OLLAMA_API_KEY=`, `OLLAMA_MODEL=gpt-oss:20b`, `DEFAULT_LOCATION=서울` | 3 |
| `README.md` | Install/run, env setup, exit codes, Windows cmd examples | ~50 |

### Step 1 — Scaffolding (AC: 단일 진입점, 로그 분리)
- `argparse`: positional `query` (required), optional `--location`
- Read env: `OLLAMA_API_KEY` (required), `OLLAMA_MODEL` (default `gpt-oss:20b`), `DEFAULT_LOCATION` (default `서울`)
- `logging.basicConfig(stream=sys.stderr, level=logging.INFO, format=...)`
- If `OLLAMA_API_KEY` missing → log Korean error, exit 2

### Step 2 — Location resolution (AC: Graceful Error 3)
- Priority: `--location` arg > query regex scan > `DEFAULT_LOCATION`
- Regex: extract first `[가-힣]+` token preceding `날씨|기온|비|눈|예보` keywords
- **Blocklist:** if extracted token ∈ {`오늘`, `내일`, `지금`, `현재`, `요즘`, `오전`, `오후`, `저녁`, `아침`} → discard, fall back to `DEFAULT_LOCATION`
- Log to stderr: "지역을 찾지 못해 기본값 '{default}'을 사용합니다." when fallback triggered

### Step 3 — wttr.in fetch (AC: Happy path, Graceful Error 1 & 2)
- URL: `https://wttr.in/{urllib.parse.quote(location)}?format=j1&lang=ko`
- Headers: `User-Agent: diy-weather-agent/0.1`
- Timeout: 10s
- Error mapping:
  - `requests.ConnectionError` → stderr "인터넷 연결을 확인해주세요.", exit 3
  - `requests.Timeout` → stderr "날씨 서버 응답이 지연되고 있어요. 잠시 후 다시 시도해주세요.", exit 4
  - `status != 200` → stderr f"날씨 서버 장애 중이에요 (HTTP {code}).", exit 5
  - Other `requests.RequestException` → stderr generic Korean message, exit 5
- **Extract Korean fields:**
  - `current_condition[0].lang_ko[0].value` for weather description
  - `temp_C`, `FeelsLikeC`, `humidity`, `windspeedKmph` for current
  - `weather[0].hourly[4].lang_ko[0].value` + `weather[0..1].maxtempC/mintempC` for short-term

### Step 4 — Ollama Cloud call (AC: 현재+단기 통합, Korean output, 시크릿 미노출)
- Endpoint: `POST https://ollama.com/api/chat`
- Headers: `Authorization: Bearer {OLLAMA_API_KEY}`, `Content-Type: application/json`
- Body:
  ```json
  {
    "model": "gpt-oss:20b",
    "messages": [
      {"role": "system", "content": SYSTEM_PROMPT},
      {"role": "user", "content": USER_PROMPT}
    ],
    "stream": false
  }
  ```
- **SYSTEM_PROMPT (locked):**
  > 당신은 한국어로만 답하는 날씨 요약 비서입니다. 반드시 한국어로, 간결하게 1~3문장으로 답하세요. 사용자의 질문과 주어진 wttr.in JSON 데이터를 바탕으로 (1) 현재 기온·체감온도·습도·바람 중 관련 있는 것과 (2) 오늘~내일 단기 예보 코멘트를 자연스럽게 통합하세요. 데이터에 없는 정보는 추측하지 말고, 숫자는 섭씨·% 단위를 명시하세요. 이모지는 최대 1개까지만.
- **USER_PROMPT:** `f"질문: {query}\n지역: {location}\nwttr.in 데이터:\n{json.dumps(trimmed_weather, ensure_ascii=False)}"`
- `trimmed_weather` = compact dict with only Korean-friendly fields (no raw English `weatherDesc`)
- Timeout: 30s
- Error: 401 / 5xx / ConnectionError / Timeout → stderr Korean message, exit 6. **Never** include the key in any log/stderr.
- Extract: `response.json()["message"]["content"]`

### Step 5 — Output
- `print(answer)` to stdout
- exit 0

### Exit Codes
| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Config (missing OLLAMA_API_KEY) |
| 3 | Offline (ConnectionError at wttr) |
| 4 | wttr timeout |
| 5 | wttr non-200 / unexpected request exception |
| 6 | Ollama Cloud failure |

---

## Manual Acceptance Tests (no test framework)

| # | Command | Expected |
|---|---------|----------|
| T1 | `python main.py "서울 오늘 날씨"` | 1–3 Korean sentences; contains tempC + forecast verb |
| T2 | `python main.py "내일 비 와?"` | Uses default 서울; stderr notes 기본값 사용 |
| T3 | `python main.py "부산 내일 기온"` | Uses 부산; mentions tomorrow |
| T4 | Disconnect Wi-Fi → T1 | exit 3, stderr "인터넷 연결..."; stdout empty |
| T5 | unset OLLAMA_API_KEY → T1 | exit 2, Korean config error |
| T6 | `python main.py "ㄱㄴㄷ 날씨"` | Graceful fallback (default or unknown) |
| T7 | `grep OLLAMA_API_KEY= main.py` | No hardcoded key |
| T8 | stdout of T1 contains `[가-힣]+` | Korean chars present (sanity) |

---

## Non-Goals (explicit exclusions)
Raspberry Pi port · Flask/web UI · GUI · memory/multi-turn · tool-calling agent framework · LangChain · web scraping · CDP · login sessions · 논문 요약 · Obsidian sync · local Ollama daemon · English output · i18n · pytest · CI · Docker · packaging.

---

## Critic Sign-off
- Principle-option consistency: PASS
- Fair alternatives: PASS
- Risk mitigation clarity: PASS
- Testable acceptance criteria: PASS (with non-blocking note on T9 wttr-5xx mock test for post-MVP)
- Concrete verification: PASS
- Spec conformance: PASS

**Verdict:** APPROVE — ready for autopilot Phase 2 (Execution).
