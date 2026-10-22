
def calculate_weighted_score(scores, criteria):
    """Calculate the absolute weighted score on a 0–100 scale."""
    total_weight = sum(float(c["weight"]) for c in criteria)

    if total_weight <= 0:
        raise ValueError("Total criterion weight must be positive.")

    if abs(total_weight - 100.0) > 1e-6:
        raise ValueError("Criterion weights must total 100.")

    score_by_name = {
        c["name"]: float(scores[c["name"]]) for c in criteria
    }

    weighted_score = 0.0

    for criterion in criteria:
        name = criterion["name"]
        weight = float(criterion["weight"])
        max_score = float(criterion["max_score"])
        score = score_by_name[name]

        if max_score <= 0:
            raise ValueError(f"Invalid maximum score for {name}.")

        if not 0 <= score <= max_score:
            raise ValueError(f"Score out of range for {name}.")

        weighted_score += (score / max_score) * weight

    return round(weighted_score, 4)


def calculate_peer_metrics(supplier_scores, criteria):
    """Calculate criterion benchmarks, gaps, relative percentages and PPI."""
    benchmarks = {}

    for criterion in criteria:
        name = criterion["name"]
        benchmarks[name] = max(
            (float(s[name]) for s in supplier_scores),
            default=0.0,
        )

    results = {}

    for supplier in supplier_scores:
        metrics = {}
        ppi = 0.0

        for criterion in criteria:
            name = criterion["name"]
            weight = float(criterion["weight"])
            score = float(supplier[name])
            benchmark = benchmarks[name]

            relative_pct = (
                (score / benchmark) * 100 if benchmark > 0 else 0.0
            )

            metrics[name] = {
                "score": score,
                "benchmark": benchmark,
                "gap": round(score - benchmark, 4),
                "relative_performance_pct": round(relative_pct, 4),
            }

            ppi += relative_pct * weight / 100

        results[supplier["supplier_name"]] = {
            "criteria": metrics,
            "ppi": round(ppi, 4),
        }

    return results


def rank_suppliers(suppliers):
    """Rank deterministically using the specified tie-break order."""
    ordered = sorted(
        suppliers,
        key=lambda s: (
            -float(s["ppi"]),
            s["submission_date"] or "9999-12-31",
            -float(s["experience_rating"] or 0),
            s["supplier_name"].casefold(),
        ),
    )

    return [
        {**supplier, "rank": index}
        for index, supplier in enumerate(ordered, start=1)
    ]

