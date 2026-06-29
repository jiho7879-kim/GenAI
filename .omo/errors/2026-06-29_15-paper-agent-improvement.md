---
title: "Paper Agent RAG 개선 — Phase 0-3 구현 결과"
date: 2026-06-29
category: decision
severity: info
---

## 개요

Paper Agent (RAG Q&A)의 학술 특화 개선 Phase 0-3 구현 완료.
기존 Naive RAG를 Advanced RAG로 업그레이드.

## 변경 범위

| Phase | 변경 사항 | 주요 파일 |
|-------|----------|----------|
| Phase 0 | Semantic Chunking — 학술 섹션 인식 분할 | `src/ingest.py` |
| Phase 1 | Query Rewriter Agent — HyDE + Decomposition + Expansion | `src/agents/query_rewriter.py` |
| Phase 2 | Multi-Strategy Retrieval — Multi-Query + RRF Fusion | `src/rag_chain.py` |
| Phase 3 | Academic Prompt Engineering — 질문 유형별 5종 Prompt | `src/rag_chain.py` |

## Phase 0: Semantic Chunking

**문제**: RecursiveCharacterTextSplitter가 단순 문자수 기준 분할, 섹션 경계 무시

**해결**: 
- `SECTION_PATTERNS` 24개 패턴 (영문 14개 + 한글 10개) 도입
- `_detect_section()`: numbering prefix (2.1, II., A.) stripping 후 regex matching
- `_split_by_sections()`: 섹션 헤더를 chunk boundary로 사용
- 각 chunk에 `section_name` metadata 자동 부여 → 검색 시 특정 섹션 집중 가능

**결정 근거**:
- 섹션 경계가 문단 경계보다 정보 단위로서 더 의미있음
- Section metadata는 Phase 2 Multi-Retrieval의 전제 조건
- BGE-m3 CPU-only 환경에서 chunk_size=768 유지

## Phase 1: Query Rewriter Agent

**문제**: 사용자 질문을 그대로 embedding → noise 포함, 약어 미확장

**해결**:
- `ABBREVIATION_MAP` 30+개 TCAD/반도체 약어
- `_expand_abbreviations()`: regex boundary matching으로 약어 감지 및 확장
- `rewrite_query()`: LLM-based rewriting (HyDE + Decomposition + Keyword Extraction)
- Fallback: `_extract_keywords()` (noise word removal + unique keyword 10개 limit)
- Ollama timeout=15s 실패 시 자동 fallback

**결정 근거**:
- QueryRewiter와 QueryOptimizer 분리: Arxiv search용 vs RAG용은 prompt/전략이 완전히 다름
- Abbreviation expansion은 LLM 없이 regex로 먼저 수행 (속도)
- HyDE snippet은 임베딩 검색에 hypothetical document 제공

## Phase 2: Multi-Strategy Retrieval

**문제**: 단일 similarity search + RetrievalQA chain으로 custom 검색 전략 불가

**해결**:
- `RetrievalQA` → LCEL (`prompt | llm`) + 수동 retrieval pipeline
- `_detect_question_type()`: keyword 기반 질문 유형 분류 (4 types + general)
- `_expand_query_terms()`: 약어 확장 sub-query 생성
- `_generate_sub_queries()`: 질문 유형별 focused query 추가 (최대 5개)
- `_rrf_fusion()`: Reciprocal Rank Fusion (k=60) — 다중 검색 결과 융합
- `retrieve()`: multi-query + RRF fusion 통합
- `query()`: use_enhanced=True/False 지원

**결정 근거**:
- 질문 유형 분류는 keyword 기반 (LLM 무호출) — Phase 1 QueryRewriter가 LLM rewriting 담당
- RRF k=60은 표준 상수
- BM25 hybrid는 CPU 부하 + 의존성 증가로 생략 (multi-query + RRF로 충분히 대체)

## Phase 3: Academic Prompt Engineering

**문제**: 단일 QA prompt로 모든 질문 유형 처리

**해결**: 5종 prompt template
- `PROMPT_METHODOLOGY`: 접근법 개요 → 파라미터 → 절차 → 검증
- `PROMPT_RESULT`: 주요 발견 → 비교 → 의의 (exact numerical value 강제)
- `PROMPT_THEORY`: 정의 → 물리 원리 → TCAD 응용 → 논문 예제
- `PROMPT_COMPARISON`: 비교 대상 → 유사점 → 차이점(table) → Trade-off
- `PROMPT_GENERAL`: 기존 QA template 유지

## 검증 결과

- `ruff check src/ tests/` — All checks passed (0 errors)
- `ruff format --check src/ tests/` — All files formatted
- `pytest tests/ -v` — 104 passed (기존 44 + 신규 60)

## 교안 연계

| 강의 모듈 | 적용 포인트 |
|-----------|-----------|
| Langchain RAG 구축 (3일) | LCEL pipeline, Multi-Query Retriever, RRF Fusion |
| Agentic RAG (3일) | Query Rewriting Agent, Self-Reflection |
| Naive → Advanced RAG | Query Transformation, Routing, Fusion 실제 구현 |
