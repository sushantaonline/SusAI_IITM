
"""Test supplier-specific retrieval for all five RFP criteria."""

from src.rfp_evaluator.rag_pipeline import retrieve_evidence


CRITERIA = [
    (
        "Technical Capability",
        "Cloud architecture, scalability, availability, disaster recovery, "
        "APIs, and banking-system integrations.",
    ),
    (
        "Implementation Plan",
        "Migration strategy, milestones, timelines, testing, rollback, "
        "and business continuity.",
    ),
    (
        "Commercial Value",
        "Total cost, pricing transparency, licensing, implementation costs, "
        "and cost assumptions.",
    ),
    (
        "Security & Compliance",
        "Identity and access management, encryption, audit logs, "
        "vulnerability management, incident response, and compliance evidence.",
    ),
    (
        "Support & Experience",
        "Service levels, support coverage, incident resolution, "
        "banking experience, and customer references.",
    ),
]


def main():
    # Use the filename-derived supplier identifier from the indexed metadata.
    supplier_name = "apx_apex_systems"

    for criterion_name, description in CRITERIA:
        print(f"\n{'=' * 70}")
        print("CRITERION:", criterion_name)
        print("SUPPLIER:", supplier_name)
        print("=" * 70)

        evidence = retrieve_evidence(
            supplier_name=supplier_name,
            criterion_name=criterion_name,
            criterion_description=description,
            top_k=3,
        )

        for item in evidence:
            print(
                f"\nSource: {item['source_filename']} | "
                f"Page: {item['page_number']} | "
                f"Distance: {item['cosine_distance']:.4f}"
            )
            print(item["text"])

        if not evidence:
            print("No evidence retrieved.")


if __name__ == "__main__":
    main()
