# Paper Agent (RAG Q&A) 개선 Plan — 학술 특화 Query → Retrieval → Generation

> 작성일: 2026-06-29
> 상태: Plan (구현 전)
> 관련 교안: Langchain & Langgraph RAG 구축 (3일) + 멀티 Agent 서비스 개발 (2일) + Agentic RAG

---

## 1. 문제 진단

### 1.1 현재 코드의 문제점

| # | 문제 | 심각도 | 현재 코드 위치 |
|---|------|--------|---------------|
| 1 | **Raw question을 그대로 embedding에 사용** | 🔴 | `rag_chain.py:122-125` — `vectorstore.as_retriever()`가 question을 있는 그대로 검색에 사용 |
| 2 | **단일 검색 전략 (오직 similarity)** | 🔴 | `rag_chain.py:122` — `search_type="similarity"` 고정, keyword 검색 없음 |
| 3 | **top_k=5 고정, reranking 없음** | 🟡 | `rag_chain.py:124` — `search_kwargs={"k": 5}`, 검색된 chunk를 그대로 LLM에 전달 |
| 4 | **Chunk가 학술 구조를 무시** | 🟡 | `ingest.py:258` — `RecursiveCharacterTextSplitter`가 단순 문자수 기준 분할, 섹션 경계 무시 |
| 5 | **단일 QA prompt template** | 🟡 | `rag_chain.py:34-45` — 질문 유형(방법론/결과분석/이론설명)별 prompt 분기 없음 |
| 6 | **Citation이 page 번호뿐** | 🟡 | `paper_agent.py:35` — `source_filename + page`만 표시, section명/paragraph 위치 없음 |
| 7 | **답변 품질 검증 없음** | 🔴 | 답변의 각 claim이 실제 context에 grounding되어 있는지 검증하지 않음 |
| 8 | **Lost-in-the-middle 문제** | 🟡 | `chain_type="stuff"`로 모든 chunk를 순서대로 LLM에 전달, 중간 chunk는 attention 저하 |
| 9 | **멀티 문서 비교/대조 불가** | 🟡 | `PaperAgent.ask()`는 단일 질문에 단일 답변만 반환, 문서 간 비교 질문 처리 불가 |
| 10 | **한국어 질문 ⇒ 영문 논문 검색 품질 저하** | 🟡 | supervisor가 intent="paper"로 분류해도, multilinugal embedding(BGE-m3)의 한계 존재 |

### 1.2 학술 Q&A 특화에서의 추가 고려사항

| 특성 | 현재 상태 | 필요 상태 |
|------|----------|----------|
| **용어 정규화** | "TCAD", "Technology CAD", "Technology Computer-Aided Design" → 각각 다른 chunk로 검색됨 | 동의어 확장 / Abbreviation normalization |
| **수식/표현 검색** | 수식이 포함된 chunk는 검색에서 누락되기 쉬움 | LaTeX 표현 고려한 chunk 검색 |
| **인용 추적** | 논문 내 reference chain 정보 없음 | "이 방법은 [3]에서 제안됨" 같은 citation 관계 추적 |
| **실험 결과 vs 이론** | 실험 결과 설명과 이론적 배경이 혼재 | 질문 의도에 따라 실험 결과 또는 이론 섹션에 가중치 부여 |

### 1.3 근본 원인

```
사용자 질문: "Explain the TCAD calibration methodology used in this paper"
    → Supervisor: intent="paper"
    → PaperAgent.ask(질문)
    → RAGChain.query(질문)
    → Retriever: similarity_search(질문, k=5)
         - 질문 전체 문장이 embedding됨 → "calibration"과 관련없는 chunk도 유사도 높게 나올 수 있음
         - "TCAD calibration"만 검색하고 싶은데 "methodology used in this paper" 같은 noise 포함
    → LLM: 5개 chunk를 그대로 context로 전달
         - 관련 없는 chunk가 중간에 끼어들면 답변 품질 저하
         - chunk 순서가 semantic 중요도와 무관
    → 답변: citation이 page 번호뿐, grounding 검증 없음
```

---

## 2. 교안 연계 포인트 (발표자료 활용)

### 2.1 강의 내용 연결

