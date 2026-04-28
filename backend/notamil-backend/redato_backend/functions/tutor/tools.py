from typing import Any, Callable, Dict

TOOLS_REGISTRY: Dict[str, Callable[[Dict[str, Any]], Any]] = {}


def register_function(name: str):
    def decorator(func: Callable[[Dict[str, Any]], Any]):
        TOOLS_REGISTRY[name] = func
        return func

    return decorator
