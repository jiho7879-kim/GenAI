---
title: "프로젝트 계획 결정사항 — Research Agent v1→v2→v3 진화"
date: 2026-06-29
category: decision
severity: info
---

## 증상 (Symptom)

프로젝트 요구사항이 추상적인 수준에서 주어짐: "Fast Campus Gen AI Intensive 과정 Final Project로 제출할 Research Agent 제작".
평가 기준이 50%의 고비중이었으나, 첫 요청당시 구체적인 범위·기술스택·아키텍쳐가 정해지지 않은 상태.

## 시도한 해결책 (Attempted Solutions)

### v1 — 첫 번째 계획 (너무 광범위)
- 전체 반도체 산업 전반을 커버하려 시도
- Multi-Agent를 Langgraph로 풀려고 시도
- 2-tier (4b + API) 구조
- 문제점: "석사 2년 동안 쓸 Research Assistant"라는 진짜 니즈에 비해 범위가 과도하게 큼

### v2 — 두 번째 계획 (범위 축소)
- 반도체소자 + TCAD + ML로 도메인 한정
- Ollama only (사외망, API-key 서비스 불가)
- FAISS + BGE-m3 결정 (Chroma vs FAISS 논의 해결)
- 문제점: Streamlit/AWS/Gradio 배포 논의에서 오버스펙 발생, Multi-Agent 범위가 여전히 모호

### v3 — 최종 계획 (결정 완료)
- Local only (Windows 11, CPU-only, Intel Iris Xe, 32GB RAM)
- Ollama (qwen3.5:4b default, qwen3.5:9b complex) + Zen Free fallback (Big Pickle)
- FAISS (서버리스, 단일 `streamlit run app.py`)
- BGE-m3 (Korean + TCAD technical term coverage)
- Scope: Full MVP = PDF upload + RAG Q&A + Multi-Agent (Supervisor/Paper/Arxiv/Report) + Arxiv Search
- Error docs: code error + idea/direction error 모두 `.omo/errors/`에 기록 (final report 포함)

## 결정사항 요약 (Key Decisions)

| Q# | 질문 | 선택 | 근거 |
|---|---|---|---|
| Q1 | Vector Store: FAISS vs Chroma | **FAISS** | 서버리스, 평가자가 `streamlit run app.py` 하나로 실행 가능 |
| Q2 | Embedding: Ollama vs BGE-m3 | **BGE-m3 (BAAI/bge-m3)** | 다국어(영문+한글) + TCAD 전문용어 처리, CPU에서도 동작 |
| Q3 | 프로젝트 범위 (A/B/C) | **C — Full MVP** | 50% 평가 비중, Multi-Agent + RAG + Arxiv 모든 기술 포함 |
| Q4 | Error 문서화 | **필수, 통합 템플릿** | Final report 제출자료로 활용, code error + idea error 모두 |
| Q5 | 일정 | **3일 (Day1 RAG → Day2 Agent → Day3 Arxiv)** | 중간고사(7/2) 전 완료 |

## 근본 원인 분석 (Root Cause)

- 초기 요청이 "Final Project"라는 하나의 목표만 제시 → scope, tech stack, architecture가 전부 미정
- 첫 계획(v1)이 "반도체 산업 전반"으로 너무 큼 → 사용자 니즈 청취 후 "석사 2년 연구보조"로 좁힘
- 3번의 iteration(v1→v2→v3)을 통해 사용자가 원하는 정확한 범위와 기술 스택을 확정

## 교훈 (Lesson Learned)

1. **추상적인 요청 → 반드시 iteration**: v1→v2→v3 질문을 통해 진짜 니즈를 발굴해야 함
2. **사용자 제약을 먼저 파악**: 사외망, CPU-only, 무료, API-key 불가 — 이게 모든 기술 선택의 전제조건
3. **평가자 경험을 최우선**: `pip install && streamlit run app.py`로 실행 가능해야 함
4. **Error 문서를 final report에 포함**: code error + idea/direction error 모두 체계적으로 기록

## 최종 코드 / Fix (Resolution)

Final plan saved to: `.omo/plans/research-agent-plan-v3-final.md`

Chosen architecture:
```
research-agent/
├── app.py              # Streamlit UI (3-tab)
├── src/
│   ├── ingest.py       # PyMuPDF → RecursiveCharacterTextSplitter → BGE-m3 → FAISS
│   ├── rag_chain.py    # Langchain RetrievalQA with Ollama
│   └── agents/
│       ├── supervisor.py   # Intent classifier
│       ├── paper_agent.py  # RAG Q&A wrapper
│       ├── arxiv_agent.py  # Arxiv search
│       └── report_agent.py # Markdown formatting
├── vectorstore/        # FAISS index (runtime generated)
├── data/papers/        # Uploaded PDFs
└── .omo/
    ├── errors/         # Trial & error documentation
    └── plans/          # Project plans
```
