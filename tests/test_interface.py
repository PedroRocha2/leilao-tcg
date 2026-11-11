import threading
from datetime import date, timedelta
from decimal import Decimal

import pytest
from werkzeug.serving import make_server

from apoio import (ADMIN_LOGIN, ADMIN_SENHA, ITERACOES_DE_TESTE, SENHA, aprovar_leilao, catalogo_de_teste,
                   criar_leilao, outro_navegador)
from app import create_app
from app.cadastro import criar_conta
from app.db import agora_utc, conectar, para_texto, transacao
from app.repositorios import RepositorioClientes, RepositorioLeiloes

EMAIL = "interface@teste.com"


@pytest.fixture
def servidor(tmp_path):
    banco = str(tmp_path / "interface.sqlite3")
    app = create_app({"TESTING": True, "DATABASE": banco, "SECRET_KEY": "chave-interface",
                      "PBKDF2_ITERACOES": ITERACOES_DE_TESTE, "CATALOGO": catalogo_de_teste(),
                      "PASTA_DE_FOTOS": str(tmp_path / "fotos"), "PASTA_DO_CATALOGO": str(tmp_path / "catalogo")})
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
    yield {"url": f"http://127.0.0.1:{http.server_port}", "banco": banco, "charizard": charizard, "app": app}
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


def test_leilao_encerra_na_tela_e_mostra_o_arremate_a_quem_venceu(servidor, pagina):
    pagina.goto(f"{servidor['url']}/entrar?proximo=/leiloes/{servidor['charizard']}")
    pagina.fill("#email", EMAIL)
    pagina.fill("#senha", SENHA)
    pagina.click("form.formulario button[type=submit]")
    pagina.wait_for_selector("#valor-lance")
    pagina.click("[data-enviar]")
    pagina.locator("[data-ok]").filter(has_text="registrado").wait_for()

    conexao = conectar(servidor["banco"])
    conexao.execute("UPDATE leiloes SET data_fim_prevista = ? WHERE id = ?",
                    (para_texto(agora_utc() + timedelta(seconds=3)), servidor["charizard"]))
    conexao.close()

    aviso = pagina.locator(".lance__aviso").filter(has_text="Você arrematou esta carta por R$ 2.355,00.")
    aviso.wait_for(timeout=15000)
    assert pagina.inner_text("[data-situacao]") == "Encerrado"
    assert pagina.inner_text("[data-rotulo-valor]") == "Valor do arremate"
    assert pagina.locator("[data-form-lance]").count() == 0
    assert "Lance vencedor" in pagina.inner_text("[data-linhas-lances] tr.maior")

    pagina.click("text=Ver meus arremates")
    pagina.wait_for_url("**/minha-conta/arremates")
    assert "Charizard" in pagina.inner_text(".meu-lance")
    assert "Aguardando pagamento" in pagina.inner_text(".meu-lance")


def test_pagina_inicial_leva_aos_leiloes_aos_jogos_e_a_busca(servidor, pagina):
    pagina.goto(f"{servidor['url']}/")
    assert pagina.evaluate("window.scrollY") == 0
    pagina.click("text=Quero comprar")
    pagina.wait_for_function("""() => { const y = document.querySelector('#titulo-leiloes').getBoundingClientRect().top;
                                        return y > 60 && y < 200; }""")
    assert pagina.url.endswith("/#leiloes") and pagina.locator("#leiloes .cartao").count() == 15

    assert pagina.get_attribute("text=Quero vender", "href") == "/entrar?proximo=/vender/novo"
    pagina.click(".jogo-card >> text=Magic: The Gathering")
    pagina.wait_for_url("**/jogos/magic-the-gathering")
    assert pagina.inner_text("h1") == "Magic: The Gathering" and pagina.locator(".cartao").count() == 5
    assert pagina.input_value("#busca-jogo") == "magic-the-gathering"

    # A busca do topo respeita o jogo do combobox e acha pelo nome ou pelo código.
    pagina.fill("#busca-carta", "156")
    pagina.press("#busca-carta", "Enter")
    pagina.wait_for_url("**/jogos/magic-the-gathering?q=156")
    assert pagina.locator(".cartao").count() == 1 and "Shivan Dragon" in pagina.inner_text(".cartao")
    pagina.select_option("#busca-jogo", "")
    pagina.fill("#busca-carta", "dragon")
    pagina.click(".busca-topo__botao")
    pagina.wait_for_url("**/leiloes?jogo=&q=dragon")
    assert pagina.locator(".cartao").count() == 3 and pagina.input_value("#busca-carta") == "dragon"

    pagina.click(".nav__item >> text=Meus lances")
    pagina.wait_for_url("**/entrar?proximo=/minha-conta/lances")
    pagina.fill("#email", EMAIL)
    pagina.fill("#senha", SENHA)
    pagina.click("form.formulario button[type=submit]")
    pagina.wait_for_url("**/minha-conta/lances")
    pagina.click(".marca")
    assert pagina.get_attribute("text=Quero vender", "href") == "/vender/novo"


