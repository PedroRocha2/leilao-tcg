from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from apoio import (AGORA, ID_DO_RAIO, IMAGEM_DE_TESTE, aprovar_leilao as aprovar, avancar_relogio, criar_conta,
                   criar_leilao, lance_json, leiloes_criados, navegador_admin, no_fuso_da_loja, novo_cliente,
                   outro_navegador)
from app.dominio.leiloes import (CONDICOES, INCREMENTO_DA_LOJA, Jogo, LanceRecusado, MotivoRecusa, StatusCarta,
                                 StatusLeilao)

VALOR = Decimal
INICIO = AGORA + timedelta(hours=1)
FIM = AGORA + timedelta(days=3)


@pytest.fixture
def ana():
    return novo_cliente(1, "100200300")


@pytest.fixture
def bruno():
    return novo_cliente(2, "200300400")


def carta_da(vendedor, **mudancas):
    dados = {"nome": "Charizard", "jogo": Jogo("Pokémon", 1), "edicao": "Base Set (4/102)",
             "condicao": CONDICOES[0], "descricao": "Holo sem riscos.", "fotos": ["fotos/charizard.webp"]}
    dados.update(mudancas)
    return vendedor.cadastrarCarta(**dados)


def leilao_da(vendedor, **mudancas):
    dados = {"lanceInicial": VALOR("50"), "dataInicio": INICIO, "dataFimPrevista": FIM,
             "incrementoMinimo": INCREMENTO_DA_LOJA, "agora": AGORA}
    dados.update(mudancas)
    return vendedor.criarLeilao(carta_da(vendedor), **dados)


def test_cadastrar_carta_guarda_os_dados_e_aguarda_o_deposito(ana):
    carta = carta_da(ana)
    assert (carta.nome, carta.jogo.nome, carta.edicao, carta.condicao) == (
        "Charizard", "Pokémon", "Base Set (4/102)", "Near Mint (NM)")
    assert carta.vendedor is ana and carta.fotos == ["fotos/charizard.webp"]
    assert carta.status == StatusCarta.AGUARDANDO_DEPOSITO


@pytest.mark.parametrize("campo, vazio", [("nome", ""), ("jogo", None), ("edicao", ""), ("condicao", ""),
                                          ("fotos", [])])
def test_rn04_carta_sem_um_dado_obrigatorio_e_recusada(ana, campo, vazio):
    with pytest.raises(ValueError, match="RN04"):
        carta_da(ana, **{campo: vazio})


def test_criar_leilao_nasce_pendente_com_o_incremento_da_loja(ana):
    leilao = leilao_da(ana, lanceInicial=VALOR("50"))
    assert leilao.status == StatusLeilao.PENDENTE
    assert leilao.lanceInicial == VALOR("50.00") and leilao.incrementoMinimo == VALOR("5.00")
    assert (leilao.dataInicio, leilao.dataFimPrevista) == (INICIO, FIM)
    assert leilao.lances == [] and leilao.carta.vendedor is ana


def test_rn05_fim_previsto_tem_de_ser_depois_do_inicio_e_estar_no_futuro(ana):
    with pytest.raises(ValueError, match="RN05"):
        leilao_da(ana, dataFimPrevista=INICIO)
    with pytest.raises(ValueError, match="RN05"):
        leilao_da(ana, dataInicio=AGORA - timedelta(days=2), dataFimPrevista=AGORA - timedelta(days=1))


def test_rn04_lance_minimo_inicial_tem_de_ser_maior_que_zero(ana):
    with pytest.raises(ValueError, match="lance inicial"):
        leilao_da(ana, lanceInicial=VALOR("0"))


@pytest.mark.parametrize("situacao", [{"bloqueado": True}, {"ativo": False}])
def test_rn15_conta_bloqueada_nao_cria_leilao(situacao):
    bloqueada = novo_cliente(3, "300400500", **situacao)
    assert bloqueada.podeCriarLeilao() is False
    with pytest.raises(ValueError, match="RN15"):
        leilao_da(bloqueada)


def test_so_o_vendedor_cria_leilao_para_a_carta(ana, bruno):
    with pytest.raises(ValueError, match="vendedor"):
        bruno.criarLeilao(carta_da(ana), VALOR("50"), INICIO, FIM, INCREMENTO_DA_LOJA, AGORA)


