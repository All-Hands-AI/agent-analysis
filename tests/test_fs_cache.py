import pytest
from unittest.mock import patch, MagicMock, call

# Import the fs_cache implementation
# Assuming the fs_cache is in a module called cache_utils.py
from analysis.utility import fs_cache

# Test fixture to manage environment variables using pytest's monkeypatch
@pytest.fixture
def clean_env(monkeypatch):
    # monkeypatch automatically cleans up after each test
    monkeypatch.delenv('FS_CACHE_INVALIDATE', raising=False)
    monkeypatch.delenv('FS_CACHE_DISABLE', raising=False)
    return monkeypatch

# Mock expensive function for testing
@pytest.fixture
def mock_expensive_func():
    mock_func = MagicMock(return_value="expensive result")
    return mock_func

# Test class to verify behavior with methods
class TestClass:
    def __init__(self):
        self.counter = 0
    
    @fs_cache()
    def cached_method(self, arg):
        self.counter += 1
        return f"result-{arg}-{self.counter}"


def test_basic_caching(clean_env, tmp_path, mock_expensive_func):
    """Test that the function is only called once when cached."""
    # Create a cache directory within pytest's temporary directory
    cache_dir = tmp_path / "cache"
    
    # Create decorated function
    decorated_func = fs_cache(cache_dir=str(cache_dir))(mock_expensive_func)
    
    # Call function twice with same arguments
    result1 = decorated_func("test_arg")
    result2 = decorated_func("test_arg")
    
    # Verify results are equal
    assert result1 == result2
    
    # Verify function was only called once
    assert mock_expensive_func.call_count == 1
    mock_expensive_func.assert_called_once_with("test_arg")


def test_different_args_different_cache(clean_env, tmp_path, mock_expensive_func):
    """Test that different arguments result in different cache entries."""
    cache_dir = tmp_path / "cache"
    
    # Create decorated function
    decorated_func = fs_cache(cache_dir=str(cache_dir))(mock_expensive_func)
    
    # Call function with different arguments
    decorated_func("arg1")
    decorated_func("arg2")
    
    # Verify function was called twice with different arguments
    assert mock_expensive_func.call_count == 2
    mock_expensive_func.assert_has_calls([call("arg1"), call("arg2")])


def test_cache_invalidation(clean_env, tmp_path, mock_expensive_func):
    """Test that cache is invalidated when the environment variable is set."""
    cache_dir = tmp_path / "cache"
    
    # Create decorated function
    decorated_func = fs_cache(cache_dir=str(cache_dir))(mock_expensive_func)
    
    # Call function once to cache result
    result1 = decorated_func("test_arg")
    
    # Set environment variable to invalidate cache
    clean_env.setenv('FS_CACHE_INVALIDATE', '1')
    
    # Call function again with same argument
    result2 = decorated_func("test_arg")
    
    # Verify results are equal (function returns same value)
    assert result1 == result2
    
    # Verify function was called twice
    assert mock_expensive_func.call_count == 2
    mock_expensive_func.assert_has_calls([call("test_arg"), call("test_arg")])


def test_cache_disable(clean_env, tmp_path, mock_expensive_func):
    """Test that caching is disabled when the environment variable is set."""
    cache_dir = tmp_path / "cache"
    
    # Create decorated function
    decorated_func = fs_cache(cache_dir=str(cache_dir))(mock_expensive_func)
    
    # Set environment variable to disable cache
    clean_env.setenv('FS_CACHE_DISABLE', '1')
    
    # Call function twice with same arguments
    decorated_func("test_arg")
    decorated_func("test_arg")
    
    # Verify function was called twice (caching was disabled)
    assert mock_expensive_func.call_count == 2
    mock_expensive_func.assert_has_calls([call("test_arg"), call("test_arg")])


def test_custom_env_vars(clean_env, tmp_path, mock_expensive_func):
    """Test that custom environment variable names work."""
    cache_dir = tmp_path / "cache"
    
    # Create decorated function with custom env var names
    decorated_func = fs_cache(
        cache_dir=str(cache_dir),
        env_invalidate="CUSTOM_INVALIDATE",
        env_disable="CUSTOM_DISABLE"
    )(mock_expensive_func)
    
    # Call function once to cache result
    decorated_func("test_arg")
    
    # Standard env vars should have no effect
    clean_env.setenv('FS_CACHE_INVALIDATE', '1')
    decorated_func("test_arg")
    
    # Custom env vars should work
    clean_env.setenv('CUSTOM_INVALIDATE', '1')
    decorated_func("test_arg")
    
    # Verify function was called twice (once for initial and once for custom invalidate)
    assert mock_expensive_func.call_count == 2


def test_method_caching(clean_env, tmp_path):
    """Test that the decorator works properly for class methods."""
    # Patch the fs_cache to use our temporary directory
    with patch('cache_utils.fs_cache', fs_cache(cache_dir=str(tmp_path / "cache"))):
        # Create instance and call method twice
        instance = TestClass()
        result1 = instance.cached_method("arg")
        result2 = instance.cached_method("arg")
        
        # Results should be the same (cached) even though counter incremented
        assert result1 == result2
        
        # Counter should only be incremented once
        assert instance.counter == 1


def test_pickle_failure(clean_env, tmp_path):
    """Test that the function handles pickle failures gracefully."""
    cache_dir = tmp_path / "cache"
    
    # Create a function that returns an unpicklable object
    def unpicklable_func():
        # Create an object with a cycle - this cannot be pickled
        a = {}
        a['self'] = a
        return a
    
    # Create decorated function
    decorated_func = fs_cache(cache_dir=str(cache_dir))(unpicklable_func)
    
    # Call function - should not raise an error
    with patch('builtins.print') as mock_print:
        decorated_func()
    
    # Should print a warning
    mock_print.assert_called_once()
    assert "Warning" in mock_print.call_args[0][0]


def test_cache_read_failure(clean_env, tmp_path):
    """Test that the function handles cache read failures gracefully."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(exist_ok=True)
    
    # Create a cached result file with invalid data
    @fs_cache(cache_dir=str(cache_dir))
    def simple_func():
        return "result"
    
    # Call once to create cache
    simple_func()
    
    # Find the cache file
    cache_files = list(cache_dir.iterdir())
    assert len(cache_files) == 1
    
    # Corrupt the cache file
    with open(cache_files[0], 'w') as f:
        f.write("This is not valid pickle data")
    
    # Call function again - should regenerate result
    result = simple_func()
    assert result == "result"
