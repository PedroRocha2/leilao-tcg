import io
import json
import urllib.error
from decimal import Decimal
from email.message import Message

import pytest

from apoio import ID_DO_RAIO, IMAGEM_DE_TESTE, TransporteFalso, amostra, catalogo_de_teste
from app.catalogo import Catalogo, CatalogoIndisponivel, PrecoMedio
from app.catalogo.base import LIMITE_DE_RESULTADOS, CartaDoCatalogo, Memoria, preco_medio
from app.catalogo.http import TAMANHO_MAXIMO, Transporte, _RedirecionamentoConferido, conferir_endereco
from app.catalogo.pokemon import Tcgdex

POKEMON, MAGIC, YUGIOH, ONE_PIECE = "Pokémon", "Magic: The Gathering", "Yu-Gi-Oh!", "One Piece Card Game"


@pytest.fixture
def catalogo():
    return catalogo_de_teste()


def test_catalogo_tem_os_quatro_jogos(catalogo):
    assert catalogo.jogos == [POKEMON, MAGIC, YUGIOH, ONE_PIECE]


def test_pokemon_traz_nome_codigo_edicao_especificacoes_e_imagem(catalogo):
    cartas = catalogo.buscar(POKEMON, "charizard")
    assert [carta.id for carta in cartas] == ["base1-4", "pl4-1", "gym2-2", "cel25-23"]

    charizard = cartas[0]
    assert (charizard.jogo, charizard.nome, charizard.codigo) == (POKEMON, "Charizard", "4/102")
    assert charizard.edicoes == ("Base Set (4/102)",)
    assert dict(charizard.especificacoes) == {
        "Categoria": "Pokémon", "Estágio": "Stage2", "Tipo": "Fire", "HP": "120", "Raridade": "Rare",
        "Ilustração": "Mitsuhiro Arita"}
    assert charizard.miniatura == "https://assets.tcgdex.net/en/base/base1/4/low.webp"
    assert charizard.imagem == "https://assets.tcgdex.net/en/base/base1/4/high.webp"


def test_pokemon_sem_imagem_no_catalogo_fica_fora_da_busca(catalogo):
    """RN04: a carta precisa de foto."""
    assert "2024sv-1" not in [carta.id for carta in catalogo.buscar(POKEMON, "charizard")]


def test_pokemon_carta_de_treinador_so_mostra_o_que_a_api_informa(catalogo):
    treinador = catalogo.buscar(POKEMON, "charizard")[-1]
    especificacoes = dict(treinador.especificacoes)
    assert especificacoes["Categoria"] == "Treinador" and especificacoes["Tipo de treinador"] == "Supporter"
    assert "HP" not in especificacoes and "Estágio" not in especificacoes


def test_magic_traz_uma_carta_por_impressao(catalogo):
    cartas = catalogo.buscar(MAGIC, "lightning bolt")
    assert [carta.codigo for carta in cartas] == ["SLC 83", "PLST CLB-187", "INR 60"]

    raio = cartas[0]
    assert (raio.id, raio.nome) == (ID_DO_RAIO, "Lightning Bolt")
    assert raio.edicoes == ("Secret Lair Countdown (83)",)
    assert dict(raio.especificacoes) == {"Tipo": "Instant", "Custo de mana": "{R}", "Raridade": "Rare",
                                         "Idioma": "EN"}
    assert raio.texto == "Lightning Bolt deals 3 damage to any target."
    assert "/normal/" in raio.miniatura and "/large/" in raio.imagem


def test_magic_carta_de_duas_faces_usa_a_frente_como_foto(catalogo):
    delver = catalogo.buscar(MAGIC, "lightning bolt")[2]
    assert delver.nome == "Delver of Secrets // Insectile Aberration"
    assert "/front/" in delver.miniatura and "/front/" in delver.imagem
    assert dict(delver.especificacoes)["Poder/Resistência"] == "1/1"
    assert " // " in delver.texto


def test_magic_busca_pelo_nome_so_cartas_de_papel_e_ignora_aspas(catalogo):
    catalogo.buscar(MAGIC, 'lightning "bolt"')
    pedido = catalogo.transporte.pedidos[-1]
    assert pedido.startswith("https://api.scryfall.com/cards/search?")
    assert "q=name%3A%22lightning++bolt+%22+game%3Apaper" in pedido and "unique=prints" in pedido


