class BaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def Field(default=None, **kwargs):
    return default
