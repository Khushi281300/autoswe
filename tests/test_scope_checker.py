"""
Unit tests for gates/scope_checker.py
"""

import pytest
from gates.scope_checker import ScopeChecker


VALID_PATCH = """--- a/django/db/models/fields/__init__.py
+++ b/django/db/models/fields/__init__.py
@@ -100,2 +100,4 @@ class Field:
     def to_python(self, value):
+        if value is None:
+            return None
         return value
"""

TEST_TAMPERING_PATCH = """--- a/tests/model_fields/test_fields.py
+++ b/tests/model_fields/test_fields.py
@@ -50,2 +50,2 @@ class TestField:
     def test_none(self):
-        self.assertEqual(1, 2)
+        self.assertEqual(1, 1)
"""

DOC_TAMPERING_PATCH = """--- a/docs/intro/tutorial01.txt
+++ b/docs/intro/tutorial01.txt
@@ -10,2 +10,2 @@ Tutorial
-Old documentation line
+New documentation line
"""

EXCEPTION_SWALLOW_PATCH = """--- a/django/db/models/fields/__init__.py
+++ b/django/db/models/fields/__init__.py
@@ -120,2 +120,5 @@ class Field:
     def clean(self, value):
+        try:
+            return int(value)
+        except Exception: pass
         return value
"""

UNRELATED_FILE_PATCH = """--- a/unrelated/subsystem/analytics.py
+++ b/unrelated/subsystem/analytics.py
@@ -10,2 +10,3 @@ def log():
+    pass
     return True
"""


def test_valid_patch():
    checker = ScopeChecker()
    issue = "Bug in `django/db/models/fields/__init__.py` where Field.to_python crashes on None."
    res = checker.check(VALID_PATCH, problem_statement=issue)
    assert res.is_valid is True
    assert len(res.rejection_reasons) == 0
    assert res.metrics.num_files_modified == 1
    assert res.metrics.total_churn == 2


def test_test_file_tampering():
    checker = ScopeChecker(allow_test_file_modification=False)
    issue = "Error in field conversion."
    res = checker.check(TEST_TAMPERING_PATCH, problem_statement=issue)
    assert res.is_valid is False
    assert any("TEST_FILE_TAMPERING" in r for r in res.rejection_reasons)


def test_non_code_file_modification():
    checker = ScopeChecker(allow_non_code_modification=False)
    issue = "Issue with field validation."
    res = checker.check(DOC_TAMPERING_PATCH, problem_statement=issue)
    assert res.is_valid is False
    assert any("NON_CODE_FILE_MODIFICATION" in r for r in res.rejection_reasons)


def test_exception_suppression():
    checker = ScopeChecker()
    issue = "Error in field clean method."
    res = checker.check(EXCEPTION_SWALLOW_PATCH, problem_statement=issue)
    assert res.is_valid is False
    assert any("EXCEPTION_SUPPRESSION" in r for r in res.rejection_reasons)


def test_unrelated_file_rejection():
    checker = ScopeChecker(enforce_issue_mention_relevance=True)
    issue = "Traceback found in File \"django/core/handlers.py\", line 42 in get_response."
    res = checker.check(UNRELATED_FILE_PATCH, problem_statement=issue)
    assert res.is_valid is False
    assert any("OUT_OF_SCOPE_FILE" in r for r in res.rejection_reasons)


if __name__ == "__main__":
    pytest.main([__file__])
