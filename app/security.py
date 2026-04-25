from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

_ph = PasswordHasher()


def hash_senha(senha: str) -> str:
    return _ph.hash(senha)


def verificar_senha(hash_armazenado: str, senha_digitada: str) -> bool:
    try:
        return _ph.verify(hash_armazenado, senha_digitada)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
