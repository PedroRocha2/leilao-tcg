"""RNF01: a tela do leilão e a área de envio de lance são responsivas e adaptadas a celulares.

Critérios medidos num navegador real (Playwright), em 360, 390 e 768 px de largura:
  1. sem rolagem horizontal (scrollWidth da página <= largura da janela);
  2. cronômetro, lance atual, campo e botão "Dar lance" inteiros dentro da largura da tela, com o
     lance atual e o cronômetro numa linha só e o campo com pelo menos 160 px para digitar;
  3. alvos de toque (campo, botão, miniaturas, abas, chips e botão do menu) com pelo menos 44 x 44 px;
  4. fonte do campo de valor >= 16 px (o iOS não aplica zoom automático);
  5. o lance funciona nessa largura: recusa com o motivo junto ao campo e aceite sem recarregar;
  6. o menu superior recolhe num botão operável pelo teclado.
Evidências: screenshots e medicoes.json em evidencias/rnf01/.
"""

import json
import threading
from datetime import date
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from apoio import ITERACOES_DE_TESTE, SENHA
from app import create_app
from app.cadastro import criar_conta
from app.db import conectar
from app.repositorios import RepositorioClientes

LARGURAS = [(360, 640), (390, 844), (768, 1024)]
ALVO_MINIMO = 44
EVIDENCIAS = Path(__file__).resolve().parent.parent / "evidencias" / "rnf01"
MEDICOES: dict[str, dict] = {}
EMAIL = "rnf01@teste.com"


@pytest.fixture
def servidor(tmp_path):
    """Servidor com banco novo por teste: cada largura começa do Charizard em R$ 2.350,00."""
    banco = tmp_path / "rnf01.sqlite3"
    app = create_app({
        "TESTING": True,
        "DATABASE": str(banco),
        "SECRET_KEY": "chave-rnf01",
        "PBKDF2_ITERACOES": ITERACOES_DE_TESTE,
    })
    conexao = conectar(str(banco))
    criar_conta(RepositorioClientes(conexao), nome="Teste Responsivo", email=EMAIL, telefone="48991234567",
                cpf="529.982.247-25", senha=SENHA, confirmacao=SENHA, hoje=date.today(),
                iteracoes=ITERACOES_DE_TESTE)
    charizard = conexao.execute(
        "SELECT l.id FROM leiloes l JOIN cartas c ON c.id = l.carta_id WHERE c.nome = 'Charizard'"
    ).fetchone()[0]
    conexao.close()

    http = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield {"url": f"http://127.0.0.1:{http.server_port}", "charizard": charizard}
    http.shutdown()
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    (EVIDENCIAS / "medicoes.json").write_text(json.dumps(MEDICOES, indent=2, ensure_ascii=False), encoding="utf-8")


def medir(page, seletor):
    return page.eval_on_selector(
        seletor,
        """el => { const r = el.getBoundingClientRect();
                  return {esquerda: r.left, direita: r.right, largura: r.width, altura: r.height,
                          fonte: parseFloat(getComputedStyle(el).fontSize)}; }""",
    )


def medir_todos(page, seletor):
    return page.eval_on_selector_all(
        seletor, "els => els.map(e => { const r = e.getBoundingClientRect(); return [r.width, r.height, r.right]; })"
    )


def largura_da_pagina(page):
    return page.evaluate("() => ({rolagem: document.documentElement.scrollWidth, janela: window.innerWidth})")


def capturar_pagina_inteira(page, caminho):
    """Carrega as fotos com loading="lazy" e volta ao topo antes da captura (o menu é fixo)."""
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_function("[...document.images].every(img => img.complete)")
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(caminho), full_page=True)


def entrar(page, servidor, destino):
    page.goto(f"{servidor['url']}/entrar?proximo={destino}")
    page.fill("#email", EMAIL)
    page.fill("#senha", SENHA)
    page.click("form.formulario button[type=submit]")
    page.wait_for_url(f"**{destino}")