def test_rn12_leilao_so_entra_em_andamento_depois_de_aprovado(ana, bruno):
    leilao = leilao_da(ana)
    with pytest.raises(ValueError, match="aprovado"):
        leilao.iniciar(INICIO)
    with pytest.raises(LanceRecusado) as erro:
        bruno.darLance(leilao, VALOR("50"), INICIO)
    assert erro.value.motivo is MotivoRecusa.LEILAO_INATIVO

    leilao.aprovar(AGORA)
    assert (leilao.status, leilao.carta.status) == (StatusLeilao.APROVADO, StatusCarta.APROVADA)
    with pytest.raises(ValueError, match="início"):
        leilao.iniciar(INICIO - timedelta(seconds=1))

    leilao.iniciar(INICIO)
    assert (leilao.status, leilao.carta.status) == (StatusLeilao.ATIVO, StatusCarta.EM_LEILAO)
    assert bruno.darLance(leilao, VALOR("50"), INICIO).valor == VALOR("50.00")


def test_aprovacao_so_vale_para_leilao_pendente_e_dentro_do_prazo(ana):
    leilao = leilao_da(ana)
    with pytest.raises(ValueError, match="fim previsto"):
        leilao.aprovar(FIM)
    leilao.aprovar(AGORA)
    with pytest.raises(ValueError, match="aguarda aprovação"):
        leilao.aprovar(AGORA)


def test_rn11_vendedor_nao_da_lance_no_leilao_que_criou(ana):
    leilao = leilao_da(ana)
    leilao.aprovar(AGORA)
    leilao.iniciar(INICIO)
    with pytest.raises(LanceRecusado) as erro:
        ana.darLance(leilao, VALOR("50"), INICIO)
    assert erro.value.motivo is MotivoRecusa.PROPRIO_LEILAO


def test_leilao_criado_pelo_cliente_termina_em_arremate_para_ele_como_vendedor(ana, bruno):
    leilao = leilao_da(ana)
    leilao.aprovar(AGORA)
    leilao.iniciar(INICIO)
    bruno.darLance(leilao, VALOR("80"), INICIO)
    arremate = leilao.encerrar(FIM)
    assert (arremate.vendedor, arremate.comprador, arremate.valor) == (ana, bruno, VALOR("80.00"))
    assert leilao.carta.status == StatusCarta.ARREMATADA


@pytest.fixture
def logado(cliente_http):
    criar_conta(cliente_http)
    return cliente_http


@pytest.fixture
def transporte(app):
    return app.config["CATALOGO"].transporte


def fotos_gravadas(app):
    pasta = Path(app.config["PASTA_DE_FOTOS"])
    return sorted(pasta.iterdir()) if pasta.exists() else []


@pytest.mark.parametrize("url", ["/vender", "/vender/novo", "/vender/novo?jogo=pokemon&carta=base1-4",
                                 "/vender/miniatura?jogo=pokemon&carta=base1-4"])
def test_vender_exige_login(cliente_http, url):
    resposta = cliente_http.get(url)
    assert resposta.status_code == 302
    assert resposta.headers["Location"].startswith("/entrar?proximo=")


def test_criar_leilao_sem_login_nao_cria_nada(cliente_http, app, banco):
    assert criar_leilao(cliente_http, app).status_code == 302
    assert leiloes_criados(banco) == []


def test_menu_mostra_vender_so_para_quem_esta_logado(cliente_http):
    assert 'href="/vender"' not in cliente_http.get("/leiloes").get_data(as_text=True)
    criar_conta(cliente_http)
    assert 'href="/vender"' in cliente_http.get("/leiloes").get_data(as_text=True)


def test_vender_sem_cartas_convida_a_criar_o_primeiro_leilao(logado):
    pagina = logado.get("/vender").get_data(as_text=True)
    assert "Você ainda não anunciou nenhuma carta." in pagina
    assert 'href="/vender/novo"' in pagina


