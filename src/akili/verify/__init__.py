"""
Verification layer: proof check over canonical facts.

If answer is derivable → return answer + (x,y) proof.
If not → deterministic REFUSE.
"""

from akili.verify.models import AnswerWithProof, ProofPoint, Refuse
from akili.verify.proof import verify_and_answer

__all__ = ["AnswerWithProof", "ProofPoint", "Refuse", "verify_and_answer"]
