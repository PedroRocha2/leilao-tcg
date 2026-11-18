import os
import secrets
from pathlib import Path

from flask import Flask

from app import db
from app.anuncio import MAXIMO_DE_FOTOS, TAMANHO_MAXIMO_DA_FOTO
from app.catalogo import criar_catalogo
from app.correio import PORTA_PADRAO, CorreioLocal, CorreioSMTP
from app.dominio import senhas
from app.mercado_pago import MercadoPago
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
        PASTA_DE_FOTOS=str(Path(app.instance_path) / "fotos"),
        PASTA_DO_CATALOGO=str(Path(app.instance_path) / "catalogo"),
        MAX_CONTENT_LENGTH=MAXIMO_DE_FOTOS * TAMANHO_MAXIMO_DA_FOTO + 1024 * 1024,
        # O Scryfall exige um User-Agent identificado.
        CATALOGO_USER_AGENT="leilao-de-cartas/1.0",
        # Troque pelas variáveis de ambiente antes do uso real.
        ADMIN_LOGIN=os.environ.get("LEILAO_ADMIN_LOGIN", "admin-jiujitsu"),
        ADMIN_SENHA=os.environ.get("LEILAO_ADMIN_SENHA", "osscachorro"),
        # RF11: sem credencial, vale o gateway local, que confirma na hora sem cobrar.
        MERCADO_PAGO_TOKEN=os.environ.get("MERCADOPAGO_ACCESS_TOKEN", "").strip(),
        URL_PUBLICA=os.environ.get("LEILAO_URL_PUBLICA", "").strip(),
        SMTP_SERVIDOR=os.environ.get("LEILAO_SMTP_SERVIDOR", "").strip(),
        SMTP_PORTA=os.environ.get("LEILAO_SMTP_PORTA", "").strip(),
        SMTP_USUARIO=os.environ.get("LEILAO_SMTP_USUARIO", "").strip(),
        SMTP_SENHA=os.environ.get("LEILAO_SMTP_SENHA", ""),
        EMAIL_REMETENTE=os.environ.get("LEILAO_EMAIL_REMETENTE", "").strip(),
    )
    if config:
        app.config.update(config)
    if "GATEWAY" not in app.config:
        token = app.config["MERCADO_PAGO_TOKEN"]
        app.config["GATEWAY"] = MercadoPago(token) if token else GatewayLocal()
    if "CORREIO" not in app.config:
        servidor = app.config["SMTP_SERVIDOR"]
        app.config["CORREIO"] = CorreioSMTP(
            servidor, int(app.config["SMTP_PORTA"] or PORTA_PADRAO), app.config["SMTP_USUARIO"],
            app.config["SMTP_SENHA"], app.config["EMAIL_REMETENTE"]) if servidor else CorreioLocal()
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
