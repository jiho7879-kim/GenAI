# Research Agent — Project Rules

> 이 프로젝트를 지속할 때 반드시 따라야 할 규칙과 제약사항.
> 새 에이전트가 이 프로젝트를接手하더라도 일관성을 유지하도록 보장함.

---

## 🚫 절대 제약 (Hard Constraints)

이 조건들은 변경할 수 없음. 모든 기술 결정의 전제조건.

| # | 제약 | 이유 |
|---|------|------|
| 1 | **CPU-only** (Intel Iris Xe iGPU) | GPU 없음. chunk_size 512 max, top_k 5 max |
| 2 | **사외망** | 외부 API-key 서비스 사용 불가 (OpenAI/Claude 등) |
| 3 | **Free of charge** | Ollama + Zen Free만 허용 |
| 4 | **Windows 11** | PowerShell 명령어, 경로 구분자 `\\` |
| 5 | **단일 명령어 실행** | `pip install && streamlit run app.py`로 evaluator가 실행 가능해야 함 |

---

## 📝 문서화 규칙

### 필수 기록 대상
모든 **시행착오**와 **결정사항**은 반드시 `.omo/errors/`에 문서화.

- **code-error**: 실제 코드 오류 (에러 메시지, 스택트레이스 포함)
- **decision**: 기술 선택과 그 근거 (왜 A가 아닌 B를 선택했는지)
- **test-result**: 통합 테스트 결과, 환경 정보
- **idea-error**: 방향성 실수 (틀린 접근법, 나중에 깨달은 것)

### 문서 템플릿 (필수 항목)
모든 문서는 다음 5개 섹션을 포함:

```markdown
---
title: "제목"
date: YYYY-MM-DD
category: code-error | decision | test-result | idea-error
severity: low | medium | high | info
---

## 증상 (Symptom)
## 시도한 해결책 (Attempted Solutions)
## 근본 원인 분석 (Root Cause)
## 교훈 (Lesson Learned)
## 최종 코드 / Fix (Resolution)
```

### 문서 작성 시점
- 에러 발견 → **즉시 초안 작성** (해결 전/중/후 과정 모두 기록)
- 결정 완료 → **즉시 근거와 함께 기록** (선택지를 나열하고 선택 이유를 명시)

---

## 🏗️ 아키텍쳐 규칙

### Vector Store: FAISS (고정)
- Chroma 사용 금지 (서버 프로세스 필요)
- FAISS는 서버리스, `allow_dangerous_deserialization=True` 필요
- 저장 위치: `vectorstore/` (gitignore 처리됨)

### Embedding: BAAI/bge-m3 (고정)
- `all-MiniLM-L6-v2` 사용 금지 (English only, Korean TCAD 용어 처리 불가)
- `normalize_embeddings=True` (cosine similarity)
- CPU device 강제: `model_kwargs={"device": "cpu"}`

### RAG: Langchain RetrievalQA (고정)
- `chain_type="stuff"` (한 번에 모든 context → CPU 메모리 효율)
- `return_source_documents=True`
- `langchain.chains` → **`langchain_classic.chains`** (Langchain 1.3+ migration)
- `langchain.text_splitter` → **`langchain_text_splitters`**

### Agent: Class-based Composition (고정)
- Langgraph 사용 금지 (CPU-only 오버헤드, 4개 Agent는 단순 composition으로 충분)
- 각 Agent는 독립 class, Supervisor가 라우팅

### LLM: Ollama
- Default: `qwen3.5:4b` (3.4GB, 빠름)
- Complex: `qwen3.5:9b` (6.6GB, 정확함)
- Fallback: Zen Free (Big Pickle / Qwen3.6 Plus Free)

### PDF: PyMuPDF (fitz)
- `PyMuPDFLoader`로 Langchain 직접 연결
- page metadata 자동 포함 (source, page number)

---

## 🔄 개발 워크플로우

