import os
import json
import hashlib
import functools
import pickle
from typing import Any, Callable, TypeVar, cast

T = TypeVar('T')

def fs_cache(
    cache_dir: str = '/tmp/fs_cache',
    env_invalidate: str = 'FS_CACHE_INVALIDATE',
    env_disable: str = 'FS_CACHE_DISABLE'
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    A decorator that caches the result of any function to the filesystem.
    
    The cache behavior can be controlled via environment variables:
    - Setting env_invalidate to any non-empty value will ignore existing cache but still save results
    - Setting env_disable to any non-empty value will completely disable caching
    
    Args:
        cache_dir: Directory to store cached results. Defaults to '/tmp/fs_cache'.
        env_invalidate: Environment variable name that controls cache invalidation.
            Defaults to 'FS_CACHE_INVALIDATE'.
        env_disable: Environment variable name that controls cache disabling.
            Defaults to 'FS_CACHE_DISABLE'.
        
    Returns:
        The decorated function with caching enabled according to environment variables.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Check if caching is completely disabled by env var
            cache_disabled = os.environ.get(env_disable, '') != ''
            if cache_disabled:
                return func(*args, **kwargs)
            
            # Create the cache directory if it doesn't exist
            os.makedirs(cache_dir, exist_ok=True)
            
            # Generate a cache key based on the function name and arguments
            cache_key = _generate_cache_key(func.__name__, args, kwargs)
            cache_path = os.path.join(cache_dir, cache_key)
            
            # Check if cache should be invalidated by env var
            should_invalidate = os.environ.get(env_invalidate, '') != ''
            
            # Use cached result if available and not invalidated
            if os.path.exists(cache_path) and not should_invalidate:
                try:
                    with open(cache_path, 'rb') as f:
                        return cast(T, pickle.load(f))
                except (pickle.PickleError, EOFError, AttributeError):
                    # If there's any issue loading the cache, proceed to regenerate it
                    pass
            
            # Execute the function and cache the result
            result = func(*args, **kwargs)
            
            # Save the result to cache
            try:
                with open(cache_path, 'wb') as f:
                    pickle.dump(result, f)
            except (pickle.PickleError, TypeError):
                # If caching fails, just return the result without caching
                print(f"Warning: Could not cache result for {func.__name__}")
                
            return result
        
        return wrapper
    
    return decorator

def _generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Generate a unique cache key based on function name and arguments."""
    # Convert arguments to a JSON-serializable format
    args_str = json.dumps(args, sort_keys=True, default=str)
    kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
    
    # Create a hash of the function name and arguments
    key_data = f"{func_name}:{args_str}:{kwargs_str}".encode('utf-8')
    return hashlib.md5(key_data).hexdigest()

# Example usage:
"""
import requests
import time
import os

@fs_cache()
def fetch_data(url: str) -> dict:
    print(f"Fetching data from {url}...")
    time.sleep(1)  # Simulate slow operation
    response = requests.get(url)
    return response.json()

# Normal call (uses cache if available)
data1 = fetch_data("https://api.example.com/data")

# To invalidate cache (ignore existing cache but still save results):
# os.environ['FS_CACHE_INVALIDATE'] = '1'
# data2 = fetch_data("https://api.example.com/data")

# To disable cache completely (don't read or write cache):
# os.environ['FS_CACHE_DISABLE'] = '1'
# data3 = fetch_data("https://api.example.com/data")

# Use different environment variable names:
@fs_cache(
    env_invalidate='MY_APP_INVALIDATE_CACHE',
    env_disable='MY_APP_DISABLE_CACHE'
)
def custom_fetch():
    # This will respond to different environment variables
    pass
"""