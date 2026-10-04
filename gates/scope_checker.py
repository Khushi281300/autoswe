"""
gates/scope_checker.py

Oracle-free AST and structural scope checker for APR candidate patches.
Ensures candidate patches adhere to problem localization bounds without
relying on the ground-truth developer patch or hidden tests.
"""

import os
import re
from io import StringIO
from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional, Any
from unidiff import PatchSet, PatchedFile, Hunk


@dataclass
class ScopeMetrics:
    num_files_modified: int = 0
    num_hunks: int = 0
    lines_added: int = 0
    lines_deleted: int = 0
    total_churn: int = 0
    modified_files: List[str] = field(default_factory=list)
    modified_test_files: List[str] = field(default_factory=list)
    modified_non_code_files: List[str] = field(default_factory=list)
    files_unrelated_to_issue: List[str] = field(default_factory=list)
    signature_modifications: List[str] = field(default_factory=list)
    broad_exception_swallows: int = 0
    dummy_constant_returns: int = 0


@dataclass
class ScopeCheckResult:
    is_valid: bool
    rejection_reasons: List[str] = field(default_factory=list)
    metrics: ScopeMetrics = field(default_factory=ScopeMetrics)
    diagnostic_message: str = ""


def fix_short_hunk_patch(patch_content: str, retry: int = 0) -> str:
    """Repairs patches with slightly miscounted hunk lengths."""
    try:
        PatchSet(StringIO(patch_content))
        return patch_content
    except Exception:
        if retry >= 4:
            return patch_content
        return fix_short_hunk_patch(patch_content + "\n ", retry + 1)


