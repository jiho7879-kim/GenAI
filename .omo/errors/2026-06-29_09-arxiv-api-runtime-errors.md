---
title: "arxiv 4.0.0 API 호환성 + torchvision 누락 — Runtime 오류"
date: 2026-06-29
category: code-error
severity: high
---

## 증상 (Symptom)

`streamlit run app.py` 실행 후 Streamlit 서버는 정상 기동했으나, 다음과 같은 오류들이 발생:

### 오류 1: arxiv Search.results() AttributeError (CRITICAL)
```
[ERROR] src.agents.arxiv_agent: Arxiv search failed:
'Search' object has no attribute 'results'
```

### 오류 2: torchvision ModuleNotFoundError (NON-BLOCKING)
```
ModuleNotFoundError: No module named 'torchvision'
 File: transformers/models/zoedepth/image_processing_zoedepth.py
```
Streamlit watcher가 transformers 모듈 스캔 중 torchvision 부재로 경고 발생.
Non-blocking이지만 로그를 오염시키고, evaluator가惊吓할 수 있음.

## 시도한 해결책 (Attempted Solutions)

### 원인 분석

**오류 1**: `arxiv` 패키지가 2.x → 4.0.0으로 major upgrade되면서 API가 breaking change 발생.
`requirements.txt`에 `arxiv>=2.1.0`로 명시 → 최신 4.0.0 설치됨.

```python
# OLD API (arxiv 2.x) — 작동 안 함
search = arxiv.Search(query=..., max_results=...)
for paper in search.results():  # AttributeError!

# NEW API (arxiv 4.x)
client = arxiv.Client()
search = arxiv.Search(query=..., max_results=...)
for paper in client.results(search):  # OK
```

변경된 API 상세:
- `.results()` 메서드가 `Search` → `Client`로 이동
- `paper.published`가 string이 아닌 datetime 객체로 반환
- `paper.authors`가 `Author` namedtuple 리스트 (`.name` 속성 유지)
- `paper.get_short_id()` 메서드 추가 (버전 접미사 없는 ID 추출)

**오류 2**: `transformers 5.12.1`에서 `torchvision`을 일부 모델에서 import.
`sentence-transformers`의 의존성으로 설치되나 `torchvision`은 optional.
CPU-only 환경에서는 실제 사용되지 않지만, Streamlit watcher가 import 시도.

### 해결

**오류 1 — arxiv_agent.py 전체 수정**:
```python
# src/agents/arxiv_agent.py — search() 메서드
# BEFORE
search = arxiv.Search(...)
for paper in search.results():

# AFTER
client = arxiv.Client()
search = arxiv.Search(...)
for paper in client.results(search):
```

`get_paper_detail()` 메서드도 동일하게 `client.results(search)`로 수정.
`paper.published.date()` → `paper.published.strftime("%Y-%m-%d")`로 datetime 처리 명시화.
`entry_id.split("/")[-1].split("v")[0]` → `paper.get_short_id()`로 단순화.

**오류 2 — torchvision 설치**:
```bash
pip install torchvision
```
CPU-only에서 추론에는 불필요하지만, Streamlit watcher 경고 제거를 위해 설치.
`requirements.txt`에도 `torchvision>=0.19.0` 추가.

## 근본 원인 분석 (Root Cause)

1. **의존성 버전 고정 부재**: `arxiv>=2.1.0`는 major upgrade(4.x)를 허용함
   - `arxiv 2.x` → `search.results()` 정상
   - `arxiv 4.x` → `search.results()` 삭제됨 → AttributeError
2. **pip install 타임아웃 이후 검증 생략**: 첫 pip install이 timeout으로 중단됐다가 재시도 성공했으나,
   버전 차이로 인한 API 호환성을 놓침
3. **테스트 환경 부재**: Ollama 미설치 환경에서 import만 검증하고 실제 실행은 검증하지 못함

## 교훈 (Lesson Learned)

1. **requirements.txt는 주요 패키지 버전을 고정하거나 major version 범위를 제한해야 함**
   - `arxiv>=2.1.0,<4.0.0` 또는 `arxiv==3.*`로 제한
   - 또는 최신 API에 맞춰 코드를 작성하고 문서화
2. **pip install 완료 후에는 import 검증뿐 아니라 실제 기능 테스트까지 해야 함**
   - 특히 외부 API(arxiv)는 실제 호출해봐야 정상 동작 확인 가능
3. **Streamlit watcher 경고도 무시하지 말 것**: evaluator가 "오류"로 오인할 수 있음
4. **major version upgrade는 항상 breaking change를 수반**: changelog 확인 필수

## 최종 코드 (Resolution)

변경 파일:
- `src/agents/arxiv_agent.py` — `search.results()` → `client.results(search)` (2개 메서드)
- `requirements.txt` — `torchvision>=0.19.0` 추가
