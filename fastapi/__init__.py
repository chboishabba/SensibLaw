class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str | None = None):
        self.status_code = status_code
        self.detail = detail

class APIRouter:

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class APIRouter:
    def __init__(self):
        pass

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