def test_yugioh_traz_as_edicoes_da_carta_para_o_vendedor_escolher(catalogo):
    cartas = catalogo.buscar(YUGIOH, "dark magician")
    assert [carta.nome for carta in cartas] == ["Dark Magician", "Dark Magician Girl"]

    mago = cartas[0]
    assert (mago.id, mago.codigo) == ("46986414", "46986414")
    assert mago.edicoes == ("2016 Mega-Tins (CT13-EN003)", "2017 Mega-Tins (CT14-EN001)",
                            "Battle of Chaos (25TH-EN001)", "Booster Pack Collectors Tins 2002 (BPT-001)")
    assert dict(mago.especificacoes) == {
        "Tipo de carta": "Normal Monster", "Tipo": "Spellcaster", "Atributo": "DARK", "Nível": "7",
        "ATK/DEF": "2500/2100", "Arquétipo": "Dark Magician"}
    assert "ultimate wizard" in mago.texto
    assert mago.miniatura.endswith("/cards_small/46986414.jpg") and mago.imagem.endswith("/cards/46986414.jpg")


def test_one_piece_junta_colecoes_decks_e_promocionais(catalogo):
    cartas = catalogo.buscar(ONE_PIECE, "luffy")
    assert [carta.id for carta in cartas] == ["OP01-024", "OP01-003", "OP01-024_p1", "OP01-003_p1", "ST01-012",
                                              "P-900"]
    grupos = sorted(pedido.split("/api/")[1].split("/")[0] for pedido in catalogo.transporte.pedidos)
    assert grupos == ["decks", "promos", "sets"]

    luffy = cartas[0]
    assert (luffy.nome, luffy.codigo) == ("Monkey.D.Luffy", "OP01-024")
    assert luffy.edicoes == ("Romance Dawn (OP01-024)",)
    assert dict(luffy.especificacoes) == {
        "Tipo de carta": "Character", "Cor": "Red", "Custo": "2", "Poder": "3000", "Counter": "1000",
        "Atributo": "Strike", "Subtipos": "Straw Hat Crew Supernovas", "Raridade": "SR"}
    assert luffy.texto.startswith("[DON!! x2]")
    assert luffy.miniatura == luffy.imagem == "https://optcgapi.com/media/static/Card_Images/OP01-024.jpg"


def test_one_piece_tira_o_numero_do_nome_e_mantem_a_variacao(catalogo):
    nomes = {carta.id: carta.nome for carta in catalogo.buscar(ONE_PIECE, "luffy")}
    assert nomes["OP01-024_p1"] == "Monkey.D.Luffy (Parallel)"
    assert nomes["P-900"] == "Monkey.D.Luffy (Sealed Battle 2024 Vol. 2)"
    assert catalogo.obter(ONE_PIECE, "OP01-024_p3").nome == "Monkey.D.Luffy (Alternate Art)"


def ids(cartas):
    return [carta.id for carta in cartas]


@pytest.mark.parametrize("codigo, achadas", [
    ("90/112", ["ex6-90"]),
    ("4/102", ["hgss4-4", "base1-4"]),
    ("004/198", ["sv01-004"]),
    ("4/198", ["sv01-004"]),
    ("90 / 112", ["ex6-90"]),
])
def test_pokemon_acha_a_carta_pelo_codigo_impresso(catalogo, codigo, achadas):
    """O número antes da barra e o total da coleção depois, como está na carta."""
    cartas = catalogo.buscar(POKEMON, codigo)
    assert ids(cartas) == achadas
    assert all(carta.codigo.lstrip("0") == codigo.replace(" ", "").lstrip("0") for carta in cartas)


def test_pokemon_codigo_pede_so_as_cartas_das_colecoes_com_aquele_total(catalogo):
    (energia,) = catalogo.buscar(POKEMON, "90/112")
    assert (energia.nome, energia.edicoes) == ("Energy Switch", ("FireRed & LeafGreen (90/112)",))
    colecoes, cartas = catalogo.transporte.corpos
    assert "sets" in colecoes["query"] and colecoes["variables"] == {}
    assert cartas["variables"] == {"carta0": "ex6-90", "carta1": "ex6-090"}

    catalogo.buscar(POKEMON, "4/102")
    assert len(catalogo.transporte.corpos) == 3, "a lista de coleções é consultada uma vez só"
    assert catalogo.buscar(POKEMON, "90/999") == [] and len(catalogo.transporte.corpos) == 3


