"""
Unit tests for gates/composite_gate.py and gates/sanitizer.py
"""

import pytest
from gates.composite_gate import CompositeVerificationGate
from gates.sanitizer import PatchSanitizer

PATCH_WITH_SCRATCH = """--- a/django/db/models/fields/__init__.py
+++ b/django/db/models/fields/__init__.py
@@ -100,2 +100,4 @@ class Field:
     def to_python(self, value):
+        if value is None:
+            return None
         return value
--- /dev/null
+++ b/reproduce_error.py
@@ -0,0 +1,2 @@
+import django
+print("reproducing bug")
"""



def test_sanitizer_prunes_scratch_file():
    sanitizer = PatchSanitizer()
    clean_patch, pruned = sanitizer.sanitize(PATCH_WITH_SCRATCH)
    assert len(pruned) == 1
    assert "reproduce_error.py" in pruned[0]
    assert "reproduce_error.py" not in clean_patch
    assert "django/db/models/fields/__init__.py" in clean_patch


def test_composite_gate_with_auto_sanitize():
    gate = CompositeVerificationGate(auto_sanitize_scratch_files=True)
    issue = "Issue in `django/db/models/fields/__init__.py` where to_python crashes on None."
    res = gate.evaluate(PATCH_WITH_SCRATCH, problem_statement=issue)
    assert res.is_valid is True
    assert len(res.pruned_scratch_files) == 1
    assert "reproduce_error.py" in res.pruned_scratch_files[0]
    assert "PASSED" in res.diagnostic_feedback


def test_composite_gate_without_auto_sanitize_flags_scratch():
    gate = CompositeVerificationGate(auto_sanitize_scratch_files=False)
    issue = "Issue in `django/db/models/fields/__init__.py` where to_python crashes on None."
    res = gate.evaluate(PATCH_WITH_SCRATCH, problem_statement=issue)
    assert res.is_valid is False
    assert any("OUT_OF_SCOPE_FILE" in r for r in res.rejection_reasons)


if __name__ == "__main__":
    pytest.main([__file__])
