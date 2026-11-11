"""Pokémon pelo TCGdex (https://tcgdex.dev): as cartas pela API GraphQL e o preço pela ficha da carta."""
import re
from urllib.parse import quote

from app.catalogo.base import LIMITE_DE_RESULTADOS, CartaDoCatalogo, Memoria, PrecoMedio, especificacoes, preco_medio

API = "https://api.tcgdex.net/v2/graphql"
FICHA = "https://api.tcgdex.net/v2/en/cards"
_CAMPOS = ("id localId name image rarity hp types category stage trainerType energyType illustrator "
           "set { name cardCount { official } }")


def _consulta(filtro: str, variavel: str, tipo: str, quantas: int) -> str:
    return (f"query(${variavel}: {tipo}!) {{ cards(filters: {{{filtro}: ${variavel}}}, "
            f"pagination: {{page: 1, itemsPerPage: {quantas}}}) {{ {_CAMPOS} }} }}")


_BUSCA = _consulta("name", "nome", "String", LIMITE_DE_RESULTADOS)
# Os filtros do TCGdex acham o texto em qualquer parte do campo: "90" traz 090, 190 e SM90, e "30th-" traz
# também a coleção "30th-c". Por isso vem uma página maior, e sobra o que serve.
_POR_NUMERO = _consulta("localId", "numero", "String", 300)
_DA_COLECAO = _consulta("id", "colecao", "ID", 2 * LIMITE_DE_RESULTADOS)
_CARTA = f"query($id: ID!) {{ card(id: $id) {{ {_CAMPOS} }} }}"
_COLECOES = "{ sets { id releaseDate serie { id } cardCount { official } } }"

_CATEGORIAS = {"Pokemon": "Pokémon", "Trainer": "Treinador", "Energy": "Energia"}
# O código impresso na carta: número, barra e total da coleção (90/112, TG05/TG30), ou só o número (SWSH001).
_CODIGO = re.compile(r"^([A-Za-z]{0,5}\d{1,4}[A-Za-z]?)\s*(?:/\s*([A-Za-z]{0,5}\d{0,4}))?$")
_POCKET = "tcgp"
_COLECOES_RECENTES = 3
_COLECOES_POR_CONSULTA = 20
# O TCGplayer separa o preço por acabamento: vale o da carta comum e, se ela não existe, o da holográfica.
_ACABAMENTOS = ("normal", "holofoil", "reverse-holofoil")