def test_pokemon_numero_sem_o_total_traz_a_carta_de_cada_colecao(catalogo):
    """O TCGdex acha o número em qualquer parte (090, 190, BW90): sobra só o número exato."""
    for digitado in ("90", "090", "90/"):
        assert ids(catalogo.buscar(POKEMON, digitado)) == ["ex6-90", "sv01-090", "base1-90"]
        assert catalogo.transporte.corpos[-1]["variables"] == {"numero": "90"}
    assert ids(catalogo.buscar(POKEMON, "bw90")) == ["bwp-BW90"]


def test_pokemon_total_pela_metade_filtra_pelo_que_ja_foi_digitado(catalogo, monkeypatch):
    """Enquanto o total ainda serve a coleções demais, as cartas vêm pelo número e sobra o total que combina."""
    monkeypatch.setattr("app.catalogo.pokemon._COLECOES_POR_CONSULTA", 1)
    assert ids(catalogo.buscar(POKEMON, "90/1")) == ["ex6-90", "sv01-090", "base1-90"]
    assert catalogo.transporte.corpos[-1]["variables"] == {"numero": "90"}
    assert ids(catalogo.buscar(POKEMON, "90/11")) == ["ex6-90"]
    assert catalogo.transporte.corpos[-1]["variables"] == {"carta0": "ex6-90", "carta1": "ex6-090"}


def test_pokemon_nome_com_numero_continua_sendo_busca_pelo_nome(catalogo):
    catalogo.buscar(POKEMON, "Porygon2")
    assert catalogo.transporte.corpos[-1]["variables"] == {"nome": "Porygon2"}


@pytest.mark.parametrize("codigo, achadas", [
    ("OP02-025", ["OP02-025", "OP02-025_p1"]),
    ("op02-02", ["OP02-025", "OP02-025_p1", "OP02-026"]),
    ("OP02", ["OP02-025", "OP02-025_p1", "OP02-026"]),
    ("b02-025", []),
])
def test_one_piece_acha_a_carta_pelo_codigo_ou_pelo_comeco_dele(catalogo, codigo, achadas):
    """A API acha o código em qualquer parte ("b02-025" traz EB02-025): vale só o que começa pelo digitado."""
    assert ids(catalogo.buscar(ONE_PIECE, codigo)) == achadas
    assert all(f"card_image_id={codigo.upper()}" in pedido for pedido in catalogo.transporte.pedidos)
    assert len(catalogo.transporte.pedidos) == 3


def test_so_pokemon_e_one_piece_buscam_pelo_codigo(catalogo):
    exemplos = [catalogo.exemplo_de_codigo(jogo) for jogo in catalogo.jogos]
    assert exemplos == ["90/112", None, None, "OP02-025"]


@pytest.mark.parametrize("jogo, achadas, pedido", [
    (POKEMON, ["30th-001", "30th-002"], None),
    (MAGIC, ["91e787cb-a9b0-4353-86b4-a4340122fd2f", "1ad53db3-57e2-416d-907d-a71f63009c06"],
     "q=game%3Apaper+%28st%3Aexpansion+or+st%3Acore%29+date%3C%3Dtoday&unique=prints&order=released"),
    (YUGIOH, ["99630221", "25024929"], "sort=new&format=tcg&num=60&offset=0"),
    (ONE_PIECE, ["EB05-001", "EB05-001_p1", "EB05-002", "OP13-100"], "/api/sets/EB-05/"),
])
def test_sugestoes_sao_os_lancamentos_recentes_de_cada_jogo(catalogo, jogo, achadas, pedido):
    assert ids(catalogo.sugestoes(jogo)) == achadas
    assert pedido is None or catalogo.transporte.pedidos[-1].endswith(pedido)

    pedidos = len(catalogo.transporte.pedidos)
    assert ids(catalogo.sugestoes(jogo)) == achadas
    assert len(catalogo.transporte.pedidos) == pedidos, "as sugestões ficam guardadas"
    assert catalogo.obter(jogo, achadas[0]).id == achadas[0]
    assert len(catalogo.transporte.pedidos) == pedidos, "a carta sugerida não é consultada de novo"


