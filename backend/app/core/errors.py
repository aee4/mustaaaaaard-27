class Problem(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message


def require(condition: object, status: int, code: str, message: str) -> None:
    if not condition:
        raise Problem(status, code, message)
