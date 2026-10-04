"""
Oracle-Free Verification Gates for LLM Issue-Resolving Agents.
"""

from .scope_checker import ScopeChecker, ScopeCheckResult
from .behavior_checker import BehaviorChecker, BehaviorCheckResult

__all__ = [
    "ScopeChecker",
    "ScopeCheckResult",
    "BehaviorChecker",
    "BehaviorCheckResult",
]

