# Research Agent — Implementation Plan v3 (FINAL)

> **프로젝트**: 석사 2년간 사용할 개인 Research Assistant  
> **연구 분야**: 반도체소자 + TCAD 시뮬레이션 + TCAD 내 ML  
> **MVP 기한**: 7/8(화) ~ 7/10(목) 3일  
> **환경**: CPU-only (32GB RAM), Ollama local + Zen Free Hybrid, Windows 11  
> **평가**: 프로젝트 50% — 채점자가 로컬 실행 가능해야 함 (FAISS + Streamlit)

---

## ✅ 최종 결정 사항

| 항목 | 결정 | 사유 |
|---|---|---|
| 연구 분야 | 반도체소자 + TCAD + ML | 샘플 논문: Arxiv TCAD+ML |
| MVP 범위 | **PDF RAG + Multi-Agent + Arxiv Search** | 최대 기술 범위 |
| Vector DB | **FAISS** | 채점자 1-step 실행, 가벼움 |
| Embedding | **BGE-m3 (BAAI/bge-m3)** | 한국어+영어+기술용어, 속도 균형 |
| LLM (빠름) | Ollama qwen3.5:4b | 일상 질문, 요약 |
| LLM (정확) | Ollama qwen3.5:9b / Zen Free | Agent 의사결정, 장문 |
| PDF 파싱 | PyMuPDF (fitz) | 라이선스 무료, 경량 |
| 에러 문서화 | `.omo/errors/YYYY-MM-DD_*.md` | 템플릿 통일, 최종 리포트 필수 |
| 샘플 논문 | Arxiv TCAD+ML 3~5편 | Public domain, 무료 |

---

## 1. Architecture

```
                    ┌─────────────────────────────┐
                    │    Streamlit (3 Tabs)        │
                    │  📚 Paper Lab  🔍 Search  ⚙️│
                    └────────────┬────────────────┘
                                 │
                    ┌────────────▼────────────────┐
                    │     Supervisor Agent          │
                    │  intent: paper/search/report  │
                    └────┬───────────┬─────────────┘
                         │           │
              ┌──────────▼──┐   ┌────▼──────────┐
              │ Paper RAG   │   │ Arxiv Search  │
              │ Agent       │   │ Agent         │
              │ (Q&A,요약)  │   │ (키워드 검색) │
              └──────┬──────┘   └──────┬─────────┘
                     │                 │
              ┌──────▼──────────────────▼──────────┐
              │         Report Agent                │
              │    (결과 통합 + Markdown 포맷팅)     │
              └────────────────────────────────────┘
```

## 2. Data Flow

```
사용자 입력 → Supervisor (의도 분류)
    ├─ "paper" → Paper RAG Agent
    │              ├─ FAISS 검색 (관련 chunk)
    │              ├─ LLM 답변 생성 (cited chunk 포함)
    │              └─ Report Agent (포맷팅)
    │
    ├─ "search" → Arxiv Search Agent
    │              ├─ Arxiv API 검색
    │              ├─ 결과 요약
    │              └─ Report Agent (포맷팅)
    │
    └─ "report" → Paper RAG + Arxiv 통합 → Report Agent
```

## 3. Directory Structure

```
research-agent/
├── app.py                     # Streamlit 메인
├── requirements.txt
├── README.md
├── src/
│   ├── ingest.py             # PDF → chunk → FAISS
│   ├── rag_chain.py          # Langchain RAG chain
│   └── agents/
│       ├── supervisor.py     # 의도 분류 Agent
│       ├── paper_agent.py    # 논문 Q&A Agent
│       ├── arxiv_agent.py    # Arxiv 검색 Agent
│       └── report_agent.py   # 결과 통합 Agent
├── data/
│   └── papers/               # 샘플 TCAD+ML 논문 3~5편
├── vectorstore/              # FAISS 인덱스 (gitignore)
└── .omo/
    ├── errors/               # 시행착오 기록 (필수)
    └── plans/                # Plan 역사
```

## 4. Development Timeline

### Day 1 (7/8) — Core RAG Pipeline

