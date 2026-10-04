"""
Unit tests for gates/behavior_checker.py
"""

import pytest
from gates.behavior_checker import BehaviorChecker

VALID_FIX = """--- a/django/db/models/fields/__init__.py
+++ b/django/db/models/fields/__init__.py
@@ -100,2 +100,4 @@ class Field:
     def to_python(self, value):
+        if value is None:
+            return None
         return value
"""

SIGNATURE_CHANGE = """--- a/django/db/models/fields/__init__.py
+++ b/django/db/models/fields/__init__.py
@@ -50,2 +50,2 @@ class Field:
-    def validate(self, value, model_instance):
+    def validate(self, value, model_instance, extra_param):
         pass
"""

HARDCODED_RETURN = """--- a/django/db/models/fields/__init__.py
+++ b/django/db/models/fields/__init__.py
@@ -80,2 +80,4 @@ class Field:
     def get_prep_value(self, value):
+        if value == "magic_test_val":
+            return 42
         return value
"""

GUARD_DELETION = """--- a/django/db/models/fields/__init__.py
+++ b/django/db/models/fields/__init__.py
@@ -60,3 +60,1 @@ class Field:
     def check(self, value):
-        if not value:
-            raise ValueError("Value cannot be empty")
         return True
"""


def test_valid_behavior():
    checker = BehaviorChecker()
    res = checker.check(VALID_FIX)
    assert res.is_valid is True
    assert len(res.rejection_reasons) == 0


def test_signature_mutation():
    checker = BehaviorChecker()
    res = checker.check(SIGNATURE_CHANGE)
    assert res.is_valid is False
    assert any("PUBLIC_API_MUTATION" in r for r in res.rejection_reasons)


def test_hardcoded_return():
    checker = BehaviorChecker()
    res = checker.check(HARDCODED_RETURN)
    assert res.is_valid is False
    assert any("HARDCODED_TEST_OVERFIT" in r for r in res.rejection_reasons)


def test_guard_deletion():
    checker = BehaviorChecker()
    res = checker.check(GUARD_DELETION)
    assert res.is_valid is False
    assert any("VALIDATION_GUARD_REMOVAL" in r for r in res.rejection_reasons)


if __name__ == "__main__":
    pytest.main([__file__])
