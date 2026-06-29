# 📚 Research Agent — TCAD + Semiconductor Device Paper Assistant

> Fast Campus Gen AI Intensive Course — Final Project
> 석사 2년 동안 사용할 개인 Research Assistant (반도체소자 + TCAD + ML)

---

## Table of Contents

1. [Overview](#overview)
2. [Tech Stack](#tech-stack)
3. [Architecture](#architecture)
4. [Installation](#installation)
5. [Usage](#usage)
6. [Agent Pipeline](#agent-pipeline)
7. [Project Structure](#project-structure)
8. [Error Documentation Index](#error-documentation-index)
9. [Sample Queries](#sample-queries)
10. [License](#license)

---

## Overview

A **Multi-Agent RAG system** built from scratch as the Final Project for the Fast Campus Gen AI Intensive course. Designed to assist a graduate student researching **semiconductor devices, TCAD simulation, and machine learning methodology** over their 2-year master's program.

### Key Features

| Feature | Description |
|---------|-------------|
| 📤 **PDF Ingestion** | Upload research papers → automatic chunking + BGE-m3 embedding → FAISS index |
| 💬 **RAG Q&A** | Ask questions about your paper library with cited sources |
| 🤖 **Multi-Agent Pipeline** | Supervisor classifies intent → specialist agents handle each task |
| 🔍 **Arxiv Search** | Discover new papers with LLM-generated summaries |
| 📋 **Report Generation** | Combine RAG knowledge + search results into structured reports |
| 🧠 **Agent Trace** | See the AI's real-time thought process in the UI |

### Design Constraints

| Constraint | Decision |
|------------|----------|
| CPU-only (Intel Iris Xe) | BGE-m3 for embedding, qwen3.5:4b for default LLM |
| 사외망 (no API-key services) | Local Ollama only (no OpenAI/Claude API) |
| Free of charge | Ollama + Zen Free (Big Pickle) hybrid |
| Single-command run | FAISS (no separate server) — `streamlit run app.py` |
| 50% project grade | Full MVP: RAG + Multi-Agent + Arxiv Search + Streamlit UI |

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | Streamlit | 1.58.0 |
| RAG Framework | Langchain + Langchain-Classic | 1.3.11 |
| Vector Store | FAISS (CPU) | 1.14.3 |
| Embedding Model | BAAI/bge-m3 (multilingual) | via sentence-transformers 5.6.0 |
| LLM | Ollama (qwen3.5:4b / qwen3.5:9b) | — |
| PDF Parser | PyMuPDF4LLM (layout-aware) | 1.27.2.3 |
| External API | Arxiv | 4.0.0 |

---

## Architecture

```
User Input (Streamlit chat)
    │
    ▼
┌──────────────────────────────────────────────────────┐
│ [Supervisor Agent]                                    │
│ Intent: { paper | search | report }                   │
│ Uses Ollama qwen3.5:4b, temperature=0.0               │
└──────────────────────┬───────────────────────────────┘
                       │
          ┌────────────┼────────────────┐
          ▼            ▼                ▼
   ┌──────────┐ ┌───────────┐ ┌──────────────┐
   │ Paper    │ │ Arxiv     │ │ Report       │
   │ Agent    │ │ Search    │ │ Agent        │
   │ (RAG QA) │ │ Agent     │ │ (Formatting) │
   └────┬─────┘ └─────┬─────┘ └──────┬───────┘
        │             │              │
        ▼             │              │
   ┌──────────┐       │              │
   │ RAGChain │       │              │
   │  ┌─────┐ │       │              │
   │  │FAISS│ │       │              │
   │  │BGE  │ │       │              │
   │  │  m3 │ │       │              │
   │  └─────┘ │       │              │
   │  │Ollama│ │       │              │
   │  └─────┘ │       │              │
   └────┬─────┘       │              │
        └──────┬──────┘              │
               │                     │
               ▼                     │
        ┌──────────────┐             │
        │ Final Answer  │◄────────────┘
        │ + Sources     │
        │ + Agent Trace │
        └──────────────┘
               │
               ▼
        Streamlit UI (3 tabs)
        ┌─────────┬──────┬──────┐
        │Paper Lab│Arxiv │About │
        │ (Q&A)   │Search│      │
        └─────────┴──────┴──────┘
```

---

## Installation

### Prerequisites

- **Python 3.10+** (tested on 3.13.14)
- **Ollama** with models:
  ```bash
  ollama pull qwen3.5:4b    # 3.4 GB — fast, default
  ollama pull qwen3.5:9b    # 6.6 GB — accurate, for complex queries
  ```
- **Windows 11** (also works on macOS/Linux with minor path adjustments)

### Step-by-Step

```bash
# 1. Clone or copy the project
cd research-agent

# 2. (Recommended) Create virtual environment
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. Install dependencies (3–10 min depending on network)
pip install -r requirements.txt

# 4. Verify Ollama is running
ollama list
# Expected: qwen3.5:4b (and optionally qwen3.5:9b)

# 5. Start the app
streamlit run app.py
```

> **Note**: First run will download BGE-m3 model (~2.2 GB) from HuggingFace on first embedding. Subsequent runs use cached model.

### OCR for Scanned PDFs (Optional)

PyMuPDF4LLM automatically detects scanned / image-only PDF pages and runs OCR via **Tesseract** when needed. To enable this:

```bash
# Windows (requires admin or scoop)
scoop install tesseract tesseract-languages

# macOS
brew install tesseract tesseract-lang

# Linux
sudo apt install tesseract-ocr tesseract-ocr-eng
```

OCR is triggered automatically for pages with illegible text. To force OCR on every page:

```python
import pymupdf4llm
md = pymupdf4llm.to_markdown("scanned.pdf", force_ocr=True)
```

> **Note**: OCR is **not needed** for most born-digital academic PDFs. It is 1000× slower than native extraction and only activates when the text layer is corrupt or missing (images only).

---

## Usage

### Tab 1: 📚 Paper Lab

1. **Upload a PDF** — Click "Browse files" and select a TCAD/semiconductor paper
2. **Wait for ingestion** — Progress bar shows chunking → embedding → indexing
3. **Ask questions** — Type your query in the chat input
4. **View Agent Trace** — Right panel shows real-time agent thought process
5. **Read Sources** — Expand "📚 Sources" to see which chunks were used

### Tab 2: 🔍 Arxiv Search

1. **Enter search query** — e.g., "TCAD machine learning GAA FET"
2. **Browse results** — Each paper includes title, authors, abstract, and LLM summary
3. **Combine with RAG** — Search results can be merged with existing paper knowledge

### Tab 3: ℹ️ About

- System status (vector store, model, ingested files)
- Architecture documentation
- Environment information

### Settings (Sidebar)

| Setting | Options | Description |
|---------|---------|-------------|
| LLM Model | `qwen3.5:4b` (fast) / `qwen3.5:9b` (accurate) | Switch between speed and quality |
| Reload Vector Store | Button | Re-read FAISS index from disk |
| Clear Chat | Button | Reset conversation history |

---

## Agent Pipeline

### Supervisor Agent (`src/agents/supervisor.py`)

Classifies user intent using Ollama (temperature=0.0, 64 tokens max):

| Intent | Trigger phrases | Routed to |
|--------|----------------|-----------|
| `paper` | "What does this paper say about...", "Summarize...", "Explain..." | Paper Agent (RAG) |
| `search` | "Find papers about...", "Search for...", "Look up..." | Arxiv Search Agent |
| `report` | "Write a report...", "Create a literature review..." | Paper + Report Agent |

### Paper Agent (`src/agents/paper_agent.py`)

- Wraps `RAGChain` which retrieves from FAISS and generates with Ollama
- Returns answer + formatted source citations (source, page number, content preview)
- Deduplicates sources by content hash

### Arxiv Search Agent (`src/agents/arxiv_agent.py`)

- Searches Arxiv API (no API key required)
- Caches results for 1 hour to avoid redundant API calls
- Generates 1-2 sentence LLM summaries of each paper
- Supports detail fetch by Arxiv ID

### Report Agent (`src/agents/report_agent.py`)

- Formats Q&A answers + sources as Markdown
- Combines RAG + Arxiv search into comprehensive reports
- Optional LLM enhancement for polishing output

### RAGChain (`src/rag_chain.py`)

- `RetrievalQA` with `chain_type="stuff"` (all retrieved chunks in one prompt)
- Two prompt templates: QA (technical answer) and Summarize (structured summary)
- Support for model switching at runtime

### Ingest Pipeline (`src/ingest.py`)

```
PDF → pymupdf4llm (layout-aware markdown) → Section-aware Splitter → BGE-m3 → FAISS
```

- **Layout-aware extraction**: Multi-column reading order, table detection, header/footer stripping
- **Table metadata**: Each chunk includes `table_count` and `has_tables` metadata
- **Section-aware chunking**: Academic section headers (Introduction, Methodology, Results, etc.) detected as natural chunk boundaries
- Chunk size: 768 characters, overlap: 50 characters
- Embedding: BAAI/bge-m3 (multilingual, CPU-optimized)
- Merge: New documents are merged into existing index
- **OCR**: Automatic fallback for scanned/image PDFs (requires Tesseract)

---

## Project Structure

```
research-agent/
│
├── app.py                     # Streamlit entry point (3 tabs)
├── requirements.txt           # Python dependencies
├── README.md                  # This file
│
├── src/
│   ├── __init__.py
│   ├── ingest.py              # PDF → chunk → BGE-m3 → FAISS
│   ├── rag_chain.py           # Langchain RetrievalQA with Ollama
│   │
│   └── agents/
│       ├── __init__.py
│       ├── supervisor.py      # Intent classifier Agent
│       ├── paper_agent.py     # Paper Q&A Agent (RAG wrapper)
│       ├── arxiv_agent.py     # Arxiv search Agent
│       └── report_agent.py    # Result formatting Agent
│
├── data/
│   └── papers/                # Uploaded PDFs (runtime)
│
├── vectorstore/               # FAISS index (runtime generated, gitignored)
│   ├── index.faiss
│   └── index.pkl
│
└── .omo/
    ├── errors/                # Trial & error documentation (8 files)
    │   ├── 2026-06-29_01-pdf-text-extract-failed.md
    │   ├── 2026-06-29_02-look-at-timeout.md
    │   ├── 2026-06-29_03-powershell-vs-bash.md
    │   ├── 2026-06-29_04-planning-decisions.md
    │   ├── 2026-06-29_05-architectural-decisions.md
    │   ├── 2026-06-29_06-pip-install-timeout.md
    │   ├── 2026-06-29_07-langchain-module-migration.md
    │   └── 2026-06-29_08-integration-test-results.md
    │
    └── plans/
        └── research-agent-plan-v3-final.md

```

---

## Error Documentation Index

All trial-and-error (code errors + design decisions) are systematically documented in `.omo/errors/` for inclusion in the final report.

| # | File | Category | Key Lesson |
|---|------|----------|------------|
| 01 | `01-pdf-text-extract-failed.md` | code-error | PDF에 이미지로 된 텍스트는 PyMuPDF로 추출 불가 → OCR 필요 |
| 02 | `02-look-at-timeout.md` | code-error | 대용량 PDF(150p) look_at 타임아웃 → 페이지 단위 분할 |
| 03 | `03-powershell-vs-bash.md` | code-error | `&&` → `; if ($?) { }` Windows PowerShell 호환 문제 |
| 04 | `04-planning-decisions.md` | **decision** | v1→v2→v3 계획 진화, Q1~Q5 기술 선택 근거 |
| 05 | `05-architectural-decisions.md` | **decision** | FAISS vs Chroma, Langchain vs 직접구현, BGE-m3 선택 이유 |
| 06 | `06-pip-install-timeout.md` | code-error | pip install 5분 타임아웃 → 10분으로 증가 |
| 07 | `07-langchain-module-migration.md` | code-error | `langchain.chains` → `langchain_classic.chains` migration |
| 08 | `08-integration-test-results.md` | test-result | Import 체인 검증 + Ollama 미설치 환경 이슈 |

---

## Sample Queries

**Paper Q&A (after uploading TCAD papers):**
- "What does this paper say about TCAD calibration methodology?"
- "Explain the GAA FET structure described in the paper"
- "Summarize the key findings on machine learning for TCAD"
- "Compare the approaches in papers 1 and 3"

**Arxiv Search:**
- "Search for GAA FET simulation papers on Arxiv"
- "Find recent papers on TCAD machine learning"
- "Look up papers about semiconductor device modeling"

**Report Generation:**
- "Write a report comparing ML methods in TCAD from my papers"
- "Create a literature review draft on TCAD calibration"
- "Generate a comprehensive report on my paper collection"

---

## Performance Notes

- **CPU-only**: Vector dimension is 1024 (BGE-m3). top_k=5 recommended for latency.
- **Chunk size 512**: Optimized for CPU memory — larger chunks cause OOM on Iris Xe.
- **First embedding is slow**: BGE-m3 model download + first inference takes 1-3 minutes.
- **Subsequent queries**: Cached embedding model, only PDF parsing and LLM inference needed.

---

## License

This project is created for educational purposes as part of the Fast Campus Gen AI Intensive Course.