def test_pokemon_sugere_a_colecao_mais_nova_que_ja_tem_imagem(catalogo):
    """A Delta Reign (me06) é a mais nova e ainda não tem imagens; a B2a é do Pokémon TCG Pocket, que é digital."""
    catalogo.sugestoes(POKEMON)
    consultadas = [corpo["variables"].get("colecao") for corpo in catalogo.transporte.corpos]
    assert consultadas == [None, "me06-", "30th-"]


def test_one_piece_sugere_a_colecao_anterior_quando_a_mais_nova_vem_vazia(catalogo, monkeypatch):
    responder = catalogo.transporte.json
    consultadas = []

    def sem_a_mais_nova(url, *resto, **opcoes):
        if "/sets/" not in url:
            return responder(url, *resto, **opcoes)
        consultadas.append(url.rsplit("/", 2)[1])
        return amostra("one_piece_colecao") if consultadas[-1] == "OP-17" else None

    monkeypatch.setattr(catalogo.transporte, "json", sem_a_mais_nova)
    assert ids(catalogo.sugestoes(ONE_PIECE))[0] == "EB05-001"
    assert consultadas == ["EB-05", "OP-17"]


def test_sugestoes_vazias_nao_ficam_guardadas(catalogo, monkeypatch):
    responder = catalogo.transporte.json
    monkeypatch.setattr(catalogo.transporte, "json", lambda *args, **opcoes: {"data": []})
    assert catalogo.sugestoes(YUGIOH) == []
    monkeypatch.setattr(catalogo.transporte, "json", responder)
    assert len(catalogo.sugestoes(YUGIOH)) == 2


@pytest.mark.parametrize("jogo, busca, id, preco", [
    (MAGIC, "lightning", ID_DO_RAIO, PrecoMedio(Decimal("9.82"), "USD", "TCGplayer")),
    (YUGIOH, "dark", "46986414", PrecoMedio(Decimal("0.33"), "USD", "TCGplayer")),
    (ONE_PIECE, "luffy", "OP01-024_p1", PrecoMedio(Decimal("220.4"), "USD", "TCGplayer")),
])
def test_preco_medio_vem_junto_com_a_carta(catalogo, jogo, busca, id, preco):
    carta = next(carta for carta in catalogo.buscar(jogo, busca) if carta.id == id)
    pedidos = len(catalogo.transporte.pedidos)
    assert carta.preco == preco and catalogo.preco(carta) == preco
    assert catalogo.preco(catalogo.obter(jogo, id)) == preco
    assert len(catalogo.transporte.pedidos) == pedidos


def test_magic_sem_preco_da_carta_comum_usa_o_da_foil(catalogo):
    foil, comum = catalogo.sugestoes(MAGIC)
    assert foil.preco == PrecoMedio(Decimal("3.50"), "USD", "TCGplayer")
    assert comum.preco == PrecoMedio(Decimal("0.26"), "USD", "TCGplayer")


def test_pokemon_consulta_o_preco_na_ficha_da_carta(catalogo):
    """A busca do TCGdex não traz preço: ele vem da ficha, quando o vendedor escolhe a carta."""
    charizard = catalogo.buscar(POKEMON, "charizard")[0]
    assert charizard.preco is None
    assert catalogo.preco(charizard) == PrecoMedio(Decimal("922.32"), "USD", "TCGplayer")
    assert catalogo.transporte.pedidos[-1] == "https://api.tcgdex.net/v2/en/cards/base1-4"

    pedidos = len(catalogo.transporte.pedidos)
    assert catalogo.preco(catalogo.obter(POKEMON, "base1-4")).valor == Decimal("922.32")
    assert len(catalogo.transporte.pedidos) == pedidos, "o preço consultado fica guardado com a carta"


def test_pokemon_preco_da_carta_comum_e_sem_tcgplayer_o_do_cardmarket(catalogo):
    tcgdex = Tcgdex(catalogo.transporte)
    assert tcgdex.preco("ex6-90") == PrecoMedio(Decimal("2.11"), "USD", "TCGplayer")
    assert tcgdex.preco("swsh9tg-TG05") == PrecoMedio(Decimal("13.79"), "EUR", "Cardmarket")
    assert tcgdex.preco("pl4-1") is None


