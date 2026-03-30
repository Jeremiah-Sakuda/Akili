"""
Verification layer: proof check over canonical facts.

If answer is derivable → return answer + (x,y) proof.
If not → deterministic REFUSE.
"""

from akili.verify.compare import ComparisonResult, compare_documents, format_comparison_response
from akili.verify.derived import try_derived_queries
from akili.verify.models import (
    AnswerWithProof, ConfidenceScore, ProofChain, ProofPoint, ProofStep, Refuse,
)
from akili.verify.proof import verify_and_answer
from akili.verify.z3_checks import Z3CheckResult, Z3Issue, run_z3_checks

__all__ = [
    "AnswerWithProof", "ComparisonResult", "ConfidenceScore",
    "ProofChain", "ProofPoint", "ProofStep", "Refuse",
    "compare_documents", "format_comparison_response", "try_derived_queries",
    "verify_and_answer", "run_z3_checks", "Z3CheckResult", "Z3Issue",
]