| 교안 모듈 | 핵심 개념 | Plan에서 활용 |
|-----------|----------|-------------|
| **Langchain & Langgraph RAG 구축** (3일차) | RAG pipeline 구성, Retriever, Generator | Phase 1-3: Query rewriting + Multi-retrieval + Generation 개선 |
| **Agentic RAG** (3일차 후반) | Query rewriting, Retrieval Grader, Hallucination Checker | Phase 4: Self-RAG / Reflection Agent (답변 검증) |
| **멀티 Agent 서비스 개발** (2일차) | Multi-Agent Pipeline, Tool use, Orchestration | Phase 5: 논문 분석 Agent Pipeline (Paper Analyst) |
| **Naive RAG → Advanced RAG** | Query transformation, Routing, Fusion | Phase 1-3 전체가 이 커리큘럼과 직접 연결 |

### 2.2 발표자료 연계 포인트

**Before-After 비교 (Arxiv Search와 동일한 패턴):**

| Stage | Before | After | 관련 기술 |
|-------|--------|-------|----------|
| **Query** | "What does this paper say about TCAD calibration?" 그대로 embedding | LLM으로 "TCAD calibration" 추출 + 동의어 확장 + 질문 유형 분류 | Query Rewriting (Agentic RAG) |
| **Retrieval** | Similarity search (k=5) 단일 | Multi-Query + Hybrid (keyword+semantic) + Reranking | Advanced RAG (Langchain) |
| **Generation** | 5개 chunk → one-shot generation | Selected chunks → Domain prompt → Citation check → Self-reflection | Self-RAG, Reflection |
| **Citation** | "p.3" | "Section 2.1 (p.3): 실제 인용된 문장" | Grounded generation |

**발표 키포인트:**
1. **Naive RAG → Advanced RAG 진화 과정**: Query rewriting, Multi-Query, Reranking, HyDE 각각의 효과를 ablation study 형태로 제시
2. **Agentic RAG의 실제 구현**: 단순 RAG가 아니라 Agent 패턴(Reflection, Tool use)을 RAG에 통합
3. **학술 도메인 특화**: 일반 RAG와 TCAD/반도체 도메인 RAG의 차별점

---

## 3. 상세 구현 Plan

### Phase 0: Chunking 개선 (선행 조건)

**목표**: 학술 논문 구조를 존중하는 chunking 전략 도입

**변경 파일**: `src/ingest.py`

```python
# 현재 (line 258)
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=768, chunk_overlap=50, length_function=len
)

# 개선 방향 1: Semantic Chunking
# - "Introduction", "Methodology", "Results", "Conclusion" 같은 섹션 헤더를 기준으로 분할
# - 각 섹션 내에서만 RecursiveCharacterTextSplitter 적용
# - section_name을 metadata에 저장 -> 검색 시 "이 질문은 Results 섹션에 집중" 가능

# 개선 방향 2: Sentence-window Chunking
# - 작은 chunk(256 chars)로 검색하고, 검색된 chunk의 주변 문장(각 128 chars)을 함께 context로 전달
# - 검색 정밀도는 높이고, LLM에는 충분한 context 제공
```

**교안 연결**: Langchain Document Splitter 전략, Chunk size 최적화

---

### Phase 1: Query Rewriting Agent (RAG용)

**목표**: 사용자 질문을 RAG 검색에 최적화된 형태로 변환 (Arxiv Query Optimizer와 유사한 패턴)

**변경 파일**: `src/agents/query_rewriter.py` (신규)

**세부 구현**:
```python
# Query Rewriting 종류 (질문 유형에 따라 선택)

# 1. Query Decomposition (복잡한 질문 → 단순 sub-question)
# 입력: "Compare the TCAD calibration methods in papers 1 and 3"
# 출력: [
#   "TCAD calibration method in paper 1",
#   "TCAD calibration method in paper 3",
#   "comparison of TCAD calibration approaches"
# ]

# 2. Query Expansion (동의어/약어 확장)
# 입력: "GAA FET device structure"
# 출력: "gate-all-around FET device structure OR GAA FET device structure"

# 3. HyDE (Hypothetical Document Embedding)
# 입력: "What are the key parameters for TCAD calibration?"
# 출력: 가상의 문서 청크 생성 (이 질문에 대한 답변을 포함한 문단)
#      → 이 가상 문서를 embedding해서 검색 (검색 정확도 대폭 향상)

# 4. Query Translation (한국어 → 영어)
# 입력: "TCAD 캘리브레이션 방법론 설명해줘"
# 출력: "TCAD calibration methodology"
```