def test_busca_comeca_com_os_quatro_jogos_e_pokemon_escolhido(logado):
    pagina = logado.get("/vender/novo").get_data(as_text=True)
    for jogo, slug in (("Pokémon", "pokemon"), ("Magic: The Gathering", "magic-the-gathering"),
                       ("Yu-Gi-Oh!", "yu-gi-oh"), ("One Piece Card Game", "one-piece-card-game")):
        assert f'href="/vender/novo?jogo={slug}"' in pagina and f">{jogo}</a>" in pagina
    assert 'href="/vender/novo?jogo=pokemon" aria-current="true"' in pagina
    assert "Sugestões de Pokémon" in pagina and pagina.count('class="cartao"') == 2
    assert "ou o código impresso nela, como" in pagina and ">90/112<" in pagina


@pytest.mark.parametrize("jogo, nome, cartas, trechos", [
    ("pokemon", "Pokémon", 2, (">Exeggcute</a>", "30th Celebration (001/128)", "carta=30th-001")),
    ("magic-the-gathering", "Magic: The Gathering", 2, (">Omnipresence</a>", "FRA 448", "Reality Fracture (448)")),
    ("yu-gi-oh", "Yu-Gi-Oh!", 2, (">Just Flip a Coin</a>", "25024929", "Beyond the Brave (BETB-EN083)")),
    ("one-piece-card-game", "One Piece Card Game", 4, (">Jewelry Bonney</a>", ">EB05-001<", "carta=EB05-001_p1")),
])
def test_escolher_o_jogo_ja_mostra_as_sugestoes_do_catalogo(logado, transporte, jogo, nome, cartas, trechos):
    pagina = logado.get(f"/vender/novo?jogo={jogo}").get_data(as_text=True)
    assert f"Sugestões de {nome}" in pagina and "Lançamentos recentes do jogo." in pagina
    assert pagina.count('class="cartao"') == cartas and "encontrada" not in pagina
    for trecho in trechos:
        assert trecho in pagina

    pedidos = len(transporte.pedidos)
    assert logado.get(f"/vender/novo?jogo={jogo}").status_code == 200
    assert len(transporte.pedidos) == pedidos, "as sugestões não são consultadas a cada visita"


def test_filtro_vazio_volta_para_as_sugestoes(logado):
    assert "Sugestões de Pokémon" in logado.get("/vender/novo?jogo=pokemon&q=++").get_data(as_text=True)


def test_busca_mostra_imagem_nome_codigo_edicao_e_especificacoes(logado):
    pagina = logado.get("/vender/novo?jogo=pokemon&q=charizard").get_data(as_text=True)
    assert pagina.count('class="cartao"') == 4 and "4 cartas encontradas em Pokémon" in pagina
    for trecho in (">Charizard</a>", "Base Set (4/102)", ">4/102<", "Pokémon · Stage2 · Fire",
                   'src="/vender/miniatura?jogo=pokemon&amp;carta=base1-4"',
                   'href="/vender/novo?jogo=pokemon&amp;carta=base1-4"'):
        assert trecho in pagina


@pytest.mark.parametrize("jogo, busca, trechos", [
    ("magic-the-gathering", "lightning", (">Lightning Bolt</a>", "SLC 83", "Secret Lair Countdown (83)", "Instant")),
    ("yu-gi-oh", "dark", (">Dark Magician</a>", "46986414", "4 edições", "Normal Monster · Spellcaster · DARK")),
    ("one-piece-card-game", "luffy", (">Monkey.D.Luffy</a>", "OP01-024", "Romance Dawn (OP01-024)", "Character")),
])
def test_filtro_de_jogo_busca_no_catalogo_daquele_jogo(logado, jogo, busca, trechos):
    pagina = logado.get(f"/vender/novo?jogo={jogo}&q={busca}").get_data(as_text=True)
    for trecho in trechos:
        assert trecho in pagina
    assert f'href="/vender/novo?jogo={jogo}" aria-current="true"' in pagina
    assert "Charizard" not in pagina and "Sugestões" not in pagina


