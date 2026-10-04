"""
gates/sanitizer.py

Automated patch sanitizer and pruner.
Detects and strips accidental scratch reproduction files (e.g., reproduce_error.py,
reproduce.py, test_edge_cases.py) from candidate patches before submission.
"""

from io import StringIO
from typing import Tuple, List
from unidiff import PatchSet
from .scope_checker import fix_short_hunk_patch


SCRATCH_PATTERNS = [
    "reproduce",
    "repro",
    "test_edge_cases",
    "test_fix",
    "test_patch",
    "reproduce_issue",
    "reproduce_error",
]


class PatchSanitizer:
    """
    Cleans candidate patches by stripping out scratch reproduction scripts
    leaked by agents during reasoning.
    """

    @staticmethod
    def is_scratch_file(file_path: str) -> bool:
        normalized = file_path.replace("\\", "/").lower()
        base_name = normalized.split("/")[-1]
        name_no_ext = base_name.rsplit(".", 1)[0]
        
        # Check if the file is in root directory and matches scratch patterns
        is_root_or_top = "/" not in normalized or len(normalized.split("/")) <= 2
        matches_pattern = any(p in name_no_ext for p in SCRATCH_PATTERNS)
        
        return is_root_or_top and matches_pattern

    def sanitize(self, patch_str: str) -> Tuple[str, List[str]]:
        """
        Removes scratch files from the patch.
        Returns: (sanitized_patch_str, list_of_pruned_files)
        """
        if not patch_str or not patch_str.strip():
            return patch_str, []

        repaired_patch = fix_short_hunk_patch(patch_str)
        try:
            patch_set = PatchSet(StringIO(repaired_patch))
        except Exception:
            return patch_str, []

        pruned_files = []
        clean_file_diffs = []

        for patched_file in patch_set:
            file_path = patched_file.path
            if self.is_scratch_file(file_path):
                pruned_files.append(file_path)
            else:
                clean_file_diffs.append(str(patched_file))

        sanitized_patch = "".join(clean_file_diffs)
        return sanitized_patch, pruned_files
