import os
import secrets
from pathlib import Path

from flask import Flask

from app import db
from app.dominio import senhas

RAIZ = Path(__file__).resolve().parent.parent


def _chave_secreta(pasta_instancia: Path) -> str:
    """Chave de sessão estável entre reinícios, gerada na primeira execução."""
    if os.environ.get("LEILAO_SECRET_KEY"):
        return os.environ["LEILAO_SECRET_KEY"]
    arquivo = pasta_instancia / "secret_key"
    if not arquivo.exists():
        pasta_instancia.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(secrets.token_hex(32), encoding="utf-8")
    return arquivo.read_text(encoding="utf-8").strip()


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_path=str(RAIZ / "instance"))
    app.config.update(
        DATABASE=str(Path(app.instance_path) / "leilao.sqlite3"),
        RELOGIO=db.agora_utc,
        PBKDF2_ITERACOES=senhas.ITERACOES_PADRAO,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if config:
        app.config.update(config)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = _chave_secreta(Path(app.instance_path))

    db.registrar(app)
    db.preparar_banco(app.config["DATABASE"])

    from app.rotas import registrar

    registrar(app)
    return app
