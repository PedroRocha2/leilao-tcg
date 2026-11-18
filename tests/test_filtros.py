"""Os filtros pelas características das cartas: na página de cada jogo (RF06) e na busca de Criar leilão."""
from urllib.parse import parse_qs, urlsplit

import pytest

from apoio import (ITERACOES_DE_TESTE, TransporteFalso, amostra, aprovar_leilao, catalogo_de_teste, criar_conta,
                   criar_leilao, leiloes_criados)
from app import db
from app.catalogo import Catalogo, atributos_da_descricao, criar_catalogo
from app.catalogo.base import LIMITE_DE_RESULTADOS, Filtro, atributos, por_virgula
from app.catalogo.magic import Scryfall
from app.catalogo.one_piece import Optcg
from app.catalogo.pokemon import Tcgdex
from app.catalogo.yugioh import Ygoprodeck
from app.db import conectar

POKEMON, MAGIC, YUGIOH, ONE_PIECE = "Pokémon", "Magic: The Gathering", "Yu-Gi-Oh!", "One Piece Card Game"


def nomes(pagina: str) -> list[str]:
    partes = pagina.split('class="cartao__nome"')[1:]
    return [parte.split("</a>")[0].rsplit(">", 1)[-1] for parte in partes]


# ------------------------------------------------------------------------------------ definição dos filtros

def test_cada_jogo_tem_os_seus_filtros():
    catalogo = catalogo_de_teste()
    rotulos = {jogo: [filtro.rotulo for filtro in catalogo.filtros(jogo)] for jogo in catalogo.jogos}
    assert rotulos == {
        POKEMON: ["Categoria", "Tipo", "Estágio", "Raridade"],
        MAGIC: ["Cor", "Tipo", "Raridade"],
        YUGIOH: ["Tipo de carta", "Atributo", "Tipo", "Nível"],
        ONE_PIECE: ["Cor", "Tipo de carta", "Custo", "Poder", "Atributo", "Raridade"],
    }
    for jogo in catalogo.jogos:
        chaves = [filtro.chave for filtro in catalogo.filtros(jogo)]
        # As chaves viram parâmetros do endereço: não se repetem nem colidem com os da busca.
        assert len(set(chaves)) == len(chaves) and not {"q", "jogo", "carta"} & set(chaves)
    assert catalogo.filtros("Xadrez") == ()


def test_atributos_saem_das_especificacoes_e_so_valem_as_opcoes_do_filtro():
    filtros = (Filtro("tipo", "Tipo", ("Fire", "Water"), ficha="Tipo", separar=por_virgula),
               Filtro("raridade", "Raridade", ("Rare",), ficha="Raridade"))
    assert atributos(filtros, [("Tipo", "Fire, Water, Fire"), ("Raridade", "Rare"), ("HP", "120")]) == (
        ("tipo", "Fire"), ("tipo", "Water"), ("raridade", "Rare"))
    assert atributos(filtros, [("Tipo", "Grass"), ("Raridade", "None")]) == ()


@pytest.mark.parametrize("jogo, busca, id_da_carta, esperado", [
    (POKEMON, "charizard", "base1-4",
     {("categoria", "Pokémon"), ("tipo", "Fire"), ("estagio", "Stage2"), ("raridade", "Rare")}),
    (MAGIC, "lightning bolt", "bba5ea18-4e58-42a8-b613-2178706476a6",
     {("cor", "Vermelha"), ("tipo", "Instant"), ("raridade", "Rare")}),
    (YUGIOH, "dark magician", "46986414",
     {("categoria", "Normal Monster"), ("atributo", "DARK"), ("tipo", "Spellcaster"), ("nivel", "7")}),
    (ONE_PIECE, "luffy", "OP01-024",
     {("cor", "Red"), ("categoria", "Character"), ("custo", "2"), ("poder", "3000"), ("atributo", "Strike"),
      ("raridade", "SR")}),
])
def test_carta_de_cada_jogo_tem_os_atributos_do_catalogo(jogo, busca, id_da_carta, esperado):
    catalogo = catalogo_de_teste()
    carta = next(carta for carta in catalogo.buscar(jogo, busca) if carta.id == id_da_carta)
    assert set(catalogo.atributos(jogo, carta.especificacoes)) == esperado


