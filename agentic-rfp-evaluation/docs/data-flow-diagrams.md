# ProcureAI Data-Flow Diagrams (DFD)

A DFD describes **where data comes from, how it is transformed, where it is stored, and which external systems receive it**. These diagrams document the current prototype.

## DFD Level 0 — Context diagram

```mermaid
flowchart LR
    USER[Procurement user] -->|Select PDFs / run request| SYS((ProcureAI system))
    SYS -->|Scores / ranking / evidence / risks / JSON| USER
    FILES[(Local proposal PDFs)] -->|Proposal content| SYS
    SYS -->|Prompt containing retrieved proposal evidence| OR[OpenRouter LLM API]
    OR -->|LLM evaluation JSON| SYS
    SYS <--> |Criteria / runs / results| SQL[(Local SQLite database)]
    SYS <--> |Chunk vectors / metadata / similarity search| CH[(Local ChromaDB vector store)]
```

## DFD Level 1 — Evaluation data flow

```mermaid
flowchart TB
    P1[1. Select supplier PDFs] --> P2[2. Extract PDF text and page numbers]
    P2 --> P3[3. Split into chunks and attach metadata]
    P3 --> P4[4. Embed chunks with local embedding model]
    P4 --> D1[(ChromaDB vector index)]

    P1 --> P5[5. Load active criteria and weights]
    P5 --> P6[6. Build criterion-specific retrieval queries]
    D1 --> P6
    P6 --> P7[7. Retrieve relevant evidence chunks]
    P7 --> P8[8. Send evidence and rubric to OpenRouter]
    P8 --> X1[External LLM inference]
    X1 --> P9[9. Validate response schema]
    P9 --> P10[10. Calculate weighted totals and ranks in Python]
    P10 --> D2[(SQLite evaluation results)]
    P10 --> P11[11. Render dashboard and JSON export]
```

## Data inventory and trust boundaries

| Data | Origin | Processing/storage | External transmission? |
|---|---|---|---|
| Proposal PDF/text | Local sample files or user upload | Extracted and chunked in Python | Retrieved evidence may be sent to OpenRouter for evaluation |
| Chunk metadata | Filename, supplier identifier, page/chunk information | Stored with vectors in ChromaDB | May accompany retrieved evidence if included in the prompt |
| Embeddings | Local embedding model | ChromaDB | No, when the local embedding model is used as configured |
| Evaluation JSON | OpenRouter response | Validated, scored, persisted in SQLite | Received from OpenRouter |
| Scores/rankings | Deterministic Python calculation | SQLite and Streamlit | Not necessarily transmitted unless separately configured |
| API key | Developer environment | Read by application at runtime | Sent as authentication to OpenRouter; never expose in UI/logs/repository |

## Privacy note

The current prototype uses synthetic data. Before using real supplier proposals, obtain organizational approval for sending retrieved proposal content to the selected external model provider and review data retention, confidentiality, and contractual terms. A public GitHub repository must not contain real proposals or credentials.
