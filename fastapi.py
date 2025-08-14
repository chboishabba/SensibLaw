class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

class APIRouter:
    def __init__(self):
        pass
    def get(self, *args, **kwargs):
        def deco(fn):
            return fn
        return deco
    def post(self, *args, **kwargs):
        def deco(fn):
            return fn
        return deco

def Query(*args, **kwargs):
    return None