def test_vendedor_cria_leilao_pelo_catalogo_e_ve_a_aprovacao_na_tela(servidor, pagina):
    pagina.goto(f"{servidor['url']}/entrar?proximo=/vender")
    pagina.fill("#email", EMAIL)
    pagina.fill("#senha", SENHA)
    pagina.click("form.formulario button[type=submit]")
    pagina.click("text=Criar leilão")

    pagina.click(".chip >> text=Yu-Gi-Oh!")
    assert pagina.get_attribute(".chip[aria-current]", "href").endswith("jogo=yu-gi-oh")
    assert pagina.inner_text("#titulo-resultados") == "Sugestões de Yu-Gi-Oh!"
    assert "Just Flip a Coin" in pagina.inner_text(".grade")

    # O filtro troca as cartas enquanto o vendedor digita, sem enviar o formulário.
    titulo = "document.querySelector('#titulo-resultados').textContent.startsWith(%r)"
    pagina.fill("#q", "dark")
    pagina.wait_for_function(titulo % "2 cartas encontradas")
    assert pagina.url.endswith("/vender/novo?jogo=yu-gi-oh&q=dark")
    assert pagina.inner_text("[data-filtro-status]") == "2 cartas encontradas em Yu-Gi-Oh!"
    pagina.fill("#q", "")
    pagina.wait_for_function(titulo % "Sugestões")
    assert pagina.url.endswith("/vender/novo?jogo=yu-gi-oh")
    pagina.fill("#q", "dark")
    pagina.click(".busca button[type=submit]")
    pagina.wait_for_function(titulo % "2 cartas encontradas")
    assert pagina.locator(".cartao").count() == 2
    assert "46986414" in pagina.inner_text(".cartao >> nth=0")
    pagina.wait_for_function(
        "[...document.querySelectorAll('.cartao__foto')].every(img => img.complete && img.naturalWidth > 0)")

    pagina.click(".cartao__nome a >> text=Dark Magician Girl")
    assert pagina.inner_text("h1") == "Dark Magician Girl"
    assert "US$\xa00,44" in pagina.inner_text(".preco-medio") and "TCGplayer" in pagina.inner_text(".preco-medio")
    assert "Effect Monster" in pagina.inner_text(".anuncio__carta .ficha")
    pagina.select_option("#edicao", index=1)
    pagina.select_option("#condicao", "Lightly Played (LP)")
    pagina.fill("#lance_inicial", "trinta e cinco")
    pagina.click("form.formulario button[type=submit]")
    assert "Lance mínimo inicial: Valor em formato inválido." in pagina.inner_text(".resumo-erros")
    assert pagina.evaluate("document.activeElement.id") == "lance_inicial"
    assert pagina.input_value("#condicao") == "Lightly Played (LP)"

    pagina.fill("#lance_inicial", "35,00")
    pagina.click("form.formulario button[type=submit]")
    pagina.wait_for_url("**/vender")
    carta = pagina.locator(".meu-lance")
    assert "Dark Magician Girl" in carta.inner_text() and "Aguardando depósito" in carta.inner_text()

    pagina.click(".meu-lance__nome a")
    assert pagina.inner_text("[data-situacao]") == "Aguardando aprovação"
    numero = pagina.url.rsplit("/", 1)[-1]
    assert "aprovado" in aprovar_leilao(servidor["app"], int(numero))
    pagina.locator(".lance__aviso").filter(has_text="Você é o vendedor desta carta").wait_for(timeout=15000)
    assert pagina.inner_text("[data-situacao]") == "Ativo"


def test_lojista_entra_aprova_o_leilao_e_percorre_a_administracao(servidor, pagina):
    vendedor = outro_navegador(servidor["app"], email="vendedor@teste.com", cpf="111.444.777-35")
    assert criar_leilao(vendedor, servidor["app"]).status_code == 303

    pagina.goto(f"{servidor['url']}/entrar")
    pagina.fill("#email", ADMIN_LOGIN)
    pagina.fill("#senha", ADMIN_SENHA)
    pagina.click("form.formulario button[type=submit]")
    pagina.wait_for_url("**/admin/leiloes")
    assert pagina.inner_text("h1") == "Administração"
    assert "(1" in pagina.inner_text(".aba[aria-current]")
    assert "Charizard" in pagina.inner_text(".pendente")

    pagina.click("text=Aprovar e registrar depósito")
    pagina.locator(".aviso").filter(has_text="aprovado: já está recebendo lances").wait_for()
    assert pagina.locator(".pendente").count() == 0
    assert pagina.inner_text(".aba[aria-current]") == "Leilões"

    for aba, titulo in (("Entregas", "Entrega de cartas"), ("Saques", "Saques solicitados"), ("Usuários", "Usuários"),
                        ("Cartas", "Cartas cadastradas"), ("Histórico", "Histórico de leilões finalizados"),
                        ("Financeiro", "Extrato financeiro"), ("Configurações", "Configurações da loja"),
                        ("Auditoria", "Log de auditoria")):
        pagina.click(f".conta-abas .aba >> text={aba}")
        assert pagina.inner_text("#titulo-secao") == titulo
        assert pagina.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), aba
    assert "aprovação de leilão" in pagina.inner_text(".tabela")

    pagina.click(".conta-abas__sair button")
    pagina.wait_for_url("**/leiloes")
    assert pagina.locator(".cartao").count() == 16


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
