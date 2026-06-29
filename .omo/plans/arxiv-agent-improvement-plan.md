# Arxiv Search Agent 개선 Plan

> 작성일: 2026-06-29
> 상태: Plan (구현 전)
> 관련 교안: Langchain & Langgraph RAG 구축 (3일) + 멀티 Agent 서비스 개발 (2일)

---

## 1. 문제 진단

### 1.1 현재 코드의 문제점

| # | 문제 | 심각도 | 현재 코드 (arxiv_agent.py) |
|---|------|--------|--------------------------|
| 1 | **Raw query를 그대로 Arxiv API에 전달** | 🔴 | `search = arxiv.Search(query=query, ...)` — query가 전처리 없이 그대로 전달됨 |
| 2 | **Stop word / noise가 query에 포함** | 🔴 | 사용자가 "Search for GAA FET papers on Arxiv"라고 입력하면 `cleaned_query` = "Search for GAA FET papers on Arxiv" 그대로 전송 |
| 3 | **Arxiv 고급 query syntax 미사용** | 🟡 | `ti:`, `au:`, `cat:`, `AND`, `OR`, `"phrase"` 등 Arxiv API가 지원하는 검색 기능을 전혀 활용하지 않음 |
| 4 | **카테고리 필터링 없음** | 🟡 | TCAD/semiconductor 관련 카테고리(`physics.app-ph`, `cond-mat.mtrl-sci`, `cs.LG` 등)로 필터링 불가 |
| 5 | **요약이 단순 abstract truncation** | 🟡 | `paper.summary[:300] + "..."` — LLM을 통한 의미 있는 요약 없음 |
| 6 | **결과 후처리 없음** | 🟡 | Relevance 순으로 받은 결과를 그대로 반환. reranking/filtering 없음 |
| 7 | **Session 휘발성 캐시** | 🟢 | `_search_cache = {}` — 앱 재시작 시 캐시 소멸 |
| 8 | **한국어 query 처리 없음** | 🟡 | 한국어 query를 Arxiv API에 그대로 전달 (Arxiv은 영문 검색 엔진) |

### 1.2 근본 원인

```
사용자 입력: "GAA FET 최신 논문 찾아줘"
    → Supervisor: intent="search", cleaned_query="GAA FET 최신 논문 찾아줘"
    → Arxiv API: query="GAA FET 최신 논문 찾아줘"  ← 문제!
    → Arxiv은 영문 검색 엔진이라 한국어 query로는 관련 결과를 찾지 못함
    → 쓰레기 결과 반환
```

### 1.3 개선 방향

```
사용자 입력: "GAA FET 최신 논문 찾아줘"
    → Supervisor: intent="search", cleaned_query="GAA FET 최신 논문 찾아줘"
    → [NEW] Query Optimizer Agent
        1. LLM으로 query意图 분석 및 영문 변환
        2. Arxiv query syntax로 변환
        3. 관련 카테고리 자동 추가
    → 최적화된 query: "ti:'gate-all-around FET' OR ti:'GAA FET' AND cat:cond-mat.mtrl-sci"
    → Arxiv API: 정확한 검색 결과
    → [NEW] LLM Summary: 각 논문의 초록을 2-3문장으로 요약
    → [NEW] Relevance Reranking: 내 논문 library와의 관련도 순으로 정렬
```

---

## 2. 교안 연계 포인트

### 2.1 강의 내용과 연결

| 교안 모듈 | 연결 기술 | Plan에서 활용 |
|-----------|----------|-------------|
| **Langchain & Langgraph RAG 구축** (3일) | RAG pipeline, Agentic RAG | Query Optimizer Agent (LLM으로 query rewrite) |
| **멀티 Agent 서비스 개발** (2일) | Orchestration, Supervision 패턴 | Supervisor → QueryOptimizerAgent → ArxivSearchAgent 체인 |
| **Agentic RAG** | RAG + Agent 결합 | 검색 결과를 내 library의 RAG와 결합 (기존 코드) |
| **Streamlit 웹 서비스** | UI/UX | 검색 결과 UI 개선 (카테고리 필터, 관련도 표시) |