@pytest.mark.parametrize("linha, cores, esperado", [
    ("Legendary Artifact Creature — Golem", ["R", "G"],
     {("tipo", "Artifact"), ("tipo", "Creature"), ("cor", "Vermelha"), ("cor", "Verde")}),
    ("Basic Land — Forest", [], {("tipo", "Land"), ("cor", "Incolor")}),
    ("Creature — Human // Enchantment — Aura", ["W"],
     {("tipo", "Creature"), ("tipo", "Enchantment"), ("cor", "Branca")}),
])
def test_magic_separa_os_tipos_e_as_cores_da_carta(linha, cores, esperado):
    dados = {**amostra("magic_carta"), "type_line": linha, "colors": cores}
    transporte = TransporteFalso()
    transporte.json = lambda url, corpo=None, vazio=(): dados
    carta = criar_catalogo("teste", transporte).obter(MAGIC, dados["id"])
    assert set(criar_catalogo("teste", transporte).atributos(MAGIC, carta.especificacoes)) >= esperado


def test_one_piece_separa_as_cores_e_os_atributos_juntos_e_ignora_o_que_a_api_manda_sujo():
    catalogo = catalogo_de_teste()
    pares = catalogo.atributos(ONE_PIECE, [("Cor", "Green Red"), ("Atributo", "Slash / Special"),
                                           ("Poder", "Ohara"), ("Custo", "None"), ("Raridade", "L")])
    assert pares == (("cor", "Green"), ("cor", "Red"), ("atributo", "Slash"), ("atributo", "Special"),
                     ("raridade", "L"))
    raridade = catalogo.filtros(ONE_PIECE)[-1]
    assert (raridade.nome("SR"), raridade.nome("XX")) == ("Super Rare (SR)", "XX")


# ------------------------------------------------------------------------------------ o que vai para as APIs

class Espiao:
    """Um transporte que anota os pedidos e devolve as respostas combinadas, na ordem."""

    def __init__(self, *respostas):
        self.pedidos, self.corpos, self._respostas = [], [], list(respostas)

    def json(self, url, corpo=None, vazio=(404,)):
        self.pedidos.append(url)
        self.corpos.append(corpo)
        return self._respostas.pop(0) if self._respostas else None

    def consulta(self, posicao=0) -> dict:
        return {chave: valores[0] for chave, valores in parse_qs(urlsplit(self.pedidos[posicao]).query).items()}


def test_pokemon_filtra_pela_api_rest_e_busca_os_dados_das_cartas_em_um_pedido():
    lista = [{"id": "base1-4", "localId": "4", "name": "Charizard", "image": "https://assets.tcgdex.net/en/base/base1/4"},
             {"id": "sem-foto-1", "localId": "1", "name": "Charizard"},
             {"id": "P-A-007", "localId": "007", "name": "Charizard", "image": "https://assets.tcgdex.net/en/tcgp/P-A/007"}]
    detalhes = {"data": {"carta0": amostra("pokemon_carta")["data"]["card"]}}
    espiao = Espiao(lista, detalhes)

    cartas = Tcgdex(espiao).buscar("char", {"categoria": ["Pokémon"], "tipo": ["Fire"], "estagio": ["Stage2"],
                                            "raridade": ["Rare"]})
    assert [carta.id for carta in cartas] == ["base1-4"]
    assert espiao.pedidos[0].startswith("https://api.tcgdex.net/v2/en/cards?")
    assert espiao.consulta() == {
        "category": "eq:Pokemon", "types": "Fire", "stage": "eq:Stage2", "rarity": "eq:Rare", "name": "char",
        "pagination:page": "1", "pagination:itemsPerPage": str(3 * LIMITE_DE_RESULTADOS)}
    # Só a carta com imagem e que não é do Pokémon TCG Pocket tem os dados pedidos ao GraphQL.
    assert espiao.corpos[1]["variables"] == {"carta0": "base1-4"}

    vazio = Espiao([])
    assert Tcgdex(vazio).buscar("", {"tipo": ["Water"]}) == [] and len(vazio.pedidos) == 1
    assert "name" not in vazio.consulta()


