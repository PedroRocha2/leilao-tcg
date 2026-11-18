"""Pokémon pelo TCGdex (https://tcgdex.dev): cartas pelo GraphQL, preço pela ficha da carta."""
import re
from collections.abc import Mapping, Sequence
from urllib.parse import quote, urlencode

from app.catalogo.base import (LIMITE_DE_RESULTADOS, CartaDoCatalogo, Filtro, Memoria, PrecoMedio, especificacoes,
                               por_virgula, preco_medio)

API = "https://api.tcgdex.net/v2/graphql"
FICHA = "https://api.tcgdex.net/v2/en/cards"
_CAMPOS = ("id localId name image rarity hp types category stage trainerType energyType illustrator "
           "set { name cardCount { official } }")


def _consulta(filtro: str, variavel: str, tipo: str, quantas: int) -> str:
    return (f"query(${variavel}: {tipo}!) {{ cards(filters: {{{filtro}: ${variavel}}}, "
            f"pagination: {{page: 1, itemsPerPage: {quantas}}}) {{ {_CAMPOS} }} }}")


_BUSCA = _consulta("name", "nome", "String", LIMITE_DE_RESULTADOS)
# O TCGdex acha o texto em qualquer parte ("90" traz 190 e SM90): vem uma página maior.
_POR_NUMERO = _consulta("localId", "numero", "String", 300)
_DA_COLECAO = _consulta("id", "colecao", "ID", 2 * LIMITE_DE_RESULTADOS)
_CARTA = f"query($id: ID!) {{ card(id: $id) {{ {_CAMPOS} }} }}"
_COLECOES = "{ sets { id releaseDate serie { id } cardCount { official } } }"

_CATEGORIAS = {"Pokemon": "Pokémon", "Trainer": "Treinador", "Energy": "Energia"}
_TIPOS = ("Colorless", "Darkness", "Dragon", "Fairy", "Fighting", "Fire", "Grass", "Lightning", "Metal", "Psychic",
          "Water")
_ESTAGIOS = ("Basic", "Stage1", "Stage2", "Baby", "BREAK", "LEVEL-UP", "MEGA", "RESTORED", "V-UNION", "VMAX", "VSTAR")
# Só as de cartas físicas (sem o Pokémon TCG Pocket).
_RARIDADES = (
    "Common", "Uncommon", "Rare", "Rare Holo", "Holo Rare", "Holo Rare V", "Holo Rare VMAX", "Holo Rare VSTAR",
    "Double rare", "Ultra Rare", "Illustration rare", "Special illustration rare", "Hyper rare", "Secret Rare",
    "Shiny rare", "Shiny rare V", "Shiny rare VMAX", "Shiny Ultra Rare", "Amazing Rare", "Radiant Rare",
    "ACE SPEC Rare", "Rare PRIME", "Rare Holo LV.X", "LEGEND", "Full Art Trainer", "Classic Collection",
    "Black White Rare", "Mega Attack Rare", "Mega Hyper Rare", "Futuristic Rare", "RGB Rare", "Pikachu Rare", "Promo")
# "eq:" pede o valor exato ("Rare" traria "Holo Rare"); "|" separa valores como "ou".
_NA_API = {"categoria": ("category", "eq:"), "tipo": ("types", ""), "estagio": ("stage", "eq:"),
           "raridade": ("rarity", "eq:")}
_CATEGORIAS_NA_API = {nome: chave for chave, nome in _CATEGORIAS.items()}
# Código impresso: 90/112, TG05/TG30 ou SWSH001.
_CODIGO = re.compile(r"^([A-Za-z]{0,5}\d{1,4}[A-Za-z]?)\s*(?:/\s*([A-Za-z]{0,5}\d{0,4}))?$")
_POCKET = "tcgp"
_COLECOES_RECENTES = 3
_COLECOES_POR_CONSULTA = 20
# Em ordem de preferência: a carta comum antes da holográfica.
_ACABAMENTOS = ("normal", "holofoil", "reverse-holofoil")