@pytest.mark.parametrize("jogo, codigo, resumo, cartas", [
    ("pokemon", "90/112", "1 carta encontrada em Pokémon", ["ex6-90"]),
    ("pokemon", "4/102", "2 cartas encontradas em Pokémon", ["hgss4-4", "base1-4"]),
    ("one-piece-card-game", "OP02-025", "2 cartas encontradas em One Piece Card Game", ["OP02-025", "OP02-025_p1"]),
    ("one-piece-card-game", "op02-02", "3 cartas encontradas em One Piece Card Game",
     ["OP02-025", "OP02-025_p1", "OP02-026"]),
])
def test_filtro_tambem_acha_pelo_codigo_impresso_na_carta(logado, jogo, codigo, resumo, cartas):
    pagina = logado.get("/vender/novo", query_string={"jogo": jogo, "q": codigo}).get_data(as_text=True)
    assert resumo in pagina and pagina.count('class="cartao"') == len(cartas)
    posicoes = [pagina.index(f'href="/vender/novo?jogo={jogo}&amp;carta={carta}"') for carta in cartas]
    assert posicoes == sorted(posicoes)


@pytest.mark.parametrize("jogo, onde", [("pokemon", "no nome ou no código"), ("magic-the-gathering", "no nome")])
def test_busca_sem_resultado_orienta_o_vendedor(logado, jogo, onde):
    pagina = logado.get(f"/vender/novo?jogo={jogo}&q=nenhuma").get_data(as_text=True)
    assert f"com “nenhuma” {onde}." in pagina
    assert 'class="cartao"' not in pagina


def test_busca_com_uma_letra_nao_consulta_o_catalogo(logado, transporte):
    pagina = logado.get("/vender/novo?jogo=pokemon&q=c").get_data(as_text=True)
    assert "Digite pelo menos 2 caracteres para filtrar as cartas." in pagina and transporte.pedidos == []


def test_jogo_desconhecido_volta_para_a_busca(logado):
    assert logado.get("/vender/novo?jogo=xadrez&q=rei").headers["Location"] == "/vender/novo"


@pytest.mark.parametrize("url", ["/vender/novo?jogo=pokemon&q=charizard", "/vender/novo?jogo=pokemon"])
def test_catalogo_fora_do_ar_avisa_sem_derrubar_a_pagina(logado, transporte, url):
    transporte.fora_do_ar = True
    resposta = logado.get(url)
    pagina = resposta.get_data(as_text=True)
    assert resposta.status_code == 502
    assert "Não foi possível consultar o catálogo de Pokémon agora." in pagina
    assert 'id="q"' in pagina and pagina.count('class="chip"') == 4


def test_miniatura_e_baixada_uma_vez_e_servida_pela_loja(logado, transporte, app):
    logado.get("/vender/novo?jogo=pokemon&q=charizard")
    resposta = logado.get("/vender/miniatura?jogo=pokemon&carta=base1-4")
    assert resposta.status_code == 200 and resposta.mimetype == "image/png"
    assert resposta.get_data() == IMAGEM_DE_TESTE
    resposta.close()
    assert len(list(Path(app.config["PASTA_DO_CATALOGO"]).iterdir())) == 1

    pedidos = len(transporte.pedidos)
    logado.get("/vender/miniatura?jogo=pokemon&carta=base1-4").close()
    assert len(transporte.pedidos) == pedidos


@pytest.mark.parametrize("consulta", ["jogo=pokemon&carta=base1-999", "jogo=xadrez&carta=base1-4", "jogo=pokemon"])
def test_miniatura_de_carta_que_nao_existe(logado, consulta):
    assert logado.get(f"/vender/miniatura?{consulta}").status_code == 404


def test_formulario_traz_os_dados_do_catalogo_e_as_datas_sugeridas(logado, app):
    pagina = logado.get("/vender/novo?jogo=pokemon&carta=base1-4").get_data(as_text=True)
    for trecho in ("Charizard", ">4/102<", ">Base Set (4/102)<", ">Mitsuhiro Arita<",
                   "Categoria: Pokémon; Estágio: Stage2; Tipo: Fire; HP: 120; Raridade: Rare",
                   f'value="{no_fuso_da_loja(app)}"', f'value="{no_fuso_da_loja(app, days=7)}"',
                   "O incremento mínimo entre lances é R$ 5,00"):
        assert trecho in pagina
    for condicao in CONDICOES:
        assert f'<option value="{condicao}">' in pagina
    assert 'name="edicao"' not in pagina