def test_pokemon_manda_as_opcoes_do_mesmo_filtro_separadas_por_barra():
    espiao = Espiao([])
    Tcgdex(espiao).buscar("", {"categoria": ["Treinador", "Energia"], "tipo": ["Fire", "Water"],
                               "raridade": ["Rare", "Holo Rare"], "estagio": ["Basic", "Stage2"]})
    consulta = espiao.consulta()
    assert (consulta["category"], consulta["types"], consulta["rarity"], consulta["stage"]) == (
        "eq:Trainer|Energy", "Fire|Water", "eq:Rare|Holo Rare", "eq:Basic|Stage2")


def test_pokemon_sem_filtros_continua_buscando_pelo_nome_no_graphql():
    espiao = Espiao(amostra("pokemon_busca"))
    assert Tcgdex(espiao).buscar("charizard") and espiao.corpos[0]["variables"] == {"nome": "charizard"}


@pytest.mark.parametrize("nome, filtros, consulta", [
    ("bolt", {"cor": ["Vermelha"], "tipo": ["Instant"], "raridade": ["Mythic"]},
     'name:"bolt" game:paper c:r t:instant r:mythic'),
    ("", {"cor": ["Incolor"]}, "game:paper c:c"),
    ("", {"cor": ["Azul"], "tipo": ["Creature"]}, "game:paper c:u t:creature"),
    ("", {"cor": ["Vermelha", "Azul", "Incolor"], "raridade": ["Rare", "Mythic"]},
     "game:paper (c:r or c:u or c:c) (r:rare or r:mythic)"),
    ("bolt", {}, 'name:"bolt" game:paper'),
])
def test_magic_monta_a_pesquisa_do_scryfall(nome, filtros, consulta):
    espiao = Espiao(amostra("magic_busca"))
    assert Scryfall(espiao).buscar(nome, filtros)
    assert espiao.consulta() == {"q": consulta, "unique": "prints", "order": "released"}


def test_yugioh_manda_os_filtros_e_sem_nome_pede_as_cartas_mais_novas():
    espiao = Espiao(amostra("yugioh_busca"), amostra("yugioh_busca"))
    fonte = Ygoprodeck(espiao)
    fonte.buscar("dragon", {"categoria": ["Fusion Monster"], "atributo": ["DARK"], "tipo": ["Dragon"],
                            "nivel": ["8"]})
    assert espiao.consulta(0) == {"fname": "dragon", "type": "Fusion Monster", "attribute": "DARK",
                                  "race": "Dragon", "level": "8", "num": "60", "offset": "0"}
    fonte.buscar("", {"atributo": ["WATER"]})
    assert espiao.consulta(1) == {"sort": "new", "format": "tcg", "attribute": "WATER", "num": "60", "offset": "0"}


def test_yugioh_junta_as_opcoes_por_virgula_e_faz_um_pedido_por_nivel():
    espiao = Espiao()
    Ygoprodeck(espiao).buscar("", {"categoria": ["Spell Card", "Trap Card"], "atributo": ["DARK", "LIGHT"],
                                   "tipo": ["Dragon", "Spellcaster"]})
    assert espiao.consulta() == {"sort": "new", "format": "tcg", "type": "Spell Card,Trap Card",
                                 "attribute": "DARK,LIGHT", "race": "Dragon,Spellcaster", "num": "60", "offset": "0"}

    # A API só aceita um nível por pedido: as cartas de cada nível entram intercaladas.
    carta = amostra("yugioh_carta")["data"][0]
    por_nivel = Espiao({"data": [{**carta, "id": 71, "level": 7}, {**carta, "id": 72, "level": 7}]},
                       {"data": [{**carta, "id": 81, "level": 8}]})
    cartas = Ygoprodeck(por_nivel).buscar("", {"nivel": ["7", "8"], "atributo": ["DARK"]})
    assert sorted(por_nivel.consulta(n)["level"] for n in (0, 1)) == ["7", "8"]
    assert all(por_nivel.consulta(n)["attribute"] == "DARK" for n in (0, 1))
    assert sorted(carta.id for carta in cartas) == ["71", "72", "81"] and cartas[2].id == "72"


