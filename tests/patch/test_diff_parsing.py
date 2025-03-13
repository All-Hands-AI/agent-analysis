from analysis.models.patch import _parse_git_diff

def test_simple_removal():
    """Test parsing a diff with a simple line removal."""
    diff = """
--- a/file.py
+++ b/file.py
@@ -10,7 +10,6 @@ def some_function():
    print("Hello")
    print("World")
-    print("To Remove")
    print("Goodbye")
"""
    result = _parse_git_diff(diff)
    assert "file.py" in result
    assert result["file.py"] == {12}  # Line 12 was removed

def test_simple_addition():
    """Test parsing a diff with a simple line addition."""
    diff = """
--- a/file.py
+++ b/file.py
@@ -10,6 +10,7 @@ def some_function():
    print("Hello")
    print("World")
+    print("New Line")
    print("Goodbye")
"""
    result = _parse_git_diff(diff)
    assert "file.py" in result
    assert result["file.py"] == {12}  # Addition happened at line 12

def test_multiple_changes():
    """Test parsing a diff with multiple additions and removals."""
    diff = """
--- a/file.py
+++ b/file.py
@@ -10,8 +10,9 @@ def some_function():
    print("Hello")
    print("World")
-    print("Old Line 1")
-    print("Old Line 2")
+    print("New Line 1")
+    print("New Line 2")
+    print("New Line 3")
    print("Goodbye")
"""
    result = _parse_git_diff(diff)
    assert "file.py" in result
    assert result["file.py"] == {12, 13, 14}  # Lines 12 and 13 were modified

def test_multiple_files():
    """Test parsing a diff with changes to multiple files."""
    diff = """
--- a/file1.py
+++ b/file1.py
@@ -5,6 +5,7 @@ def func1():
    pass
+    print("New")
    

--- a/file2.py
+++ b/file2.py
@@ -10,7 +10,6 @@ def func2():
    print("Hello")
-    print("Remove")
    print("World")
"""
    result = _parse_git_diff(diff)
    assert "file1.py" in result
    assert "file2.py" in result
    assert result["file1.py"] == {6}
    assert result["file2.py"] == {11}

def test_new_file():
    """Test parsing a diff with a new file."""
    diff = """
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,5 @@
+# New file
+def new_function():
+    print("Hello")
+    return True
+
"""
    result = _parse_git_diff(diff)
    assert "new_file.py" in result
    assert result["new_file.py"] == {0}  # New files mark line 0 as changed

def test_deleted_file():
    """Test parsing a diff with a deleted file."""
    diff = """
--- a/deleted_file.py
+++ /dev/null
@@ -1,5 +0,0 @@
-# Deleted file
-def old_function():
-    print("Goodbye")
-    return False
-
"""
    result = _parse_git_diff(diff)
    assert "deleted_file.py" in result
    assert result["deleted_file.py"] == {1, 2, 3, 4, 5}  # All lines were removed

def test_complex_diff():
    """Test parsing a more complex diff with multiple hunks."""
    diff = """
--- a/complex.py
+++ b/complex.py
@@ -5,7 +5,8 @@ def start():
    print("Start")
-    do_something()
+    # Modified line
+    do_something_else()
    

@@ -20,6 +21,7 @@ def middle():
    print("Middle")
+    new_function()
    

@@ -35,7 +37,6 @@ def end():
    print("End")
-    cleanup()
    return True
"""
    result = _parse_git_diff(diff)
    assert "complex.py" in result
    assert result["complex.py"] == {6, 7, 21, 36}

def test_missing_file_header():
    """Test parsing a diff with a missing file header."""
    diff = """
@@ -10,7 +10,6 @@ def some_function():
    print("Hello")
    print("World")
-    print("To Remove")
    print("Goodbye")
"""
    result = _parse_git_diff(diff)
    assert result == {}  # No file header, so no changes recorded

def test_malformed_hunk_header():
    """Test parsing a diff with a malformed hunk header."""
    diff = """
--- a/file.py
+++ b/file.py
@@ invalid,7 +10,6 @@ def some_function():
    print("Hello")
    print("World")
-    print("To Remove")
    print("Goodbye")
"""
    # Should not raise an exception, but should also not record any changes
    result = _parse_git_diff(diff)
    assert "file.py" in result
    assert len(result["file.py"]) == 0  # No changes recorded due to invalid hunk header