@pytest.mark.parametrize("jogo, carta, preco", [
    ("pokemon", "base1-4", "US$\xa0922,32"),
    ("magic-the-gathering", ID_DO_RAIO, "US$\xa09,82"),
    ("yu-gi-oh", "46986414", "US$\xa00,33"),
    ("one-piece-card-game", "OP01-024_p1", "US$\xa0220,40"),
])
def test_formulario_mostra_o_valor_medio_de_mercado_da_carta(logado, jogo, carta, preco):
    pagina = logado.get(f"/vender/novo?jogo={jogo}&carta={carta}").get_data(as_text=True)
    assert "Valor médio de mercado" in pagina and f">{preco}<" in pagina
    assert "Preço de venda no TCGplayer, em dólares." in pagina


def test_formulario_abre_mesmo_sem_o_preco_da_carta(logado, transporte):
    logado.get("/vender/novo?jogo=pokemon&q=charizard")
    sem_preco = logado.get("/vender/novo?jogo=pokemon&carta=pl4-1")
    assert sem_preco.status_code == 200
    assert "O catálogo não tem o preço desta carta no momento." in sem_preco.get_data(as_text=True)

    transporte.fora_do_ar = True
    fora_do_ar = logado.get("/vender/novo?jogo=pokemon&carta=base1-4")
    assert fora_do_ar.status_code == 200
    assert "O catálogo não tem o preço desta carta no momento." in fora_do_ar.get_data(as_text=True)


def test_formulario_de_yugioh_pede_a_edicao(logado):
    pagina = logado.get("/vender/novo?jogo=yu-gi-oh&carta=46986414").get_data(as_text=True)
    assert '<select id="edicao" name="edicao"' in pagina
    assert pagina.count("<option", pagina.index('id="edicao"'), pagina.index('id="condicao"')) == 5
    assert '<option value="Battle of Chaos (25TH-EN001)">' in pagina


def test_formulario_de_carta_que_nao_existe(logado):
    assert logado.get("/vender/novo?jogo=pokemon&carta=base1-999").status_code == 404


def test_criar_leilao_cadastra_a_carta_e_o_leilao_pendente(logado, app, banco):
    resposta = criar_leilao(logado, app)
    assert (resposta.status_code, resposta.headers["Location"]) == (303, "/vender")

    (leilao,) = leiloes_criados(banco)
    ana = banco.execute("SELECT id FROM usuarios WHERE email = ?", ("ana@teste.com",)).fetchone()["id"]
    assert (leilao["nome"], leilao["jogo"], leilao["edicao"]) == ("Charizard", "Pokémon", "Base Set (4/102)")
    assert (leilao["condicao"], leilao["descricao"]) == ("Near Mint (NM)", "Holo sem riscos e bordas limpas.")
    assert (leilao["status"], leilao["status_da_carta"]) == ("pendente", "aguardando depósito")
    assert (leilao["lance_inicial_centavos"], leilao["incremento_minimo_centavos"]) == (5000, 500)
    assert leilao["vendedor_id"] == ana and leilao["data_fim_real"] is None
    assert banco.execute("SELECT COUNT(*) FROM jogos").fetchone()[0] == 3

    (foto,) = fotos_gravadas(app)
    assert leilao["foto"] == f"fotos/{foto.name}" and foto.read_bytes() == IMAGEM_DE_TESTE
    servida = logado.get(f"/fotos/{foto.name}")
    assert servida.status_code == 200 and servida.mimetype == "image/png"
    servida.close()


def test_leilao_criado_aparece_em_vender_e_nao_na_lista_de_ativos(logado, app, banco):
    pagina = logado.get(criar_leilao(logado, app).headers["Location"]).get_data(as_text=True)
    (leilao,) = leiloes_criados(banco)
    for trecho in ("Leilão criado. Leve a carta à loja", f'href="/leiloes/{leilao["id"]}">Charizard</a>',
                   "Aguardando depósito", "R$ 50,00", "Nenhum lance"):
        assert trecho in pagina
    assert logado.get("/leiloes").get_data(as_text=True).count('class="cartao"') == 15


def test_datas_do_formulario_sao_lidas_no_fuso_da_loja(logado, app, banco):
    criar_leilao(logado, app, inicio="2030-03-10T14:30", fim="2030-03-12T09:00")
    (leilao,) = leiloes_criados(banco)
    assert leilao["data_inicio"] == "2030-03-10T17:30:00.000+00:00"
    assert leilao["data_fim_prevista"] == "2030-03-12T12:00:00.000+00:00"