def test_one_piece_manda_os_filtros_aos_tres_enderecos_da_api():
    espiao = Espiao(amostra("one_piece_carta"), [], [])
    cartas = Optcg(espiao).buscar("luffy", {"cor": ["Red"], "categoria": ["Character"], "custo": ["2"],
                                            "poder": ["3000"], "atributo": ["Strike"], "raridade": ["SR"]})
    # A amostra traz a carta e as variações dela (arte alternativa, paralela), todas com os mesmos atributos.
    assert cartas and {carta.codigo for carta in cartas} == {"OP01-024"}
    assert sorted(urlsplit(url).path for url in espiao.pedidos) == [
        "/api/decks/filtered/", "/api/promos/filtered/", "/api/sets/filtered/"]
    assert espiao.consulta() == {"card_name": "luffy", "color": "Red", "card_type": "Character", "card_cost": "2",
                                 "card_power": "3000", "attribute": "Strike", "rarity": "SR"}

    so_filtros = Espiao([], [], [])
    Optcg(so_filtros).buscar("", {"cor": ["Blue"]})
    assert so_filtros.consulta() == {"color": "Blue"}


def test_one_piece_faz_um_pedido_por_opcao_do_primeiro_filtro_com_varias():
    """A API aceita um valor por filtro: o que não vai no pedido fica para a conferência da loja."""
    espiao = Espiao()
    Optcg(espiao).buscar("", {"cor": ["Red", "Blue"], "categoria": ["Leader"], "raridade": ["SR", "SEC"]})
    consultas = [espiao.consulta(n) for n in range(len(espiao.pedidos))]
    assert len(consultas) == 6 and all(consulta["card_type"] == "Leader" for consulta in consultas)
    assert sorted(consulta["color"] for consulta in consultas) == ["Blue"] * 3 + ["Red"] * 3
    assert not any("rarity" in consulta for consulta in consultas)

    # Com o nome digitado, um pedido só: o nome já estreita a busca e a loja confere as opções.
    com_nome = Espiao()
    Optcg(com_nome).buscar("luffy", {"cor": ["Red", "Blue"], "categoria": ["Leader"]})
    assert [com_nome.consulta(n) for n in range(3)] == [{"card_name": "luffy", "card_type": "Leader"}] * 3


def test_catalogo_confere_as_cartas_que_a_api_devolve_e_descarta_filtro_invalido():
    class Fonte:
        jogo = "Teste"
        filtros = (Filtro("cor", "Cor", ("Red", "Blue"), ficha="Cor"),)

        def __init__(self):
            self.pedidos = []

        def buscar(self, texto, filtros=None):
            self.pedidos.append((texto, filtros))
            carta = catalogo_de_teste().buscar(ONE_PIECE, "luffy")[0]
            # A API ignorou o filtro e mandou uma carta de cada cor.
            return [carta.__class__(**{**carta.__dict__, "jogo": "Teste", "id": cor,
                                       "especificacoes": (("Cor", cor),)}) for cor in ("Red", "Blue", "Red")]

    fonte = Fonte()
    catalogo = Catalogo(TransporteFalso(), [fonte])
    assert [carta.id for carta in catalogo.buscar("Teste", "", {"cor": "Blue"})] == ["Blue"]
    assert fonte.pedidos[-1] == ("", {"cor": ["Blue"]})
    assert [carta.id for carta in catalogo.buscar("Teste", "", {"cor": ["Blue", "Red"]})] == ["Red", "Blue", "Red"]
    assert len(catalogo.buscar("Teste", "luffy", {"cor": "Rosa", "poder": "9000"})) == 3
    assert fonte.pedidos[-1] == ("luffy", None)
    assert catalogo.filtros_validos("Teste", {"cor": "Red", "tipo": "x"}) == {"cor": ["Red"]}
    assert catalogo.filtros_validos("Teste", {"cor": ["Blue", "Rosa", "Blue", "Red"]}) == {"cor": ["Blue", "Red"]}


# ---------------------------------------------------------------------------------- página de cada jogo (RF06)