### 2.2 발표자료 연계 아이디어

Before-After 비교:
- **Before**: "GAA FET 찾아줘" → Arxiv에 그대로 전달 → 엉뚱한 결과
- **After**: "GAA FET 찾아줘" → Query Optimizer Agent가 영문 변환 + 카테고리 지정 → 정확한 결과 + LLM 요약

이 구조를 발표하면:
1. Agentic RAG의 실제 적용 사례 제시 가능
2. Multi-agent orchestration의 필요성 입증
3. RAG의 Query Rewrite 개념을 Arxiv 검색에 확장 적용

---

## 3. 상세 구현 Plan

### Phase 1: Query Optimizer Agent (1일)

**목표**: 사용자 query를 Arxiv에 최적화된 query로 변환

```
src/agents/query_optimizer.py  (신규)
```

**세부 구현**:

```python
# Query Optimizer Agent
# 1. LLM(qwen3.5:4b)으로 query 분석
#    - 검색 의도 파악 (주제, 저자, 연도 등)
#    - 한국어 → 영어 변환
#    - 불용어 제거 ("찾아줘", "search for", "papers about")
#    
# 2. Arxiv query syntax 생성
#    - AND / OR / NOT 연산자 사용
#    - ti: (title), au: (author), cat: (category) 필드 지정
#    - phrase matching for technical terms ("GAA FET")
#
# 3. 카테고리 자동 추천
#    - TCAD 관련: physics.app-ph, cond-mat.mtrl-sci
#    - ML 관련: cs.LG, cs.AI, stat.ML
#    - Device 관련: physics.ins-det, cond-mat.mes-hall
```

**테스트 케이스**:
| 입력 | 기대 출력 |
|------|----------|
| "GAA FET 최신 논문" | `ti:"gate-all-around FET" OR ti:"GAA FET" AND cat:cond-mat.mtrl-sci` |
| "TCAD machine learning calibration" | `ti:TCAD AND ti:calibration AND (cat:physics.app-ph OR cat:cs.LG)` |
| "2019년 이후 TCAD 논문" | `ti:TCAD AND submittedDate:[20190101 TO 20261231]` |

### Phase 2: LLM Summary 강화 (1일)

**목표**: 검색 결과 각각에 LLM 요약을 추가 (비동기, fallback 있음)

**변경 사항**:
- `arxiv_agent.py`의 `search()` 메서드에서 `summarize_paper()` 호출 추가
- 단, timeout 10초로 제한 → 실패 시 truncated abstract fallback
- Batch summary: 5개 결과를 한 번에 요약하는 프롬프트 (더 빠름)

```python
# Batch summarization prompt:
"""
Summarize the following 5 papers in 1-2 sentences each.
Focus on: (1) What problem? (2) What method? (3) Key result?

1. Title: {t1}
   Abstract: {a1[:300]}
2. Title: {t2}
   Abstract: {a2[:300]}
...
"""
```

### Phase 3: Relevance Reranking (0.5일)

**목표**: 내 paper library와의 유사도 기반으로 검색 결과 재정렬

**변경 사항**:
- 검색 결과 각각을 embedding(BGE-m3)으로 vector화
- 내 library vector store의 centroid와 cosine similarity 계산
- 유사도 순으로 결과 재정렬

**제약**: CPU-only → top_k=5로 제한 (유사도 계산 비용)

### Phase 4: Supervisor 개선 (0.5일)

**목표**: Search intent 분류 정확도 향상 + query 전처리

**변경 사항**:
- `supervisor.py`의 `route()`에서 search intent로 분류 시:
  - "search", "find", "look up" 등의 prefix 제거
  - 한국어 검색어 패턴 인식 ("찾아줘", "검색해" 등)
