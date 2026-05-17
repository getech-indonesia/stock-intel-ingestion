import time
import functools

# Caching decorator
cache = {}
def cache_result(func):
    @functools.wraps(func)
    def wrapper(*args):
        if args in cache:
            print('Returning cached result for:', args)
            return cache[args]
        result = func(*args)
        cache[args] = result
        return result
    return wrapper


# Retry logic decorator

def retry(max_attempts=3, delay=1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    print(f'Attempt {attempts} failed: {e}')
                    time.sleep(delay)
            raise Exception(f'Function {func.__name__} failed after {max_attempts} attempts')
        return wrapper
    return decorator


# Request timing decorator

def time_request(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f'Execution time for {func.__name__}: {end_time - start_time:.4f} seconds')
        return result
    return wrapper
