import os
import json
import hashlib
import functools
import pickle
from typing import Any, Callable, cast

def fs_cache[T](
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
    # Handle bound methods by extracting class and method names
    if args and hasattr(args[0], '__class__') and hasattr(args[0].__class__, func_name):
        # This is likely a method call - include class name in the key
        class_name = args[0].__class__.__name__
        # Skip the 'self' argument for methods
        method_args = args[1:]
        args_for_key = (class_name,) + method_args
    else:
        args_for_key = args
    
    try:
        # Try to JSON serialize the arguments
        args_str = json.dumps(args_for_key, sort_keys=True, default=str)
        kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
    except (TypeError, ValueError):
        # If JSON serialization fails, use string representation
        args_str = str(args_for_key)
        kwargs_str = str(kwargs)
    
    # Create a hash of the function name and arguments
    key_data = f"{func_name}:{args_str}:{kwargs_str}".encode('utf-8')
    return hashlib.md5(key_data).hexdigest()

