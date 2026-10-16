import base64
import hashlib
import hmac
import secrets

ALGORITMO = "pbkdf2_sha256"
ITERACOES_PADRAO = 600_000
TAMANHO_MINIMO = 8


def _b64(dados: bytes) -> str:
    return base64.b64encode(dados).decode("ascii")


def gerar_hash(senha: str, iteracoes: int = ITERACOES_PADRAO) -> str:
    salt = secrets.token_bytes(16)
    derivada = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, iteracoes)
    return f"{ALGORITMO}${iteracoes}${_b64(salt)}${_b64(derivada)}"


def conferir(senha: str, senha_hash: str) -> bool:
    partes = (senha_hash or "").split("$")
    if len(partes) != 4 or partes[0] != ALGORITMO or not partes[1].isdigit():
        return False
    try:
        salt = base64.b64decode(partes[2], validate=True)
        esperado = base64.b64decode(partes[3], validate=True)
    except ValueError:
        return False
    derivada = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, int(partes[1]))
    return hmac.compare_digest(derivada, esperado)


def senha_inutilizavel() -> str:
    return "!" + secrets.token_hex(16)
