# Arxiv Search Agent 개선 구현

> 작성일: 2026-06-29
> 관련 Plan: `.omo/plans/arxiv-agent-improvement-plan.md`
> 검증: `ruff check` + `ruff format --check` 0 errors, `pytest tests/` 44/44 pass

---

## 변경 개요

5개 Phase로 구성된 Arxiv Search Agent 개선 Plan 구현 완료.

| Phase | 파일 | 변경 유형 | 설명 |
|-------|------|----------|------|
| 1 | `src/agents/query_optimizer.py` | **신규** | LLM query rewrite Agent (176 lines) |
| 2 | `src/agents/arxiv_agent.py` | 수정 | `batch_summarize()` 메서드 추가 (기존에 이미 구현됨) |
| 3 | `src/agents/arxiv_agent.py` | 수정 | `rerank()` + `rag_chain.compute_similarity_scores()` 연동 (기존에 이미 구현됨) |
| 4 | `src/agents/supervisor.py` | 수정 | `route()`에서 search intent 시 `optimize_query()` 호출 (기존에 이미 구현됨) |
| 5 | `app.py` | 수정 | 검색 결과 UI에 최적화된 query 정보 표시 |
| 테스트 | `tests/test_query_optimizer.py` | 신규 | 18개 단위 테스트 (기존에 이미 구현됨) |

## Phase별 상세

### Phase 1: Query Optimizer Agent

**파일**: `src/agents/query_optimizer.py`

핵심 컴포넌트:
- `optimize_query(user_query)` — 메인 엔트리 포인트. LLM 호출 → 실패 시 `_basic_clean` fallback
- `_ollama_generate()` — Ollama API 직접 호출 (langchain 의존성 없음)
- `_parse_llm_response()` — JSON 추출 (markdown fence tolerance)
- `_basic_clean()` — LLM 없이 noise word 제거 (한국어 + 영어)
- `_detect_query_type()` — Arxiv query syntax heuristic 분류
- `QUERY_OPTIMIZER_PROMPT` — Few-shot prompt (한국어→영어 번역, 카테고리 추천)
- `DOMAIN_CATEGORIES` — TCAD/semiconductor/ML 도메인 카테고리 매핑

**Fallback chain**: LLM 성공 → 최적화된 query / LLM 실패(Ollama down/timeout) → `_basic_clean()` → 원본 query

### Phase 2: LLM Batch Summarization

**파일**: `src/agents/arxiv_agent.py`, 메서드 `batch_summarize()`

- 5개 논문을 1회 LLM 호출로 배치 요약 (130 tokens × 5 = ~650 tokens budget)
- 프롬프트 구조: (1) What problem? (2) What method? (3) Key result?
- Parse: numbered list regex fallback
- 실패 시 기존 truncated abstract 보존

### Phase 3: Relevance Reranking

**파일**: `src/agents/arxiv_agent.py`, 메서드 `rerank()`

- 각 논문 abstract를 BGE-m3로 embedding
- 내 library vector store centroid와 cosine similarity 계산
- `top_k=5` 제한 (CPU-only Intel Iris Xe)
- 결과에 `similarity` key (0.0~1.0) 추가

### Phase 4: Supervisor Routing

**파일**: `src/agents/supervisor.py`, 메서드 `route()`

- Search intent → `optimize_query(user_input)` 호출
- 반환값: `(intent, optimized_query.final_query)`
- 기존에 이미 import 및 호출 코드 구현되어 있음

### Phase 5: UI 개선

**파일**: `app.py`

- **🔧 Query Optimization expander**: 검색 시 optimized query Before/After 표시
- 카테고리 태그 (파란색 badge 형태로 시각화)
- 언어 감지 표시 (한국어→영어 번역 시 표시)
- **✨ LLM badge**: LLM 요약이 적용된 경우 표시 (단순 truncation과 구분)

## 테스트

**파일**: `tests/test_query_optimizer.py` — 18 tests across 5 classes

| Test Class | 테스트 내용 | 개수 |
|-----------|-----------|------|
| `TestBasicClean` | 한국어/영어 noise 제거, technical term 보존, empty handling | 6 |
| `TestParseLLMResponse` | JSON parsing, markdown fence, malformed JSON | 6 |
| `TestDetectQueryType` | ti:/au:/cat:/general heuristic | 4 |
| `TestOptimizeQuery` | Empty/fallback/final_query string 보장 | 5 |
| `TestOptimizedQuery` | Default values, is_fallback property | 3 |

**전체 테스트 스위트**: 44 tests / 44 pass (1 warning: langchain-community sunset)

## 검증 결과

```
ruff check app.py src/agents/ → All checks passed!
ruff format --check app.py src/agents/ → 4 files already formatted
pytest tests/ → 44 passed in 61.22s
scripts/validate_imports.py → pass (6 modules)
```

## 교안 연계 포인트

1. **Agentic RAG**: Query rewrite는 Langchain & Langgraph RAG 교안의 Agentic RAG 패턴 실제 적용 사례
2. **Multi-agent orchestration**: Supervisor → Query Optimizer → Arxiv Search Agent 체인 (멀티 Agent 서비스 교안)
3. **LLM as a tool**: LLM을 단순 chatbot이 아닌 검색 엔진 최적화 도구로 활용
4. **Before-After 시연**: UI에 Before/After query 표시 기능 추가 → 발표자료에 활용 가능

## 발표자료 활용 아이디어

```
Before: "GAA FET 최신 논문 찾아줘"
  → Arxiv API raw query = "GAA FET 최신 논문 찾아줘" (한국어 → 쓰레기 결과)
  
After: "GAA FET 최신 논문 찾아줘"
  → Query Optimizer: ti:"gate-all-around FET" OR ti:"GAA FET" AND cat:cond-mat.mtrl-sci
  → Arxiv API 정확한 검색 결과
  → LLM 요약 + Library relevance reranking
  → UI에 Before/After 표시
```