def test_primeira_carta_de_um_jogo_novo_cadastra_o_jogo(logado, app, banco):
    assert criar_leilao(logado, app, jogo="one-piece-card-game", carta="OP01-024_p1").status_code == 303
    (leilao,) = leiloes_criados(banco)
    assert (leilao["nome"], leilao["jogo"]) == ("Monkey.D.Luffy (Parallel)", "One Piece Card Game")
    assert leilao["edicao"] == "Romance Dawn (OP01-024)"

    criar_leilao(logado, app, jogo="one-piece-card-game", carta="OP01-024")
    assert banco.execute("SELECT COUNT(*) FROM jogos").fetchone()[0] == 4


def test_yugioh_grava_a_edicao_escolhida_e_recusa_a_que_nao_e_da_carta(logado, app, banco):
    yugioh = {"jogo": "yu-gi-oh", "carta": "46986414"}
    for edicao in ("", "Legend of Blue Eyes White Dragon (LOB-005)"):
        resposta = criar_leilao(logado, app, **yugioh, edicao=edicao)
        assert resposta.status_code == 422 and "Escolha a edição da sua carta." in resposta.get_data(as_text=True)
    assert leiloes_criados(banco) == []

    assert criar_leilao(logado, app, **yugioh, edicao="Battle of Chaos (25TH-EN001)").status_code == 303
    (leilao,) = leiloes_criados(banco)
    assert (leilao["nome"], leilao["edicao"]) == ("Dark Magician", "Battle of Chaos (25TH-EN001)")


def test_nome_edicao_e_foto_vem_do_catalogo_e_nao_do_formulario(logado, app, banco, transporte):
    criar_leilao(logado, app, nome="Carta falsa", edicao="Edição inventada",
                 imagem="https://exemplo.com/outra.png", foto="https://exemplo.com/outra.png")
    (leilao,) = leiloes_criados(banco)
    assert (leilao["nome"], leilao["edicao"]) == ("Charizard", "Base Set (4/102)")
    assert transporte.pedidos[-1] == "https://assets.tcgdex.net/en/base/base1/4/high.webp"


@pytest.mark.parametrize("campo, valor, mensagem", [
    ("condicao", "", "Escolha a condição da carta."),
    ("condicao", "Perfeita", "Escolha a condição da carta."),
    ("descricao", "   ", "Descreva a carta e o estado em que ela está."),
    ("descricao", "x" * 1001, "Use no máximo 1000 caracteres."),
    ("lance_inicial", "", "Informe o lance mínimo inicial."),
    ("lance_inicial", "cinquenta", "Valor em formato inválido."),
    ("lance_inicial", "0", "Informe um valor maior que zero, como 50,00."),
    ("inicio", "", "Informe a data e a hora de início."),
    ("inicio", "amanhã", "Informe a data e a hora de início."),
    ("fim", "", "Informe a data e a hora do fim previsto."),
])
def test_dado_invalido_e_apontado_no_campo_e_nada_e_criado(logado, app, banco, campo, valor, mensagem):
    resposta = criar_leilao(logado, app, **{campo: valor})
    pagina = resposta.get_data(as_text=True)
    assert resposta.status_code == 422 and mensagem in pagina
    assert f'id="erro-{campo}"' in pagina and 'role="alert"' in pagina
    assert 'value="50,00"' in pagina or campo == "lance_inicial"
    assert leiloes_criados(banco) == [] and fotos_gravadas(app) == []


def test_rn05_datas_do_leilao_sao_conferidas(logado, app, banco):
    for mudancas, mensagem in [
        ({"inicio": no_fuso_da_loja(app, minutes=-16)}, "A data de início já passou."),
        ({"fim": no_fuso_da_loja(app)}, "O fim previsto precisa ser depois do início."),
        ({"inicio": no_fuso_da_loja(app, days=5)}, "O fim previsto precisa ser depois do início."),
        ({"inicio": no_fuso_da_loja(app, minutes=-10), "fim": no_fuso_da_loja(app, minutes=-5)},
         "O fim previsto precisa estar no futuro."),
    ]:
        resposta = criar_leilao(logado, app, **mudancas)
        assert resposta.status_code == 422 and mensagem in resposta.get_data(as_text=True)
    assert leiloes_criados(banco) == []


