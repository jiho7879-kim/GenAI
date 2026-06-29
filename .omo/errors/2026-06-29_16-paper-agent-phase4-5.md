---
title: "Paper Agent RAG 개선 — Phase 4-5 구현 결과"
date: 2026-06-29
category: decision
severity: info
---

## 개요

Paper Agent 고도화 Phase 4 (Self-Reflection) 및 Phase 5 (Analyst Pipeline) 구현.
Agentic RAG 패턴을 CPU-only 환경에 최적화하여 적용.

## 변경 범위

| Phase | 변경 사항 | 주요 파일 |
|-------|----------|----------|
| Phase 4 | Answer Verification — claim grounding 검증 | `src/agents/paper_agent.py` |
| Phase 5 | Analyst Pipeline — multi-step 분석 워크플로 | `src/agents/analyst_agent.py` |

## Phase 4: Answer Verification (Self-Reflection)

**문제**: RAG 답변의 각 claim이 실제 context에 grounding되어 있는지 검증 불가

**해결**:
- `CLAIM_CHECK_PROMPT`: fact-checker prompt (answer + context → claim별 YES/PARTIAL/NO 분류)
- `PaperAgent.verify_answer()`: 생성된 답변을 context 대조 검증
- `_parse_verification()`: LLM JSON 출력 파싱 (markdown fence tolerant)

**경량화 전략** (CPU-only):
- Full Self-RAG (2-pass) 대신 1-pass verification
- LLM 호출 1회로 claim 분류 + correction 생성
- 검증 실패 시에도 답변은 유지, `verification.summary`로 사용자에게 투명하게 공개

**출력 구조**:
```python
{
    "verified": True/False,
    "claims": [
        {"claim": "...", "status": "YES|PARTIAL|NO", "correction": "..."},
    ],
    "summary": "✅ All 3 claims supported by context."
}
```

## Phase 5: Analyst Agent Pipeline

**문제**: 복잡한 분석 질문(비교/대조/종합)을 단일 QA로 처리 불가

**해결**: `AnalystAgent` — sequential 4-step pipeline

```
User: "Compare TCAD calibration methods across papers"
    │
    ├── Step 1: RETRIEVE — Multi-query + RRF fusion
    │   └── 관련 chunk 수집
    │
    ├── Step 2: READ — 논문별 focused sub-query
    │   └── 각 파일별로 집중 질문 → 개별 분석
    │
    ├── Step 3: COMPARE (comparison 질문만)
    │   └── Cross-paper comparison prompt + table
    │
    ├── Step 4: VERIFY — Answer grounding 검증
    │   └── Phase 4 verify_answer() 활용
    │
    └── Output: 종합 보고서 + trace log
```

**결정 근거**:
- Langgraph 대신 sequential pipeline: CPU-only에서 병렬 LLM 호출 부담 회피
- 기존 PaperAgent + RAGChain + ReportAgent 재사용
- Trace log으로 각 step 수행 내역 기록 (발표자료 + 디버깅 용이)
- Comparison 질문만 Step 3 활성화 (질문 유형 감지)

## 교안 연계

| 강의 모듈 | 적용 포인트 |
|-----------|-----------|
| Agentic RAG (Self-RAG) | Reflection pattern을 경량 1-pass로 구현 |
| Multi-Agent Pipeline | Retriever→Reader→Comparator→Verifier→Report |
| Tool-based Agent | 기존 Agent를 pipeline step으로 orchestration |

## 추후 개선 사항

- PDF page image table/chart OCR (PyMuDraw + PaddleOCR)
- Citation graph (reference chain 추적)
- Async verification (UI streaming)
- Phase 4 verification 결과를 바탕으로 답변 자동 보강 (2-pass)
