import secrets
from collections.abc import Callable

# Без символів, які легко сплутати: 0/O, 1/I/L
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


def generate_code(length: int = CODE_LENGTH) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def unique_code(exists: Callable[[str], bool], attempts: int = 20) -> str:
    """Генерує код, якого ще немає в базі."""
    for _ in range(attempts):
        code = generate_code()
        if not exists(code):
            return code
    raise RuntimeError("Не вдалося згенерувати унікальний код запрошення")


def normalize_code(code: str) -> str:
    return code.strip().upper().replace(" ", "").replace("-", "")