def test_painel_mostra_so_as_opcoes_que_algum_leilao_ativo_tem_com_o_total(cliente_http):
    pagina = cliente_http.get("/jogos/pokemon").get_data(as_text=True)
    assert '<aside class="jogo__filtros" aria-label="Filtros de Pokémon">' in pagina
    for legenda in ("Categoria", "Tipo", "Estágio", "Raridade"):
        assert f"<legend>{legenda}</legend>" in pagina
    for valor in ("Fire", "Water", "Grass", "Lightning", "Psychic", "Basic", "Stage2", "Common", "Rare"):
        assert f'value="{valor}"' in pagina
    # Nenhum leilão ativo de carta do tipo Dragon nem de raridade Uncommon: as opções não aparecem.
    assert 'value="Dragon"' not in pagina and 'value="Uncommon"' not in pagina
    assert 'name="estagio" value="Stage2">' in pagina and "(3 leilões)" in pagina and "(1 leilão)" in pagina
    assert "Limpar filtros" not in pagina and "checked" not in pagina


@pytest.mark.parametrize("url, achadas", [
    ("/jogos/pokemon?tipo=Fire", ["Charizard"]),
    ("/jogos/pokemon?estagio=Basic", ["Pikachu", "Mewtwo"]),
    # RN23
    ("/jogos/pokemon?tipo=Fire&tipo=Water", ["Charizard", "Blastoise"]),
    ("/jogos/pokemon?estagio=Stage2&raridade=Rare&tipo=Grass", ["Venusaur"]),
    ("/jogos/pokemon?estagio=Basic&tipo=Fire", []),
    ("/jogos/pokemon?raridade=Rare&q=char", ["Charizard"]),
    ("/jogos/magic-the-gathering?cor=Vermelha", ["Shivan Dragon", "Lightning Bolt"]),
    ("/jogos/magic-the-gathering?cor=Incolor&tipo=Artifact", ["Sol Ring"]),
    ("/jogos/magic-the-gathering?tipo=Instant&raridade=Uncommon", ["Counterspell"]),
    ("/jogos/yu-gi-oh?atributo=LIGHT", ["Blue-Eyes White Dragon"]),
    ("/jogos/yu-gi-oh?tipo=Dragon", ["Red-Eyes Black Dragon", "Blue-Eyes White Dragon"]),
    ("/jogos/yu-gi-oh?categoria=Effect+Monster&nivel=1", ["Kuriboh"]),
    ("/jogos/pokemon?tipo=Fogo&cor=Vermelha&poder=9000", ["Venusaur", "Pikachu", "Blastoise", "Mewtwo", "Charizard"]),
])
def test_filtros_da_pagina_do_jogo(cliente_http, url, achadas):
    resposta = cliente_http.get(url)
    assert resposta.status_code == 200
    assert sorted(nomes(resposta.get_data(as_text=True))) == sorted(achadas)


def test_pagina_filtrada_marca_as_opcoes_resume_e_oferece_limpar(cliente_http):
    pagina = cliente_http.get("/jogos/pokemon?tipo=Fire&tipo=Water&q=a").get_data(as_text=True)
    assert 'name="tipo" value="Fire" checked>' in pagina and 'name="tipo" value="Water" checked>' in pagina
    assert 'name="tipo" value="Grass">' in pagina
    assert "2 cartas de Pokémon com “a” com os filtros escolhidos recebendo lances." in " ".join(pagina.split())
    assert '<input type="hidden" name="q" value="a">' in pagina
    assert '<a class="filtros__limpar" href="/jogos/pokemon?q=a">Limpar filtros</a>' in pagina

    vazia = cliente_http.get("/jogos/pokemon?estagio=Basic&tipo=Fire").get_data(as_text=True)
    assert "Nenhum leilão ativo de Pokémon com esses filtros." in vazia
    assert "Nenhuma carta de Pokémon com os filtros escolhidos recebendo lances neste momento." in " ".join(vazia.split())
    assert 'name="estagio" value="Basic" checked>' in vazia and 'name="tipo" value="Fire" checked>' in vazia


def test_filtro_so_conta_leilao_ativo(cliente_http, banco):
    banco.execute("UPDATE leiloes SET status = 'cancelado' WHERE carta_id = (SELECT id FROM cartas WHERE nome ="
                  " 'Charizard')")
    pagina = cliente_http.get("/jogos/pokemon").get_data(as_text=True)
    assert 'value="Fire"' not in pagina and 'value="Water"' in pagina
    assert nomes(cliente_http.get("/jogos/pokemon?tipo=Fire").get_data(as_text=True)) == []


