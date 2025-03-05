import unidiff

from analysis.models.patch import _find_changed_locations
from tests.patch.utility import git_diff


def create_patch(
    original: str, modified: str, filename: str = "test.py"
) -> unidiff.PatchedFile:
    """Helper function to create a PatchedFile from original and modified code."""

    patch_text = git_diff(original, modified, filename=filename)
    patch_set = unidiff.PatchSet(patch_text)
    return patch_set[0]


def test_top_level_changes():
    """Test that top-level changes have empty scope lists."""
    original = """x = 1
y = 2
"""
    modified = """x = 1
y = 3  # Changed value
"""
    patch = create_patch(original, modified)
    locations = _find_changed_locations(original, patch)

    assert len(locations) == 1
    assert [scope.name for scope in locations[0].scopes] == ["test.py"]
    assert locations[0].line == 2


def test_function_scope():
    """Test that changes in functions are tracked with the correct scope."""
    original = """def test_func():
    x = 1
    return x
"""
    modified = """def test_func():
    x = 2  # Changed value
    return x
"""
    patch = create_patch(original, modified)
    locations = _find_changed_locations(original, patch)

    assert len(locations) == 1
    assert [scope.name for scope in locations[0].scopes] == ["test.py", "test_func"]
    assert locations[0].line == 2


def test_class_scope():
    """Test that changes in classes are tracked with the correct scope."""
    original = """class TestClass:
    x = 1
"""
    modified = """class TestClass:
    x = 2  # Changed value
"""
    patch = create_patch(original, modified)
    locations = _find_changed_locations(original, patch)

    assert len(locations) == 1
    assert [scope.name for scope in locations[0].scopes] == ["test.py", "TestClass"]
    assert locations[0].line == 2


def test_method_in_class():
    """Test that changes in class methods are tracked correctly."""
    original = """class TestClass:
    def test_method(self):
        return 1
"""
    modified = """class TestClass:
    def test_method(self):
        return 2  # Changed value
"""
    patch = create_patch(original, modified)
    locations = _find_changed_locations(original, patch)

    assert len(locations) == 1
    assert [scope.name for scope in locations[0].scopes] == [
        "test.py",
        "TestClass",
        "test_method",
    ]
    assert locations[0].line == 3


def test_class_in_function():
    """Test that classes nested in functions are tracked correctly."""
    original = """def outer_func():
    class InnerClass:
        x = 1
    return InnerClass()
"""
    modified = """def outer_func():
    class InnerClass:
        x = 2  # Changed value
    return InnerClass()
"""
    patch = create_patch(original, modified)
    locations = _find_changed_locations(original, patch)

    assert len(locations) == 1
    assert [scope.name for scope in locations[0].scopes] == [
        "test.py",
        "outer_func",
        "InnerClass",
    ]
    assert locations[0].line == 3


def test_nested_functions():
    """Test that nested functions are tracked correctly."""
    original = """def outer_func():
    def inner_func():
        return 1
    return inner_func()
"""
    modified = """def outer_func():
    def inner_func():
        return 2  # Changed value
    return inner_func()
"""
    patch = create_patch(original, modified)
    locations = _find_changed_locations(original, patch)

    assert len(locations) == 1
    assert [scope.name for scope in locations[0].scopes] == [
        "test.py",
        "outer_func",
        "inner_func",
    ]
    assert locations[0].line == 3


def test_nested_classes():
    """Test that nested classes are tracked correctly."""
    original = """class OuterClass:
    class InnerClass:
        x = 1
"""
    modified = """class OuterClass:
    class InnerClass:
        x = 2  # Changed value
"""
    patch = create_patch(original, modified)
    locations = _find_changed_locations(original, patch)

    assert len(locations) == 1
    assert [scope.name for scope in locations[0].scopes] == [
        "test.py",
        "OuterClass",
        "InnerClass",
    ]
    assert locations[0].line == 3


def test_async_function():
    """Test that async functions are tracked correctly."""
    original = """async def async_func():
    return 1
"""
    modified = """async def async_func():
    return 2  # Changed value
"""
    patch = create_patch(original, modified)
    locations = _find_changed_locations(original, patch)

    assert len(locations) == 1
    assert [scope.name for scope in locations[0].scopes] == ["test.py", "async_func"]
    assert locations[0].line == 2


def test_multiline_change():
    """Test handling changes that span multiple lines."""
    original = """def func():
    x = (1 +
         2 +
         3)
"""
    modified = """def func():
    x = (10 +  # Changed
         20 +  # Changed
         30)   # Changed
"""
    patch = create_patch(original, modified)
    locations = _find_changed_locations(original, patch)

    # This should identify the change at least once within the function scope
    assert any(
        [scope.name for scope in loc.scopes] == ["test.py", "func"] for loc in locations
    )


def test_change_in_function_signature():
    """Test detecting changes in function signatures."""
    original = """def func(a, b):
    return a + b
"""
    modified = """def func(a, b, c=0):  # Added parameter
    return a + b
"""
    patch = create_patch(original, modified)
    locations = _find_changed_locations(original, patch)

    assert len(locations) == 1
    assert [scope.name for scope in locations[0].scopes] == ["test.py", "func"]


def test_deeply_nested_scopes():
    """Test deeply nested scopes."""
    original = """def level1():
    def level2():
        class Level3:
            def level4(self):
                def level5():
                    x = 1
                return level5()
        return Level3()
    return level2()
"""
    modified = """def level1():
    def level2():
        class Level3:
            def level4(self):
                def level5():
                    x = 2  # Changed
                return level5()
        return Level3()
    return level2()
"""
    patch = create_patch(original, modified)
    locations = _find_changed_locations(original, patch)

    assert len(locations) == 1
    assert [scope.name for scope in locations[0].scopes] == [
        "test.py",
        "level1",
        "level2",
        "Level3",
        "level4",
        "level5",
    ]
    assert locations[0].line == 6
