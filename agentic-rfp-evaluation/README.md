# ProcureAI — Agentic RFP Evaluation & Supplier Ranking

ProcureAI is a portfolio prototype that evaluates synthetic supplier proposals against weighted procurement criteria. It combines a Streamlit UI, PDF text extraction, local retrieval-augmented generation (RAG), an LLM accessed through OpenRouter, deterministic Python scoring, and SQLite persistence.

> **Prototype notice:** This is a demonstration project using synthetic proposal data. It is not a certified procurement, security, legal, or compliance decision system. Human review is required before any real-world decision.

## Current capabilities

- Select one or more supplier proposal PDFs for evaluation.
- Extract proposal text and retrieve relevant evidence from a local Chroma vector store.
- Use a local Sentence Transformers embedding model for semantic retrieval.
- Use an OpenRouter-hosted LLM to produce criterion scores, explanations, evidence references, risks, and missing information.
- Calculate weighted totals and rankings deterministically in Python.
- Store evaluation runs/results in SQLite.
- Display a Streamlit dashboard, supplier comparisons, and JSON exports.

## Architecture and design documents

- [Solution architecture](docs/architecture.md)
- [Data-flow diagrams (DFD)](docs/data-flow-diagrams.md)
- [Control-flow diagram (CFD)](docs/control-flow-diagram.md)
- [Security and public-repository checklist](docs/public-repository-checklist.md)

The diagrams use Mermaid syntax and render directly on GitHub. The current implementation uses a LangChain text-splitting component. Do not describe LangGraph or a full LangChain orchestration chain as implemented until that integration has actually been added and tested.

## Technology stack

- Python 3.12
- Streamlit
- PyMuPDF
- LangChain text splitters (`langchain-text-splitters`)
- Sentence Transformers (`all-MiniLM-L6-v2`)
- ChromaDB
- OpenRouter API (model configured locally)
- Pydantic
- SQLite
- Plotly

## Run locally

1. Create and activate a Python 3.12 virtual environment.
2. Install the dependencies listed in `requirements.txt`.
3. Configure `OPENROUTER_API_KEY` in a local `.env` or your terminal environment. Never commit credentials.
4. Ensure the synthetic PDFs are in `data/input/` and build the local vector index using the project's indexing script.
5. Start Streamlit:

   ```powershell
   streamlit run app.py --server.fileWatcherType none
   ```

Follow the current project scripts and setup notes for the exact index-build command and configuration options.

## Repository hygiene

Do not commit `.env`, API keys, virtual environments, local databases containing non-public information, generated Chroma persistence files, caches, or real supplier proposals. Commit only synthetic sample documents that you have permission to publish.

## Evaluation criteria

The prototype uses five weighted criteria:

| Criterion | Weight |
|---|---:|
| Technical Capability | 30% |
| Implementation Plan | 20% |
| Commercial Value | 20% |
| Security & Compliance | 20% |
| Support & Experience | 10% |

The weights must total 100%. The LLM assesses evidence; Python calculates weighted totals and ranks. Scores and claims should be verified by a human reviewer.

## Roadmap

- Add automated unit and integration tests for chunking, retrieval, scoring, and schema validation.
- Improve latency through bounded parallel evaluation and safe caching.
- Add a LangChain chat-model/prompt integration if it provides a clear benefit.
- Consider LangGraph for stateful orchestration, retries, and human approval after the baseline is stable.
- Add deployment configuration and CI checks.
- Consider an n8n presentation workflow that calls the existing application/API rather than duplicating business scoring logic.
