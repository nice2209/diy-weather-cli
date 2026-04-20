"""DIY Weather Agent MVP.

한국어 질문을 받아 wttr.in 날씨 JSON을 가져오고, Ollama Cloud LLM에게
1~3문장짜리 한국어 요약을 부탁하는 단일 파일 CLI.

예) python main.py "서울 오늘 날씨"
    python main.py "내일 비 와?" --location 부산
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import urllib.parse
from typing import Any

import requests

WTTR_URL = "https://wttr.in/{location}?format=j1&lang=ko"
WTTR_UA = "diy-weather-agent/0.1"
WTTR_TIMEOUT = 10

OLLAMA_URL = "https://ollama.com/api/chat"
OLLAMA_TIMEOUT = 30
DEFAULT_MODEL = "gpt-oss:20b"
DEFAULT_LOCATION = "서울"

# 지역 정규식이 잡아도 버리는 토큰 (시간/시점 표현 + 날씨 어휘 자체).
LOCATION_BLOCKLIST = {
    "오늘", "내일", "모레", "지금", "현재", "요즘", "오전", "오후", "저녁", "아침", "밤", "새벽", "어제",
    "날씨", "기온", "예보", "바람", "습도", "강수", "강우", "기상", "일기",
}
# 지역 후보(2자 이상 한글) + 최대 2단어 사이 + 날씨 키워드. '서울 오늘 날씨'에서도 '서울'을 잡도록.
LOCATION_PATTERN = re.compile(r"([가-힣]{2,})(?:\s+\S+){0,2}\s*(?:날씨|기온|비|눈|예보|바람|습도)")

SYSTEM_PROMPT = (
    "당신은 한국어로만 답하는 날씨 요약 비서입니다. "
    "반드시 한국어로, 간결하게 1~3문장으로 답하세요. "
    "사용자의 질문과 주어진 wttr.in JSON 데이터를 바탕으로 "
    "(1) 현재 기온·체감온도·습도·바람 중 관련 있는 것과 "
    "(2) 오늘~내일 단기 예보 코멘트를 자연스럽게 통합하세요. "
    "데이터에 없는 정보는 추측하지 말고, 숫자는 섭씨·% 단위를 명시하세요. "
    "이모지는 최대 1개까지만."
)

log = logging.getLogger("weather")

# 단어 끝에 붙으면 떼어내는 조사. '서울이' → '서울', '부산에서' → '부산'.
LOCATION_PARTICLES = ("에서", "에는", "에도", "에", "은", "는", "이", "가", "을", "를", "와", "과", "의", "도")


def _strip_particle(token: str) -> str:
    for p in LOCATION_PARTICLES:
        if token.endswith(p) and len(token) > len(p) + 1:
            return token[: -len(p)]
    return token


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """CLI 인자 파싱."""
    parser = argparse.ArgumentParser(description="한국어 날씨 요약 에이전트 (wttr.in + Ollama Cloud)")
    parser.add_argument("query", help="날씨에 대한 한국어 질문")
    parser.add_argument("--location", default=None, help="조회할 지역 (질문 속 지역어보다 우선)")
    return parser.parse_args(argv)


def resolve_location(query: str, cli_location: str | None, default_location: str) -> str:
    """우선순위: --location > 질문 정규식 > 기본값.

    정규식은 여러 개가 매칭될 수 있으므로 전부 훑어 블록리스트가 아닌 첫 토큰을 선택.
    예) '서울 오늘 날씨' → '오늘'(블록)과 '서울'(유효) 중 '서울'을 고른다.
    """
    if cli_location:
        return cli_location.strip()
    candidates = [_strip_particle(m.group(1).strip()) for m in LOCATION_PATTERN.finditer(query)]
    for token in candidates:
        if token and token not in LOCATION_BLOCKLIST:
            return token
    reason = "질문에서 시점 표현만 찾았어요." if candidates else "지역을 찾지 못했어요."
    print(f"{reason} 기본값 '{default_location}'을(를) 사용합니다.", file=sys.stderr)
    return default_location


def fetch_weather(location: str) -> dict[str, Any]:
    """wttr.in에서 한국어 필드 포함 JSON을 받아온다."""
    url = WTTR_URL.format(location=urllib.parse.quote(location))
    try:
        response = requests.get(url, headers={"User-Agent": WTTR_UA}, timeout=WTTR_TIMEOUT)
    except requests.ConnectionError:
        print("인터넷 연결을 확인해주세요.", file=sys.stderr)
        sys.exit(3)
    except requests.Timeout:
        print("날씨 서버 응답이 지연되고 있어요. 잠시 후 다시 시도해주세요.", file=sys.stderr)
        sys.exit(4)
    except requests.RequestException as exc:
        log.debug("wttr.in 예외: %s", exc)
        print("날씨 서버에 접속할 수 없어요.", file=sys.stderr)
        sys.exit(5)

    if response.status_code != 200:
        print(f"날씨 서버 장애 중이에요 (HTTP {response.status_code}).", file=sys.stderr)
        sys.exit(5)
    try:
        return response.json()
    except ValueError:
        print("날씨 서버가 이상한 응답을 보냈어요.", file=sys.stderr)
        sys.exit(5)


def _lang_ko(entry: dict[str, Any]) -> str:
    """current_condition / hourly 항목에서 한국어 설명을 뽑는다."""
    for key in ("lang_ko", "weatherDesc"):
        items = entry.get(key) or []
        if items:
            value = items[0].get("value", "")
            if value:
                return value
    return ""


def trim_weather(raw: dict[str, Any], location: str) -> dict[str, Any]:
    """LLM에 보낼 wttr.in JSON을 한국어 친화 필드만 남겨 압축한다."""
    trimmed: dict[str, Any] = {"지역": location}

    current_list = raw.get("current_condition") or []
    if current_list:
        cur = current_list[0]
        trimmed["현재"] = {
            "날씨": _lang_ko(cur),
            "기온C": cur.get("temp_C"),
            "체감온도C": cur.get("FeelsLikeC"),
            "습도퍼센트": cur.get("humidity"),
            "풍속kmh": cur.get("windspeedKmph"),
        }

    forecast: list[dict[str, Any]] = []
    for day in (raw.get("weather") or [])[:2]:
        hourly = day.get("hourly") or []
        # 3시간 간격 기준 인덱스 4 ≈ 정오. 정보 부족 시 마지막 시점으로 폴백.
        pick = hourly[4] if len(hourly) > 4 else (hourly[-1] if hourly else {})
        forecast.append({
            "날짜": day.get("date"),
            "최고C": day.get("maxtempC"),
            "최저C": day.get("mintempC"),
            "대표시점_날씨": _lang_ko(pick) if pick else "",
            "강수확률퍼센트": pick.get("chanceofrain") if pick else None,
        })
    if forecast:
        trimmed["단기예보"] = forecast
    return trimmed


def ask_ollama(query: str, location: str, trimmed: dict[str, Any], api_key: str, model: str) -> str:
    """Ollama Cloud /api/chat에 요청해 한국어 답변을 받는다."""
    user_prompt = (
        f"질문: {query}\n"
        f"지역: {location}\n"
        f"wttr.in 데이터:\n{json.dumps(trimmed, ensure_ascii=False)}"
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        response = requests.post(OLLAMA_URL, headers=headers, json=body, timeout=OLLAMA_TIMEOUT)
    except requests.ConnectionError:
        print("Ollama Cloud에 연결할 수 없어요. 인터넷을 확인해주세요.", file=sys.stderr)
        sys.exit(6)
    except requests.Timeout:
        print("Ollama Cloud 응답이 너무 오래 걸려요.", file=sys.stderr)
        sys.exit(6)
    except requests.RequestException as exc:
        log.debug("Ollama 예외: %s", exc)
        print("Ollama Cloud 호출에 실패했어요.", file=sys.stderr)
        sys.exit(6)

    if response.status_code != 200:
        # 상태 코드만 노출하고 API 키는 어디에도 찍지 않는다.
        print(f"Ollama Cloud 호출 실패 (HTTP {response.status_code}).", file=sys.stderr)
        sys.exit(6)

    try:
        return response.json()["message"]["content"].strip()
    except (ValueError, KeyError, TypeError) as exc:
        log.debug("Ollama 응답 파싱 실패: %s", exc)
        print("Ollama Cloud 응답을 해석하지 못했어요.", file=sys.stderr)
        sys.exit(6)


def _force_utf8_stdio() -> None:
    """Windows cp949 콘솔에서도 한글이 깨지지 않도록 stdout/stderr를 UTF-8로 재설정."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            pass