class Tcgdex:
    jogo = "Pokémon"
    exemplo_de_codigo = "90/112"
    filtros = (
        Filtro("categoria", "Categoria", tuple(_CATEGORIAS.values()), ficha="Categoria"),
        Filtro("tipo", "Tipo", _TIPOS, ficha="Tipo", separar=por_virgula),
        Filtro("estagio", "Estágio", _ESTAGIOS, ficha="Estágio"),
        Filtro("raridade", "Raridade", _RARIDADES, ficha="Raridade"),
    )

    def __init__(self, transporte):
        self.transporte = transporte
        self._memoria = Memoria()

    def buscar(self, texto: str, filtros: Mapping[str, Sequence[str]] | None = None) -> list[CartaDoCatalogo]:
        codigo = _CODIGO.match(texto)
        if codigo:
            return self._por_codigo(codigo[1].upper(), "".join(filter(str.isdigit, codigo[2] or "")))
        if filtros:
            return self._filtradas(texto, filtros)
        resposta = self.transporte.json(API, {"query": _BUSCA, "variables": {"nome": texto}})
        return _com_imagem(resposta["data"]["cards"])

    def _filtradas(self, nome: str, filtros: Mapping[str, Sequence[str]]) -> list[CartaDoCatalogo]:
        """O GraphQL não filtra pelo tipo: a lista vem da API REST e os dados, do GraphQL."""
        consulta = {}
        for chave, (parametro, prefixo) in _NA_API.items():
            if chave in filtros:
                valores = [_CATEGORIAS_NA_API.get(valor, valor) for valor in filtros[chave]]
                consulta[parametro] = prefixo + "|".join(valores)
        if nome:
            consulta["name"] = nome
        # Página maior: parte das cartas não tem imagem ou é do Pokémon TCG Pocket.
        consulta |= {"pagination:page": 1, "pagination:itemsPerPage": 3 * LIMITE_DE_RESULTADOS}
        lista = self.transporte.json(f"{FICHA}?{urlencode(consulta)}") or []
        ids = [carta["id"] for carta in lista if carta.get("image") and f"/{_POCKET}/" not in carta["image"]]
        return self._por_id(ids[:LIMITE_DE_RESULTADOS]) if ids else []

    def sugestoes(self) -> list[CartaDoCatalogo]:
        # O TCGdex cadastra a coleção antes de ter as imagens.
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
        """`total` é o começo do total da coleção, como o vendedor digitou."""
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
        """Várias cartas em um pedido só."""
        variaveis = {f"carta{n}": id for n, id in enumerate(ids)}
        parametros = ", ".join(f"${nome}: ID!" for nome in variaveis)
        pedidos = " ".join(f"{nome}: card(id: ${nome}) {{ {_CAMPOS} }}" for nome in variaveis)
        resposta = self.transporte.json(
            API, {"query": f"query({parametros}) {{ {pedidos} }}", "variables": variaveis})
        return _com_imagem(resposta["data"].values())

    def _colecoes(self) -> list[dict]:
        return self._memoria.obter("coleções", self._consultar_colecoes)

    def _consultar_colecoes(self) -> list[dict]:
        resposta = self.transporte.json(API, {"query": _COLECOES, "variables": {}})
        # O Pokémon TCG Pocket não tem carta física.
        fisicas = [colecao for colecao in resposta["data"]["sets"] if colecao["serie"]["id"] != _POCKET]
        return sorted(fisicas, key=lambda colecao: colecao.get("releaseDate") or "", reverse=True)


def _sem_zeros(numero: str) -> str:
    return numero.lstrip("0") or "0"


def _escritas(numero: str) -> list[str]:
    """O TCGdex grava sem zeros à esquerda nas coleções antigas e com três dígitos nas novas."""
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