- `query_optimizer` 호출 여부 결정 (LLM이 필요없는 간단한 query는 skip)

### Phase 5: UI 개선 (0.5일)

**목표**: 검색 결과에 metadata를 더 풍부하게 표시

**변경 사항**:
- `app.py` Tab 2: Arxiv 검색 결과에 카테고리, 관련도 badge 표시
- "Download & Ingest" 버튼 추가 (검색 결과에서 바로 PDF ingest)
- 결과에 "이 논문이 내 library와 얼마나 관련있는지" 표시 (Phase 3 연계)

---

## 4. 구현 순서 및 의존성

```
Phase 1 (Query Optimizer) ──→ Phase 2 (LLM Summary)
                                    ↓
Phase 4 (Supervisor) ──────→ Phase 3 (Reranking) ──→ Phase 5 (UI)
```

| Phase | 선행 조건 | 예상 시간 | 난이도 |
|-------|----------|----------|--------|
| **Phase 1** | 없음 | 2h | 중 |
| **Phase 2** | Phase 1 | 1h | 하 |
| **Phase 3** | Phase 2 | 1.5h | 중 |
| **Phase 4** | Phase 1 | 1h | 하 |
| **Phase 5** | Phase 3 | 1h | 중 |

**추천 실행 순서**: Phase 1 → Phase 4 → Phase 2 → Phase 3 → Phase 5

---

## 5. 변경 범위 요약

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `src/agents/arxiv_agent.py` | 수정 | `search()` 메서드에 LLM summary + reranking 추가 |
| `src/agents/query_optimizer.py` | **신규** | Query rewrite Agent |
| `src/agents/supervisor.py` | 수정 | `route()`에서 query 전처리 + optimizer 호출 |
| `app.py` | 수정 | Arxiv 검색 탭 UI 개선, Download & Ingest 버튼 |
| `src/rag_chain.py` | 수정 (선택) | 검색 결과와 vector store 유사도 계산 API 추가 |
| `tests/test_query_optimizer.py` | **신규** | Query optimizer 단위 테스트 |
| `.omo/errors/` | 신규 | 변경 사항 문서화 |

---

## 6. 리스크 및 완화 방안

| 리스크 | 영향 | 완화 방안 |
|--------|------|----------|
| Ollama LLM 호출로 인한 검색 지연 | 검색 시간 2배 증가 | Phase 1에서 LLM skip 조건 추가 (단순 query는 직접 전달) |
| CPU-only embedding reranking 속도 | reranking에 1-2초 추가 | top_k=5 제한, 검색 결과 10개만 reranking |
| LLM query rewrite 실패 | query 왜곡 | Fallback: LLM 실패 시 원본 query 그대로 사용 |
| 한국어 query 처리 품질 | 번역 정확도 | LLM prompt에 "Translate to English" 강제 명시 |

---

## 7. 교안 연계 요약 (발표자료 용)

### Architecture Diagram

```
Before:
User → Supervisor → Arxiv API → Raw Results → User
  
After:
User → Supervisor (의도 분류)
          ↓
    Query Optimizer Agent (LLM query rewrite ← Langgraph / Agentic RAG)
          ↓
    Arxiv API (최적화된 query)
          ↓
    LLM Summary (batch summarization)
          ↓
    Relevance Reranking (내 library와 유사도)
          ↓
    User (정확한 결과 + 요약 + 관련도)
```

### 발표 키포인트

1. **Agentic RAG의 실제 적용**: Query rewrite는 전형적인 Agentic RAG 패턴
2. **Multi-agent orchestration**: Supervisor → Optimizer → Searcher → Reranker
3. **LLM as a tool**: 검색 품질 향상을 위해 LLM을 단순 chatbot이 아닌 검색 엔진 최적화 도구로 활용
4. **Harness engineering**: 모든 변경사항은 `ruff check` + `pytest` 검증 통과 필수
