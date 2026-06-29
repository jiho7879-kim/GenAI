# Research Agent — Implementation Plan v2

> **프로젝트**: 석사 2년간 사용할 개인 Research Assistant (반도체소자 + TCAD + ML)  
> **기한**: 7/8(화) ~ 7/10(목) 3일 MVP 완성 → 이후 2년 확장  
> **핵심 제약**: CPU-only (32GB RAM), 사외망, 비용 무료  
> **평가**: 프로젝트 50% — 채점자가 로컬에서 실행/확인 가능해야 함

---

## ✅ 결정 완료된 사항

| 항목 | 결정 | 사유 |
|---|---|---|
| 연구 분야 | 반도체소자 + TCAD + TCAD 내 ML | 샘플 논문 수집 방향 확정 |
| MVP 범위 | **PDF RAG + Multi-Agent + Arxiv Search** (최대 범위) | 가능한 많은 기술 포함 |
| 샘플 논문 | Arxiv TCAD+ML 3~5편 다운로드 | Public 도메인, 무료 |
| 에러 문서화 | `.omo/errors/YYYY-MM-DD_*.md` | 최종 리포트 필수 자료 |

---

## 🔴 Q3/Q4 추천 및 결정

### Q3. Vector DB

| 항목 | FAISS | Chroma |
|---|---|---|
| 설치 | `pip install faiss-cpu` (1초) | `pip install chromadb` |
| 실행 방식 | 파일 기반 (별도 서버 불필요) | **서버 프로세스 실행 필요** |
| 채점자 실행 | 그냥 `app.py` 실행 시 자동 로드 | `chroma run` 별도 실행 필요 |
| 메모리 | 가벼움 (100MB 이하) | 상대적으로 무거움 |
| metadata 필터 | 간단한 구현 가능 | 기본 지원 |
| **추천 이유** | ✅ **채점자가 바로 실행 가능** | ❌ 평가 환경에서 추가 설정 부담 |

> **👉 추천: FAISS** — 채점자가 `pip install` 후 `streamlit run app.py`만으로 바로 확인 가능.  
> TCAD 특화 필터링(디바이스 종류, 파라미터 등)은 FAISS + Dict metadata로도 충분히 구현 가능.

### Q4. 임베딩 모델

| 항목 | all-MiniLM-L6-v2 | BGE-m3 | Ollama qwen3.5 |
|---|---|---|---|
| 크기 | 80MB | 2.2GB | 3.4GB |
| 속도 | ⚡ 매우 빠름 | 빠름 | 느림 (CPU) |
| 다국어 | 영어만 | **한국어+영어+기술용어** | 한국어+영어 |
| 품질 | 보통 | **높음** | 높음 |
| 서비스 배포 | 가벼워서 좋음 | 무난 | 무거움 |
| **추천 이유** | ❌ TCAD 기술용어에 약함 | ✅ **발란스 최적** | ❌ CPU에서 너무 느림 |

> **👉 추천: BGE-m3 (BAAI/bge-m3)** — 한국어+영어+기술용어 모두 커버, FAISS와 호환,  
>  80MB보단 크지만 CPU에서 준수한 속도, 서비스 배포도 무난.  
>  *대안: BGE-small (400MB)로 더 가볍게 가능*

### 결정해주세요:
- **Vector DB**: FAISS / Chroma (추천: FAISS)
- **Embedding**: BGE-m3 / all-MiniLM-L6-v2 / qwen3.5 (추천: BGE-m3)

---

## 1. Architecture (확정안)

```
┌────────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                       │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  📚 Paper Lab    │  │  🔍 Search   │  │  ⚙️ Settings │ │
│  │  (PDF upload,    │  │  (Arxiv 검색,│  │  (모델 선택,  │ │
│  │   Q&A, 요약)     │  │  논문 찾기)  │  │  chunk 설정)  │ │
│  └────────┬─────────┘  └──────┬───────┘  └──────────────┘ │
└───────────┼──────────────────┼──────────────────────────────┘
            │                  │
            ▼                  ▼
┌────────────────────────────────────────────────────────────┐
│                    Supervisor Agent                          │
│  의도 분류: "질문" / "요약" / "검색" / "비교"               │
└────────┬─────────┬──────────────┬───────────────────────────┘
         │         │              │
         ▼         ▼              ▼
┌────────────┐ ┌─────────┐ ┌──────────────┐
│Paper RAG   │ │Arxiv    │ │Report Agent  │
│Agent       │ │Search   │ │(결과 통합,    │
│(PDF 기반   │ │Agent    │ │ 마크다운      │
│ Q&A, 요약) │ │(키워드  │ │ 포맷팅)       │
│            │ │ 검색)   │ │              │
└──────┬─────┘ └─────────┘ └──────┬───────┘
       │                          │
       ▼                          ▼
┌──────────────┐       ┌─────────────────┐
│  Vector Store│       │  Markdown/Text   │
│  (FAISS)     │       │  최종 출력       │
└──────────────┘       └─────────────────┘
```

