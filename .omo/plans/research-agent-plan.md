# Research Agent — Implementation Plan

> **프로젝트**: 석사 2년간 사용할 개인 Research Assistant  
> **기한**: 7/8(화) ~ 7/10(목) 3일 MVP 완성 → 이후 2년 확장  
> **핵심 제약**: CPU-only (32GB RAM), 사외망, 비용 무료  

---

## 🔴 RESOLVE NEEDED — Plan 확정 전에 결정할 사항들

아래 질문들에 답변해주시면 plan을 구체화하겠습니다.

### Q1. 연구 분야
> **질문**: 석사 과정의 연구 분야가 무엇인가요?  
> **이유**: CSV 실험 비교 Agent, Arxiv Watch 키워드, 샘플 논문 수집 방향이 결정됨  
> **예시**: NLP, Computer Vision, 추천 시스템, HCI, AI 의료, etc.

### Q2. MVP scope (3일간 개발 범위)
> **질문**: 3일 프로젝트 기간에 아래 중 어디까지 포함하나요?  
> (A) PDF upload + RAG Q&A + 요약 (B) A + Arxiv 검색 (C) B + Multi-Agent 기초 (D) 직접 정함  

### Q3. Vector DB 선택
> **질문**: 가벼운 FAISS vs 기능이 많은 Chroma?  
> - FAISS: 메모리 사용 적음, CPU 빠름, 설치 간단  
> - Chroma: metadata 필터링, 지속성, 더 풍부한 API (단 CPU 환경에서 약간 더 무거움)

### Q4. Embedding 모델
> **질문**: 임베딩은 Ollama 로컬 모델 vs 경량 Python 모델 vs Zen Free API?  
> - `all-MiniLM-L6-v2`: 80MB, 빠름, CPU OK (추천)  
> - Ollama `qwen3.5:4b`로 임베딩: 느림, 품질 좋음  
> - Zen Free API: 네트워크 필요, 무료配额有限  

### Q5. 시연용 샘플 논문
> **질문**: 데모에 사용할 샘플 논문 PDF는 어떻게 확보하나요?  
> - Arxiv에서 연구 분야 관련 논문 3~5편 다운로드  
> - 다른 경로가 필요하면 말씀해주세요

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                     │
│  ┌──────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │Paper │ │Arxiv     │ │Experiment│ │Writing         │  │
│  │Q&A   │ │Watch     │ │Analyzer  │ │Assistant       │  │
│  └──┬───┘ └────┬─────┘ └────┬─────┘ └───────┬────────┘  │
└─────┼──────────┼────────────┼────────────────┼───────────┘
      │          │            │                │
      ▼          ▼            ▼                ▼
┌─────────────────────────────────────────────────────────┐
│                    Supervisor Agent                        │
│          (의도 분류 + Agent 라우팅)                       │
└────┬──────────┬────────────┬────────────────┬────────────┘
     │          │            │                │
     ▼          ▼            ▼                ▼
┌────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐
│Paper   │ │Arxiv     │ │Exp       │ │Related Work    │
│RAG     │ │Search    │ │Compare   │ │Draft           │
│Agent   │ │Agent     │ │Agent     │ │Agent           │
└───┬────┘ └──────────┘ └──────────┘ └───────┬────────┘
    │                                         │
    ▼                                         ▼
┌─────────────┐                    ┌────────────────────┐
│ Vector Store│                    │  Report Generator  │
│ (FAISS)     │                    │  (Markdown/LaTeX)  │
└─────────────┘                    └────────────────────┘
```

## 2. MVP Tech Stack (3일 완성)

| 계층 | 기술 | 선택 이유 |
|---|---|---|
| **Frontend** | Streamlit | 과정에서 배움, 빠른 프로토타이핑 |
| **Agent Framework** | Langgraph | 과정 커리큘럼 포함, Multi-Agent 구조 |
| **RAG** | Langchain | 과정에서 배움 |
| **Vector DB** | 🔴 FAISS vs Chroma (Q3) | |
| **Embedding** | 🔴 (Q4) | |
| **LLM (local)** | Ollama qwen3.5:4b (일반) / 9b (복잡) | CPU 한계, 무료 |
| **LLM (cloud)** | Zen Free (Big Pickle) — 복잡한 Agent 전용 | 무료, 빠름 |
| **PDF 파싱** | PyMuPDF (fitz) or pdfplumber | 라이선스 무료 |
| **문서화 폴더** | `.omo/errors/YYYY-MM-DD_*.md` | 체계적 기록 |

## 3. Error Documentation System

### 저장 구조
```
.omo/errors/
├── 2026-06-29_초기환경셋업.md
├── 2026-06-29_pdf-텍스트추출-실패.md
├── 2026-07-01_ocr-품질-이슈.md
├── 2026-07-08_rag-chunking-최적화.md
└── ...
```

### 템플릿 (모든 에러 문서에 통일)

```markdown
# [날짜] 에러 제목

