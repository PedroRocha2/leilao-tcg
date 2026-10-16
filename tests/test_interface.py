import threading
from datetime import date, timedelta
from decimal import Decimal

import pytest
from werkzeug.serving import make_server

from apoio import ITERACOES_DE_TESTE, SENHA
from app import create_app
from app.cadastro import criar_conta
from app.db import agora_utc, conectar, para_texto, transacao
from app.repositorios import RepositorioClientes, RepositorioLeiloes

EMAIL = "interface@teste.com"


@pytest.fixture
def servidor(tmp_path):
    banco = str(tmp_path / "interface.sqlite3")
    app = create_app({"TESTING": True, "DATABASE": banco, "SECRET_KEY": "chave-interface",
                      "PBKDF2_ITERACOES": ITERACOES_DE_TESTE})
    conexao = conectar(banco)
    criar_conta(RepositorioClientes(conexao), nome="Teste Interface", email=EMAIL, telefone="48991234567",
                cpf="529.982.247-25", senha=SENHA, confirmacao=SENHA, hoje=date.today(),
                iteracoes=ITERACOES_DE_TESTE)
    charizard = conexao.execute(
        "SELECT l.id FROM leiloes l JOIN cartas c ON c.id = l.carta_id WHERE c.nome = 'Charizard'"
    ).fetchone()[0]
    conexao.close()
    http = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    yield {"url": f"http://127.0.0.1:{http.server_port}", "banco": banco, "charizard": charizard}
    http.shutdown()


@pytest.fixture
def pagina(servidor, browser):
    contexto = browser.new_context(viewport={"width": 1280, "height": 900})
    page = contexto.new_page()
    yield page
    contexto.close()


def test_abas_com_teclado_e_aba_no_endereco(servidor, pagina):
    pagina.goto(f"{servidor['url']}/leiloes/{servidor['charizard']}")
    abas = pagina.locator("[role=tab]")
    assert abas.count() == 3
    assert pagina.locator("#painel-lances").is_visible() and not pagina.locator("#painel-detalhes").is_visible()

    abas.first.focus()
    pagina.keyboard.press("ArrowRight")
    assert pagina.evaluate("document.activeElement.textContent.trim()") == "Detalhes"
    assert pagina.get_attribute("#aba-painel-detalhes", "aria-selected") == "true"
    assert pagina.locator("#painel-detalhes").is_visible() and not pagina.locator("#painel-lances").is_visible()
    assert pagina.url.endswith("#painel-detalhes")

    pagina.reload()
    assert pagina.get_attribute("#aba-painel-detalhes", "aria-selected") == "true"
    pagina.keyboard.press("End")
    abas.nth(1).focus()
    pagina.keyboard.press("End")
    assert pagina.locator("#painel-descricao").is_visible()


def test_miniaturas_trocam_a_foto_e_a_foto_amplia(servidor, pagina):
    pagina.goto(f"{servidor['url']}/leiloes/{servidor['charizard']}")
    principal = pagina.locator("[data-foto-principal]")
    assert principal.get_attribute("src").endswith("charizard-frente.webp")

    pagina.locator(".miniatura").nth(1).click()
    assert principal.get_attribute("src").endswith("charizard-arte.webp")
    assert pagina.locator(".miniatura").nth(1).get_attribute("aria-pressed") == "true"
    assert pagina.locator(".miniatura").nth(0).get_attribute("aria-pressed") == "false"

    ampliar = pagina.locator("[data-ampliar]")
    assert ampliar.get_attribute("role") == "button"
    ampliar.focus()
    pagina.keyboard.press(" ")
    dialogo = pagina.locator("[data-ampliacao]")
    assert dialogo.is_visible()
    assert pagina.locator("[data-ampliacao-foto]").get_attribute("src").endswith("charizard-arte.webp")
    assert "foto 2 de 3" in pagina.inner_text("[data-ampliacao-titulo]")

    pagina.keyboard.press("ArrowRight")
    assert pagina.locator("[data-ampliacao-foto]").get_attribute("src").endswith("charizard-canto.webp")
    pagina.keyboard.press("Escape")
    assert not dialogo.is_visible()
    assert pagina.evaluate("document.activeElement.hasAttribute('data-ampliar')")


def test_lance_atualiza_a_pagina_sem_recarregar(servidor, pagina):
    pagina.goto(f"{servidor['url']}/entrar?proximo=/leiloes/{servidor['charizard']}")
    pagina.fill("#email", EMAIL)
    pagina.fill("#senha", SENHA)
    pagina.click("form.formulario button[type=submit]")
    pagina.wait_for_selector("#valor-lance")
    pagina.evaluate("window.mesmaPagina = true")

    pagina.click("[data-enviar]")
    pagina.locator("[data-ok]").filter(has_text="registrado").wait_for()
    assert pagina.evaluate("window.mesmaPagina") is True
    assert pagina.inner_text("[data-valor]") == "R$ 2.355,00"
    assert pagina.inner_text(".painel [data-total-lances]") == "5"
    assert pagina.input_value("#valor-lance") == "2.360,00"
    assert "Você" in pagina.inner_text("[data-linhas-lances] tr.maior")
    pagina.wait_for_function("document.querySelector('[data-anuncio]').textContent.includes('Você está liderando')")


def test_lance_de_outra_pessoa_aparece_e_e_anunciado(servidor, pagina):
    pagina.goto(f"{servidor['url']}/leiloes/{servidor['charizard']}")
    conexao = conectar(servidor["banco"])
    clientes = RepositorioClientes(conexao)
    leiloes = RepositorioLeiloes(conexao, clientes)
    with transacao(conexao, imediata=True):
        leilao = leiloes.por_id(servidor["charizard"])
        outro = clientes.por_email(EMAIL)
        lance = outro.darLance(leilao, Decimal("2500.00"), agora_utc())
        leiloes.salvar_lance(leilao, lance)
    conexao.close()

    pagina.wait_for_function("document.querySelector('[data-valor]').textContent.includes('2.500,00')", timeout=8000)
    assert "Licitante" in pagina.inner_text("[data-linhas-lances] tr.maior")
    pagina.wait_for_function("document.querySelector('[data-anuncio]').textContent.includes('Novo lance atual')")
    assert pagina.inner_text("[data-minimo]") == "R$ 2.505,00"


def test_rn02_prorrogacao_atualiza_o_cronometro(servidor, pagina):
    conexao = conectar(servidor["banco"])
    fim = agora_utc() + timedelta(minutes=2)
    conexao.execute("UPDATE leiloes SET data_fim_prevista = ? WHERE id = ?", (para_texto(fim), servidor["charizard"]))
    conexao.close()
    pagina.goto(f"{servidor['url']}/entrar?proximo=/leiloes/{servidor['charizard']}")
    pagina.fill("#email", EMAIL)
    pagina.fill("#senha", SENHA)
    pagina.click("form.formulario button[type=submit]")
    pagina.wait_for_selector("#valor-lance")
    antes = pagina.get_attribute(".painel [data-contagem]", "data-alvo")
    pagina.click("[data-enviar]")
    pagina.locator("[data-ok]").filter(has_text="registrado").wait_for()
    depois = pagina.get_attribute(".painel [data-contagem]", "data-alvo")
    assert depois != antes
    assert pagina.inner_text(".painel [data-contagem]").startswith("4 min")
