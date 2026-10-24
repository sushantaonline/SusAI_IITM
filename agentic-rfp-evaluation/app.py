import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

# Streamlit Community Cloud stores secrets in st.secrets. Populate the
# environment before importing config.py/evaluator.py, which read env vars
# during module import. Local environment variables remain supported.
try:
    if "OPENROUTER_API_KEY" in st.secrets:
        os.environ["OPENROUTER_API_KEY"] = str(st.secrets["OPENROUTER_API_KEY"])
    if "OPENROUTER_MODEL" in st.secrets:
        os.environ["OPENROUTER_MODEL"] = str(st.secrets["OPENROUTER_MODEL"])
except Exception:
    # Local runs without a Streamlit secrets file can use environment variables.
    pass

from src.rfp_evaluator.config import (
    DB_PATH,
    INPUT_DIR,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    PROJECT_ROOT,
)
from src.rfp_evaluator.database import (
    initialize_database,
    get_connection,
    save_supplier_result,
)
from src.rfp_evaluator.pdf_extractor import extract_pdf_text
from src.rfp_evaluator.evaluator import evaluate_supplier
from src.rfp_evaluator.scoring import (
    calculate_weighted_score,
    calculate_peer_metrics,
    rank_suppliers,
)


def ensure_chroma_index():
    """Build the proposal vector index if it is missing or empty."""
    import chromadb

    chroma_dir = PROJECT_ROOT / "data" / "chroma_db"
    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection_names = {
        collection.name for collection in client.list_collections()
    }

    if "supplier_proposals" in collection_names:
        collection = client.get_collection("supplier_proposals")
        if collection.count() > 0:
            return

    pdf_files = sorted(INPUT_DIR.glob("*.pdf"))
    if not pdf_files:
        st.error(f"No supplier PDFs found in {INPUT_DIR}")
        st.stop()

    build_script = PROJECT_ROOT / "build_vector_store.py"
    if not build_script.is_file():
        st.error(f"Vector index build script not found: {build_script}")
        st.stop()

    with st.spinner(
        f"Initializing supplier search index from {len(pdf_files)} PDFs. "
        "The first startup may take several minutes..."
    ):
        result = subprocess.run(
            [sys.executable, str(build_script)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )

    if result.returncode != 0:
        st.error("Failed to build the ChromaDB index.")
        st.code(result.stderr or result.stdout or "No build output was returned.")
        st.stop()

    # Confirm that the build produced a usable collection.
    client = chromadb.PersistentClient(path=str(chroma_dir))
    if "supplier_proposals" not in {
        collection.name for collection in client.list_collections()
    }:
        st.error("Index build finished, but supplier_proposals was not created.")
        st.code(result.stdout or "No build output was returned.")
        st.stop()

    collection = client.get_collection("supplier_proposals")
    if collection.count() == 0:
        st.error("The supplier proposal index contains no vectors.")
        st.code(result.stdout or "No build output was returned.")
        st.stop()

    st.success(f"Supplier search index ready: {collection.count()} chunks.")


# ============================================================
# 1. PAGE CONFIGURATION
# Streamlit reruns this script whenever a user interacts with
# a widget. Session state preserves completed evaluation results.
# ============================================================

st.set_page_config(
    page_title="AI Procurement Intelligence",
    page_icon="📊",
    layout="wide",
)

# The PDFs are committed to the repository; build the generated Chroma index
# on first cloud startup when it is not already available.
ensure_chroma_index()

st.title("🏦 AI Procurement Intelligence")
st.caption(
    "Agentic RFP Evaluation & Supplier Ranking | "
    "LLM + Deterministic Python + SQLite"
)


# ============================================================
# 2. SIDEBAR: AI CONFIGURATION
# Display the configured LLM and integration status.
# Never display the actual API key.
# ============================================================

with st.sidebar:
    st.header("🤖 AI Configuration")
    st.write("**Provider:** OpenRouter")
    st.write(f"**Model:** `{OPENROUTER_MODEL}`")
    st.write("**Evaluation:** LLM + deterministic Python")
    st.write("**RAG:** Local Chroma retrieval enabled")

    st.write(
        "**API key:** Configured"
        if OPENROUTER_API_KEY
        else "**API key:** Missing"
    )

    st.divider()
    st.caption("Procurement domain: Banking / Financial Services")


# ============================================================
# 3. DATABASE AND ACTIVE EVALUATION CRITERIA
# Criteria and weights are loaded from SQLite, not hardcoded
# into the scoring calculations.
# ============================================================

initialize_database()

with get_connection() as conn:
    criteria = [
        dict(row)
        for row in conn.execute(
            """
            SELECT name, weight, max_score
            FROM evaluation_criteria
            WHERE active = 1
            ORDER BY id
            """
        ).fetchall()
    ]

if not criteria:
    st.error("No active evaluation criteria found in the database.")
    st.stop()

total_weight = sum(float(c["weight"]) for c in criteria)

if abs(total_weight - 100.0) > 1e-6:
    st.error(
        f"Active criterion weights total {total_weight}%, not 100%. "
        "Correct the criteria before evaluating suppliers."
    )
    st.stop()


# ============================================================
# 4. EVALUATION CRITERIA DISPLAY
# Show procurement users how the final score is weighted.
# ============================================================

with st.expander("📋 Evaluation criteria and weights", expanded=False):
    st.dataframe(
        criteria,
        width="stretch",
        hide_index=True,
        column_config={
            "name": st.column_config.TextColumn("Criterion"),
            "weight": st.column_config.NumberColumn(
                "Weight (%)", format="%.0f%%"
            ),
            "max_score": st.column_config.NumberColumn(
                "Maximum score", format="%.1f"
            ),
        },
    )


# ============================================================
# 5. SUPPLIER PDF INPUT
# Support either PDFs already in data/input or browser uploads.
# Supplier metadata is collected before evaluation.
# ============================================================

st.header("📄 Supplier proposals")

uploaded_files = st.file_uploader(
    "Upload supplier PDF proposals",
    type=["pdf"],
    accept_multiple_files=True,
    help="Alternatively, choose PDFs already stored in data/input.",
)

local_files = sorted(INPUT_DIR.glob("*.pdf")) if INPUT_DIR.exists() else []

source = st.radio(
    "Proposal source",
    ["Existing local PDFs", "Uploaded PDFs"],
    horizontal=True,
)

if source == "Existing local PDFs":
    available_files = local_files
else:
    available_files = uploaded_files or []

# Let users explicitly select one or more proposals. A selected proposal
# is visually highlighted; multi-selection preserves supplier comparison.
st.subheader("Select proposals to evaluate")
st.caption(
    "Select one supplier for an individual evaluation, or select multiple "
    "suppliers to compare them on the leaderboard and spider chart."
)

selected_files = []
for file in available_files:
    filename = file.name
    checkbox_key = f"proposal_selected_{source}_{filename}"

    with st.container(border=True):
        is_selected = st.checkbox(
            f"📄 {filename}",
            key=checkbox_key,
        )
        if is_selected:
            selected_files.append(file)
            st.success("Selected for evaluation", icon="✅")

st.write(f"**Proposals selected for evaluation: {len(selected_files)}**")

supplier_metadata = {}

for index, file in enumerate(selected_files):
    filename = file.name
    default_name = filename.split("_rfp_response")[0]

    with st.expander(f"📝 Supplier details — {filename}", expanded=False):
        name = st.text_input(
            "Supplier name",
            value=default_name,
            key=f"name_{source}_{filename}",
        )

        submission_date = st.date_input(
            "Submission date",
            key=f"date_{source}_{filename}",
        )

        experience = st.slider(
            "Historical experience rating",
            min_value=0,
            max_value=10,
            value=5,
            key=f"experience_{source}_{filename}",
        )

        supplier_metadata[filename] = {
            "name": name,
            "submission_date": submission_date.isoformat(),
            "experience_rating": experience,
        }


# ============================================================
# 6. EVALUATION PIPELINE
# The LLM assesses the proposal. Python calculates all numeric
# weighted scores, peer metrics, and deterministic rankings.
# ============================================================

st.header("⚙️ Run evaluation")

if st.button(
    "🚀 Evaluate suppliers",
    type="primary",
    disabled=not selected_files,
):
    if not selected_files:
        st.error("Select at least one PDF.")
        st.stop()

    # Prevent blank or duplicate names within this evaluation.
    names = [
        metadata["name"].strip()
        for metadata in supplier_metadata.values()
    ]

    if any(not name for name in names):
        st.error("Every supplier must have a name.")
        st.stop()

    if len(names) != len(set(name.casefold() for name in names)):
        st.error("Supplier names must be unique within a run.")
        st.stop()

    run_id = str(uuid.uuid4())
    evaluations = []

    progress = st.progress(0)
    status = st.empty()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO rfp_runs (run_id, created_at, status)
            VALUES (?, ?, ?)
            """,
            (
                run_id,
                datetime.now().isoformat(timespec="seconds"),
                "RUNNING",
            ),
        )

    try:
        for index, file in enumerate(selected_files):
            status.info(f"Evaluating {file.name}...")

            # Extract text differently for local files and uploads.
            if source == "Existing local PDFs":
                document_text = extract_pdf_text(INPUT_DIR / file.name)
            else:
                # PyMuPDF reads the uploaded PDF directly from memory.
                import pymupdf

                with pymupdf.open(
                    stream=file.getvalue(),
                    filetype="pdf",
                ) as document:
                    document_text = "\n".join(
                        page.get_text() for page in document
                    )

            metadata = supplier_metadata[file.name]

            # LLM output includes scores, evidence, justifications,
            # risks, and missing information for each criterion.
            result = evaluate_supplier(
                metadata["name"].strip(),
                document_text,
                criteria,
            )

            scores = {
                name: item["score"]
                for name, item in result["criteria"].items()
            }

            # Deterministic business logic: LLM does not calculate
            # the weighted total or decide the supplier ranking.
            weighted = calculate_weighted_score(scores, criteria)

            evaluations.append({
                "supplier_name": metadata["name"].strip(),
                "submission_date": metadata["submission_date"],
                "experience_rating": metadata["experience_rating"],
                "evaluation": result,
                "scores": scores,
                "absolute_weighted_score": weighted,
            })

            progress.progress((index + 1) / len(selected_files))

        # Compare suppliers against the best score for each criterion.
        peer_metrics = calculate_peer_metrics(
            [
                {
                    "supplier_name": item["supplier_name"],
                    **item["scores"],
                }
                for item in evaluations
            ],
            criteria,
        )

        for item in evaluations:
            item["ppi"] = peer_metrics[item["supplier_name"]]["ppi"]

        # Apply the established tie-break order from scoring.py.
        ranked = rank_suppliers(evaluations)

        # Persist every supplier result against this unique run ID.
        for item in ranked:
            save_supplier_result(
                run_id=run_id,
                supplier_name=item["supplier_name"],
                submission_date=item["submission_date"],
                experience_rating=item["experience_rating"],
                evaluation=item["evaluation"],
                weighted_score=item["absolute_weighted_score"],
                ppi=item["ppi"],
                rank=item["rank"],
            )

        with get_connection() as conn:
            conn.execute(
                "UPDATE rfp_runs SET status = ? WHERE run_id = ?",
                ("COMPLETED", run_id),
            )

        # Session state makes results available after Streamlit reruns.
        st.session_state["ranked"] = ranked
        st.session_state["peer_metrics"] = peer_metrics
        st.session_state["run_id"] = run_id

        status.success(
            f"Evaluation completed successfully. Run ID: {run_id}"
        )

    except Exception as exc:
        with get_connection() as conn:
            conn.execute(
                "UPDATE rfp_runs SET status = ? WHERE run_id = ?",
                ("FAILED", run_id),
            )

        status.error(f"Evaluation failed: {exc}")


# ============================================================
# 7. ANALYTICS DASHBOARD
# Display results only after a successful evaluation.
# ============================================================

if "ranked" in st.session_state:
    ranked = st.session_state["ranked"]

    # Use the sorted list to calculate dashboard summary metrics.
    top_supplier = ranked[0]
    highest_score = max(
        item["absolute_weighted_score"] for item in ranked
    )
    average_score = sum(
        item["absolute_weighted_score"] for item in ranked
    ) / len(ranked)

    st.divider()
    st.header("📊 Evaluation dashboard")

    # KPI cards give procurement users an immediate summary.
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    kpi1.metric("Suppliers evaluated", len(ranked))
    kpi2.metric("🏆 Top supplier", top_supplier["supplier_name"])
    kpi3.metric("Highest weighted score", f"{highest_score:.2f}/100")
    kpi4.metric("Average weighted score", f"{average_score:.2f}/100")

    st.caption(f"Evaluation run: {st.session_state['run_id']}")


    # ========================================================
    # 8. INTERACTIVE RADAR / SPIDER CHART
    # Compare criterion-level scores on a common 0–10 scale.
    # Each supplier becomes a separate polygon.
    # ========================================================

    st.subheader("🕸️ Supplier comparison — Spider chart")

    supplier_names = [
        item["supplier_name"] for item in ranked
    ]

    default_selection = supplier_names[:min(5, len(supplier_names))]

    selected_suppliers = st.multiselect(
        "Choose suppliers to compare",
        options=supplier_names,
        default=default_selection,
        help="Compare a few suppliers at a time to keep the chart readable.",
    )

    if selected_suppliers:
        fig = go.Figure()

        # Criterion names determine the radar chart axes.
        criterion_names = [c["name"] for c in criteria]

        for item in ranked:
            if item["supplier_name"] not in selected_suppliers:
                continue

            scores = item["scores"]

            # Close the polygon by repeating the first axis and score.
            theta = criterion_names + [criterion_names[0]]
            values = [float(scores[name]) for name in criterion_names]
            values.append(values[0])

            fig.add_trace(
                go.Scatterpolar(
                    r=values,
                    theta=theta,
                    name=item["supplier_name"],
                    fill="toself",
                    opacity=0.65,
                    hovertemplate=(
                        "<b>%{fullData.name}</b><br>"
                        "%{theta}: %{r:.2f}/10"
                        "<extra></extra>"
                    ),
                )
            )

        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 10],
                    tick0=0,
                    dtick=2,
                ),
            ),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.25,
                xanchor="center",
                x=0.5,
            ),
            margin=dict(l=40, r=40, t=35, b=100),
            height=560,
        )

        st.plotly_chart(fig, width="stretch")

        st.caption(
            "Higher values indicate stronger assessed evidence. "
            "These are LLM-generated criterion scores, not verified "
            "facts or probabilities of supplier success."
        )
    else:
        st.info("Select at least one supplier to display the radar chart.")


    # ========================================================
    # 9. STYLED LEADERBOARD
    # Show final rank, absolute weighted score, and peer performance.
    # ========================================================

    st.subheader("🏆 Supplier leaderboard")

    leaderboard = [
        {
            "Rank": item["rank"],
            "Supplier": item["supplier_name"],
            "Weighted score (/100)": item["absolute_weighted_score"],
            "PPI (%)": item["ppi"],
            "Submission date": item["submission_date"],
            "Experience (/10)": item["experience_rating"],
        }
        for item in ranked
    ]

    st.dataframe(
        leaderboard,
        width="stretch",
        hide_index=True,
        height=min(440, 40 + 36 * len(leaderboard)),
        column_config={
            "Rank": st.column_config.NumberColumn(
                "Rank", format="%d"
            ),
            "Supplier": st.column_config.TextColumn("Supplier"),
            "Weighted score (/100)": st.column_config.ProgressColumn(
                "Weighted score",
                min_value=0,
                max_value=100,
                format="%.2f",
            ),
            "PPI (%)": st.column_config.NumberColumn(
                "Peer Performance Index",
                format="%.2f%%",
            ),
            "Submission date": st.column_config.DateColumn(
                "Submission date",
                format="YYYY-MM-DD",
            ),
            "Experience (/10)": st.column_config.NumberColumn(
                "Experience", format="%.1f"
            ),
        },
    )


    # ========================================================
    # 10. DETAILED SUPPLIER SCORECARD
    # Show criterion scores, LLM explanations, and evidence.
    # ========================================================

    st.subheader("🔎 Supplier scorecard")

    choice = st.selectbox(
        "Select a supplier",
        options=supplier_names,
    )

    selected = next(
        item for item in ranked
        if item["supplier_name"] == choice
    )

    score_col, ppi_col, rank_col = st.columns(3)

    score_col.metric(
        "Weighted score",
        f"{selected['absolute_weighted_score']:.2f}/100",
    )
    ppi_col.metric("PPI", f"{selected['ppi']:.2f}%")
    rank_col.metric("Final rank", f"#{selected['rank']}")

    # Build a criterion-level table with evidence and explanations.
    scorecard_rows = []

    for criterion in criteria:
        name = criterion["name"]
        detail = selected["evaluation"]["criteria"][name]

        scorecard_rows.append({
            "Criterion": name,
            "Weight (%)": criterion["weight"],
            "Score": detail["score"],
            "Maximum": criterion["max_score"],
            "Justification": detail["justification"],
            "Evidence": detail["evidence"],
        })

    st.dataframe(
        scorecard_rows,
        width="stretch",
        hide_index=True,
        column_config={
            "Weight (%)": st.column_config.NumberColumn(
                "Weight", format="%.0f%%"
            ),
            "Score": st.column_config.NumberColumn(
                "Score", format="%.2f"
            ),
            "Maximum": st.column_config.NumberColumn(
                "Maximum", format="%.1f"
            ),
            "Justification": st.column_config.TextColumn(
                "LLM justification", width="large"
            ),
            "Evidence": st.column_config.TextColumn(
                "Proposal evidence", width="large"
            ),
        },
    )

    # Show the relative-performance calculations separately.
    peer_metrics = st.session_state["peer_metrics"]
    supplier_peer = peer_metrics[selected["supplier_name"]]

    with st.expander("📐 Peer benchmarks and criterion gaps"):
        peer_rows = []

        for criterion in criteria:
            name = criterion["name"]
            metric = supplier_peer["criteria"][name]

            peer_rows.append({
                "Criterion": name,
                "Supplier score": metric["score"],
                "Peer benchmark": metric["benchmark"],
                "Gap": metric["gap"],
                "Relative performance (%)": (
                    metric["relative_performance_pct"]
                ),
            })

        st.dataframe(
            peer_rows,
            width="stretch",
            hide_index=True,
            column_config={
                "Supplier score": st.column_config.NumberColumn(
                    format="%.2f"
                ),
                "Peer benchmark": st.column_config.NumberColumn(
                    format="%.2f"
                ),
                "Gap": st.column_config.NumberColumn(
                    format="%+.2f"
                ),
                "Relative performance (%)": (
                    st.column_config.NumberColumn(format="%.2f%%")
                ),
            },
        )

    # Risks and missing information are useful for procurement review.
    evaluation = selected["evaluation"]

    risk_col, missing_col = st.columns(2)

    with risk_col:
        st.markdown("#### ⚠️ Identified risks")
        risks = evaluation.get("risks", [])

        if risks:
            for risk in risks:
                st.warning(risk)
        else:
            st.success("No risks were returned by the LLM.")

    with missing_col:
        st.markdown("#### 🧩 Missing information")
        missing = evaluation.get("missing_information", [])

        if missing:
            for information in missing:
                st.info(information)
        else:
            st.success("No missing information was returned by the LLM.")


    # ========================================================
    # 11. EXPORT
    # Preserve the detailed evaluation data in downloadable JSON.
    # ========================================================

    st.subheader("📥 Export results")

    st.download_button(
        "Download all evaluation results (JSON)",
        data=json.dumps(ranked, indent=2, ensure_ascii=False),
        file_name=f"rfp_evaluation_{st.session_state['run_id']}.json",
        mime="application/json",
    )

else:
    st.info(
        "Select supplier proposals and run an evaluation to display "
        "the dashboard, spider chart, leaderboard, and scorecards."
    )