class Tcgdex:
    jogo = "Pokémon"
    exemplo_de_codigo = "90/112"

    def __init__(self, transporte):
        self.transporte = transporte
        self._memoria = Memoria()

    def buscar(self, texto: str) -> list[CartaDoCatalogo]:
        codigo = _CODIGO.match(texto)
        if codigo:
            return self._por_codigo(codigo[1].upper(), "".join(filter(str.isdigit, codigo[2] or "")))
        resposta = self.transporte.json(API, {"query": _BUSCA, "variables": {"nome": texto}})
        return _com_imagem(resposta["data"]["cards"])

    def sugestoes(self) -> list[CartaDoCatalogo]:
        # O TCGdex cadastra a coleção antes de ter as imagens: vale a mais recente que já tem.
        for colecao in self._colecoes()[:_COLECOES_RECENTES]:
            resposta = self.transporte.json(
                API, {"query": _DA_COLECAO, "variables": {"colecao": f'{colecao["id"]}-'}})
            cartas = _com_imagem(resposta["data"]["cards"])
            if cartas:
                return cartas
        return []

    def obter(self, id: str) -> CartaDoCatalogo | None:
        resposta = self.transporte.json(API, {"query": _CARTA, "variables": {"id": id}})
        dados = (resposta.get("data") or {}).get("card")
        return _carta(dados) if dados else None

    def preco(self, id: str) -> PrecoMedio | None:
        ficha = self.transporte.json(f"{FICHA}/{quote(id, safe='')}") or {}
        precos = ficha.get("pricing") or {}
        tcgplayer = precos.get("tcgplayer") or {}
        for acabamento in dict.fromkeys((*_ACABAMENTOS, *tcgplayer)):
            dados = tcgplayer.get(acabamento)
            if isinstance(dados, dict) and (preco := preco_medio(dados.get("marketPrice"), "USD", "TCGplayer")):
                return preco
        return preco_medio((precos.get("cardmarket") or {}).get("avg"), "EUR", "Cardmarket")

    def _por_codigo(self, numero: str, total: str) -> list[CartaDoCatalogo]:
        """As cartas de número `numero`; `total` é o que o vendedor já digitou do total da coleção."""
        if total:
            colecoes = [colecao["id"] for colecao in self._colecoes()
                        if str(colecao["cardCount"]["official"]).startswith(total)]
            if not colecoes:
                return []
            if len(colecoes) <= _COLECOES_POR_CONSULTA:
                return self._por_id([f"{colecao}-{escrita}" for colecao in colecoes for escrita in _escritas(numero)])
        resposta = self.transporte.json(API, {"query": _POR_NUMERO, "variables": {"numero": _sem_zeros(numero)}})
        return _com_imagem(
            dados for dados in resposta["data"]["cards"] or []
            if _sem_zeros(dados["localId"].upper()) == _sem_zeros(numero)
            and str((dados["set"].get("cardCount") or {}).get("official")).startswith(total))

    def _por_id(self, ids: list[str]) -> list[CartaDoCatalogo]:
        """Várias cartas em um pedido só; o id da carta no TCGdex é "coleção-número"."""
        variaveis = {f"carta{n}": id for n, id in enumerate(ids)}
        parametros = ", ".join(f"${nome}: ID!" for nome in variaveis)
        pedidos = " ".join(f"{nome}: card(id: ${nome}) {{ {_CAMPOS} }}" for nome in variaveis)
        resposta = self.transporte.json(
            API, {"query": f"query({parametros}) {{ {pedidos} }}", "variables": variaveis})
        return _com_imagem(resposta["data"].values())

    def _colecoes(self) -> list[dict]:
        """As coleções de cartas físicas, da mais recente para a mais antiga."""
        return self._memoria.obter("coleções", self._consultar_colecoes)

    def _consultar_colecoes(self) -> list[dict]:
        resposta = self.transporte.json(API, {"query": _COLECOES, "variables": {}})
        # O TCGdex também cataloga o Pokémon TCG Pocket, que não tem carta física para leiloar.
        fisicas = [colecao for colecao in resposta["data"]["sets"] if colecao["serie"]["id"] != _POCKET]
        return sorted(fisicas, key=lambda colecao: colecao.get("releaseDate") or "", reverse=True)


def _sem_zeros(numero: str) -> str:
    return numero.lstrip("0") or "0"


def _escritas(numero: str) -> list[str]:
    """Como o TCGdex grava o número: sem zeros à esquerda nas coleções antigas, com três dígitos nas novas."""
    if not numero.isdigit():
        return [numero]
    curto = _sem_zeros(numero)
    return list(dict.fromkeys((curto, curto.zfill(3))))


def _com_imagem(cartas) -> list[CartaDoCatalogo]:
    return [carta for dados in cartas or [] if dados and (carta := _carta(dados))]


def _carta(dados: dict) -> CartaDoCatalogo | None:
    if not dados.get("image"):
        return None
    colecao = dados["set"]
    total = (colecao.get("cardCount") or {}).get("official")
    codigo = f'{dados["localId"]}/{total}' if total else dados["localId"]
    return CartaDoCatalogo(
        jogo=Tcgdex.jogo,
        id=dados["id"],
        nome=dados["name"],
        codigo=codigo,
        edicoes=(f'{colecao["name"]} ({codigo})',),
        especificacoes=especificacoes(
            ("Categoria", _CATEGORIAS.get(dados.get("category"), dados.get("category"))),
            ("Estágio", dados.get("stage")),
            ("Tipo", ", ".join(dados.get("types") or [])),
            ("HP", dados.get("hp")),
            ("Tipo de treinador", dados.get("trainerType")),
            ("Tipo de energia", dados.get("energyType")),
            ("Raridade", dados.get("rarity")),
            ("Ilustração", dados.get("illustrator")),
        ),
        texto="",
        miniatura=f'{dados["image"]}/low.webp',
        imagem=f'{dados["image"]}/high.webp',
    )
