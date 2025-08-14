class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str | None = None):
        self.status_code = status_code
        self.detail = detail

class APIRouter:
    def get(self, path: str):
        def decorator(func):
            return func
        return decorator

    def post(self, path: str):
        def decorator(func):
            return func
        return decorator


def Query(default=None, **kwargs):
    return default