def test_leilao_criado_pelo_catalogo_grava_os_atributos_e_entra_nos_filtros(cliente_http, app, banco):
    criar_conta(cliente_http)
    criar_leilao(cliente_http, app, jogo="one-piece-card-game", carta="OP01-024")
    numero = leiloes_criados(banco)[0]["id"]
    gravados = {(linha["chave"], linha["valor"]) for linha in banco.execute(
        "SELECT a.chave, a.valor FROM carta_atributos a JOIN leiloes l ON l.carta_id = a.carta_id WHERE l.id = ?",
        (numero,))}
    assert gravados == {("cor", "Red"), ("categoria", "Character"), ("custo", "2"), ("poder", "3000"),
                        ("atributo", "Strike"), ("raridade", "SR")}

    assert "jogo__filtros" not in cliente_http.get("/jogos/one-piece-card-game").get_data(as_text=True)
    aprovar_leilao(app, numero)
    pagina = cliente_http.get("/jogos/one-piece-card-game").get_data(as_text=True)
    for legenda in ("Cor", "Tipo de carta", "Custo", "Poder", "Atributo", "Raridade"):
        assert f"<legend>{legenda}</legend>" in pagina
    assert "Super Rare (SR)" in pagina and 'name="poder" value="3000">' in pagina
    assert nomes(cliente_http.get("/jogos/one-piece-card-game?cor=Red&poder=3000").get_data(as_text=True)) == [
        "Monkey.D.Luffy"]
    assert nomes(cliente_http.get("/jogos/one-piece-card-game?cor=Blue").get_data(as_text=True)) == []


def test_remover_a_carta_apaga_os_atributos_dela(cliente_http, app, banco):
    from apoio import CSRF, navegador_admin
    criar_conta(cliente_http)
    criar_leilao(cliente_http, app)
    numero = leiloes_criados(banco)[0]["id"]
    antes = banco.execute("SELECT COUNT(*) FROM carta_atributos").fetchone()[0]
    navegador_admin(app).post(f"/admin/cartas/{numero}/remover", data={"csrf_token": CSRF})
    assert banco.execute("SELECT COUNT(*) FROM carta_atributos").fetchone()[0] == antes - 4


# ------------------------------------------------------------------------------------ busca de Criar leilão

@pytest.fixture
def logado(cliente_http):
    criar_conta(cliente_http)
    return cliente_http


@pytest.mark.parametrize("jogo, nome, rotulos, opcao", [
    ("pokemon", "Pokémon", ["Categoria", "Tipo", "Estágio", "Raridade"], ("raridade", "Mega Hyper Rare")),
    ("magic-the-gathering", "Magic: The Gathering", ["Cor", "Tipo", "Raridade"], ("cor", "Incolor")),
    ("yu-gi-oh", "Yu-Gi-Oh!", ["Tipo de carta", "Atributo", "Tipo", "Nível"], ("nivel", "12")),
    ("one-piece-card-game", "One Piece Card Game", ["Cor", "Tipo de carta", "Custo", "Poder", "Atributo", "Raridade"],
     ("poder", "13000")),
])
def test_busca_de_criar_leilao_tem_o_mesmo_painel_de_filtros_da_pagina_do_jogo(logado, jogo, nome, rotulos, opcao):
    pagina = logado.get(f"/vender/novo?jogo={jogo}").get_data(as_text=True)
    assert f'<aside class="jogo__filtros" aria-label="Filtros de {nome}">' in pagina
    assert '<details class="filtros" open data-filtros>' in pagina
    assert [parte.split("</legend>")[0] for parte in pagina.split("<legend>")[1:]] == rotulos
    assert 'name="{}" value="{}">'.format(*opcao) in pagina
    assert "filtro__total" not in pagina and "checked" not in pagina and "Limpar filtros" not in pagina
    assert "Sugestões de" in pagina and "<select" not in pagina.split("<main")[1]
    assert pagina.index('data-filtro-cartas') < pagina.index('<aside class="jogo__filtros"') < pagina.index('id="q"')
    assert "Escolha o jogo e a sua carta" not in pagina and "cabecalho__texto" not in pagina


