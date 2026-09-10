"""Phase 5.1 — AI Evaluation & Quality control pack.

Representative pack. Not 53 families. Not 333 controls.
QF-0005 eval_gate stays on the frozen C1 dest (CEE-0003). This pack
adds the sibling eval/quality jobs that C1 left out.

Absence of evidence is UNKNOWN, not FAIL.
"""

from __future__ import annotations

P5_EVAL_SPECS: list[dict] = [
    {
        "id": "CEE-0101",
        "family_id": "QF-0027",
        "control_id": "CTRL-0305",
        "diagnostic_job": "retrieval_eval",
        "strong": [
            "A retrieval evaluator scores ranked results against labeled relevant sources.",
            "A named retrieval metric such as nDCG, recall@k, or context precision is computed in a harness.",
        ],
        "supporting": [
            "A retrieval metric name is configured without a function that scores retrieved sources.",
        ],
        "insufficient_alone": [
            "A comment says to evaluate retrieval quality.",
            "Product search ranking exists with no relevance labels.",
        ],
        "contradiction": [
            "Retrieval relevance evaluation is explicitly skipped or disabled.",
        ],
        "evidence_sources": ["tests", "code"],
        "notes": "Retrieval metrics only. Faithfulness evaluators are grounding_eval. Pre-prod gates are eval_gate.",
    },
    {
        "id": "CEE-0102",
        "family_id": "QF-0042",
        "control_id": "CTRL-0321",
        "diagnostic_job": "tool_selection_eval",
        "strong": [
            "A harness scores whether the agent selected the expected tool for the task.",
            "Tool-choice accuracy is computed against labeled expected tools.",
        ],
        "supporting": [
            "A test names an expected tool without scoring selection across cases.",
        ],
        "insufficient_alone": [
            "A tool catalog or tools list exists with no selection evaluation.",
        ],
        "contradiction": [
            "Tool-selection evaluation is explicitly skipped or disabled.",
        ],
        "evidence_sources": ["tests", "code"],
        "notes": "Did the agent pick the right tool. The catalog itself is tool_catalog_scope.",
    },
    {
        "id": "CEE-0103",
        "family_id": "QF-0043",
        "control_id": "CTRL-0198",
        "diagnostic_job": "online_eval",
        "strong": [
            "Production traffic is scored by an online quality monitor after release.",
            "An online eval job runs on live outputs without waiting for a new offline suite.",
        ],
        "supporting": [
            "A production quality score is logged on the serving path without a monitor that can fail.",
        ],
        "insufficient_alone": [
            "An offline eval suite exists with no production-traffic scoring.",
            "A product feature scores users or documents and is named evaluation.",
        ],
        "contradiction": [
            "Online quality monitoring is explicitly disabled on the production path.",
        ],
        "evidence_sources": ["code", "ops", "ci"],
        "notes": "Online eval on production traffic. Pre-production gates are eval_gate.",
    },
    {
        "id": "CEE-0104",
        "family_id": "QF-0044",
        "control_id": "CTRL-0207",
        "diagnostic_job": "eval_dataset",
        "strong": [
            "A labeled eval dataset holds inputs plus reference outputs used only by evaluators.",
            "Named labeled eval examples exist so a behavior can be scored.",
        ],
        "supporting": [
            "Gold labels or eval examples are referenced without a dataset object.",
        ],
        "insufficient_alone": [
            "Unit-test fixtures exist without behavior-quality labels.",
            "An evals folder name exists with no labeled examples.",
        ],
        "contradiction": [
            "The eval dataset is explicitly disabled or gold labels are turned off.",
        ],
        "evidence_sources": ["tests", "code"],
        "notes": "Dataset presence. The gate that consumes the dataset is eval_gate.",
    },
    {
        "id": "CEE-0105",
        "family_id": "QF-0045",
        "control_id": "CTRL-0301",
        "diagnostic_job": "grounding_eval",
        "strong": [
            "A faithfulness or groundedness evaluator scores whether the answer stayed in retrieved context.",
            "A named faithfulness_score compares generated output to retrieved evidence.",
        ],
        "supporting": [
            "Citations are checked without a faithfulness scorer.",
        ],
        "insufficient_alone": [
            "A prompt tells the model to be faithful or stay grounded.",
        ],
        "contradiction": [
            "Faithfulness evaluation is explicitly skipped or disabled.",
        ],
        "evidence_sources": ["tests", "code"],
        "notes": "Faithfulness evaluators. Exist-stance grounding is QF-0006. Retrieval metrics are retrieval_eval.",
    },
    {
        "id": "CEE-0106",
        "family_id": "QF-0054",
        "control_id": "CTRL-0247",
        "diagnostic_job": "eval_leakage",
        "strong": [
            "A check detects overlap between training, evaluation, and auxiliary or retrieved data.",
            "Splits are deduplicated so eval items do not leak into training or retrieval.",
        ],
        "supporting": [
            "Train and eval paths are separated without an overlap check.",
        ],
        "insufficient_alone": [
            "A random train_test_split is used with no leakage check.",
        ],
        "contradiction": [
            "Train and eval overlap is explicitly allowed.",
        ],
        "evidence_sources": ["tests", "code"],
        "notes": "Train/eval/aux overlap. Dataset presence is eval_dataset.",
    },
]
