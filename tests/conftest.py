import os
from pathlib import Path

import pytest

from apoio import CSRF, ITERACOES_DE_TESTE
from app import create_app
from app.db import conectar


def pytest_configure(config):
    """Usa o Chrome ou o Edge instalados quando o Chromium do Playwright não foi baixado."""
    if not hasattr(config.option, "browser_channel") or config.option.browser_channel:
        return
    pasta = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".cache")) / "ms-playwright"
    if not pasta.exists():
        pasta = Path.home() / ".cache" / "ms-playwright"
    if any(pasta.glob("chromium-*")):
        return
    chrome = Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe"
    config.option.browser_channel = "chrome" if chrome.exists() else "msedge"


@pytest.fixture
def app(tmp_path):
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "teste.sqlite3"),
        "SECRET_KEY": "chave-de-teste",
        "PBKDF2_ITERACOES": ITERACOES_DE_TESTE,
    })


@pytest.fixture
def cliente_http(app):
    navegador = app.test_client()
    with navegador.session_transaction() as sessao:
        sessao["csrf"] = CSRF
    return navegador


@pytest.fixture
def banco(app):
    conexao = conectar(app.config["DATABASE"])
    yield conexao
    conexao.close()