def test_filtro_escolhido_busca_no_catalogo_mesmo_sem_nome(logado, transporte_de_one_piece):
    resposta = logado.get("/vender/novo?jogo=one-piece-card-game&cor=Red&categoria=Character&raridade=SR")
    pagina = resposta.get_data(as_text=True)
    assert resposta.status_code == 200
    assert "cartas encontradas em One Piece Card Game" in pagina or "carta encontrada em One Piece Card Game" in pagina
    assert 'name="cor" value="Red" checked>' in pagina and 'name="cor" value="Blue">' in pagina
    assert 'name="raridade" value="SR" checked>' in pagina and "Super Rare (SR)" in pagina
    assert '<a class="filtros__limpar" href="/vender/novo?jogo=one-piece-card-game">Limpar filtros</a>' in pagina
    assert "Sugestões de" not in pagina and ">Monkey.D.Luffy<" in pagina
    consulta = parse_qs(urlsplit(transporte_de_one_piece.pedidos[-1]).query)
    assert consulta == {"color": ["Red"], "card_type": ["Character"], "rarity": ["SR"]}


@pytest.fixture
def transporte_de_one_piece(app):
    """O catálogo de teste responde aos filtros do One Piece com as cartas da amostra do Luffy."""
    transporte = app.config["CATALOGO"].transporte
    original = transporte._optcg

    def optcg(caminho, consulta):
        if caminho.endswith("/filtered/") and "card_name" not in consulta and "card_image_id" not in consulta:
            return amostra("one_piece_sets") if "/sets/" in caminho else None
        return original(caminho, consulta)

    transporte._optcg = optcg
    return transporte


def test_filtro_que_nenhuma_carta_atende_e_filtro_invalido(logado, transporte_de_one_piece):
    vazia = logado.get("/vender/novo?jogo=one-piece-card-game&cor=Yellow&poder=13000").get_data(as_text=True)
    assert "Nenhuma carta de One Piece Card Game com esses filtros." in vazia
    assert "Tire algum filtro" in vazia

    com_nome = logado.get("/vender/novo?jogo=one-piece-card-game&q=luffy&poder=13000").get_data(as_text=True)
    assert "Nenhuma carta de One Piece Card Game com esses filtros e “luffy” no nome ou no código." in com_nome

    invalida = logado.get("/vender/novo?jogo=one-piece-card-game&cor=Rosa&estagio=Stage2").get_data(as_text=True)
    assert "Sugestões de One Piece Card Game" in invalida


def test_varias_opcoes_do_mesmo_filtro_na_busca_de_criar_leilao(logado):
    uma = nomes(logado.get("/vender/novo?jogo=one-piece-card-game&q=luffy&categoria=Leader").get_data(as_text=True))
    resposta = logado.get("/vender/novo?jogo=one-piece-card-game&q=luffy&categoria=Leader&categoria=Character")
    pagina = resposta.get_data(as_text=True)
    assert 'name="categoria" value="Leader" checked>' in pagina
    assert 'name="categoria" value="Character" checked>' in pagina
    assert len(nomes(pagina)) > len(uma) > 0
    assert 'href="/vender/novo?jogo=one-piece-card-game&amp;q=luffy">Limpar filtros</a>' in pagina


def test_nome_e_filtro_juntos_estreitam_a_busca(logado):
    todas = nomes(logado.get("/vender/novo?jogo=one-piece-card-game&q=luffy").get_data(as_text=True))
    lideres = nomes(logado.get("/vender/novo?jogo=one-piece-card-game&q=luffy&categoria=Leader").get_data(as_text=True))
    assert 0 < len(lideres) < len(todas)


def test_catalogo_fora_do_ar_com_filtro_avisa_sem_derrubar_a_pagina(logado, app):
    app.config["CATALOGO"].transporte.fora_do_ar = True
    resposta = logado.get("/vender/novo?jogo=yu-gi-oh&atributo=DARK")
    assert resposta.status_code == 502
    assert "Não foi possível consultar o catálogo de Yu-Gi-Oh! agora." in resposta.get_data(as_text=True)


# ------------------------------------------------------------------------------- bancos que já existiam