## 2. MVP Tech Stack

| 계층 | 기술 | 비고 |
|---|---|---|
| **Frontend** | Streamlit | 멀티탭 UI (Paper Lab / Search / Settings) |
| **Agent** | Langgraph | Supervisor → 3개 Specialist Agents |
| **RAG** | Langchain | PDF ingest → chunk → retrieve |
| **Vector DB** | 🔴 FAISS / Chroma | |
| **Embedding** | 🔴 BGE-m3 / all-MiniLM-L6-v2 / Ollama | |
| **LLM (local)** | Ollama qwen3.5:4b | 빠른 응답 필요할 때 |
| **LLM (heavy)** | Zen Free (Big Pickle / Qwen3.6 Plus Free) | Agent 의사결정, 장문 생성 |
| **PDF parsing** | PyMuPDF (fitz) | 텍스트 + 메타데이터 추출 |

## 3. Component Design

### 3.1 PDF Ingest Pipeline (`ingest.py`)

```
PDF file
  → PyMuPDF로 텍스트 추출
  → RecursiveCharacterTextSplitter (chunk_size=???)
  → BGE-m3 임베딩
  → FAISS에 저장 (with metadata: filename, page, chunk_id)
```

**TCAD 특화 고려사항**:
- TCAD 결과 CSV/그래프가 포함된 논문은 figure caption도 chunk에 포함
- 디바이스 파라미터(도핑 농도, gate length 등)가 포함된段落에 태깅

### 3.2 Supervisor Agent (`supervisor.py`)

```python
# 의도 분류 로직
intent_classifier = """
다음 질문의 의도를 분류하세요:
- "paper": 업로드된 논문에 대한 질문/요약
- "search": Arxiv에서 새 논문 검색
- "report": 종합 리포트 작성

질문: {user_input}
의도:
"""
```

### 3.3 Paper RAG Agent (`paper_agent.py`)

```
Input: 질문 + vectorstore reference
Process: 
  1. vectorstore에서 관련 chunk 검색 (top_k=???)
  2. LLM이 chunk 기반으로 답변 생성
  3. cited chunk 정보 함께 반환
Output: 답변 + 인용 chunk 리스트
```

### 3.4 Arxiv Search Agent (`arxiv_agent.py`)

```
Input: 검색 키워드 (예: "TCAD machine learning")
Process:
  1. Arxiv API로 검색 (abstract, title)
  2. 결과 리스트에서 관련도 높은 논문 선별
  3. 각 논문 요약 생성
Output: 논문 리스트 + 요약
```

### 3.5 Streamlit UI (`app.py`)

```python
# Tab 구조
tab1, tab2, tab3 = st.tabs(["📚 Paper Lab", "🔍 Arxiv Search", "⚙️ Settings"])

# Paper Lab: PDF 업로드 + 채팅 + Agent trace 사이드바
with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        # 채팅 인터페이스
    with col2:
        # Agent thought process 표시
        with st.expander("🤖 Agent Trace"):
            st.json(agent_log)

# Arxiv Search: 키워드 입력 → 결과 리스트 → 선택적 ingest
with tab2:
    keyword = st.text_input("Search arxiv...")
    if keyword:
        results = arxiv_agent.run(keyword)
        for paper in results:
            st.markdown(f"**{paper.title}**")
            st.write(paper.summary)

# Settings: 모델 선택, chunk size, top_k 등
with tab3:
    st.selectbox("LLM Model", ["qwen3.5:4b (빠름)", "qwen3.5:9b (정확)", "Zen Free"])
    st.slider("Chunk Size", 256, 2048, 512)
```

## 4. Error Documentation System

### 위치
```
.omo/errors/
```

### 템플릿 (모든 파일 통일)

```markdown
# [YYYY-MM-DD] 에러 제목

## 분류
- [ ] Code Error: 잘못된 코드
- [ ] Direction Error: 설계/아이디어 오류  
- [ ] Performance: 속도/메모리 이슈
- [ ] Environment: 환경/의존성 문제

## 상황
- 의도:
- 발생:
- 원인 추정:

## 실패 기록
[실패한 코드 or 설계]

## 수정 기록
[수정된 코드 or 개선된 설계]

## 차이점 분석
- 다른 점:
- 수정이 효과적이었던 이유:

## 재발 방지
```

### 파일명 컨벤션
```
YYYY-MM-DD_번호-짧은설명.md
예: 2026-07-08_01-faiss-load-failed.md
    2026-07-08_02-chunk-too-large-oom.md
    2026-07-09_03-agent-routing-wrong.md
```

## 5. Development Timeline (3일, 24H)

### Day 1 (7/8, 화) — Core RAG