**Fallback**: LLM 실패 시 원본 질문 유지 (query_optimizer.py와 동일 패턴)

**Prompt 템플릿**:
```
You are a search query optimizer for a scientific RAG system.
Your task: rewrite the user's question to maximize retrieval accuracy.

Rules:
1. Extract ONLY the core technical keywords — remove question words, filler phrases
2. For Korean questions → translate to English technical terms
3. Expand abbreviations: "GAA FET" → "gate-all-around FET"
4. If the question is complex, break it into multiple simpler queries
5. Output JSON: {"queries": ["query1", "query2", ...], "type": "expand|decompose|hyde|translate"}
```

**교안 연결**: Langchain Query Rewriting (Agentic RAG), HyDE 패턴

---

### Phase 2: Multi-Strategy Retrieval

**목표**: 질문 유형에 따라 최적의 검색 전략 선택 + 결과 융합

**변경 파일**: `src/rag_chain.py`, `src/agents/paper_agent.py`

**세부 구현**:

```
질문 유형 분류 (LLM or Rule-based):
  - "방법론": "how", "method", "approach", "technique", "calibration"
  - "결과분석": "result", "performance", "accuracy", "improvement"
  - "이론설명": "what is", "define", "explain", "principle", "theory"
  - "비교": "compare", "difference", "vs", "versus", "contrast"
  - "요약": "summarize", "overview", "summary"

검색 전략 (질문 유형별):
  - 방법론 → title+abstract 유사도 검색 (Introduction/Methodology 섹션에 가중치)
  - 결과분석 → Results 섹션 집중 검색 (section metadata 활용)
  - 이론설명 → 일반 similarity + keyword hybrid
  - 비교 → Multi-Query + 각각 검색 후 병합

검색 결과 융합 (Fusion):
  1. 각 전략에서 top_k=5씩 검색 (총 10-15개)
  2. 중복 제거 (content hash)
  3. Reciprocal Rank Fusion (RRF)로 순위 재조정
  4. 상위 5개 선택 → LLM에 전달

Hybrid Search (keyword + semantic):
  - BM25 (keyword) + FAISS (semantic) → 가중치 0.3 / 0.7
  - CPU-only 제약: BM25는 pickle dump, FAISS는 index.faiss
  - Fallback: BM25 없으면 pure semantic
```

**교안 연결**: Langchain Ensemble Retriever, Multi-Query Retriever, RRF Fusion

---

### Phase 3: Academic Prompt Engineering & Generation

**목표**: 학술 도메인 특화 prompt + structured output + citation grounding

**변경 파일**: `src/rag_chain.py`

**세부 구현**:

```python
# 질문 유형별 Prompt Template 교체
PROMPTS = {
    "methodology": """You are analyzing a TCAD/semiconductor paper's methodology...
Focus on: simulation setup, parameters, calibration steps, tools used...
Include specific numerical values and equation references from the context.
Structure your answer:
  - Approach Overview
  - Key Parameters
  - Calibration/Simulation Steps
  - Validation Method""",

    "result_analysis": """You are analyzing experimental/simulation results from a paper...
Focus on: quantitative results, graphs, tables, performance metrics...
Report exact numbers and comparisons mentioned in the context.
Include: best result, baseline comparison, statistical significance if available.""",

    "theory": """You are explaining technical concepts from TCAD/semiconductor papers...
Define each term clearly, connect to device physics principles.
Use the context to provide concrete examples from the paper.
When explaining equations, break down each term's physical meaning.""",

    "comparison": """You are comparing multiple approaches/papers...
Create a structured comparison: similarities, differences, trade-offs.
Use a table format when possible.
Support each point with specific citations from the provided context.""",

    "general": QA_PROMPT_TEMPLATE,  # 현재 template 유지
}
```