@pytest.mark.parametrize("valor", [None, "", "0.00", 0, "sem preço", float("nan")])
def test_preco_ausente_ou_zerado_nao_e_preco(valor):
    assert preco_medio(valor, "USD", "TCGplayer") is None


def test_memoria_guarda_ate_vencer_e_nao_guarda_resposta_vazia():
    agora = [0.0]
    memoria = Memoria(validade=60, relogio=lambda: agora[0])
    respostas = iter([[], ["a"], ["b"]])

    def consultar():
        return next(respostas)

    assert memoria.obter("chave", consultar) == []
    assert memoria.obter("chave", consultar) == ["a"]
    agora[0] = 59
    assert memoria.obter("chave", consultar) == ["a"]
    agora[0] = 60
    assert memoria.obter("chave", consultar) == ["b"]


@pytest.mark.parametrize("jogo", [POKEMON, MAGIC, YUGIOH, ONE_PIECE])
def test_busca_sem_resultado_devolve_lista_vazia(catalogo, jogo):
    assert catalogo.buscar(jogo, "nao existe") == []


@pytest.mark.parametrize("jogo, id, nome, codigo", [
    (POKEMON, "base1-4", "Charizard", "4/102"),
    (MAGIC, ID_DO_RAIO, "Lightning Bolt", "SLC 83"),
    (YUGIOH, "46986414", "Dark Magician", "46986414"),
    (ONE_PIECE, "OP01-024_p1", "Monkey.D.Luffy (Parallel)", "OP01-024"),
])
def test_obter_a_carta_pelo_identificador(catalogo, jogo, id, nome, codigo):
    carta = catalogo.obter(jogo, id)
    assert (carta.id, carta.nome, carta.codigo) == (id, nome, codigo)


@pytest.mark.parametrize("jogo, id", [(POKEMON, "base1-999"), (MAGIC, "0" * 8 + "-0000-0000-0000-" + "0" * 12),
                                      (YUGIOH, "1"), (ONE_PIECE, "OP99-999"), ("Xadrez", "1")])
def test_obter_carta_que_nao_existe(catalogo, jogo, id):
    assert catalogo.obter(jogo, id) is None


@pytest.mark.parametrize("jogo, id", [(MAGIC, "../sets"), (MAGIC, "nao-e-uuid"), (YUGIOH, "46986414&num=1"),
                                      (ONE_PIECE, "OP01-024/../../x"), (ONE_PIECE, "OP01 024")])
def test_identificador_mal_formado_nem_chega_a_api(catalogo, jogo, id):
    assert catalogo.obter(jogo, id) is None
    assert catalogo.transporte.pedidos == []


def test_carta_vista_na_busca_nao_e_consultada_de_novo(catalogo):
    catalogo.buscar(POKEMON, "charizard")
    pedidos = len(catalogo.transporte.pedidos)
    assert catalogo.obter(POKEMON, "pl4-1").nome == "Charizard"
    assert len(catalogo.transporte.pedidos) == pedidos


def test_api_fora_do_ar_vira_catalogo_indisponivel(catalogo):
    catalogo.transporte.fora_do_ar = True
    for jogo in catalogo.jogos:
        with pytest.raises(CatalogoIndisponivel):
            catalogo.buscar(jogo, "charizard")


def test_resposta_em_formato_inesperado_vira_catalogo_indisponivel(catalogo):
    catalogo.transporte.json = lambda *args, **kwargs: {"errors": [{"message": "Cannot query field"}], "data": None}
    with pytest.raises(CatalogoIndisponivel, match="formato inesperado"):
        catalogo.buscar(POKEMON, "charizard")


def test_busca_devolve_no_maximo_o_limite_de_resultados():
    class Fonte:
        jogo = "Teste"

        def buscar(self, nome):
            return [CartaDoCatalogo("Teste", str(n), nome, str(n), ("Edição",), (), "", "", "")
                    for n in range(LIMITE_DE_RESULTADOS + 40)]

    assert len(Catalogo(TransporteFalso(), [Fonte()]).buscar("Teste", "carta")) == LIMITE_DE_RESULTADOS


class Resposta:
    def __init__(self, conteudo: bytes, tipo: str = "application/json"):
        self.conteudo = io.BytesIO(conteudo)
        self.headers = Message()
        self.headers["Content-Type"] = tipo

    def __enter__(self):
        return self

    def __exit__(self, *erro):
        return False

    def read(self, tamanho):
        return self.conteudo.read(tamanho)


