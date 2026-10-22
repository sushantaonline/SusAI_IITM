
"""
LLM-based supplier evaluation for ProcureAI.

Responsibilities:
1. Retrieve supplier-specific evidence for each RFP criterion.
2. Send relevant evidence to the LLM for scoring and justification.
3. Preserve source filenames and page numbers for traceability.
4. Validate the response against the existing Pydantic schema.

Python remains responsible for weighted totals and rankings.
"""

import json
import urllib.request
import urllib.error

from src.rfp_evaluator.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
)
from src.rfp_evaluator.schemas import SupplierEvaluation
from src.rfp_evaluator.rag_pipeline import retrieve_evidence


# Criterion descriptions guide semantic retrieval.
# Keep these labels aligned with the existing scoring rubric.
CRITERION_DESCRIPTIONS = {
    "Technical Capability": (
        "Cloud architecture, scalability, availability, disaster recovery, "
        "REST APIs, event-driven integration, banking-system integration, "
        "resilience, and operational monitoring."
    ),
    "Implementation Plan": (
        "Implementation phases, migration strategy, milestones, timelines, "
        "testing, migration rehearsal, rollback, business continuity, "
        "delivery governance, and dependencies."
    ),
    "Commercial Value": (
        "Total cost of ownership, subscription, implementation, migration "
        "and support costs, licensing, pricing transparency, exclusions, "
        "assumptions, renewal costs, and change-request charges."
    ),
    "Security & Compliance": (
        "Identity and access management, SSO, RBAC, encryption, audit logs, "
        "vulnerability management, penetration testing, incident response, "
        "data residency, disaster recovery, and documentary compliance evidence."
    ),
    "Support & Experience": (
        "Support coverage, SLA commitments, response and resolution times, "
        "service management, escalation, financial-services experience, "
        "and customer references."
    ),
}

# Evidence retrieval is limited to three chunks per criterion.
# Increase only if relevant evidence is consistently being missed.
RETRIEVAL_TOP_K = 3


def _format_criterion_evidence(supplier_name, criteria):
    """Retrieve and format evidence independently for every criterion."""

    sections = []

    for criterion in criteria:
        criterion_name = criterion["name"]

        # Fail clearly if a criterion is not covered by the retrieval rubric.
        description = CRITERION_DESCRIPTIONS.get(criterion_name)

        if description is None:
            raise ValueError(
                f"No retrieval description configured for criterion: "
                f"{criterion_name}"
            )

        evidence_items = retrieve_evidence(
            supplier_name=supplier_name,
            criterion_name=criterion_name,
            criterion_description=description,
            top_k=RETRIEVAL_TOP_K,
        )

        sections.append(f"\n### {criterion_name}")

        if not evidence_items:
            sections.append(
                "No relevant evidence was retrieved for this criterion. "
                "Do not invent evidence or assume the supplier meets "
                "the requirement."
            )
            continue

        for number, item in enumerate(evidence_items, start=1):
            source = item.get("source_filename", "Unknown source")
            page = item.get("page_number", "Unknown page")
            distance = item.get("cosine_distance")

            sections.append(
                f"\nEvidence {number}\n"
                f"Source: {source}\n"
                f"Page: {page}\n"
                f"Retrieved text:\n{item['text']}"
            )

            # Distance is diagnostic information, not a confidence score.
            if distance is not None:
                sections.append(
                    f"Retrieval cosine distance: {distance:.4f}"
                )

    return "\n".join(sections)


