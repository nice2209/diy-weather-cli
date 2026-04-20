# DIY Weather Agent (MVP)

한국어 질문을 받아 wttr.in 날씨 데이터를 Ollama Cloud LLM(`gpt-oss:20b`)에 넘겨
1~3문장짜리 한국어 요약을 출력하는 단일 파일 CLI입니다. 홍정모 스타일의 튜토리얼용
프로젝트로, 의존성은 `requests` 하나뿐입니다.

## 요구 사항
- Python 3.11
- Ollama Cloud API 키 (https://ollama.com 에서 발급)
- 인터넷 연결 (wttr.in + Ollama Cloud 호출)

## 설치
```bash
pip install -r requirements.txt
```

## 환경변수 설정

### 방법 A — `.env` 파일 (가장 간편, 권장)
프로젝트 루트에 `.env` 파일을 만듭니다 (`.env.example` 참고). 실행 시 `main.py`가 자동으로 읽습니다.

```
OLLAMA_API_KEY=여기에_발급받은_키
OLLAMA_MODEL=gpt-oss:20b
DEFAULT_LOCATION=서울
```

`.gitignore`가 `.env`를 포함하므로 실수로 커밋될 걱정은 없습니다. 운영체제 환경변수가 이미 설정돼 있다면 그 값이 우선합니다(덮어쓰지 않음).

### 방법 B — OS 환경변수 (Windows cmd 기준)
```cmd
set OLLAMA_API_KEY=여기에_발급받은_키
set OLLAMA_MODEL=gpt-oss:20b
set DEFAULT_LOCATION=서울
```
PowerShell이라면 `$env:OLLAMA_API_KEY="..."`, bash라면 `export OLLAMA_API_KEY=...`.

### 키 설명
- `OLLAMA_API_KEY` — 필수. 비어 있으면 종료 코드 2로 즉시 종료합니다.
- `OLLAMA_MODEL` — 선택. 기본값 `gpt-oss:20b` (더 큰 `gpt-oss:120b`로 교체 가능).
- `DEFAULT_LOCATION` — 선택. 기본값 `서울`.

## 실행 예시
```bash
# T1 — 지역어가 질문에 있는 경우
python main.py "서울 오늘 날씨"

# T2 — 지역어 없음 → DEFAULT_LOCATION(서울)로 폴백
python main.py "내일 비 와?"

# T3 — --location 인자로 지역 직접 지정
python main.py "내일 기온" --location 부산
```

표준 출력(stdout)에는 한국어 답변만 찍힙니다. 로그/디버그/에러 메시지는 모두
표준 에러(stderr)로 분리되므로 파이프(`>`)로 저장해도 답변만 깔끔하게 남습니다.

## 종료 코드
| 코드 | 의미 |
|------|------|
| 0 | 정상 |
| 2 | 설정 오류 (`OLLAMA_API_KEY` 누락 등) |
| 3 | 오프라인 (wttr.in 연결 실패) |
| 4 | wttr.in 응답 지연 (10초 타임아웃) |
| 5 | wttr.in 비정상 응답 (200 외 상태코드, JSON 파싱 실패 등) |
| 6 | Ollama Cloud 호출 실패 |

## 테스트
이 MVP는 `pytest` 없이 수동 테스트만 합니다. 계획서의 T1~T8 시나리오를 직접
실행해 확인하세요. 자동화 테스트는 Post-MVP로 미뤘습니다.

## 보안
- API 키는 환경변수로만 읽으며 로그·에러·stdout 어디에도 노출하지 않습니다.
- Ollama Cloud 호출이 실패해도 상태 코드만 알려주고 키는 표시하지 않습니다.