**Citation Enhancement**:
```python
# 현재: "filename.pdf, p.3"
# 개선: "Section: Methodology (p.3): "actual quoted text from paper""

# Section metadata 추출:
# - chunk metadata에 section_name 필드 추가 (ingest 시)
# - 검색 결과 표시: "**section_name** (p.page): content_preview..."
```

**Grounded Generation** (Self-RAG light):
```python
# LLM 답변 생성 후, 각 문장이 context의 어느 chunk에서 왔는지 태깅:
# "The calibration uses TCAD mixed-mode simulation [Section 2.1]"
# → LLM이 자연어로 citation 부착 (context 속 chunk 참조)

# 간단한 구현: Follow-up prompt
# "For each key claim in your answer, add a citation in brackets
#  referencing the section name from the provided context."
```

**교안 연결**: Prompt Engineering for RAG, Chain-of-Thought prompting, Structured output parsing

---

### Phase 4: Answer Quality Verification (Self-Reflection)

**목표**: 생성된 답변의 hallucination 검증 + missed information 보강

**변경 파일**: `src/agents/paper_agent.py`, `src/rag_chain.py` (옵션)

**세부 구현**:

```python
# Self-Reflection Loop (간단한 2-pass):
# Pass 1: Generate initial answer with RAG
# Pass 2: Verify each claim against context

claim_check_prompt = """You are a fact-checker for academic answers.
Given the context and the generated answer, verify each claim:

Context:
{context}

Generated Answer:
{answer}

For each claim in the answer, check:
1. Is this claim DIRECTLY supported by the context? (YES / PARTIAL / NO)
2. If PARTIAL: what additional information from context is missing?
3. If NO: what does the context actually say?

Output a JSON array:
[
  {"claim": "...", "status": "YES|PARTIAL|NO", "correction": "..."}
]
"""

# PARTIAL/NO claim이 발견되면:
#   - correction 정보를 추가하여 최종 답변 보강
#   - "찾을 수 없는 정보입니다" 명시적으로 표시
```

**단순화 전략** (CPU-only 고려):
- Full Self-RAG는 너무 무거움 (LLM 2회 호출)
- **경량 버전**: LLM 호출 1회로 답변 생성 시 citation이 context에 grounding되었는지만 확인
- 혹은 `num_predict=2048`로 생성 후, 별도 thread에서 async 검증 (UI에 streaming)

**교안 연결**: Agentic RAG (Reflection pattern), Self-RAG, ReAct

---

### Phase 5: Paper Analyst Agent Pipeline (Multi-Agent)

**목표**: 복잡한 논문 분석 워크플로를 sub-agent pipeline으로 처리

**변경 파일**: `src/agents/analyst_agent.py` (신규)

**세부 구현**:

```
사용자 질문: "이 논문들의 TCAD calibration 방법론을 비교하고,
              각각의 장단점을 분석해서 보고서로 작성해줘"

Paper Analyst Supervisor
    │
    ├── 🔍 Retriever Agent: 관련 chunk 검색 (Phase 1 + 2)
    │
    ├── 📖 Reader Agent: 각 논문별 방법론 추출
    │   └── 질문: "What TCAD calibration method does this paper use?"
    │
    ├── ⚖️ Comparator Agent: 방법론 간 차이점 분석
    │   └── 질문: "Compare the calibration approaches across papers"
    │
    ├── ✅ Verifier Agent: 각 claim의 근거 확인 (Phase 4)
    │
    └── 📋 Report Agent: 구조화된 보고서 생성 (기존 ReportAgent 활용)
```

**각 Agent의 역할**:
- **Retriever**: Query rewriting → multi-strategy search → context fusion
- **Reader**: 단일 논문/섹션에 집중한 상세 분석
- **Comparator**: 문서 간 cross-reference 분석 (실제로는 "비교해줘" 질문을 multi-query로 확장)
- **Verifier**: 답변 grounding 검증
- **Report**: Markdown 형식의 종합 보고서

**교안 연결**: Langgraph Multi-Agent Supervisor, Orchestration 패턴, Tool-based Agent

---

## 4. 구현 순서 및 의존성

