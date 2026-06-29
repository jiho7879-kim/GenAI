"""
Import Validation Harness.

Verifies that every module in the project can be imported without errors.
Run via: python scripts/validate_imports.py

Exit code 0 = all imports successful.
Exit code 1 = one or more imports failed.
"""

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# (module_name, import_name) -- the actual import to test
IMPORT_CHECKS = [
    # Core infrastructure
    (
        "src.ingest",
        "ingest_pdf, load_vectorstore, get_store_info, get_ingested_files, load_ingest_metadata",
    ),
    ("src.rag_chain", "RAGChain, MODEL_FAST, MODEL_ACCURATE"),
    # Agents
    ("src.agents.supervisor", "SupervisorAgent"),
    ("src.agents.paper_agent", "PaperAgent"),
    ("src.agents.arxiv_agent", "ArxivSearchAgent"),
    ("src.agents.report_agent", "ReportAgent"),
]

failed = []

for module_path, names in IMPORT_CHECKS:
    try:
        mod = importlib.import_module(module_path)
        for name in names.replace(" ", "").split(","):
            if not hasattr(mod, name):
                failed.append(f"{module_path} has no attribute {name!r}")
        print(f"  PASS  {module_path}  -> {names}")
    except ImportError as e:
        failed.append(f"{module_path}: {e}")
        print(f"  FAIL  {module_path}  -> {e}")

print()
if failed:
    print(f"FAIL: {len(failed)} import failure(s):")
    for f in failed:
        print(f"   - {f}")
    sys.exit(1)
else:
    print("PASS: All imports passed.")
    sys.exit(0)
