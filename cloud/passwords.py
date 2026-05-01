"""Password hashing helpers (bcrypt)."""
import bcrypt

ROUNDS = 10


def hash_password(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(rounds=ROUNDS)).decode()


def verify_password(plaintext: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode(), stored_hash.encode())
    except Exception:
        return False
