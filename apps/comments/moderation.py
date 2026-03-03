"""Backward-compat shim — canonical location is comments.services."""
from comments.services import evaluate_comment_risk

__all__ = ["evaluate_comment_risk"]
