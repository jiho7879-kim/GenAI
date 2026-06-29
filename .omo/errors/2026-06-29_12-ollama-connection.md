---
title: "Ollama 미연결 — Agent Pipeline 멈춤 문제 해결"
date: 2026-06-29
category: bug
severity: high
---

## 증상

채팅에서 질문 요청 시 "Step 1/3: Classifying intent..."에서 멈추고
"Done" 표시만 뜨고 응답이 없거나 도움말만 출력됨.

## 원인

**Ollama 서버가 실행 중이지 않음.** (`ConnectionRefusedError`)

```
사용자 입력 ("내용 요약해줘")
    ↓
Supervisor.classify() → Ollama.invoke() 호출
    ↓
ConnectionRefusedError (localhost:11434)
    ↓
Exception catch → return "unknown"
    ↓
else branch → 도움말 출력
    ↓
"✅ Done!" (Step 2/3 없이 완료)
```

Ollama는 scoop으로 설치되어 있었지만 (`C:\Users\User\scoop\shims\ollama.exe`),
서비스로 등록되지 않아 수동 실행이 필요했음.

## 수정 사항

### 1. `src/agents/supervisor.py`
- `check_ollama()` static method 추가: 앱 시작 시 Ollama 상태 확인
- LLM 오류 로그에 구체적인 안내 메시지 포함

### 2. `app.py`
- 가져오기(import) 시점에 Ollama health check 실행
- 사이드바에 Ollama 상태 표시 (✅/❌)
- `unknown` intent 처리 시 Ollama 미연결이면 한국어 안내 메시지 출력

### 3. UI 개선
사이드바:
```
🤖 LLM (Ollama)
❌ Ollama not running
Run: ollama serve in terminal
```

채팅:
```
⚠️ Ollama 서버에 연결할 수 없습니다
Research Agent는 로컬 LLM(Ollama)을 사용합니다.
Ollama가 실행 중인지 확인해주세요.

  # 터미널에서 실행:
  ollama serve
```

## 재발 방지

### 자동화 (run.ps1) ✅

`run.ps1`이 Ollama를 자동으로 찾아서 실행:

```
PowerShell에서 .\run.ps1 만 입력하면:
1. Ollama 실행 파일 검색 (scoop, Program Files, PATH)
2. 실행 중이 아니면 ollama serve를 백그라운드 실행
3. 최대 30초까지 준비 완료 대기
4. 필요 모델(qwen3.5:4b) 없으면 자동 pull
5. 그 다음 Streamlit 실행
```

### 수동 실행

```powershell
# 방법 1: 일반 실행
ollama serve

# 방법 2: 백그라운드 실행 (별도 창)
Start-Process -WindowStyle Hidden ollama -ArgumentList "serve"
```

## 수정된 파일

| 파일 | 변경 내용 |
|------|----------|
| `run.ps1` | Ollama 자동 탐색 + 실행 + 모델 체크 + Streamlit 실행 |
| `src/agents/supervisor.py` | `check_ollama()` static method 추가 |
| `app.py` | 시작 시 Ollama health check, 사이드바 상태 표시, unknown intent 처리 개선 |
| `INGEST_GUIDE.md` | Evaluator Guide (실행 방법) 섹션 추가 |