def test_inicio_de_poucos_minutos_atras_e_aceito(logado, app, banco):
    """Quem abre o formulário e demora para enviar não é barrado."""
    assert criar_leilao(logado, app, inicio=no_fuso_da_loja(app, minutes=-13)).status_code == 303
    assert len(leiloes_criados(banco)) == 1


def test_foto_que_nao_baixa_impede_a_criacao(logado, app, banco, transporte):
    logado.get("/vender/novo?jogo=pokemon&q=charizard")
    transporte.fora_do_ar = True
    resposta = criar_leilao(logado, app)
    assert resposta.status_code == 422
    assert "Não foi possível baixar a foto da carta agora." in resposta.get_data(as_text=True)
    assert leiloes_criados(banco) == [] and fotos_gravadas(app) == []


def test_rn15_conta_bloqueada_nao_ve_a_busca_nem_cria_leilao(logado, app, banco):
    banco.execute("UPDATE clientes SET bloqueado = 1 WHERE usuario_id = (SELECT id FROM usuarios WHERE email = ?)",
                  ("ana@teste.com",))
    resposta = logado.get("/vender/novo?jogo=pokemon&q=charizard")
    assert resposta.status_code == 403
    assert "Contas bloqueadas não podem criar leilões." in resposta.get_data(as_text=True)
    assert criar_leilao(logado, app).status_code == 403
    assert leiloes_criados(banco) == []


def test_rn12_leilao_pendente_so_e_visto_pelo_vendedor(logado, app, banco):
    criar_leilao(logado, app)
    numero = leiloes_criados(banco)[0]["id"]
    pagina = logado.get(f"/leiloes/{numero}").get_data(as_text=True)
    for trecho in ("Aguardando aprovação", "aguarda o depósito da carta na loja e a aprovação",
                   "Início previsto"):
        assert trecho in pagina
    assert "data-form-lance" not in pagina

    bruno = outro_navegador(app)
    assert bruno.get(f"/leiloes/{numero}").status_code == 404
    assert bruno.get(f"/leiloes/{numero}/estado").status_code == 404
    assert lance_json(bruno, numero, "50,00").status_code == 404
    assert banco.execute("SELECT COUNT(*) FROM lances WHERE leilao_id = ?", (numero,)).fetchone()[0] == 0


def test_lojista_ve_o_leilao_pendente_e_aprova(logado, app, banco):
    admin = navegador_admin(app)
    assert "Nenhum leilão aguardando aprovação." in admin.get("/admin/leiloes").get_data(as_text=True)
    criar_leilao(logado, app)
    numero = leiloes_criados(banco)[0]["id"]

    lista = admin.get("/admin/leiloes").get_data(as_text=True)
    for trecho in (f'href="/leiloes/{numero}">Charizard</a>', "Base Set (4/102)", "Near Mint (NM)", "Ana Souza",
                   "Holo sem riscos e bordas limpas.", f'action="/admin/leiloes/{numero}/aprovar"'):
        assert trecho in lista

    assert f"Leilão {numero} (Charizard) aprovado: já está recebendo lances." in aprovar(app, numero)
    (leilao,) = leiloes_criados(banco)
    assert (leilao["status"], leilao["status_da_carta"]) == ("ativo", "em leilão")
    assert "Nenhum leilão aguardando aprovação." in admin.get("/admin/leiloes").get_data(as_text=True)


def test_aprovacao_recusa_leilao_inexistente_ou_que_nao_esta_pendente(logado, app, banco):
    assert "Não existe leilão 999." in aprovar(app, 999)
    criar_leilao(logado, app)
    numero = leiloes_criados(banco)[0]["id"]
    aprovar(app, numero)
    assert "aguarda aprovação" in aprovar(app, numero)
    assert "aguarda aprovação" in aprovar(app, 1)


