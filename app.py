"""
Research Agent — Streamlit Frontend

A research assistant for semiconductor device + TCAD + ML paper management.
Supports PDF ingestion, RAG Q&A, Arxiv search, and Multi-Agent orchestration.

Usage:
    streamlit run app.py
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

import streamlit as st

# ---------- Configuration (before imports) ----------

PROJECT_ROOT = os.path.dirname(__file__)
DEFAULT_STORE_DIR = os.path.join(PROJECT_ROOT, "vectorstore")
SAMPLE_PAPER_DIR = os.path.join(PROJECT_ROOT, "data", "papers")
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Logging: write to both file and console
_log_file = os.path.join(LOG_DIR, "app.log")
_file_handler = RotatingFileHandler(
    _log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setLevel(logging.INFO)
_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setLevel(logging.INFO)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[_file_handler, _console_handler],
)
logger = logging.getLogger(__name__)

# Log startup
logger.info("=" * 60)
logger.info("Research Agent starting...")
logger.info(f"Log file: {_log_file}")

# Add project root to path
sys.path.insert(0, PROJECT_ROOT)

import urllib.request

from src.agents.supervisor import SupervisorAgent
from src.ingest import (
    get_ingested_files,
    get_store_info,
    ingest_pdf,
    load_ingest_metadata,
    reset_vectorstore,
)
from src.rag_chain import MODEL_ACCURATE, MODEL_FAST

# Check Ollama availability at startup
_ollama_ok, _ollama_msg = SupervisorAgent.check_ollama()
if not _ollama_ok:
    logger.warning(_ollama_msg)
else:
    logger.info("Ollama server is running")
from src.agents.arxiv_agent import ArxivSearchAgent
from src.agents.paper_agent import PaperAgent
from src.agents.query_optimizer import optimize_query
from src.agents.report_agent import ReportAgent

# ---------- Arxiv Download Helper ----------


def download_and_ingest_arxiv_paper(arxiv_id: str, title: str) -> str | None:
    """
    Download an Arxiv paper PDF and ingest it into the vector store.

    Args:
        arxiv_id: The Arxiv paper ID (e.g., "2401.12345").
        title: Paper title (used for filename).

    Returns:
        Status message string, or None on success.
    """
    import re

    from src.ingest import ingest_pdf

    # Sanitize title for filename
    safe_title = re.sub(r"[^\w\- ]", "", title)[:60].strip()
    filename = f"arxiv_{arxiv_id}_{safe_title}.pdf"
    save_path = os.path.join(SAMPLE_PAPER_DIR, filename)

    # Skip if already downloaded
    if os.path.exists(save_path):
        logger.info("Paper already downloaded: %s", filename)
    else:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        try:
            urllib.request.urlretrieve(pdf_url, save_path)
            logger.info("Downloaded: %s → %s", pdf_url, filename)
        except Exception as exc:
            logger.error("Failed to download %s: %s", pdf_url, exc)
            return f"❌ Download failed: {exc}"

    try:
        store = ingest_pdf(
            file_path=save_path,
            store_dir=st.session_state.vectorstore_dir,
        )
        if filename not in st.session_state.ingested_files:
            st.session_state.ingested_files.append(filename)
        st.session_state.rag_ready = True
        paper_agent.load_vectorstore(st.session_state.vectorstore_dir)
        logger.info("Ingested: %s (%d vectors)", filename, store.index.ntotal)
        return None
    except Exception as exc:
        logger.error("Ingest failed for %s: %s", filename, exc)
        return f"❌ Ingest failed: {exc}"


# ---------- Page Config ----------

st.set_page_config(
    page_title="Research Agent — TCAD Paper Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Session State Initialization ----------


def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        "messages": [],
        "vectorstore_dir": DEFAULT_STORE_DIR,
        "current_model": MODEL_FAST,
        "rag_ready": False,
        "ingested_files": [],
        "agent_trace": [],
        "arxiv_results_cache": [],
        "uploader_key": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()

# ---------- Agent Initialization (cached) ----------


@st.cache_resource
def init_agents():
    """Initialize all agents (cached to avoid reload on rerun)."""
    supervisor = SupervisorAgent()
    paper_agent = PaperAgent(
        vectorstore_dir=DEFAULT_STORE_DIR,
        model_name=MODEL_FAST,
        top_k=5,
    )
    arxiv_agent = ArxivSearchAgent(max_results=5)
    report_agent = ReportAgent()
    return supervisor, paper_agent, arxiv_agent, report_agent


supervisor, paper_agent, arxiv_agent, report_agent = init_agents()

# ---------- Sidebar ----------

with st.sidebar:
    st.title("📚 Research Agent")
    st.caption("TCAD + Semiconductor Device Paper Assistant")

    st.divider()

    # Vector Store Status
    st.subheader("🗄️ Vector Store")
    store_info = get_store_info(st.session_state.vectorstore_dir)
    if store_info["exists"]:
        st.success(f"✅ Loaded ({store_info['vector_count']} vectors)")
        st.caption(f"Model: {store_info['embedding_model'].split('/')[-1]}")
        st.session_state.rag_ready = True
        paper_agent.load_vectorstore(st.session_state.vectorstore_dir)

        # Load persistent ingest metadata into session state
        if not st.session_state.ingested_files:
            st.session_state.ingested_files = get_ingested_files(st.session_state.vectorstore_dir)
    else:
        st.warning("⚠️ No vector store found. Upload a PDF to get started.")
        st.session_state.rag_ready = False

    # LLM Status
    st.subheader("🤖 LLM (Ollama)")
    if _ollama_ok:
        st.success(f"✅ {st.session_state.current_model}")
    else:
        st.error("❌ Ollama not running")
        st.caption("Run: `ollama serve` in terminal")

    st.divider()

    # Ingested Files (from persistent metadata)
    st.subheader("📄 Papers")
    ingest_meta = load_ingest_metadata(st.session_state.vectorstore_dir)
    paper_files = ingest_meta.get("files", {})

    if paper_files:
        for fname, info in paper_files.items():
            pages = info.get("pages", "?")
            chunks = info.get("chunks", "?")
            st.caption(f"📄 {fname}  · {pages}p · {chunks} chunks")
    elif st.session_state.ingested_files:
        # Fallback: show from session state (before metadata was introduced)
        for fname in st.session_state.ingested_files:
            st.caption(f"📄 {fname}")
    elif store_info["exists"] and store_info["vector_count"] > 0:
        # Migration: FAISS exists but no metadata file yet
        st.caption(f"📚 {store_info['vector_count']} vectors available (previously ingested)")
    else:
        st.caption("No papers ingested yet.")

    st.divider()

    # Settings
    st.subheader("⚙️ Settings")
    model_choice = st.selectbox(
        "LLM Model",
        options=[MODEL_FAST, MODEL_ACCURATE],
        index=0,
        help="qwen3.5:4b = faster, qwen3.5:9b = more accurate but slower",
    )
    if model_choice != st.session_state.current_model:
        st.session_state.current_model = model_choice
        paper_agent.switch_model(model_choice)
        st.rerun()

    # Quick actions
    st.divider()
    st.subheader("🔧 Actions")
    if st.button("🔄 Reload Vector Store", use_container_width=True):
        paper_agent.load_vectorstore(st.session_state.vectorstore_dir)
        store_info = get_store_info(st.session_state.vectorstore_dir)
        if store_info["exists"]:
            st.session_state.rag_ready = True
            st.success("Reloaded!")
        else:
            st.session_state.rag_ready = False
            st.warning("No store found")
        st.rerun()

    if st.button("🧹 Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.agent_trace = []
        st.rerun()

    st.divider()

    reset_key = "_confirm_reset"
    if st.session_state.get(reset_key):
        st.warning("⚠️ 모든 임베딩과 메타데이터가 영구 삭제됩니다. PDF 파일은 유지됩니다.")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("✅ Confirm Reset", type="primary", use_container_width=True):
                try:
                    reset_vectorstore(st.session_state.vectorstore_dir, confirm=True)
                    st.session_state.rag_ready = False
                    st.session_state.ingested_files = []
                    st.session_state[reset_key] = False
                    st.success("Reset complete!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Reset failed: {e}")
        with col_b:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state[reset_key] = False
                st.rerun()
    else:
        if st.button("🗑️ Reset Vector Store", type="secondary", use_container_width=True):
            st.session_state[reset_key] = True
            st.rerun()

# ---------- Main Tabs ----------

tab1, tab2, tab3 = st.tabs(["📚 Paper Lab", "🔍 Arxiv Search", "ℹ️ About"])

# ============================================================
# TAB 1: Paper Lab — PDF Upload + Q&A
# ============================================================

with tab1:
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("📤 Upload & Ingest PDF")

        # PDF Upload (key incremented after each successful ingest to prevent infinite rerun loop)
        uploaded_file = st.file_uploader(
            "Upload a research paper (PDF)",
            type=["pdf"],
            key=f"pdf_upload_{st.session_state.uploader_key}",
            help="Upload TCAD/semiconductor device papers to build your knowledge base.",
        )

        if uploaded_file is not None:
            # Save uploaded file
            os.makedirs(SAMPLE_PAPER_DIR, exist_ok=True)
            save_path = os.path.join(SAMPLE_PAPER_DIR, uploaded_file.name)
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # Ingest (with progress bar)
            try:
                progress_bar = st.progress(0, text="Starting...")
                status_text = st.empty()

                def on_progress(msg: str, pct: int):
                    status_text.caption(msg)
                    progress_bar.progress(pct / 100, text=msg)

                store = ingest_pdf(
                    file_path=save_path,
                    store_dir=st.session_state.vectorstore_dir,
                    progress_callback=on_progress,
                )
                progress_bar.empty()
                status_text.empty()

                # Update state
                if uploaded_file.name not in st.session_state.ingested_files:
                    st.session_state.ingested_files.append(uploaded_file.name)
                st.session_state.rag_ready = True
                paper_agent.load_vectorstore(st.session_state.vectorstore_dir)

                # Record trace
                st.session_state.agent_trace.append(
                    {
                        "agent": "Ingest Pipeline",
                        "action": f"Ingested {uploaded_file.name}",
                        "result": f"{store.index.ntotal} vectors created",
                    }
                )

                st.success(f"✅ {uploaded_file.name} ingested successfully!")
                st.caption(f"Vector store now contains {store.index.ntotal} vectors")

                # Increment key to reset the file_uploader widget → prevents infinite rerun loop
                st.session_state.uploader_key += 1
                st.rerun()
            except Exception as e:
                st.error(f"❌ Ingestion failed: {str(e)}")
                logger.error(f"Ingest failed: {e}", exc_info=True)

        st.divider()

        # Chat Interface
        st.subheader("💬 Ask about your papers")

        # Display chat history
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if "sources" in msg and msg["sources"]:
                    with st.expander("📚 Sources", expanded=False):
                        st.markdown(msg["sources"])

        # Chat input
        if prompt := st.chat_input(
            "Ask about TCAD, device physics, or ML methods...",
            disabled=not st.session_state.rag_ready,
        ):
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Process with Agent pipeline
            with st.chat_message("assistant"):
                with st.status("🤖 Agent thinking...", expanded=True) as status:
                    try:
                        # Step 1: Classify intent
                        status.write("🔍 Step 1/3: Classifying intent...")
                        intent, cleaned_query = supervisor.route(prompt)
                        st.session_state.agent_trace.append(
                            {
                                "agent": "Supervisor",
                                "action": f"Classified intent: {intent}",
                                "result": cleaned_query[:100],
                            }
                        )

                        if intent == "paper":
                            # Step 2: RAG Query
                            status.write("📖 Step 2/3: Searching papers...")
                            result = paper_agent.ask(cleaned_query)
                            st.session_state.agent_trace.append(
                                {
                                    "agent": "Paper RAG Agent",
                                    "action": "Retrieved chunks and generated answer",
                                    "result": f"Found {len(result.get('source_docs', []))} relevant chunks",
                                }
                            )

                            # Step 3: Format Report
                            status.write("📝 Step 3/3: Formatting response...")
                            final_answer = report_agent.format_answer(
                                result["answer"], result["sources"]
                            )
                            st.session_state.agent_trace.append(
                                {
                                    "agent": "Report Agent",
                                    "action": "Formatted final response",
                                    "result": "Markdown formatting complete",
                                }
                            )

                        elif intent == "search":
                            # Route to Arxiv search
                            status.write("🔍 Step 2/3: Searching Arxiv...")
                            papers = arxiv_agent.search(
                                cleaned_query,
                                summarize=True,
                                model=st.session_state.current_model,
                            )
                            st.session_state.agent_trace.append(
                                {
                                    "agent": "Arxiv Search Agent",
                                    "action": f"Searched for: '{cleaned_query}'",
                                    "result": f"Found {len(papers)} papers",
                                }
                            )

                            # Optionally rerank if vector store is available
                            if st.session_state.rag_ready and papers and "error" not in papers[0]:
                                status.write("📊 Reranking by relevance to your library...")
                                papers = arxiv_agent.rerank(
                                    papers,
                                    vectorstore=paper_agent.rag.vectorstore,
                                    top_k=5,
                                )
                                status.write("📚 Step 3/3: Combining with existing knowledge...")
                                rag_result = paper_agent.ask(
                                    f"What do my existing papers say about: {cleaned_query}"
                                )
                                final_answer = report_agent.format_report(
                                    user_query=cleaned_query,
                                    rag_answer=rag_result["answer"],
                                    search_results=papers,
                                )
                                st.session_state.agent_trace.append(
                                    {
                                        "agent": "Report Agent",
                                        "action": "Combined RAG + Arxiv results",
                                        "result": "Comprehensive report generated",
                                    }
                                )
                            else:
                                # Just format search results
                                final_answer = report_agent.format_search_results(papers)

                        elif intent == "report":
                            status.write("📋 Step 2/3: Gathering information...")
                            rag_result = paper_agent.ask(cleaned_query)

                            status.write("📝 Step 3/3: Writing report...")
                            final_answer = report_agent.format_report(
                                user_query=cleaned_query,
                                rag_answer=rag_result["answer"],
                            )

                        else:
                            if not _ollama_ok:
                                final_answer = (
                                    "## ⚠️ Ollama 서버에 연결할 수 없습니다\n\n"
                                    "Research Agent는 로컬 LLM(Ollama)을 사용합니다. "
                                    "Ollama가 실행 중인지 확인해주세요.\n\n"
                                    "```powershell\n"
                                    "# 터미널에서 실행:\n"
                                    "ollama serve\n"
                                    "```\n\n"
                                    "Ollama가 실행 중이면 브라우저를 새로고침(F5) 해주세요."
                                )
                            else:
                                final_answer = (
                                    "I can help with:\n"
                                    "1. **PDF Q&A** — Upload papers and ask questions\n"
                                    "2. **Arxiv Search** — Find new papers\n"
                                    "3. **Report Writing** — Generate comprehensive reports\n\n"
                                    "Try a more specific request!"
                                )

                        status.update(label="✅ Done!", state="complete")

                    except Exception as e:
                        final_answer = f"❌ Error: {str(e)}"
                        logger.error(f"Agent pipeline failed: {e}", exc_info=True)
                        status.update(label="❌ Failed", state="error")

                # Display the final answer
                st.markdown(final_answer)

            # Save assistant message
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": final_answer,
                }
            )

    # Right column: Agent Trace
    with col_right:
        st.subheader("🤖 Agent Trace")

        with st.expander("📋 Agent Activity Log", expanded=True):
            if st.session_state.agent_trace:
                for i, trace in enumerate(reversed(st.session_state.agent_trace[-10:])):
                    st.markdown(f"**{trace['agent']}**")
                    st.caption(f"_{trace['action']}_")
                    if trace.get("result"):
                        st.caption(f"→ {trace['result']}")
                    if i < len(st.session_state.agent_trace[-10:]) - 1:
                        st.divider()
            else:
                st.caption("No agent activity yet. Start asking questions!")

        # About the agents
        with st.expander("🧠 Agent Architecture", expanded=False):
            st.markdown("""
            ```
            User Input
                ↓
            [Supervisor Agent] — intent classification
                ↓
            ┌──────┬──────┬──────────┐
            │Paper │Arxiv │ Report   │
            │RAG   │Search│ Agent    │
            │Agent │Agent │(format)  │
            └──────┴──────┴──────────┘
                ↓
            [Streamlit UI]
            ```
            """)

# ============================================================
# TAB 2: Arxiv Search
# ============================================================

with tab2:
    st.subheader("🔍 Arxiv Search")
    st.caption("Search for the latest papers on TCAD, semiconductor devices, and ML.")

    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input(
            "Search query",
            placeholder="e.g., TCAD machine learning GAA FET",
            label_visibility="collapsed",
        )
    with col2:
        max_results = st.number_input("Max results", min_value=1, max_value=20, value=5)

    # Search options
    opt_col1, opt_col2, _ = st.columns([1, 1, 2])
    with opt_col1:
        enable_summarize = st.checkbox(
            "✨ LLM summaries",
            value=False,
            help="Generate 1-2 sentence LLM summaries for each paper",
        )
    with opt_col2:
        enable_rerank = st.checkbox(
            "📊 Rerank by relevance",
            value=False,
            disabled=not st.session_state.rag_ready,
            help="Re-sort results by similarity to your paper library (requires ingested papers)",
        )

    if search_query:
        # Optimize the query via LLM (shows Before → After transformation)
        optimized = optimize_query(search_query)

        # Show optimal query info
        if not optimized.is_fallback:
            with st.expander("🔧 Query optimization", expanded=False):
                st.markdown(
                    f"**Before:** `{optimized.original}`  \n"
                    f"**After:** `{optimized.final_query}`  \n"
                    f"**Language:** {'🇰🇷 Korean (translated)' if optimized.language == 'ko' else '🇺🇸 English'}"
                )
                if optimized.categories:
                    cat_tags = " ".join(
                        f"<span style='background:#e0e7ff; padding:2px 8px; border-radius:10px; "
                        f"font-size:0.8em; margin:2px;'>{c}</span>"
                        for c in optimized.categories
                    )
                    st.markdown(f"**Categories:** {cat_tags}", unsafe_allow_html=True)

        search_kwargs = {"max_results": int(max_results), "summarize": enable_summarize}
        if enable_summarize:
            search_kwargs["model"] = st.session_state.current_model

        with st.spinner("Searching Arxiv..."):
            papers = arxiv_agent.search(optimized.final_query, **search_kwargs)
            st.session_state.arxiv_results_cache = papers

        if papers and "error" not in papers[0]:
            # Optional reranking
            if enable_rerank and st.session_state.rag_ready and papers:
                with st.spinner("Reranking by relevance to your library..."):
                    papers = arxiv_agent.rerank(
                        papers,
                        vectorstore=paper_agent.rag.vectorstore,
                        top_k=int(max_results),
                    )
                    st.session_state.arxiv_results_cache = papers

            st.success(f"Found {len(papers)} papers")
            for i, paper in enumerate(papers):
                sim = paper.get("similarity")
                sim_badge = ""
                if sim is not None:
                    pct = sim * 100
                    if pct >= 80:
                        sim_badge = f"🟢 **{pct:.0f}%** match"
                    elif pct >= 50:
                        sim_badge = f"🟡 **{pct:.0f}%** match"
                    elif pct > 0:
                        sim_badge = f"🔴 **{pct:.0f}%** match"

                # Summary type badge
                summary_type = ""
                summary_val = paper.get("summary", "")
                if summary_val and len(summary_val) > 50 and not summary_val.endswith("..."):
                    summary_type = "✨ LLM"

                with st.container():
                    cols = st.columns([5, 1])
                    with cols[0]:
                        st.markdown(f"**{i + 1}. {paper.get('title', 'Untitled')}**")
                        meta_parts = []
                        if paper.get("authors"):
                            meta_parts.append(paper["authors"])
                        if paper.get("published"):
                            meta_parts.append(paper["published"])
                        if summary_type:
                            meta_parts.append(summary_type)
                        if meta_parts:
                            st.caption(" · ".join(meta_parts))
                        if sim_badge:
                            st.caption(sim_badge)
                    with cols[1]:
                        arxiv_id = paper.get("arxiv_id", "")
                        if arxiv_id:
                            st.markdown(f"[📄 PDF](https://arxiv.org/pdf/{arxiv_id}.pdf)")
                            ingest_key = f"ingest_btn_{arxiv_id}"
                            if st.button("📥 Ingest", key=ingest_key, use_container_width=True):
                                with st.spinner(f"Downloading & ingesting {arxiv_id}..."):
                                    err = download_and_ingest_arxiv_paper(
                                        arxiv_id, paper.get("title", "")
                                    )
                                if err:
                                    st.error(err)
                                else:
                                    st.success("✅ Paper ingested! Reloading...")
                                    st.rerun()

                    # Summary
                    summary = summary_val or paper.get("abstract", "")
                    if summary:
                        st.caption(summary[:200] + ("..." if len(summary) > 200 else ""))

                    # Expandable abstract
                    abstract = paper.get("abstract", "")
                    if abstract and abstract != summary:
                        with st.expander("📄 Full abstract", expanded=False):
                            st.text(abstract)

                    st.divider()

        elif papers and "error" in papers[0]:
            st.error(papers[0]["error"])
        else:
            st.warning("No papers found.")

# ============================================================
# TAB 3: About
# ============================================================

with tab3:
    st.subheader("ℹ️ About Research Agent")

    st.markdown("""
    ### Purpose
    A research assistant designed for **semiconductor device + TCAD + ML** researchers.
    Helps manage and query a personal paper library, search for new publications,
    and generate structured reports.

    ### Tech Stack
    | Component | Technology |
    |---|---|
    | Frontend | Streamlit |
    | RAG | Langchain + FAISS |
    | Embedding | BAAI/bge-m3 (multilingual) |
    | LLM | Ollama (qwen3.5:4b / qwen3.5:9b) |
    | Agent | Langgraph-style Supervisor → Specialists |
    | PDF | PyMuPDF |

    ### Architecture
    ```
    User → Supervisor Agent (intent classification)
        → Paper RAG Agent (PDF Q&A, summarization)
        → Arxiv Search Agent (new paper discovery)
        → Report Agent (formatting, combination)
        → Streamlit UI
    ```

    ### Key Features
    - 📤 **PDF Ingestion**: Upload papers → automatic chunking + embedding
    - 💬 **RAG Q&A**: Ask questions about your paper library
    - 🔍 **Arxiv Search**: Find and summarize new papers
    - 📋 **Report Generation**: Combine knowledge into structured reports
    - 🧠 **Agent Trace**: See the AI's thought process in real-time

    ### Sample Queries
    - "What does this paper say about TCAD calibration?"
    - "Summarize the key findings"
    - "Search for GAA FET simulation papers on Arxiv"
    - "Write a report on ML methods in TCAD from my papers"

    ### Project Structure
    ```
    research-agent/
    ├── app.py              # Streamlit entry point
    ├── src/
    │   ├── ingest.py       # PDF → FAISS pipeline
    │   ├── rag_chain.py    # RAG retrieval + generation
    │   └── agents/
    │       ├── supervisor.py   # Intent classifier
    │       ├── paper_agent.py  # Paper Q&A
    │       ├── arxiv_agent.py  # Arxiv search
    │       └── report_agent.py # Report formatting
    ├── data/papers/        # Uploaded PDFs
    ├── vectorstore/        # FAISS index (generated)
    └── .omo/
        ├── errors/         # Trial & error documentation
        └── plans/          # Project plans
    ```
    """)

    st.divider()

    # System Status
    st.subheader("🔌 System Status")
    store_info = get_store_info(st.session_state.vectorstore_dir)
    ingest_meta = load_ingest_metadata(st.session_state.vectorstore_dir)
    paper_count = len(ingest_meta.get("files", {}))
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Vector Store", "✅ Loaded" if store_info["exists"] else "❌ Empty")
    with col2:
        st.metric("Vectors", str(store_info["vector_count"]))
    with col3:
        st.metric("Papers Ingested", str(paper_count))

    # Environment info
    with st.expander("🖥️ Environment", expanded=False):
        st.json(
            {
                "platform": "win32",
                "python": sys.version,
                "vectorstore": st.session_state.vectorstore_dir,
                "model": st.session_state.current_model,
                "rag_ready": st.session_state.rag_ready,
            }
        )
