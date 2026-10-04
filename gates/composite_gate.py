"""
gates/composite_gate.py

Unified Verification Gate combining ScopeChecker, BehaviorChecker, and PatchSanitizer.
Provides a single interface for agentic repair loops (like AutoSWE) to validate candidate fixes.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from .scope_checker import ScopeChecker, ScopeCheckResult
from .behavior_checker import BehaviorChecker, BehaviorCheckResult
from .sanitizer import PatchSanitizer


@dataclass
class GateResult:
    is_valid: bool
    rejection_reasons: List[str] = field(default_factory=list)
    pruned_scratch_files: List[str] = field(default_factory=list)
    sanitized_patch: str = ""
    scope_result: Optional[ScopeCheckResult] = None
    behavior_result: Optional[BehaviorCheckResult] = None
    diagnostic_feedback: str = ""


class CompositeVerificationGate:
    """
    Unified gate pipeline that validates both structural scope and behavioral contracts.
    """

    def __init__(
        self,
        auto_sanitize_scratch_files: bool = True,
        scope_checker: Optional[ScopeChecker] = None,
        behavior_checker: Optional[BehaviorChecker] = None,
    ):
        self.auto_sanitize_scratch_files = auto_sanitize_scratch_files
        self.sanitizer = PatchSanitizer()
        self.scope_checker = scope_checker or ScopeChecker()
        self.behavior_checker = behavior_checker or BehaviorChecker()

    def evaluate(self, candidate_patch: str, problem_statement: str = "") -> GateResult:
        rejection_reasons = []
        pruned_files = []
        working_patch = candidate_patch

        # Step 1: Optional scratch sanitization
        if self.auto_sanitize_scratch_files:
            working_patch, pruned_files = self.sanitizer.sanitize(candidate_patch)

        # Step 2: Scope Check
        scope_res = self.scope_checker.check(working_patch, problem_statement=problem_statement)
        if not scope_res.is_valid:
            rejection_reasons.extend(scope_res.rejection_reasons)

        # Step 3: Behavior & Contract Check
        behavior_res = self.behavior_checker.check(working_patch)
        if not behavior_res.is_valid:
            rejection_reasons.extend(behavior_res.rejection_reasons)

        is_valid = len(rejection_reasons) == 0

        # Construct actionable diagnostic feedback for LLM agent
        if is_valid:
            feedback = "PASSED: Patch conforms to all structural scope and behavioral invariants."
            if pruned_files:
                feedback += f" (Note: Pruned untracked scratch reproduction files: {pruned_files})"
        else:
            feedback = "REJECTED BY VERIFICATION GATE:\n- " + "\n- ".join(rejection_reasons)
            feedback += "\nPlease revise your patch to stay within the problem scope and preserve contracts."

        return GateResult(
            is_valid=is_valid,
            rejection_reasons=rejection_reasons,
            pruned_scratch_files=pruned_files,
            sanitized_patch=working_patch,
            scope_result=scope_res,
            behavior_result=behavior_res,
            diagnostic_feedback=feedback,
        )
