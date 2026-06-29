---
title: "아키텍쳐 결정사항 — Agent 구조, Langchain 선택, Ollama 통합"
date: 2026-06-29
category: decision
severity: info
---

## 증상 (Symptom)

Research Agent 구현 시 다음과 같은 아키텍쳐 결정이 필요했음:
1. Multi-Agent를 어떤 프레임워크로 구현할 것인가
2. RAG 체인을 Langchain으로 할 것인가, 직접 구현할 것인가
3. Supervisor가 LLM으로 intent classification을 할 것인가, 규칙 기반으로 할 것인가
4. 각 Agent 간 데이터 흐름을 어떻게 설계할 것인가

## 시도한 접근법 및 결정 (Approaches & Decisions)

### D1: Agent Framework — Langgraph vs Simple class-based

**고려한 옵션:**
- Langgraph: 상태 그래프, conditional edges, 체계적인 Agent pipeline
- Simple class-based: 각 Agent가 독립적인 class, Supervisor가 라우팅

**선택: Simple class-based**

**근거:**
- Langgraph는 CPU-only 환경에서 불필요한 오버헤드
- 현재 scope에서 Agent는 4개뿐 → 복잡한 상태관리 불필요
- class-based가 디버깅과 trace 수집에 유리
- 평가자 코드 이해에도 더 쉬움 (Langstream 50% 평가에 불필요한 복잡도)

```python
# 선택된 구조: 단순 class composition
class SupervisorAgent:     # intent classification
class PaperAgent:          # RAG Q&A
class ArxivSearchAgent:    # Arxiv search
class ReportAgent:         # Formatting
```

**실패/폐기: Langgraph 도입 시도**
- `StateGraph`, `MessageGraph` 등 개념이 오버스펙
- 컴파일/실행 구조가 Streamlit 단일 스레드와 충돌 가능성
- CPU-only에서 node 실행 스케줄링이 오히려 성능 저하

### D2: RAG 구현 — Langchain vs LlamaIndex vs 직접 구현

**고려한 옵션:**
- Langchain `RetrievalQA`: 익숙한 API, 간단한 체인 구성
- LlamaIndex: 더 많은 인덱싱 기능, TCAD 문서에 유용할 수 있음
- 직접 구현 (retrieve + prompt + generate): 최대 제어

**선택: Langchain (`RetrievalQA` + `stuff` chain)**

**근거:**
- `RetrievalQA` with `chain_type="stuff"`가 CPU에서 가장 효율적 (한 번에 모든 context 전달)
- Langchain `PromptTemplate`으로 프롬프트 관리 용이
- 직접 구현은 불필요한 재발명 (retriever, prompt, LLM call을 직접 연결해도 10줄 차이)
- LlamaIndex는 학습곡선이 가파르고 평가자가 검증하기 어려움

```python
# RAGChain 핵심: 30줄
self._qa_chain = RetrievalQA.from_chain_type(
    llm=self.llm,
    chain_type="stuff",
    retriever=retriever,
    return_source_documents=True,
    chain_type_kwargs={"prompt": prompt},
)
```

### D3: Intent Classification — LLM vs 규칙 기반

**고려한 옵션:**
- LLM 기반 (Ollama): 확장성 높음, 새로운 의도 추가 쉬움
- 규칙 기반 (regex/keyword): 빠름, 의존성 없음
- 하이브리드: LLM 우선, fallback 규칙

**선택: LLM 기반 (Ollama qwen3.5:4b, temperature=0.0)**

**근거:**
- 최종 프로젝트에서 "Agent 기술 사용" 평가 항목 충족
- 사용자가 "TCAD 논문 찾아줘", "search for GAA FET" 등 다양한 표현 사용 → 규칙 기반으로는 한계
- Temperature=0.0으로 deterministic하게 동작
- qwen3.5:4b (3.4GB)가 classification에는 충분한 성능

```python
# 64 token 제한, temperature=0.0, single label output
self._llm = Ollama(model=self.model_name, temperature=0.0, num_predict=64)
```

### D4: Embedding Model — BGE-m3 vs all-MiniLM-L6-v2 vs multilingual-e5

**고려한 옵션:**
- `all-MiniLM-L6-v2`: 빠름, 80MB, but English only, Korean TCAD 용어 처리 불가
- `BAAI/bge-m3`: 2.2GB, multilingual, 8194 vocab, Korean 포함
- `intfloat/multilingual-e5-small`: 500MB, multilingual이지만 BGE-m3보다 품질 낮음

**선택: BAAI/bge-m3**

**근거:**
- Korean + English TCAD technical terms 처리 가능
- CPU에서 inference 가능 (Intel Iris Xe에서도 수초 내 처리)
- cosine similarity 지원 (normalize_embeddings=True)
- sentence-transformers와 완벽 호환

```python
self._embedding_model = HuggingFaceEmbeddings(
    model_name="BAAI/bge-m3",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)
```

### D5: PDF Parser — PyMuPDF vs PyPDF2 vs PDFPlumber vs Unstructured

**고려한 옵션:**
- PyMuPDF (fitz): 빠름, Apache 2.0 라이선스, page별 로드 가능
- PyPDF2/PikePDF: 순수 Python, 느림
- PDFPlumber: table extraction에 강점, but TCAD 논문은 텍스트 위주
- Unstructured.io: 다양한 포맷 지원, but 무거움, CPU 부담

**선택: PyMuPDF (fitz)**

**근거:**
- Langchain `PyMuPDFLoader`로 바로 연결 가능
- Apache 2.0 라이선스 (상업용 무료, 재배포 제약 없음)
- CPU-only에서 가장 가벼움
- page metadata 자동 포함 (source, page number)

### D6: 유사문서 검색 교정·최적화 사례

**발생 문제:**
- TCAD 논문에서 GAA FET의 "GAA"와 "GaAs"가 다른 개념인데 embedding 유사도로 구분 가능한가?
- "threshold voltage"와 "Vth"가 같은 의미인데 chunk 분리 시 놓칠 수 있음

**해결: 중복 chunk 제거 로직 추가**
```python
def format_sources(sources):
    seen = set()
    for doc in sources:
        key = f"{filename}-p{page}-{content_preview[:30]}"
        if key in seen: continue
        seen.add(key)
```

## 적용 결과 (Resolution)

전체 아키텍쳐:
```
User Input (Streamlit chat)
    │
    ▼
[Supervisor Agent] — Ollama qwen3.5:4b, temperature=0.0
    │  intent ∈ {paper, search, report}
    │
    ├──► [Paper Agent] ──► RAGChain ──► FAISS (BGE-m3)
    │       │                    │
    │       │              [Ollama qwen3.5:4b/9b]
    │       │                    │
    │       └─────────────────► Answer + Sources
    │
    ├──► [Arxiv Search Agent] ──► Arxiv API
    │       │
    │       └─────────────────► Paper list + LLM summaries
    │
    └──► [Report Agent] ──► Markdown formatting
            │
            └─────────────────► Final response
```

각 결정은 "사용자 제약 조건(CPU-only, 사외망, 무료, Windows)"을 전제로 이루어짐.
