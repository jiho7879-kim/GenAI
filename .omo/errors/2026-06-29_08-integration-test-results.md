---
title: "종단간 통합 테스트 결과 — Import 체인 검증 완료"
date: 2026-06-29
category: test-result
severity: info
---

## 테스트 환경

- OS: Windows 11 (win32)
- Python: 3.13.14 (MSC v.1944 64 bit AMD64)
- CPU: Intel Iris Xe (iGPU only)
- RAM: 32GB
- Ollama: Not running in test env (user local에서 실행)
- 인터넷: 사외망 (테스트 환경에서 차단됨)

## 설치된 패키지 (검증 완료)

| 패키지 | 버전 | 상태 |
|--------|------|------|
| streamlit | 1.58.0 | ✅ |
| langchain | 1.3.11 | ✅ |
| langchain-classic | 1.0.8 | ✅ (RetrievalQA) |
| langchain-community | 0.4.2 | ✅ |
| langchain-ollama | 1.1.0 | ✅ |
| langchain-text-splitters | 1.1.2 | ✅ |
| langchain-core | 1.4.8 | ✅ |
| faiss-cpu | 1.14.3 | ✅ |
| sentence-transformers | 5.6.0 | ✅ |
| PyMuPDF | 1.27.2.3 | ✅ |
| arxiv | 4.0.0 | ✅ |
| torch | 2.12.1 | ✅ (CPU) |
| transformers | 5.12.1 | ✅ |
| python-dotenv | 1.2.2 | ✅ |
| tqdm | 4.68.3 | ✅ |

## Import 체인 검증 결과

```
src/ingest.py           ✅  (PyMuPDFLoader, FAISS, HuggingFaceEmbeddings, RecursiveCharacterTextSplitter)
src/rag_chain.py        ✅  (Ollama, RetrievalQA, PromptTemplate)
src/agents/supervisor.py   ✅  (Ollama)
src/agents/paper_agent.py  ✅  (RAGChain wrapping)
src/agents/arxiv_agent.py  ✅  (arxiv API, Ollama)
src/agents/report_agent.py ✅  (Ollama, Markdown formatting)
```

## 발견된 이슈 및 수정

### Issue #1: Langchain 모듈 경로 변경
- **증상**: `langchain.chains` → `ModuleNotFoundError`
- **원인**: langchain 1.3.11에서 `chains`와 `text_splitter`가 standalone 패키지로 분리
- **수정**: 
  - `langchain.text_splitter` → `langchain_text_splitters` (ingest.py)
  - `langchain.chains` → `langchain_classic.chains` (rag_chain.py)
  - `requirements.txt`에 `langchain-classic`, `langchain-text-splitters`, `langchain-core` 추가

### Issue #2: pip install 타임아웃
- **증상**: 5분 제한 초과
- **원인**: torch (2GB+) + transformers + sentence-transformers 대용량 패키지 설치 시간
- **수정**: 타임아웃 10분(600초)으로 증가

## 실행 불가 항목 (Ollama 미설치 환경)

- `RAGChain.query()`: Ollama LLM invoke 필요 → user 환경에서 검증 필요
- `SupervisorAgent.classify()`: Ollama LLM invoke 필요
- `ArxivSearchAgent.search()`: Arxiv API 필요 (사외망 차단)
- `streamlit run app.py`: Streamlit UI 전체 → user 환경에서 실행

## User 환경에서 검증 필요 항목

1. Ollama 설치 확인: `ollama pull qwen3.5:4b` + `ollama pull qwen3.5:9b`
2. `pip install -r requirements.txt` 실행 (예상 소요: 3~10분)
3. 샘플 TCAD 논문 1편 `data/papers/`에 저장
4. `streamlit run app.py` 실행
5. PDF 업로드 → ingest → Q&A → Agent trace 확인
6. Arxiv Search 탭에서 검색 테스트
