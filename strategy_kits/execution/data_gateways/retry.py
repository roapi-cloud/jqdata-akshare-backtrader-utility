"""通用重试装饰器"""

import functools
import time
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable)


def retry_on_failure(max_retry: int = 3, sleep: float = 1.0) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_err = None
            for i in range(max_retry):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    if i < max_retry - 1:
                        time.sleep(sleep)
            raise last_err

        return wrapper

    return decorator
