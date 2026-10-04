"""
gates/behavior_checker.py

Oracle-free behavioral contract and invariant checker for APR patches.
Inspects candidate patches for:
1. Public API signature mutations (breaking backward compatibility).
2. Silent exception suppression (cheating by swallowing errors).
3. Hardcoded literal return patterns (overfitting to unit test inputs).
4. Deletion of precondition / validation checks.
"""

import re
from io import StringIO
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from unidiff import PatchSet
from .scope_checker import fix_short_hunk_patch


@dataclass
class BehaviorMetrics:
    signature_changes: List[str] = field(default_factory=list)
    exception_suppressions: List[str] = field(default_factory=list)
    hardcoded_returns: List[str] = field(default_factory=list)
    deleted_validation_guards: List[str] = field(default_factory=list)
    total_violations: int = 0


@dataclass
class BehaviorCheckResult:
    is_valid: bool
    rejection_reasons: List[str] = field(default_factory=list)
    metrics: BehaviorMetrics = field(default_factory=BehaviorMetrics)
    diagnostic_message: str = ""


class BehaviorChecker:
    """
    Analyzes semantic patterns inside the candidate diff to prevent
    contract violations and test-overfitting cheats.
    """

    def __init__(
        self,
        allow_public_signature_change: bool = False,
        allow_exception_suppression: bool = False,
        allow_hardcoded_literals: bool = False,
    ):
        self.allow_public_signature_change = allow_public_signature_change
        self.allow_exception_suppression = allow_exception_suppression
        self.allow_hardcoded_literals = allow_hardcoded_literals

    @staticmethod
    def _is_public_function(func_name: str) -> bool:
        """Private/internal functions start with _ (except dunder methods)."""
        if func_name.startswith("__") and func_name.endswith("__"):
            return True  # dunder methods are part of Python interface contract
        return not func_name.startswith("_")

    def check(self, candidate_patch: str) -> BehaviorCheckResult:
        metrics = BehaviorMetrics()
        rejection_reasons = []

        if not candidate_patch or not candidate_patch.strip():
            return BehaviorCheckResult(
                is_valid=False,
                rejection_reasons=["EMPTY_PATCH: Patch contains no changes."],
                metrics=metrics,
                diagnostic_message="Patch is empty.",
            )

        repaired_patch = fix_short_hunk_patch(candidate_patch)
        try:
            patch_set = PatchSet(StringIO(repaired_patch))
        except Exception as e:
            return BehaviorCheckResult(
                is_valid=False,
                rejection_reasons=[f"MALFORMED_PATCH: Failed to parse diff: {str(e)}"],
                metrics=metrics,
                diagnostic_message="Invalid unified diff.",
            )

        # Regex patterns for behavioral smells
        func_def_pattern = re.compile(r'^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)\s*:')
        except_suppress_pattern = re.compile(
            r'^\s*except(\s+Exception|\s+BaseException)?\s*:\s*(pass|\.\.\.)\s*$'
        )
        single_line_hardcode = re.compile(
            r'^\s*if\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*==\s*(["\'][^"\']+["\']|\d+)\s*:\s*return\s+(["\'][^"\']+["\']|\d+|True|False|None)\s*$'
        )
        if_literal_cond = re.compile(
            r'^\s*if\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*==\s*(["\'][^"\']+["\']|\d+)\s*:\s*$'
        )
        return_literal_stmt = re.compile(
            r'^\s*return\s+(["\'][^"\']+["\']|\d+|True|False|None)\s*$'
        )
        raise_guard_pattern = re.compile(r'^\s*raise\s+([a-zA-Z_][a-zA-Z0-9_]*Error|ValueError|TypeError|KeyError)')

        for patched_file in patch_set:
            file_name = patched_file.path

            for hunk in patched_file:
                removed_funcs = {}
                added_funcs = {}
                removed_guards = []
                prev_added_if_var = None

                for line in hunk:
                    line_val = line.value.strip()

                    # Analyze removed lines
                    if line.is_removed:
                        func_match = func_def_pattern.match(line_val)
                        if func_match:
                            func_name, params = func_match.group(1), func_match.group(2)
                            removed_funcs[func_name] = params

                        if raise_guard_pattern.match(line_val):
                            removed_guards.append(line_val)

                    # Analyze added lines
                    elif line.is_added:
                        func_match = func_def_pattern.match(line_val)
                        if func_match:
                            func_name, params = func_match.group(1), func_match.group(2)
                            added_funcs[func_name] = params

                        # 1. Exception Suppression Check
                        if except_suppress_pattern.match(line_val):
                            metrics.exception_suppressions.append(f"{file_name}: {line_val}")
                            if not self.allow_exception_suppression:
                                rejection_reasons.append(
                                    f"EXCEPTION_SUPPRESSION: Swallowing exceptions in '{file_name}': '{line_val}'."
                                )

                        # 2. Hardcoded Return Check (Overfitting Cheat)
                        if single_line_hardcode.match(line_val):
                            metrics.hardcoded_returns.append(f"{file_name}: {line_val}")
                            if not self.allow_hardcoded_literals:
                                rejection_reasons.append(
                                    f"HARDCODED_TEST_OVERFIT: Hardcoded conditional return detected in '{file_name}': '{line_val}'."
                                )
                        elif prev_added_if_var and return_literal_stmt.match(line_val):
                            metrics.hardcoded_returns.append(f"{file_name}: if {prev_added_if_var}: {line_val}")
                            if not self.allow_hardcoded_literals:
                                rejection_reasons.append(
                                    f"HARDCODED_TEST_OVERFIT: Hardcoded conditional return for '{prev_added_if_var}' in '{file_name}': '{line_val}'."
                                )
                            prev_added_if_var = None
                        else:
                            cond_match = if_literal_cond.match(line_val)
                            prev_added_if_var = cond_match.group(1) if cond_match else None


                # 3. Signature Mutation Check (Contract drift)
                for fname, old_params in removed_funcs.items():
                    if fname in added_funcs:
                        new_params = added_funcs[fname]
                        if old_params.strip() != new_params.strip() and self._is_public_function(fname):
                            metrics.signature_changes.append(f"{file_name}::{fname}({old_params}) -> ({new_params})")
                            if not self.allow_public_signature_change:
                                rejection_reasons.append(
                                    f"PUBLIC_API_MUTATION: Breaking signature change on public function '{fname}' in '{file_name}'."
                                )

                # 4. Guard Deletion Check
                if removed_guards and not any("raise" in str(line) for line in hunk if line.is_added):
                    for g in removed_guards:
                        metrics.deleted_validation_guards.append(f"{file_name}: {g}")
                        rejection_reasons.append(
                            f"VALIDATION_GUARD_REMOVAL: Deleted error guard '{g}' without replacement in '{file_name}'."
                        )

        metrics.total_violations = len(rejection_reasons)
        is_valid = len(rejection_reasons) == 0
        diagnostic = "PASSED: All behavioral contract and invariant checks passed." if is_valid else "; ".join(rejection_reasons)

        return BehaviorCheckResult(
            is_valid=is_valid,
            rejection_reasons=rejection_reasons,
            metrics=metrics,
            diagnostic_message=diagnostic,
        )
