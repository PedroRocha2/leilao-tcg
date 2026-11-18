"""One Piece Card Game pela OPTCG API (https://optcgapi.com/documentation)."""
import re
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlencode

from app.catalogo.base import CartaDoCatalogo, Filtro, especificacoes, preco_medio

API = "https://optcgapi.com/api"
_GRUPOS = ("sets", "decks", "promos")
_ID = re.compile(r"^[A-Za-z0-9-]+(_[A-Za-z0-9]+)?$")
# Código impresso, inteiro ou só o começo: OP02, OP02-025, ST01-012, P-001.
_CODIGO = re.compile(r"^[A-Za-z]{1,4}(\d{1,2}|\d{0,2}-\d{0,3})$")
# A API põe o número no nome: "Monkey.D.Luffy (024)", "... (OP01-024) (Alternate Art)".
_NUMERO_NO_NOME = re.compile(r"\s*\((?:\d{3}|[A-Z]{1,4}\d{0,2}-\d{3})\)")
_COLECOES_RECENTES = 3
_CORES = ("Red", "Green", "Blue", "Purple", "Black", "Yellow")
_TIPOS_DE_CARTA = ("Leader", "Character", "Event", "Stage")
_CUSTOS = tuple(str(custo) for custo in range(11))
_PODERES = tuple(str(poder) for poder in range(0, 14000, 1000))
_ATRIBUTOS = ("Slash", "Strike", "Ranged", "Special", "Wisdom")
_RARIDADES = {"C": "Common (C)", "UC": "Uncommon (UC)", "R": "Rare (R)", "SR": "Super Rare (SR)",
              "SEC": "Secret Rare (SEC)", "L": "Leader (L)", "TR": "Treasure Rare (TR)", "PR": "Promo (PR)"}
_NA_API = {"cor": "color", "categoria": "card_type", "custo": "card_cost", "poder": "card_power",
           "atributo": "attribute", "raridade": "rarity"}


def _palavras(texto: str) -> list[str]:
    """A API junta valores múltiplos: "Green Red", "Slash / Special"."""
    return re.split(r"[\s/]+", texto)


class Optcg:
    jogo = "One Piece Card Game"
    exemplo_de_codigo = "OP02-025"
    filtros = (
        Filtro("cor", "Cor", _CORES, ficha="Cor", separar=_palavras),
        Filtro("categoria", "Tipo de carta", _TIPOS_DE_CARTA, ficha="Tipo de carta"),
        Filtro("custo", "Custo", _CUSTOS, ficha="Custo"),
        Filtro("poder", "Poder", _PODERES, ficha="Poder"),
        Filtro("atributo", "Atributo", _ATRIBUTOS, ficha="Atributo", separar=_palavras),
        Filtro("raridade", "Raridade", tuple(_RARIDADES), ficha="Raridade", nomes=_RARIDADES),
    )

    def __init__(self, transporte):
        self.transporte = transporte

    def buscar(self, texto: str, filtros: Mapping[str, Sequence[str]] | None = None) -> list[CartaDoCatalogo]:
        filtros = filtros or {}
        # A API aceita um valor por filtro: o primeiro com várias opções vira um pedido por opção.
        consulta = {_NA_API[chave]: valores[0] for chave, valores in filtros.items() if len(valores) == 1}
        varios = next((chave for chave, valores in filtros.items() if len(valores) > 1), None)
        if not _CODIGO.match(texto):
            if texto:
                consulta["card_name"] = texto
            if varios is None or texto:
                return self._filtrar(**consulta)
            listas = [self._filtrar(**consulta, **{_NA_API[varios]: valor}) for valor in filtros[varios]]
            return _com_imagem_unica(carta for posicao in range(max(map(len, listas), default=0))
                                     for lista in listas if posicao < len(lista) for carta in [lista[posicao]])
        # A API acha o código em qualquer parte ("B02-025" traz EB02-025).
        codigo = texto.upper()
        cartas = [carta for carta in self._filtrar(card_image_id=codigo, **consulta)
                  if carta.id.upper().startswith(codigo)]
        return sorted(cartas, key=lambda carta: carta.id)

    def sugestoes(self) -> list[CartaDoCatalogo]:
        # As coleções vêm em ordem de lançamento.
        colecoes = self.transporte.json(f"{API}/allSets/") or []
        for colecao in reversed(colecoes[-_COLECOES_RECENTES:]):
            cartas = _com_imagem(self.transporte.json(f'{API}/sets/{quote(colecao["set_id"], safe="")}/'))
            if cartas:
                # A coleção traz reimpressões de outras (OP13-100 na EB-05): as dela vêm primeiro.
                propria = colecao["set_id"].replace("-", "")
                return sorted(cartas, key=lambda carta: (carta.codigo.split("-")[0] not in propria, carta.id))
        return []

    def obter(self, id: str) -> CartaDoCatalogo | None:
        if not _ID.match(id):
            return None
        # Variações (arte alternativa) dividem o código: OP01-024_p1.
        codigo = quote(id.split("_")[0], safe="")
        for grupo in _GRUPOS:
            for dados in self.transporte.json(f"{API}/{grupo}/card/{codigo}/") or []:
                if dados.get("card_image_id") == id:
                    return _carta(dados)
        return None

    def _filtrar(self, **filtro: str) -> list[CartaDoCatalogo]:
        consulta = urlencode(filtro)
        with ThreadPoolExecutor(len(_GRUPOS)) as fila:
            listas = list(fila.map(
                lambda grupo: self.transporte.json(f"{API}/{grupo}/filtered/?{consulta}"), _GRUPOS))
        return _com_imagem(dados for lista in listas for dados in lista or [])


def _com_imagem_unica(cartas) -> list[CartaDoCatalogo]:
    """A carta de duas cores vem no pedido de cada cor."""
    return list({carta.id: carta for carta in cartas}.values())


def _com_imagem(cartas) -> list[CartaDoCatalogo]:
    """A mesma carta pode vir de mais de um endereço da API."""
    achadas = {dados["card_image_id"]: carta for dados in cartas or [] if (carta := _carta(dados))}
    return list(achadas.values())


def _carta(dados: dict) -> CartaDoCatalogo | None:
    if not dados.get("card_image"):
        return None
    return CartaDoCatalogo(
        jogo=Optcg.jogo,
        id=dados["card_image_id"],
        nome=_NUMERO_NO_NOME.sub("", dados["card_name"]).strip(),
        codigo=dados["card_set_id"],
        edicoes=(f'{dados["set_name"]} ({dados["card_set_id"]})',),
        especificacoes=especificacoes(
            ("Tipo de carta", dados.get("card_type")),
            ("Cor", dados.get("card_color")),
            ("Custo", dados.get("card_cost")),
            ("Poder", dados.get("card_power")),
            ("Vida", dados.get("life")),
            ("Counter", dados.get("counter_amount")),
            ("Atributo", dados.get("attribute")),
            ("Subtipos", dados.get("sub_types")),
            ("Raridade", dados.get("rarity")),
        ),
        texto=dados.get("card_text") or "",
        miniatura=dados["card_image"],
        imagem=dados["card_image"],
        # Segundo o site da API, os dados vêm do TCGplayer, que cota em dólares.
        preco=preco_medio(dados.get("market_price"), "USD", "TCGplayer"),
    )