```
Phase 0 (Chunking)
    │
    ▼
Phase 1 (Query Rewriter) ──→ Phase 2 (Multi-Retrieval)
                                    │
                                    ▼
                            Phase 3 (Prompt Engineering)
                                    │
                                    ▼
                            Phase 4 (Verification)
                                    │
                                    ▼
                            Phase 5 (Analyst Pipeline)
```

| Phase | 선행 조건 | 예상 시간 | 난이도 | 교안 연결도 |
|-------|----------|----------|--------|-----------|
| **Phase 0** Chunking | 없음 | 1h | 하 | ★★★ (Langchain Splitter) |
| **Phase 1** Query Rewriting | Phase 0 | 2h | 중 | ★★★★★ (Agentic RAG) |
| **Phase 2** Multi-Retrieval | Phase 1 | 2.5h | 중상 | ★★★★★ (Advanced RAG) |
| **Phase 3** Prompt Engineering | Phase 2 | 1.5h | 중 | ★★★★ (RAG Generation) |
| **Phase 4** Verification | Phase 3 | 2h | 중 | ★★★★★ (Self-RAG) |
| **Phase 5** Analyst Pipeline | Phase 2-4 | 2h | 상 | ★★★★★ (Multi-Agent) |

**추천 실행 순서 (MVP)**:
Phase 0 → Phase 1 → Phase 2 → Phase 3
→ Phase 4 (선택, 시간 허용 시)
→ Phase 5 (선택, 발표 자료 수준에서 conceptual 구현)

---

## 5. 변경 범위 요약

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `src/ingest.py` | 수정 | Semantic chunking, section metadata 추출 |
| `src/agents/query_rewriter.py` | **신규** | RAG Query Rewriting Agent (HyDE, decomposition, expansion) |
| `src/rag_chain.py` | 수정 | Multi-Query retriever, 질문 유형별 prompt, RRF fusion |
| `src/agents/paper_agent.py` | 수정 | `ask()` 메서드에 rewriting + reflection pipeline 추가 |
| `src/agents/analyst_agent.py` | 신규 (선택) | Multi-step 논문 분석 Agent pipeline |
| `app.py` | 수정 (최소) | Paper Agent 개선에 따른 UI 변경 (필요시) |
| `tests/test_query_rewriter.py` | **신규** | Query rewriting 단위 테스트 |
| `tests/test_rag_chain.py` | **신규** | Multi-retrieval, reranking 테스트 |
| `.omo/errors/` | 신규 | 변경 사항 문서화 |

---

## 6. 리스크 및 완화 방안

| 리스크 | 영향 | 완화 방안 |
|--------|------|----------|
| **CPU-only embedding**으로 HyDE 성능 제한 | 검색 품질 향상이 제한적 | HyDE 경량화 (64 tokens 가상 문서), BGE-m3 유지 |
| **LLM 다중 호출로 인한 지연** (query rewrite + retrieval + reflection) | 응답 시간 2-3배 증가 | Phase 1 LLM timeout=10s, Phase 4는 async (UI에 streaming) |
| **Multi-Query 검색으로 FAISS I/O 증가** | CPU 부하 | 검색은 단일 `similarity_search` → query만 expansion (FAISS query는 1회) |
| **BM25 + FAISS hybrid = 추가 의존성** | 설치 복잡도 증가 | BM25 대신 `keyword_weight` 파라미터로 간소화 (langchain 내장 retriever 활용) |
| **Semantic chunking으로 chunk 수 증가** | FAISS index 크기 증가 | section header만 기준으로 분할, chunk_size=512 유지 |
| **Self-Reflection이 오답을 오히려 확증** | 품질 저하 | Reflection prompt에 "Admit when you don't know" 강제, threshold 이하는 생략 |
| **분석 Agent pipeline이 너무 무거움** | 사용자 경험 저하 | Phase 5는 항상 실행하지 않고, "비교/분석/보고서" 키워드 있을 때만 활성화 |

---

## 7. 학술 도메인 특화 요약

### TCAD/반도체 도메인을 위한 특별 고려사항

