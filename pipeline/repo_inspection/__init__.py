"""Repo inspection substrate v1.

Normalize language-specific syntax into common repository evidence.
Do not fork the frozen 84 detector semantics by language.
Do not mutate B4 dests. Do not emit EngineeringQuestion rows.
"""

from pipeline.repo_inspection.index import index_repository
from pipeline.repo_inspection.ir import SCHEMA_VERSION, evidence_stats

__all__ = ["SCHEMA_VERSION", "evidence_stats", "index_repository"]