## 분류
- [ ] Code Error (잘못된 코드 → 수정코드)
- [ ] Direction Error (아이디어/설계 오류)
- [ ] Performance Issue (속도/메모리)
- [ ] Environment Issue (환경/의존성)

## 상황
- 무엇을 하려고 했는가:
- 어떤 일이 발생했는가:
- 예상 원인:

## 상세 기록

### 잘못된 접근 (코드 or 아이디어)
\`\`\`
(여기에 실제 실패한 코드 or 설계 기술)
\`\`\`

### 수정/개선된 접근
\`\`\`
(여기에 수정된 코드 or 개선된 설계)
\`\`\`

## 차이점 분석
- 무엇이 달랐는가:
- 왜 수정이 효과적이었는가:

## 재발 방지
- 앞으로 어떻게 방지할 것인가:
- 체크리스트 항목:
```

### 기록 원칙
1. **실패하자마자 즉시 기록** (나중에 쓰면 까먹음)
2. **"왜" 실패했는지를 반드시 포함**
3. **수정할 때는 "수정 전"과 "수정 후"를 모두 보존**
4. **하나의 파일 = 하나의 독립된 이슈**
5. 파일명 형식: `YYYY-MM-DD_짧은설명.md`

## 4. MVP Development Timeline (3일)

### Day 1 (7/8) — Foundation

| 시간 | 작업 | 산출물 |
|---|---|---|
| 08:30~09:30 | 프로젝트 기획안 작성, 아키텍처 확정 | plan.md |
| 09:30~11:00 | PDF ingest 파이프라인 구축 | ingest.py |
| 11:00~12:00 | Vector store 구축 + 임베딩 테스트 | vectorstore/ |
| 12:00~13:00 | 중식 | |
| 13:00~15:00 | Basic RAG chain (Langchain) | rag_chain.py |
| 15:00~16:00 | Streamlit 기본 UI (PDF 업로드 + Q&A) | app.py |
| 16:00~17:00 | 통합 테스트 + 에러 문서화 | errors/*.md |

### Day 2 (7/9) — Agent

| 시간 | 작업 | 산출물 |
|---|---|---|
| 08:30~10:00 | Supervisor Agent (의도 분류) | supervisor.py |
| 10:00~12:00 | Paper RAG Agent 구현 | paper_agent.py |
| 12:00~13:00 | 중식 | |
| 13:00~15:00 | Report Agent (결과 포맷팅) | report_agent.py |
| 15:00~17:00 | Agent ↔ Streamlit 연동, trace 시각화 | agent_trace.py |
| 16:00~17:00 | 자습/에러 문서화 | |

### Day 3 (7/10) — Polish + Present

| 시간 | 작업 | 산출물 |
|---|---|---|
| 08:30~10:00 | Edge case 처리 (OOM, chunk 실패 등) | |
| 10:00~12:00 | README, 발표자료, 시연 스크립트 | README.md |
| 12:00~13:00 | 중식 | |
| 13:00~15:00 | 에러 문서 검토 + 최종 정리 | errors/ 최종본 |
| 15:00~16:00 | 최종 점검 + 제출 | |
| 16:00~17:00 | 시연 리허설 | |
| 17:00~17:20 | **최종 평가** | |

## 5. Directory Structure

```
research-agent/
├── app.py                     # Streamlit 메인
├── requirements.txt
├── README.md
├── src/
│   ├── ingest.py             # PDF → chunk → vectorstore
│   ├── rag_chain.py          # Langchain RAG chain
│   ├── agents/
│   │   ├── supervisor.py     # 의도 분류 Agent
│   │   ├── paper_agent.py    # 논문 Q&A Agent
│   │   └── report_agent.py   # 결과 통합 Agent
│   └── ui/
│       ├── chat.py           # 채팅 UI 컴포넌트
│       └── sidebar.py        # 설정 사이드바
├── data/
│   └── papers/               # 샘플 논문 PDF
├── vectorstore/              # FAISS 인덱스 (gitignore)
└── .omo/
    ├── errors/               # 시행착오 기록
    ├── plans/                # plan 파일들
    └── lessons.md            # 종합 교훈
```

## 6. Post-MVP (2년 로드맵)

```
1개월차: Arxiv Search Agent 추가 (Arxiv API 연동)
3개월차: 논문 연결 그래프 시각화 (citation network)
6개월차: 실험 CSV 업로드 → 논문 결과 비교 Agent
1년차:  Related Work 자동 초안 생성
1.5년차: LaTeX 템플릿 + BibTeX 인용 자동 포맷팅
2년차:  개인 연구 KB 200편 완성 + 졸업논문 지원
```

---

> **❗ 다음 단계**: 위 🔴 Q1~Q5에 대한 답변을 주시면 plan을 구체화하고 확정합니다.  
> **plan 확정 전까지 코드 작성하지 않습니다.**