def evaluate_supplier(supplier_name, document_text, criteria):
    """
    Evaluate one supplier using criterion-specific retrieved evidence.

    The document_text argument is retained for compatibility with app.py.
    The full document is not sent to the LLM, helping reduce token usage.
    """

    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY is missing from the environment."
        )

    if not criteria:
        raise ValueError("At least one evaluation criterion is required.")

    # Retrieve evidence before calling the LLM.
    # supplier_name must match the supplier_name stored in Chroma metadata.
    evidence_text = _format_criterion_evidence(
        supplier_name=supplier_name,
        criteria=criteria,
    )

    criteria_text = "\n".join(
        f"- {criterion['name']}: "
        f"weight {criterion['weight']}%, "
        f"score from 0 to {criterion['max_score']}"
        for criterion in criteria
    )

    prompt = f"""
You are a rigorous procurement evaluator assessing a supplier proposal
for a fictional bank's cloud-based customer-service and case-management
platform.

SUPPLIER
{supplier_name}

SCORING RUBRIC

1. Technical Capability (30%)
Assess cloud architecture, scalability, availability, disaster recovery,
APIs, and integration with banking systems.

2. Implementation Plan (20%)
Assess migration strategy, milestones, delivery timelines, testing,
rollback, and business continuity.

3. Commercial Value (20%)
Assess total cost of ownership, pricing transparency, licensing,
implementation costs, and clearly stated cost assumptions.
Do not automatically reward the lowest price.

4. Security & Compliance (20%)
Assess identity and access controls, encryption, audit logs,
vulnerability management, incident response, and evidence of applicable
financial-sector compliance.
Never assume compliance without supporting evidence.

5. Support & Experience (10%)
Assess SLA commitments, support coverage, incident resolution,
relevant banking experience, and verifiable customer references.

COMMON SCORE ANCHORS (0–10)

0–2: Very weak, absent, or materially inadequate evidence.
3–4: Significant gaps; limited supporting evidence.
5–6: Partially meets requirements; some gaps remain.
7–8: Meets most requirements with credible supporting evidence.
9–10: Strong, detailed, relevant evidence with minimal gaps.

EVIDENCE AND SCORING RULES

- Evaluate only the evidence provided below.
- Evidence sections are retrieved from this supplier's indexed proposal.
- Assess each criterion independently.
- Prefer evidence directly relevant to the criterion being scored.
- Do not treat a semantically related chunk as proof of a requirement
  unless its actual text supports that conclusion.
- A retrieved chunk may contain information relevant to other criteria.
  Use it only where relevant.
- Treat supplier claims as claims, not independently verified facts.
- Never invent certifications, prices, SLAs, capabilities, or references.
- Missing evidence must reduce the score where appropriate.
- Distinguish documented evidence from unsupported assertions.
- Include concise supporting excerpts and their source filename/page
  in the evidence field.
- If no relevant evidence exists, state that clearly and score
  conservatively.
- Cosine distance is a retrieval metric, not a confidence percentage.
- Do not calculate weighted totals or supplier rankings.
  Python performs those calculations deterministically.
- Return valid JSON only, without Markdown or additional commentary.

REQUIRED OUTPUT

Return an object with this structure:

{{
  "supplier_name": "{supplier_name}",
  "criteria": {{
    "Technical Capability": {{
      "score": 0,
      "justification": "Reason for the score",
      "evidence": "Supporting excerpt with source filename and page"
    }}
  }},
  "risks": [],
  "missing_information": []
}}

Include every criterion listed below. Use scores from 0 to its
configured maximum score.

CRITERIA TO EVALUATE
{criteria_text}

RETRIEVED SUPPLIER EVIDENCE
{evidence_text}
"""

    payload = {
        "model": OPENROUTER_MODEL,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a rigorous procurement evaluator. "
                    "Use only supplied evidence. Return valid JSON."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "response_format": {"type": "json_object"},
    }

    request = urllib.request.Request(
        OPENROUTER_BASE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8501",
            "X-Title": "Agentic RFP Evaluator",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"OpenRouter HTTP error {exc.code}: {detail[:1000]}"
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"OpenRouter connection failed: {exc}"
        ) from exc

    try:
        content = result["choices"][0]["message"]["content"]
        parsed = SupplierEvaluation.model_validate_json(content)

    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError(
            "The LLM response was missing or did not match the expected "
            "evaluation schema. Check the model response and schemas.py."
        ) from exc

    expected = {criterion["name"] for criterion in criteria}
    actual = set(parsed.criteria)

    if actual != expected:
        raise ValueError(
            f"Criteria mismatch. Missing: {expected - actual}; "
            f"unexpected: {actual - expected}"
        )

    # Validate scores against each configured maximum.
    evaluation = parsed.model_dump()

    for criterion in criteria:
        name = criterion["name"]
        score = evaluation["criteria"][name]["score"]
        maximum = criterion["max_score"]

        if not isinstance(score, (int, float)) or not 0 <= score <= maximum:
            raise ValueError(
                f"Invalid score for {name}: {score}. "
                f"Expected a score between 0 and {maximum}."
            )

    return evaluation