| 시간 | 작업 | 산출물 |
|---|---|---|
| 08:30~09:00 | 환경 셋업 (pip install, Ollama 확인) | requirements.txt |
| 09:00~11:00 | **PDF Ingest Pipeline** — PyMuPDF → chunk → BGE-m3 embed → FAISS | `ingest.py`, `vectorstore/` |
| 11:00~12:00 | Ingest 테스트 (샘플 논문 3편) | |
| 12:00~13:00 | 중식 | |
| 13:00~15:00 | **RAG Chain** — Langchain retrieval QA | `rag_chain.py` |
| 15:00~16:00 | **Streamlit 기초 UI** — PDF 업로드 + 질문 + 답변 | `app.py` |
| 16:00~17:00 | 통합 테스트 + 에러 문서화 | `.omo/errors/*.md` |

### Day 2 (7/9) — Multi-Agent

| 시간 | 작업 | 산출물 |
|---|---|---|
| 08:30~10:00 | **Supervisor Agent** — 의도 분류 LLM | `supervisor.py` |
| 10:00~12:00 | **Paper RAG Agent** — RAG chain Agent 래핑 | `paper_agent.py` |
| 12:00~13:00 | 중식 | |
| 13:00~15:00 | **Report Agent** — 결과 통합, Markdown | `report_agent.py` |
| 15:00~17:00 | Agent ↔ Streamlit 연동 + trace 시각화 | `app.py` |
| 16:00~17:00 | 에러 문서화 | `.omo/errors/*.md` |

### Day 3 (7/10) — Arxiv + 최종 완성

| 시간 | 작업 | 산출물 |
|---|---|---|
| 08:30~10:00 | **Arxiv Search Agent** — API 연동 + 요약 | `arxiv_agent.py` |
| 10:00~12:00 | 종단간 통합 테스트 | |
| 12:00~13:00 | 중식 | |
| 13:00~15:00 | **README + 발표자료** | `README.md` |
| 15:00~16:00 | 에러 문서 최종 정리 | `.omo/errors/` |
| 16:00~17:00 | 시연 리허설 | |
| 17:00~17:20 | **최종 평가** | |
| ~23:59 | 제출 (Google Form + Drive) | |

## 5. Error Documentation

**위치**: `.omo/errors/YYY-MM-DD_번호-설명.md`

**템플릿**:
```markdown
# [YYYY-MM-DD] 에러 제목

## 분류
Code Error / Direction Error / Performance / Environment

## 상황
- 의도:
- 발생:
- 원인:

## 실패 기록
[코드/설계]

## 수정 기록  
[수정 코드/설계]

## 차이점 분석

## 재발 방지
```

## 6. 2년 로드맵 (Post-MVP)

| 시기 | 기능 |
|---|---|
| **7/10 (MVP)** | PDF RAG + Multi-Agent + Arxiv Search + Streamlit |
| 8월 | TCAD CSV 업로드 → 텍스트 요약 |
| 10월 | 실험 로그 ↔ 논문 결과 비교 Agent |
| 1월 | 논문 간 인용 연결 그래프 |
| 4월 | Related Work 초안 생성 Agent |
| 7월 | LaTeX + BibTeX 자동 포맷팅 |
| 12월 | 개인 KB 200편 → 졸업논문 지원 |

---

## ✅ Plan Sign-Off

**모든 모호성 해소 완료**:

| 구분 | 상태 |
|---|---|
| 연구 분야 | ✅ 반도체소자 + TCAD + ML |
| MVP 범위 | ✅ 최대 범위 (RAG + Agent + Arxiv) |
| Vector DB | ✅ FAISS |
| Embedding | ✅ BGE-m3 |
| LLM 전략 | ✅ qwen3.5:4b/9b + Zen Free Hybrid |
| 에러 문서화 | ✅ 템플릿 + 경로 확정 |
| 채점자 실행 가능 | ✅ `streamlit run app.py` 1-step |
| 샘플 데이터 | ✅ Arxiv TCAD+ML 논문 |
| 코드 금지 | ✅ Plan 완료 전까지 코드 작성 안 함 |

---

> **이 plan이 최종본입니다. 승인하시면 즉시 코드 구현에 돌입합니다.**
