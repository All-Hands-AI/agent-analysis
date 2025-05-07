import pytest
import unidiff

from analysis.models.patch import _apply_file_patch


@pytest.fixture
def simple_source():
    """Fixture providing a simple 3-line source text."""
    return "line 1\nline 2\nline 3\n"


@pytest.fixture
def longer_source():
    """Fixture providing a 10-line source text."""
    return "\n".join([f"line {i}" for i in range(1, 11)]) + "\n"


def create_patch(patch_str):
    """Helper function to create a PatchedFile from a patch string."""
    return unidiff.PatchSet.from_string(patch_str)[0]


def test_apply_diff_no_changes(simple_source):
    """Test when the diff has no changes."""
    patch_str = """--- file.py
+++ file.py
@@ -1,3 +1,3 @@
 line 1
 line 2
 line 3
"""
    file_patch = create_patch(patch_str)
    result = _apply_file_patch(simple_source, file_patch)
    assert result == simple_source


def test_apply_diff_add_single_line(simple_source):
    """Test adding a single line to the source."""
    patch_str = """--- file.py
+++ file.py
@@ -1,3 +1,4 @@
 line 1
 line 2
+new line
 line 3
"""
    file_patch = create_patch(patch_str)
    result = _apply_file_patch(simple_source, file_patch)
    assert result == "line 1\nline 2\nnew line\nline 3\n"


def test_apply_diff_remove_single_line(simple_source):
    """Test removing a single line from the source."""
    patch_str = """--- file.py
+++ file.py
@@ -1,3 +1,2 @@
 line 1
-line 2
 line 3
"""
    file_patch = create_patch(patch_str)
    result = _apply_file_patch(simple_source, file_patch)
    assert result == "line 1\nline 3\n"


def test_apply_diff_modify_line(simple_source):
    """Test modifying a line in the source."""
    patch_str = """--- file.py
+++ file.py
@@ -1,3 +1,3 @@
 line 1
-line 2
+modified line
 line 3
"""
    file_patch = create_patch(patch_str)
    result = _apply_file_patch(simple_source, file_patch)
    assert result == "line 1\nmodified line\nline 3\n"


def test_apply_diff_multiple_hunks():
    """Test applying multiple hunks in one diff."""
    source = "line 1\nline 2\nline 3\nline 4\nline 5\n"
    patch_str = """--- file.py
+++ file.py
@@ -1,3 +1,4 @@
 line 1
+inserted line
 line 2
 line 3
@@ -3,3 +4,2 @@
 line 3
 line 4
-line 5
"""
    file_patch = create_patch(patch_str)
    result = _apply_file_patch(source, file_patch)
    assert result == "line 1\ninserted line\nline 2\nline 3\nline 4\n"


def test_apply_diff_empty_source():
    """Test applying a diff to an empty source."""
    source = ""
    patch_str = """--- file.py
+++ file.py
@@ -0,0 +1,2 @@
+line 1
+line 2
"""
    file_patch = create_patch(patch_str)
    result = _apply_file_patch(source, file_patch)
    assert result == "line 1\nline 2\n"


def test_apply_diff_large_changes(longer_source):
    """Test applying large changes to source."""
    patch_str = """--- file.py
+++ file.py
@@ -1,10 +1,5 @@
-line 1
-line 2
-line 3
+new line 1
+new line 2
 line 4
 line 5
-line 6
-line 7
-line 8
-line 9
-line 10
+new line 3
"""
    file_patch = create_patch(patch_str)
    result = _apply_file_patch(longer_source, file_patch)
    assert result == "new line 1\nnew line 2\nline 4\nline 5\nnew line 3\n"


def test_apply_diff_insert_at_beginning(simple_source):
    """Test inserting lines at the beginning of the file."""
    patch_str = """--- file.py
+++ file.py
@@ -1,3 +1,5 @@
+first new line
+second new line
 line 1
 line 2
 line 3
"""
    file_patch = create_patch(patch_str)
    result = _apply_file_patch(simple_source, file_patch)
    assert result == "first new line\nsecond new line\nline 1\nline 2\nline 3\n"


def test_apply_diff_insert_at_end(simple_source):
    """Test inserting lines at the end of the file."""
    patch_str = """--- file.py
+++ file.py
@@ -1,3 +1,5 @@
 line 1
 line 2
 line 3
+new line at end
+another new line
"""
    file_patch = create_patch(patch_str)
    result = _apply_file_patch(simple_source, file_patch)
    assert result == "line 1\nline 2\nline 3\nnew line at end\nanother new line\n"


def test_apply_diff_replace_entire_file(simple_source):
    """Test replacing the entire file."""
    patch_str = """--- file.py
+++ file.py
@@ -1,3 +1,3 @@
-line 1
-line 2
-line 3
+completely
+new
+content
"""
    file_patch = create_patch(patch_str)
    result = _apply_file_patch(simple_source, file_patch)
    assert result == "completely\nnew\ncontent\n"

def test_apply_diff_complex_mixed_changes(longer_source):
    """Test a complex diff with mixed changes throughout the file."""
    patch_str = """--- file.py
+++ file.py
@@ -1,4 +1,5 @@
-line 1
+header line
+new line 1
 line 2
 line 3
 line 4
@@ -6,5 +7,5 @@
 line 6
 line 7
-line 8
-line 9
-line 10
+modified line 8
+final line
+EOF line
"""
    file_patch = create_patch(patch_str)
    result = _apply_file_patch(longer_source, file_patch)
    expected = "header line\nnew line 1\nline 2\nline 3\nline 4\nline 5\nline 6\nline 7\nmodified line 8\nfinal line\nEOF line\n"
    assert result == expected