```
1. 용어 정규화 맵
   "TCAD" = "Technology CAD" = "Technology Computer-Aided Design"
   "GAA" = "Gate-All-Around" = "GAAFET" = "GAA FET"
   "BSIM" = "Berkeley Short-channel IGFET Model"
   "DD" = "Drift-Diffusion"
   "MC" = "Monte Carlo" (transport simulation에서)

2. 섹션 가중치
   - 방법론 질문 → "Methodology", "Simulation Setup", "Calibration" 섹션 +2 가중치
   - 결과 질문 → "Results", "Discussion", "Analysis" 섹션 +2 가중치
   - 이론 질문 → "Introduction", "Background", "Theory" 섹션 +2 가중치
   (Phase 2에서 metadata 기반으로 구현)

3. 수식 인식
   - chunk에 "Equation", "(1)", "Fig." 패턴이 있으면 검색에서 우선순위 상향
   - 질문에 특정 parameter 언급 → 해당 parameter가 포함된 chunk 우선 검색

4. 인용 그래프
   - "이 방법은 [3]에서 제안됨" → [3] citation이 포함된 chunk는 방법론 관련 질문에 중요
   - (선택사항: 발표자료 conceptual 수준)
```

---

## 8. 예상 Before/After

| 질문 유형 | Before (현재) | After (개선 후) |
|-----------|--------------|----------------|
| **방법론 질문** "Explain the calibration method" | page 5 내용 중 일부 + 관련없는 chunk 혼합 | Section 2.1 (Calibration) 내용 정확히 추출 + step-by-step 설명 |
| **비교 질문** "Compare paper 1 and paper 3" | "No specific sources" 또는 한쪽만 답변 | 각각의 방법론 → 차이점 → 표 형식 비교 |
| **한국어 질문** "TCAD 캘리브레이션 방법 설명해줘" | BGE-m3가 어느 정도 검색하나 품질 불확실 | Query rewriting이 정확한 영문 keyword로 변환 → 정확한 chunk 검색 |
| **결과 분석** "What was the best mobility achieved?" | 표/그래프 내용이 chunk에 없으면 누락 | Results 섹션 가중치 검색 + "mobility" 키워드 확장 |
| **이론 질문** "What is the difference between DD and MC transport?" | DD/MC에 대한 설명이 섞여서 검색 | 각 term별 분할 검색 후 융합 → 명확한 비교 |

---

## 9. 검증 기준

각 Phase 완료 시 다음을 통과해야 함:

- `ruff check src/` — 0 errors
- `ruff format --check src/` — 모든 변경 파일 pass
- `pytest tests/` — 기존 44 tests regression pass + 신규 tests pass
- **실제 논문 질문 5개에 대한 답변 품질 평가** (선택사항):
  - 관련 chunk 정확히 검색하는가?
  - 답변이 context에 grounding되어 있는가?
  - Citation이 정확한가?

---

## 10. 교안 연계 요약 (발표자료 용)

### Architecture Evolution

```
Naive RAG (현재):
  Question → Embedding → Similarity Search → LLM → Answer

Advanced RAG (Phase 1-3):
  Question → Query Rewriting ← Agentic RAG 개념
                ↓
          Multi-Query Expansion
                ↓
          Hybrid Search (BM25 + Dense)
                ↓
          RRF Fusion → Reranking
                ↓
          Domain-Specific Prompt (질문 유형별)
                ↓
          LLM → Grounded Answer + Enhanced Citation

Agentic RAG (Phase 4-5):
  Question → Query Rewriting
                ↓
          Retrieval → Reading → Verification ← Self-RAG / Reflection
                ↓
          Answer + Citation Map
```

### 발표 키포인트

1. **RAG의 Query도 Optimization이 필요하다**: Arxiv Search와 동일한 패턴을 RAG에도 적용
2. **Naive → Advanced 진화의 실제**: Langchain이 제공하는 각 RAG component의 효과를 정량적으로 제시
3. **Self-RAG의 실용적 구현**: LLM이 자신의 답변을 검증하게 하는 Reflection 패턴
4. **도메인 특화의 중요성**: TCAD/반도체라는 학술 도메인에 맞춘 전략 차별화

---

*Plan generated by Sisyphus · 관련 교안: Langchain & Langgraph RAG 구축, 멀티 Agent 서비스 개발, Agentic RAG*