### 1. 계획 수립
```
v1 (초안) → v2 (범위 축소) → v3 (결정완료) → 사용자 승인 → 구현
```
- 코드 작성 전에 최소 2회 이상 iteration
- 모든 Q(질문)가 해결될 때까지 코드 금지

### 2. 구현 순서 (Day1~3)
```
Day1: RAG Core (ingest + rag_chain + app.py 기초)
Day2: Multi-Agent (supervisor + paper + report)
Day3: Arxiv + 테스트 + 문서화 + README + 발표자료
```

### 3. 통합 테스트 순서
```
1️⃣ import 검증 (python -c "from src.xxx import ...")
2️⃣ 실제 실행 (streamlit run app.py)
3️⃣ 기능별 시나리오 테스트 (PDF 업로드 → Q&A → Arxiv 검색)
4️⃣ 에러 발견 시 즉시 .omo/errors/ 문서화
```

### 4. 버전 관리
- `requirements.txt`에 major version 제한 필수
- 예: `arxiv>=2.1.0,<4.0.0` 또는 최신 API 기준으로 코드 작성
- Langchain처럼 breaking change가 잦은 패키지는 버전 고정 고려

---

## 🧪 검증 기준 (Done의 정의)

작업이 완료되었다고 말하려면 **모두** 충족해야 함:

- [ ] Todos의 모든 항목이 completed
- [ ] `ruff check` pass (Python linter)
- [ ] `ruff format --check` pass (Python formatter)
- [ ] `lsp_diagnostics` clean on changed files
- [ ] Import 체인 정상 동작 (`python scripts/validate_imports.py`)
- [ ] `pytest tests/` pass (단위 테스트)
- [ ] 실제 실행 시 에러 없음 (Ollama 환경 필요시 명시)
- [ ] 관련 `.omo/errors/` 문서 최신화
- [ ] 사용자 확인 완료

---

## 🏗️ 하네스 엔지니어링 (Harness Engineering)

> 품질을 **검증**이 아니라 **예방**하는 시스템. 에이전트가 코드를 작성할 때마다 자동으로 검사하는 장치.

### 1. 단일 명령어 검증 (The One Command)

모든 검증은 하나의 명령어로 실행 가능해야 함:

```powershell
.\scripts\check_all.ps1
```

이 명령어는 다음을 **순차적으로** 실행:
```
ruff format --check  →  ruff check  →  validate_imports  →  pytest
```

### 2. 검증 계층 (Validation Layers)

```
Layer 1: 정적 분석 (즉시, 1초 미만)
  ├── ruff format --check    # 코드 스타일 일관성
  └── ruff check             # 논리 오류, 안티패턴 탐지

Layer 2: 구조 검증 (5초 미만)
  ├── validate_imports.py    # 모든 모듈 import 가능 확인
  └── pytest                 # 단위 테스트 + 회귀 테스트

Layer 3: 런타임 검증 (환경 의존)
  ├── streamlit run app.py   # 앱이 정상 실행되는지 확인
  └── Ollama 연동 확인       # LLM 응답 테스트 (옵션)
```

### 3. Pre-commit Hook (Git 초기화 후 적용)

```powershell
# .git/hooks/pre-commit (Git 저장소 초기화 후 생성)
# staging된 .py 파일에 대해 ruff check + ruff format 검증
```

Hook 내용 (저장소 초기화 시 `scripts/install-hooks.ps1`로 설치):
```powershell
$changed = git diff --cached --name-only --diff-filter=AM | Where-Object { $_ -match '\.py$' }
if (-not $changed) { exit 0 }

# ruff check
& ".venv\Scripts\python.exe" -m ruff check $changed
if ($LASTEXITCODE -ne 0) { Write-Host "❌ ruff check failed"; exit 1 }

# ruff format check
& ".venv\Scripts\python.exe" -m ruff format --check $changed
if ($LASTEXITCODE -ne 0) { Write-Host "❌ ruff format failed"; exit 1 }
```