def test_descricao_antiga_devolve_os_atributos_que_ainda_estao_nela():
    assert atributos_da_descricao(
        POKEMON, "Categoria: Pokémon; Estágio: Stage2; Tipo: Fire, Water; HP: 120; Raridade: Rare; "
                 "Ilustração: Mitsuhiro Arita. Carta sem riscos. Bordas: limpas.") == (
        ("categoria", "Pokémon"), ("tipo", "Fire"), ("tipo", "Water"), ("estagio", "Stage2"), ("raridade", "Rare"))
    # Carta de Magic de antes de a especificação "Cor" existir: a cor sai do custo de mana.
    assert set(atributos_da_descricao(
        MAGIC, "Tipo: Legendary Artifact Creature — Golem; Custo de mana: {2}{R}{G}; Raridade: Mythic.")) == {
        ("cor", "Vermelha"), ("cor", "Verde"), ("tipo", "Artifact"), ("tipo", "Creature"), ("raridade", "Mythic")}
    assert atributos_da_descricao(MAGIC, "Tipo: Artifact; Custo de mana: {1}; Raridade: Uncommon.")[0] == (
        "cor", "Incolor")
    assert atributos_da_descricao(YUGIOH, "Holo sem riscos e bordas limpas.") == ()
    assert atributos_da_descricao("Xadrez", "Tipo: Fire.") == ()


def test_banco_da_versao_anterior_ganha_a_tabela_e_os_atributos_sem_perder_dados(tmp_path):
    caminho = str(tmp_path / "antigo.sqlite3")
    db.preparar_banco(caminho, administrador={"login": "adm", "senha": "segredo-forte", "iteracoes": ITERACOES_DE_TESTE})
    conexao = conectar(caminho)
    # Volta o banco para a versão 5: sem a tabela de atributos e com uma carta cadastrada por um vendedor.
    conexao.execute("DROP TABLE carta_atributos")
    conexao.execute("PRAGMA user_version = 5")
    vendedor = conexao.execute("SELECT usuario_id FROM clientes LIMIT 1").fetchone()[0]
    jogo = conexao.execute("SELECT id FROM jogos WHERE nome = ?", (POKEMON,)).fetchone()[0]
    conexao.execute(
        "INSERT INTO cartas (jogo_id, vendedor_id, nome, edicao, condicao, descricao, status) VALUES (?, ?, 'Gyarados',"
        " 'Base Set (6/102)', 'Near Mint (NM)', 'Categoria: Pokémon; Estágio: Stage1; Tipo: Water; HP: 100; "
        "Raridade: Rare. Sem riscos.', 'aguardando depósito')", (jogo, vendedor))
    cartas = conexao.execute("SELECT COUNT(*) FROM cartas").fetchone()[0]
    conexao.close()

    db.preparar_banco(caminho)
    db.preparar_banco(caminho)
    conexao = conectar(caminho)
    assert conexao.execute("PRAGMA user_version").fetchone()[0] == db.VERSAO_DO_ESQUEMA == 6
    assert conexao.execute("SELECT COUNT(*) FROM cartas").fetchone()[0] == cartas == 16

    def de(nome):
        return {(linha["chave"], linha["valor"]) for linha in conexao.execute(
            "SELECT a.chave, a.valor FROM carta_atributos a JOIN cartas c ON c.id = a.carta_id WHERE c.nome = ?",
            (nome,))}

    assert de("Gyarados") == {("categoria", "Pokémon"), ("estagio", "Stage1"), ("tipo", "Water"), ("raridade", "Rare")}
    assert de("Charizard") == {("categoria", "Pokémon"), ("estagio", "Stage2"), ("tipo", "Fire"), ("raridade", "Rare")}
    assert de("Sol Ring") == {("cor", "Incolor"), ("tipo", "Artifact"), ("raridade", "Uncommon")}
    assert conexao.execute("SELECT COUNT(DISTINCT carta_id) FROM carta_atributos").fetchone()[0] == 16
    conexao.close()


def test_carga_inicial_usa_so_valores_que_os_filtros_conhecem():
    from app.carga_inicial import ATRIBUTOS, CARTAS
    catalogo = catalogo_de_teste()
    for jogo, nome, *_ in CARTAS:
        opcoes = {filtro.chave: filtro.opcoes for filtro in catalogo.filtros(jogo)}
        for chave, valor in ATRIBUTOS[nome].items():
            assert valor in opcoes[chave], f"{nome}: {chave}={valor}"