class ScopeChecker:
    """
    Evaluates candidate patches against issue descriptions and structural bounds
    purely using generation-time information (Oracle-Free).
    """

    def __init__(
        self,
        max_files_modified: int = 4,
        max_total_churn: int = 250,
        allow_test_file_modification: bool = False,
        allow_non_code_modification: bool = False,
        enforce_issue_mention_relevance: bool = True,
    ):
        self.max_files_modified = max_files_modified
        self.max_total_churn = max_total_churn
        self.allow_test_file_modification = allow_test_file_modification
        self.allow_non_code_modification = allow_non_code_modification
        self.enforce_issue_mention_relevance = enforce_issue_mention_relevance

    @staticmethod
    def is_test_file(file_path: str) -> bool:
        """Determines if a file path belongs to a test suite."""
        normalized = file_path.replace("\\", "/").lower()
        parts = normalized.split("/")
        filename = parts[-1]
        
        # Directory check
        if any(p in ("tests", "testing", "test", "unittest") for p in parts[:-1]):
            return True
        # Filename convention check
        if filename.startswith("test_") or filename.endswith("_test.py") or filename.endswith("tests.py"):
            return True
        return False

    @staticmethod
    def is_code_file(file_path: str) -> bool:
        """Determines if a file path is a Python source code file."""
        return file_path.lower().endswith((".py", ".pyx", ".pyi"))

    @staticmethod
    def extract_symbols_from_issue(problem_statement: str) -> Dict[str, Set[str]]:
        """
        Extracts files, function names, classes, and stack traces mentioned in the issue.
        Oracle-free: extracts directly from user bug report.
        """
        extracted = {
            "file_basenames": set(),
            "paths": set(),
            "stack_trace_files": set(),
            "symbols": set(),
        }
        if not problem_statement:
            return extracted

        # 1. Stack trace patterns: File "...", line 123, in foo
        stack_trace_pattern = re.compile(r'File\s+["\']([^"\']+\.py)["\']', re.IGNORECASE)
        for match in stack_trace_pattern.finditer(problem_statement):
            full_path = match.group(1).replace("\\", "/")
            extracted["stack_trace_files"].add(full_path)
            extracted["file_basenames"].add(os.path.basename(full_path).lower())

        # 2. General Python file mentions (e.g. `models/fields.py` or `fields.py`)
        file_mention_pattern = re.compile(r'([a-zA-Z0-9_\-\\/]+\.py)', re.IGNORECASE)
        for match in file_mention_pattern.finditer(problem_statement):
            path_str = match.group(1).replace("\\", "/").strip("/")
            extracted["paths"].add(path_str.lower())
            extracted["file_basenames"].add(os.path.basename(path_str).lower())

        # 3. Code identifiers (e.g. backticked symbols `my_function` or CamelCase classes)
        code_identifier_pattern = re.compile(r'`([a-zA-Z_][a-zA-Z0-9_.]*)`')
        for match in code_identifier_pattern.finditer(problem_statement):
            ident = match.group(1)
            extracted["symbols"].add(ident)
            if "." in ident:
                for subpart in ident.split("."):
                    if len(subpart) > 2:
                        extracted["symbols"].add(subpart)

        return extracted

    def check(self, candidate_patch: str, problem_statement: str = "") -> ScopeCheckResult:
        """
        Validates the candidate patch against scope rules.
        """
        rejection_reasons = []
        metrics = ScopeMetrics()

        if not candidate_patch or not candidate_patch.strip():
            return ScopeCheckResult(
                is_valid=False,
                rejection_reasons=["EMPTY_PATCH: Patch contains no changes."],
                metrics=metrics,
                diagnostic_message="Patch is empty.",
            )

        repaired_patch = fix_short_hunk_patch(candidate_patch)
        try:
            patch_set = PatchSet(StringIO(repaired_patch))
        except Exception as e:
            return ScopeCheckResult(
                is_valid=False,
                rejection_reasons=[f"MALFORMED_PATCH: Failed to parse unified diff: {str(e)}"],
                metrics=metrics,
                diagnostic_message="Patch is not a valid unified diff.",
            )


        issue_context = self.extract_symbols_from_issue(problem_statement)

        # Iterate over modified files
        for patched_file in patch_set:
            file_path = patched_file.path
            metrics.num_files_modified += 1
            metrics.modified_files.append(file_path)

            # 1. Test file check
            if self.is_test_file(file_path):
                metrics.modified_test_files.append(file_path)
                if not self.allow_test_file_modification:
                    rejection_reasons.append(
                        f"TEST_FILE_TAMPERING: Candidate patch modifies test file '{file_path}'."
                    )

            # 2. Non-code file check
            if not self.is_code_file(file_path):
                metrics.modified_non_code_files.append(file_path)
                if not self.allow_non_code_modification:
                    rejection_reasons.append(
                        f"NON_CODE_FILE_MODIFICATION: Candidate patch modifies non-Python file '{file_path}'."
                    )

            # 3. Check relevance to issue mentions (if issue provided)
            if self.enforce_issue_mention_relevance and problem_statement:
                base_name = os.path.basename(file_path).lower()
                normalized_path = file_path.replace("\\", "/").lower()

                matches_issue = False
                # Direct basename match
                if base_name in issue_context["file_basenames"]:
                    matches_issue = True
                # Partial path match
                elif any(p in normalized_path or normalized_path in p for p in issue_context["paths"]):
                    matches_issue = True
                # Stack trace match
                elif any(st in normalized_path or normalized_path in st for st in issue_context["stack_trace_files"]):
                    matches_issue = True

                # If no file path match, check if any prominent symbol mentioned in issue appears in patch diff
                if not matches_issue:
                    hunk_text = "\n".join(str(h) for h in patched_file)
                    for sym in issue_context["symbols"]:
                        if len(sym) >= 4 and sym in hunk_text:
                            matches_issue = True
                            break

                # If the issue mentions specific files and this file is completely alien to all of them
                if not matches_issue and (issue_context["file_basenames"] or issue_context["paths"]):
                    metrics.files_unrelated_to_issue.append(file_path)
                    # We flag a warning/rejection if multiple files are touched and none match
                    rejection_reasons.append(
                        f"OUT_OF_SCOPE_FILE: Modified file '{file_path}' has no lexical or structural link to the issue report."
                    )

            # 4. Hunks and line counts
            for hunk in patched_file:
                metrics.num_hunks += 1
                for line in hunk:
                    if line.is_added:
                        metrics.lines_added += 1
                        line_str = line.value.strip()
                        # Detect exception swallowing cheat: except: pass or except Exception: pass
                        if re.match(r'^except(\s+Exception)?:\s*(pass|\.\.\.)\s*$', line_str):
                            metrics.broad_exception_swallows += 1
                            rejection_reasons.append(
                                f"EXCEPTION_SUPPRESSION: Candidate patch swallows exceptions silently: '{line_str}'."
                            )
                    elif line.is_removed:
                        metrics.lines_deleted += 1

        metrics.total_churn = metrics.lines_added + metrics.lines_deleted

        # 5. Churn thresholds
        if metrics.num_files_modified > self.max_files_modified:
            rejection_reasons.append(
                f"EXCESSIVE_FILES_MODIFIED: Patch touches {metrics.num_files_modified} files (threshold: {self.max_files_modified})."
            )

        if metrics.total_churn > self.max_total_churn:
            rejection_reasons.append(
                f"EXCESSIVE_CHURN: Total lines changed is {metrics.total_churn} (threshold: {self.max_total_churn})."
            )

        is_valid = len(rejection_reasons) == 0
        diagnostic = "PASSED: Patch meets all scope and invariant checks." if is_valid else "; ".join(rejection_reasons)

        return ScopeCheckResult(
            is_valid=is_valid,
            rejection_reasons=rejection_reasons,
            metrics=metrics,
            diagnostic_message=diagnostic,
        )