@pytest.mark.parametrize("largura, altura", LARGURAS, ids=[f"{l}px" for l, _ in LARGURAS])
def test_tela_do_leilao_e_area_de_lance(servidor, browser, largura, altura):
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    contexto = browser.new_context(viewport={"width": largura, "height": altura}, has_touch=True)
    page = contexto.new_page()
    medicao = {}

    entrar(page, servidor, f"/leiloes/{servidor['charizard']}")
    page.wait_for_selector("#valor-lance")

    pagina = largura_da_pagina(page)
    medicao["pagina"] = pagina
    assert pagina["rolagem"] <= pagina["janela"], "a página rola na horizontal"

    for nome, seletor in {
        "cronometro": ".painel [data-contagem]",
        "lance_atual": "[data-valor]",
        "campo": "#valor-lance",
        "caixa_do_campo": ".campo-valor",
        "botao": "[data-enviar]",
    }.items():
        caixa = medir(page, seletor)
        medicao[nome] = caixa
        assert caixa["esquerda"] >= 0 and caixa["direita"] <= largura, f"{nome} sai da tela"

    assert medicao["caixa_do_campo"]["altura"] >= ALVO_MINIMO
    assert medicao["botao"]["altura"] >= ALVO_MINIMO and medicao["botao"]["largura"] >= ALVO_MINIMO
    assert medicao["campo"]["fonte"] >= 16
    assert medicao["campo"]["largura"] >= 160, "o campo de valor ficou estreito demais para digitar"
    assert medicao["lance_atual"]["altura"] < 1.5 * medicao["lance_atual"]["fonte"], "o lance atual quebrou em duas linhas"
    assert medicao["cronometro"]["altura"] < 1.5 * medicao["cronometro"]["fonte"], "o cronômetro quebrou em duas linhas"
    assert page.input_value("#valor-lance") == "2.355,00"  # já preenchido com calcularLanceMinimo()

    for nome, seletor in {"miniaturas": ".miniatura", "abas": "[role=tab]"}.items():
        alvos = medir_todos(page, seletor)
        medicao[nome] = alvos
        assert alvos and all(l >= ALVO_MINIMO and a >= ALVO_MINIMO and d <= largura for l, a, d in alvos), nome

    # Regra de negócio nesta largura: recusa com o motivo junto ao campo, sem rolagem horizontal.
    page.fill("#valor-lance", "2.000,00")
    page.click("[data-enviar]")
    erro = page.locator("#erro-lance")
    erro.wait_for(state="visible")
    assert "O lance mínimo agora é R$ 2.355,00" in erro.inner_text()
    assert page.get_attribute("#valor-lance", "aria-invalid") == "true"
    caixa_erro = medir(page, "#erro-lance")
    medicao["mensagem_de_erro"] = caixa_erro
    assert caixa_erro["direita"] <= largura
    assert largura_da_pagina(page)["rolagem"] <= largura
    page.screenshot(path=str(EVIDENCIAS / f"leilao-{largura}px-recusa.png"))

    # Lance aceito sem recarregar: anúncio, tabela e novo mínimo no campo.
    page.fill("#valor-lance", "2.355,00")
    page.locator("[data-enviar]").tap()
    page.locator("[data-ok]").filter(has_text="registrado").wait_for()
    page.wait_for_function("document.querySelector('[data-anuncio]').textContent.includes('registrado')")
    assert page.inner_text("[data-valor]") == "R$ 2.355,00"
    assert page.input_value("#valor-lance") == "2.360,00"
    assert "Você" in page.inner_text("[data-linhas-lances] tr.maior")
    page.screenshot(path=str(EVIDENCIAS / f"leilao-{largura}px-aceito.png"))
    capturar_pagina_inteira(page, EVIDENCIAS / f"leilao-{largura}px-pagina-inteira.png")

    MEDICOES[f"leilao-{largura}px"] = medicao
    contexto.close()


@pytest.mark.parametrize("largura, altura", LARGURAS, ids=[f"{l}px" for l, _ in LARGURAS])
def test_lista_de_leiloes_sem_rolagem_horizontal(servidor, browser, largura, altura):
    contexto = browser.new_context(viewport={"width": largura, "height": altura})
    page = contexto.new_page()
    page.goto(f"{servidor['url']}/leiloes")
    pagina = largura_da_pagina(page)
    chips = medir_todos(page, ".chip")
    MEDICOES[f"listagem-{largura}px"] = {"pagina": pagina, "chips": chips}
    assert pagina["rolagem"] <= pagina["janela"]
    assert all(a >= ALVO_MINIMO and d <= largura for _, a, d in chips)
    page.screenshot(path=str(EVIDENCIAS / f"listagem-{largura}px.png"))
    contexto.close()


@pytest.mark.parametrize("caminho", ["/entrar", "/criar-conta"])
def test_telas_de_conta_sem_rolagem_horizontal(servidor, browser, caminho):
    contexto = browser.new_context(viewport={"width": 360, "height": 640})
    page = contexto.new_page()
    page.goto(servidor["url"] + caminho)
    assert largura_da_pagina(page)["rolagem"] <= 360
    contexto.close()


def test_menu_superior_recolhe_num_botao_acessivel_por_teclado(servidor, browser):
    contexto = browser.new_context(viewport={"width": 360, "height": 640})
    page = contexto.new_page()
    page.goto(f"{servidor['url']}/leiloes")

    lista = page.locator("#menu-principal")
    botao = page.locator(".botao-menu")
    assert botao.is_visible() and not lista.is_visible()
    assert botao.get_attribute("aria-expanded") == "false"
    assert botao.get_attribute("aria-controls") == "menu-principal"
    caixa = medir(page, ".botao-menu")
    assert caixa["largura"] >= ALVO_MINIMO and caixa["altura"] >= ALVO_MINIMO

    botao.focus()
    page.keyboard.press("Enter")
    assert lista.is_visible()
    assert botao.get_attribute("aria-expanded") == "true"
    # O foco vai para o item ativo, destacado com --accent e texto branco.
    ativo = page.evaluate("""() => { const el = document.activeElement;
        return {atual: el.getAttribute('aria-current'), texto: el.textContent.trim(),
                fundo: getComputedStyle(el).backgroundColor, cor: getComputedStyle(el).color}; }""")
    assert ativo == {"atual": "page", "texto": "Leilões", "fundo": "rgb(0, 56, 215)", "cor": "rgb(255, 255, 255)"}
    assert all(a >= ALVO_MINIMO for _, a, _ in medir_todos(page, "#menu-principal .nav__item"))
    page.screenshot(path=str(EVIDENCIAS / "menu-360px-aberto.png"))

    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.textContent.trim()") == "Entrar"
    page.keyboard.press("Escape")
    assert not lista.is_visible()
    assert botao.get_attribute("aria-expanded") == "false"
    assert page.evaluate("document.activeElement.classList.contains('botao-menu')")
    contexto.close()


def test_menu_no_desktop_fica_aberto_sem_botao(servidor, browser):
    contexto = browser.new_context(viewport={"width": 1280, "height": 800})
    page = contexto.new_page()
    page.goto(f"{servidor['url']}/leiloes")
    assert not page.locator(".botao-menu").is_visible()
    for rotulo in ("Leilões", "Entrar", "Criar conta"):
        assert page.locator("#menu-principal").get_by_text(rotulo, exact=True).is_visible()
    contexto.close()
