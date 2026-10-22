# ProcureAI Control-Flow Diagram (CFD)

A control-flow diagram shows **the order of execution and decision points**. This is different from a DFD, which focuses on data movement.

## Evaluation control flow

```mermaid
flowchart TD
    START([Start]) --> LOAD[Load configuration and active criteria]
    LOAD --> VALIDW{Weights total 100%?}
    VALIDW -- No --> ERRW[Show configuration error]
    ERRW --> END([End])
    VALIDW -- Yes --> SELECT[User selects one or more PDFs]
    SELECT --> HASFILES{At least one PDF selected?}
    HASFILES -- No --> PROMPT[Keep Evaluate disabled / request selection]
    PROMPT --> END
    HASFILES -- Yes --> LOOP[For each selected supplier]
    LOOP --> EXTRACT[Extract PDF text]
    EXTRACT --> RETRIEVE[Retrieve evidence for each criterion]
    RETRIEVE --> EVIDENCE{Evidence retrieved?}
    EVIDENCE -- No --> HANDLE[Handle empty evidence safely / flag missing evidence]
    EVIDENCE -- Yes --> CALL[Call OpenRouter evaluator]
    HANDLE --> CALL
    CALL --> PARSE[Parse and validate structured JSON]
    PARSE --> VALID{Response valid and criteria complete?}
    VALID -- No --> FAILURE[Report error or apply bounded retry policy]
    VALID -- Yes --> SAVEITEM[Calculate supplier weighted score]
    FAILURE --> NEXT{More selected suppliers?}
    SAVEITEM --> NEXT
    NEXT -- Yes --> LOOP
    NEXT -- No --> RANK[Calculate peer metrics and deterministic ranks]
    RANK --> PERSIST[Persist run and supplier results in SQLite]
    PERSIST --> DISPLAY[Render leaderboard, scorecards, chart, risks and export]
    DISPLAY --> END
```

## Runtime observability recommendations

Add structured timings around these stages before optimizing:

1. PDF text extraction.
2. Query embedding.
3. ChromaDB retrieval.
4. OpenRouter request/response (usually a likely latency source).
5. Schema validation and scoring.
6. SQLite persistence and dashboard rendering.

Log elapsed time, selected supplier ID, number of retrieved chunks, model identifier, response status, and token usage if available. Never log API keys or full confidential proposal content. Parallel execution, caching, retries, and LangGraph nodes should be added deliberately and covered by tests.