def transporte_com(resposta):
    pedidos = []

    def abrir(pedido, timeout):
        pedidos.append(pedido)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    return Transporte("loja-de-teste/1.0", abrir), pedidos


def erro_http(codigo):
    return urllib.error.HTTPError("https://api.scryfall.com/cards/x", codigo, "erro", Message(), None)


def test_transporte_le_json_e_se_identifica():
    transporte, pedidos = transporte_com(Resposta(b'{"data": [1]}'))
    assert transporte.json("https://api.scryfall.com/cards/search?q=x") == {"data": [1]}
    (pedido,) = pedidos
    assert pedido.get_header("User-agent") == "loja-de-teste/1.0"
    assert pedido.get_header("Accept") == "application/json"
    assert pedido.get_method() == "GET"


def test_transporte_envia_o_corpo_em_json():
    transporte, pedidos = transporte_com(Resposta(b"{}"))
    transporte.json("https://api.tcgdex.net/v2/graphql", {"query": "{ cards }"})
    (pedido,) = pedidos
    assert pedido.get_method() == "POST" and json.loads(pedido.data) == {"query": "{ cards }"}
    assert pedido.get_header("Content-type") == "application/json"


def test_transporte_trata_nao_encontrado_como_vazio():
    transporte, _ = transporte_com(erro_http(404))
    assert transporte.json("https://api.scryfall.com/cards/x") is None
    transporte, _ = transporte_com(erro_http(400))
    assert transporte.json("https://db.ygoprodeck.com/api/v7/cardinfo.php?fname=x", vazio=(400, 404)) is None


@pytest.mark.parametrize("falha", [erro_http(500), erro_http(400), urllib.error.URLError("sem rede"),
                                   TimeoutError("demorou")])
def test_transporte_avisa_quando_a_api_falha(falha):
    transporte, _ = transporte_com(falha)
    with pytest.raises(CatalogoIndisponivel):
        transporte.json("https://api.scryfall.com/cards/x")


def test_transporte_recusa_resposta_que_nao_e_json_ou_e_grande_demais():
    transporte, _ = transporte_com(Resposta(b"<html>manutencao</html>", "text/html"))
    with pytest.raises(CatalogoIndisponivel, match="JSON"):
        transporte.json("https://api.scryfall.com/cards/x")
    transporte, _ = transporte_com(Resposta(b"x" * (TAMANHO_MAXIMO + 1)))
    with pytest.raises(CatalogoIndisponivel, match="grande demais"):
        transporte.json("https://api.scryfall.com/cards/x")


def test_transporte_baixa_imagem_e_recusa_o_que_nao_e_imagem():
    transporte, pedidos = transporte_com(Resposta(IMAGEM_DE_TESTE, "image/png"))
    assert transporte.imagem("https://cards.scryfall.io/large/x.jpg") == (IMAGEM_DE_TESTE, "image/png")
    assert pedidos[0].get_header("Accept") == "image/*"
    transporte, _ = transporte_com(Resposta(b"<svg/>", "image/svg+xml"))
    with pytest.raises(CatalogoIndisponivel, match="imagem"):
        transporte.imagem("https://cards.scryfall.io/large/x.jpg")


@pytest.mark.parametrize("url", ["http://api.scryfall.com/cards/x", "https://exemplo.com/cards/x",
                                 "https://api.scryfall.com.exemplo.com/x", "file:///etc/passwd",
                                 "https://127.0.0.1/x", "https://optcgapi.com@exemplo.com/x"])
def test_transporte_so_fala_com_os_enderecos_dos_catalogos(url):
    transporte, pedidos = transporte_com(Resposta(b"{}"))
    with pytest.raises(CatalogoIndisponivel, match="fora dos catálogos"):
        transporte.json(url)
    with pytest.raises(CatalogoIndisponivel, match="fora dos catálogos"):
        transporte.imagem(url)
    assert pedidos == []


def test_redirecionamento_para_fora_dos_catalogos_e_recusado():
    conferir_endereco("https://cards.scryfall.io/large/x.jpg")
    with pytest.raises(CatalogoIndisponivel, match="fora dos catálogos"):
        _RedirecionamentoConferido().redirect_request(None, None, 302, "Found", Message(),
                                                      "https://exemplo.com/imagem.jpg")
