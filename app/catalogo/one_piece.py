"""One Piece Card Game pela OPTCG API (https://optcgapi.com/documentation)."""
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlencode

from app.catalogo.base import CartaDoCatalogo, especificacoes, preco_medio

API = "https://optcgapi.com/api"
# A API separa as cartas de coleções, de decks iniciais e promocionais em três endereços.
_GRUPOS = ("sets", "decks", "promos")
_ID = re.compile(r"^[A-Za-z0-9-]+(_[A-Za-z0-9]+)?$")
# O código impresso na carta, inteiro ou só o começo: OP02, OP02-0, OP02-025, ST01-012, P-001.
_CODIGO = re.compile(r"^[A-Za-z]{1,4}(\d{1,2}|\d{0,2}-\d{0,3})$")
# A API acrescenta o número da carta ao nome: "Monkey.D.Luffy (024)", "... (OP01-024) (Alternate Art)".
_NUMERO_NO_NOME = re.compile(r"\s*\((?:\d{3}|[A-Z]{1,4}\d{0,2}-\d{3})\)")
_COLECOES_RECENTES = 3


class Optcg:
    jogo = "One Piece Card Game"
    exemplo_de_codigo = "OP02-025"

    def __init__(self, transporte):
        self.transporte = transporte

    def buscar(self, texto: str) -> list[CartaDoCatalogo]:
        if not _CODIGO.match(texto):
            return self._filtrar(card_name=texto)
        # O filtro acha o código em qualquer parte ("B02-025" traria EB02-025): sobra o que começa por ele.
        codigo = texto.upper()
        cartas = [carta for carta in self._filtrar(card_image_id=codigo) if carta.id.upper().startswith(codigo)]
        return sorted(cartas, key=lambda carta: carta.id)

    def sugestoes(self) -> list[CartaDoCatalogo]:
        # A lista de coleções vem na ordem de lançamento: a última é a mais nova.
        colecoes = self.transporte.json(f"{API}/allSets/") or []
        for colecao in reversed(colecoes[-_COLECOES_RECENTES:]):
            cartas = _com_imagem(self.transporte.json(f'{API}/sets/{quote(colecao["set_id"], safe="")}/'))
            if cartas:
                # A coleção traz reimpressões de outras (OP13-100 na EB-05): as cartas dela mesma vêm primeiro.
                propria = colecao["set_id"].replace("-", "")
                return sorted(cartas, key=lambda carta: (carta.codigo.split("-")[0] not in propria, carta.id))
        return []

    def obter(self, id: str) -> CartaDoCatalogo | None:
        if not _ID.match(id):
            return None
        # As variações da carta (arte alternativa, paralela) dividem o código e mudam o sufixo: OP01-024_p1.
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


def _com_imagem(cartas) -> list[CartaDoCatalogo]:
    """Uma carta por imagem: a mesma carta pode vir de mais de um endereço da API."""
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
        # A documentação não diz de onde vem o market_price; o site da API informa que os dados das cartas
        # vêm do TCGplayer, que cota em dólares.
        preco=preco_medio(dados.get("market_price"), "USD", "TCGplayer"),
    )
