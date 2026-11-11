import os
import secrets
from pathlib import Path

from flask import Flask

from app import db
from app.catalogo import criar_catalogo
from app.dominio import senhas
from app.pagamento import GatewayLocal

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
        # Fotos das cartas cadastradas pelos vendedores e miniaturas guardadas do catálogo.
        PASTA_DE_FOTOS=str(Path(app.instance_path) / "fotos"),
        PASTA_DO_CATALOGO=str(Path(app.instance_path) / "catalogo"),
        # Como a loja se identifica para as APIs de cartas (o Scryfall exige).
        CATALOGO_USER_AGENT="leilao-de-cartas/1.0",
        # Conta do lojista, criada com o banco. Troque pelas variáveis de ambiente antes do primeiro uso real.
        ADMIN_LOGIN=os.environ.get("LEILAO_ADMIN_LOGIN", "admin-jiujitsu"),
        ADMIN_SENHA=os.environ.get("LEILAO_ADMIN_SENHA", "osscachorro"),
        GATEWAY=GatewayLocal(),
    )
    if config:
        app.config.update(config)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = _chave_secreta(Path(app.instance_path))
    if "CATALOGO" not in app.config:
        app.config["CATALOGO"] = criar_catalogo(app.config["CATALOGO_USER_AGENT"])

    db.registrar(app)
    with app.app_context():
        db.preparar_banco(app.config["DATABASE"], administrador=db.administrador_da_configuracao())

    from app.rotas import registrar

    registrar(app)
    return app