| 시간 | 작업 | 상세 |
|---|---|---|
| 08:30~09:00 | **Plan 최종 확정** | Q3/Q4 결정 + architecture sign-off |
| 09:00~09:30 | 개발환경 셋업 | `pip install` dependencies, Ollama 모델 확인 |
| 09:30~11:00 | PDF Ingest 파이프라인 | PyMuPDF → chunk → embed → FAISS |
| 11:00~12:00 | **Ingest 테스트 + 에러 기록** | TCAD 샘플 논문 3편으로 테스트 |
| 12:00~13:00 | 중식 | |
| 13:00~15:00 | RAG Chain 구축 | Langchain retrieval QA chain |
| 15:00~16:00 | Basic Streamlit UI | PDF 업로드 + 질문 입력 + 답변 출력 |
| 16:00~17:00 | Day 1 통합 테스트 | 전체 플로우 검증 + 에러 문서화 |

### Day 2 (7/9, 수) — Multi-Agent

| 시간 | 작업 | 상세 |
|---|---|---|
| 08:30~10:00 | Supervisor Agent | 의도 분류 LLM + 라우팅 로직 |
| 10:00~12:00 | Paper RAG Agent | RAG chain을 Agent로 래핑 |
| 12:00~13:00 | 중식 | |
| 13:00~15:00 | Report Agent | 결과 통합 + Markdown 포맷팅 |
| 15:00~17:00 | Agent ↔ UI 연동 | Agent trace 시각화, 탭 구성 완성 |
| 16:00~17:00 | Day 2 테스트 + 에러 기록 | Agent 라우팅 정확도 검증 |

### Day 3 (7/10, 목) — Arxiv + Polish

| 시간 | 작업 | 상세 |
|---|---|---|
| 08:30~10:00 | Arxiv Search Agent | Arxiv API 연동 + 결과 요약 |
| 10:00~12:00 | 통합 테스트 | 모든 Agent 연결 종단간 테스트 |
| 12:00~13:00 | 중식 | |
| 13:00~15:00 | **README + 발표자료** | 설치법, 구조도, 스크린샷, 에러 로그 |
| 15:00~16:00 | 에러 문서 최종 정리 | `.omo/errors/` 전체 검토 |
| 16:00~17:00 | 시연 리허설 | |
| 17:00~17:20 | **최종 평가** | |
| ~23:59 | 제출 | Google Form + Drive |

## 6. Directory Structure

```
research-agent/
├── app.py                     # Streamlit 메인
├── requirements.txt
├── README.md
├── src/
│   ├── ingest.py             # PDF → chunk → FAISS
│   ├── rag_chain.py          # Langchain RAG
│   ├── agents/
│   │   ├── supervisor.py     # 의도 분류 Agent
│   │   ├── paper_agent.py    # 논문 Q&A Agent
│   │   ├── arxiv_agent.py    # Arxiv 검색 Agent
│   │   └── report_agent.py   # 결과 통합 Agent
│   └── ui/
│       ├── paper_lab.py      # Paper Lab 탭
│       ├── arxiv_tab.py      # Arxiv Search 탭
│       └── settings.py       # 설정 탭
├── data/
│   └── papers/               # 샘플 TCAD+ML 논문 (git 추적)
├── vectorstore/              # FAISS 인덱스 (gitignore)
└── .omo/
    ├── errors/               # 시행착오 기록 (필수)
    ├── plans/                # Plan 역사
    └── lessons.md            # 종합 교훈
```

## 7. Post-MVP (2년 로드맵)

```
7/10  MVP: PDF RAG + Multi-Agent + Arxiv Search + Streamlit
         ↓
8월    TCAD 시뮬레이션 CSV 업로드 → 텍스트 요약 기능
         ↓
10월   실험 로그(CSV) ↔ 논문 결과 비교 Agent
         ↓
1월    논문 간 인용 연결 그래프 시각화
         ↓
4월    Related Work 초안 생성 Agent
         ↓
7월    LaTeX 템플릿 + BibTeX 자동 포맷팅
         ↓
12월   개인 연구 KB 200편 → 졸업논문 종합 지원
```

## 8. Risk Matrix

| 리스크 | 확률 | 영향 | 대책 |
|---|---|---|---|
| **OOM (CPU 32GB)** | 중 | 높음 | chunk size 제한(512↓), qwen3.5:4b 우선 사용 |
| **한국어 TCAD 용어 OCR 품질** | 높 | 중 | BGE-m3로 완화, 필요시 영문 논문 우선 |
| **Arxiv API rate limit** | 낮 | 중 | local cache로 1시간內 중복 호출 방지 |
| **Langgraph 학습 시간 부족** | 중 | 높 | Day2 전에 간단한 Langgraph 튜토리얼 선행 |
| **Streamlit 디버깅 지연** | 중 | 중 | 최소 UI로 시작, 점진적 개선 |
| **Zen Free API 불안정** | 중 | 중 | Ollama fallback 즉시 전환 로직 포함 |

---

> **📌 현재 상태**: Q1/Q2/Q5 확정. Q3/Q4는 위 추천안 검토 후 결정 부탁드립니다.  
> **Plan v2 확정 조건**: Q3/Q4 결정 + Architecture sign-off