def _load_dotenv(path: str = ".env") -> None:
    """표준 라이브러리만으로 .env를 읽어 이미 설정되지 않은 키만 os.environ에 주입.

    - 이미 OS 환경변수에 값이 있으면 덮어쓰지 않는다 (실행 시 `set`이 우선).
    - 주석(#)과 빈 줄 무시. `KEY=VALUE` 형태만 지원.
    - 값 주변의 큰/작은 따옴표는 벗겨낸다.
    """
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError as exc:
        log.debug(".env 읽기 실패: %s", exc)


def main(argv: list[str] | None = None) -> None:
    _force_utf8_stdio()
    _load_dotenv()
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args(argv)

    api_key = os.environ.get("OLLAMA_API_KEY", "").strip()
    if not api_key:
        print(
            "환경변수 OLLAMA_API_KEY가 설정되지 않았어요. "
            "Ollama Cloud에서 발급받은 키를 설정해주세요.",
            file=sys.stderr,
        )
        sys.exit(2)

    model = os.environ.get("OLLAMA_MODEL", "").strip() or DEFAULT_MODEL
    default_location = os.environ.get("DEFAULT_LOCATION", "").strip() or DEFAULT_LOCATION

    location = resolve_location(args.query, args.location, default_location)
    log.info("지역 결정: %s", location)

    raw = fetch_weather(location)
    trimmed = trim_weather(raw, location)
    answer = ask_ollama(args.query, location, trimmed, api_key, model)
    print(answer)
    sys.exit(0)


if __name__ == "__main__":
    main()