def test_leilao_aprovado_entra_na_lista_e_recebe_lances_de_outros_clientes(logado, app, banco):
    criar_leilao(logado, app)
    numero = leiloes_criados(banco)[0]["id"]
    aprovar(app, numero)

    lista = logado.get("/leiloes").get_data(as_text=True)
    assert lista.count('class="cartao"') == 16 and f'href="/leiloes/{numero}">Charizard</a>' in lista
    assert "Em leilão" in logado.get("/vender").get_data(as_text=True)

    recusa = lance_json(logado, numero, "50,00")
    assert recusa.status_code == 422 and recusa.get_json()["motivo"] == "proprio_leilao"
    assert "Você é o vendedor desta carta" in logado.get(f"/leiloes/{numero}").get_data(as_text=True)

    bruno = outro_navegador(app)
    assert lance_json(bruno, numero, "49,99").status_code == 422
    aceito = lance_json(bruno, numero, "50,00")
    assert aceito.status_code == 201 and aceito.get_json()["estado"]["minimo_numero"] == "55,00"
    assert "R$ 50,00" in logado.get("/vender").get_data(as_text=True)


def test_leilao_aprovado_antes_do_inicio_fica_agendado_e_comeca_sozinho(logado, app, banco):
    criar_leilao(logado, app, inicio=no_fuso_da_loja(app, hours=2))
    numero = leiloes_criados(banco)[0]["id"]
    assert "começa na data de início" in aprovar(app, numero)
    (leilao,) = leiloes_criados(banco)
    assert (leilao["status"], leilao["status_da_carta"]) == ("aprovado", "aprovada")

    visitante = app.test_client()
    pagina = visitante.get(f"/leiloes/{numero}").get_data(as_text=True)
    assert "Agendado" in pagina and "Este leilão começa em" in pagina and "Entrar para dar lance" not in pagina
    assert "Aprovada (aguardando início)" in logado.get("/vender").get_data(as_text=True)
    assert visitante.get("/leiloes").get_data(as_text=True).count('class="cartao"') == 15

    avancar_relogio(app, hours=2, minutes=1)
    assert f'href="/leiloes/{numero}">Charizard</a>' in visitante.get("/leiloes").get_data(as_text=True)
    (leilao,) = leiloes_criados(banco)
    assert (leilao["status"], leilao["status_da_carta"]) == ("ativo", "em leilão")
    assert "Entrar para dar lance" in visitante.get(f"/leiloes/{numero}").get_data(as_text=True)


def test_leilao_aprovado_depois_do_inicio_marcado_comeca_na_aprovacao(logado, app, banco):
    criar_leilao(logado, app, inicio=no_fuso_da_loja(app, hours=1))
    numero = leiloes_criados(banco)[0]["id"]
    avancar_relogio(app, hours=5)
    assert "já está recebendo lances" in aprovar(app, numero)

    avancar_relogio(app, days=4)
    assert "aguarda aprovação" in aprovar(app, numero)


def test_fim_previsto_passado_impede_a_aprovacao(logado, app, banco):
    criar_leilao(logado, app)
    numero = leiloes_criados(banco)[0]["id"]
    avancar_relogio(app, days=4)
    assert "fim previsto deste leilão já passou" in aprovar(app, numero)
    assert leiloes_criados(banco)[0]["status"] == "pendente"


def test_vendedor_acompanha_a_carta_ate_o_arremate(logado, app, banco):
    criar_leilao(logado, app)
    numero = leiloes_criados(banco)[0]["id"]
    aprovar(app, numero)
    bruno = outro_navegador(app)
    lance_json(bruno, numero, "80,00")

    avancar_relogio(app, days=4)
    pagina = logado.get("/vender").get_data(as_text=True)
    for trecho in ("Arrematada (aguardando pagamento)", "Valor do arremate", "R$ 80,00"):
        assert trecho in pagina
    assert ">Charizard</a>" in bruno.get("/minha-conta/arremates").get_data(as_text=True)
    assert "Licitante 1 arrematou esta carta por R$ 80,00." in logado.get(f"/leiloes/{numero}").get_data(as_text=True)


def test_carta_sem_lances_e_devolvida_ao_vendedor(logado, app, banco):
    criar_leilao(logado, app)
    numero = leiloes_criados(banco)[0]["id"]
    aprovar(app, numero)
    avancar_relogio(app, days=4)
    pagina = logado.get("/vender").get_data(as_text=True)
    assert "Devolvida ao vendedor" in pagina and "Nenhum lance" in pagina
    assert leiloes_criados(banco)[0]["status_da_carta"] == "devolvida ao vendedor"