### 4. 테스트 철학

| 원칙 | 설명 |
|------|------|
| **Fast-first** | 단위 테스트는 1초 이내 완료. 느린 테스트는 분리 |
| **No network** | 단위 테스트는 네트워크/외부 API 의존 금지 |
| **Temp-safe** | 파일 생성 테스트는 `tmp_path` fixture 사용 |
| **Regression lock** | 버그 수정 시 해당 버그를 검증하는 테스트를 먼저 작성 |
| **Coverage ≠ goal** | 100% 커버리지보다 핵심 로직 검증이 우선 |

### 5. 허용 규칙 (What We Allow/Disallow)

| 항목 | 규칙 |
|------|------|
| `# type: ignore` | ❌ 금지 (타입 문제는 실제로 수정) |
| `# noqa` | ✅ 허용 (단, 이유를 같은 줄에 주석으로 명시) |
| `as any` / `@ts-ignore` | ❌ TypeScript가 아닌 Python 프로젝트이므로 해당 없음 |
| Unused import | ❌ `ruff check F401`이 자동 탐지 |
| `print()` 디버깅 | ❌ `logger` 사용. `print()`는 테스트 코드에서만 허용 |
| 암시적 `except:` | ❌ 항상 특정 예외 타입 명시 |
| 매직 넘버 | ⚠️ 상수로 추출 권장 (ruff가 강제하지는 않음) |

### 6. 지속적 개선

- `ruff.toml`에 새로운 규칙을 추가할 때는 **전체 코드베이스에 일괄 적용** 후 추가
- 새로운 테스트 파일은 `tests/` 디렉토리에 `test_*.py` 패턴으로 생성
- `check_all.ps1`이 실패하면 **그 즉시 수정**. "일단 넘어가고 나중에" 금지
- `scripts/` 디렉토리의 도구는 `ruff check`에서 제외 가능 (단, `ruff format`은 적용)

---

## ⚠️ 알려진 이슈 (Known Issues)

| # | 이슈 | 영향 | 상태 |
|---|------|------|------|
| 1 | Ollama 환경에서만 LLM 기능 검증 가능 | import test로는 한계 | ⚠️ Open |
| 2 | BGE-m3 첫 로딩 시 ~2.2GB 다운로드 필요 | 초기 실행 지연 | ⚠️ Open |
| 3 | `streamlit run app.py`는 app.py 로깅만 파일에 기록 | Streamlit 서버 로그는 run.ps1 필요 | ✅ run.ps1 제공 |
| 4 | arxiv 4.x API는 `client.results(search)` 사용 | 2.x와 호환성 깨짐 | ✅ 문서화 완료 |
| 5 | `langchain-community` sunset 예정 | 향후 migration 필요 | ⚠️ Low priority |

---

## 📂 핵심 파일 위치

| 파일 | 역할 |
|------|------|
| `app.py` | Streamlit 진입점 (로깅 설정 포함) |
| `run.ps1` | Launch wrapper (stdout/stderr 자동 로깅) |
| `requirements.txt` | 의존성 목록 |
| `src/ingest.py` | PDF → FAISS 파이프라인 |
| `src/rag_chain.py` | RAG 검색 + 생성 |
| `src/agents/supervisor.py` | 의도 분류 |
| `src/agents/paper_agent.py` | 논문 Q&A |
| `src/agents/arxiv_agent.py` | Arxiv 검색 |
| `src/agents/report_agent.py` | 결과 포맷팅 |
| `logs/app.log` | 애플리케이션 로그 |
| `logs/streamlit_out_*.log` | Streamlit stdout (run.ps1 사용시) |
| `logs/streamlit_err_*.log` | Streamlit stderr (run.ps1 사용시) |
| `.omo/errors/*.md` | 시행착오 및 결정사항 문서 |
| `.omo/plans/research-agent-plan-v3-final.md` | 최종 계획서 |
