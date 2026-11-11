"""Yu-Gi-Oh! pela API do YGOPRODeck (https://ygoprodeck.com/api-guide/).

O YGOPRODeck proíbe exibir as imagens direto do site dele: elas são baixadas e servidas pela loja.
"""
from urllib.parse import urlencode

from app.catalogo.base import LIMITE_DE_RESULTADOS, CartaDoCatalogo, especificacoes, preco_medio

API = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
_SEM_RESULTADO = (400, 404)


class Ygoprodeck:
    jogo = "Yu-Gi-Oh!"

    def __init__(self, transporte):
        self.transporte = transporte

    def buscar(self, nome: str) -> list[CartaDoCatalogo]:
        return self._listar(fname=nome)

    def sugestoes(self) -> list[CartaDoCatalogo]:
        # As cartas mais novas do jogo ocidental (format=tcg): as que só saíram no Japão não têm edição.
        return self._listar(sort="new", format="tcg")

    def _listar(self, **filtro: str) -> list[CartaDoCatalogo]:
        consulta = urlencode({**filtro, "num": LIMITE_DE_RESULTADOS, "offset": 0})
        resposta = self.transporte.json(f"{API}?{consulta}", vazio=_SEM_RESULTADO)
        return [carta for dados in (resposta or {}).get("data", []) if (carta := _carta(dados))]

    def obter(self, id: str) -> CartaDoCatalogo | None:
        if not id.isdigit():
            return None
        resposta = self.transporte.json(f"{API}?id={id}", vazio=_SEM_RESULTADO)
        return _carta(resposta["data"][0]) if resposta and resposta.get("data") else None


def _carta(dados: dict) -> CartaDoCatalogo | None:
    # A mesma carta sai em várias coleções, cada uma com o seu código (LOB-005).
    edicoes = tuple(dict.fromkeys(
        f'{colecao["set_name"]} ({colecao["set_code"]})' for colecao in dados.get("card_sets") or []))
    imagens = (dados.get("card_images") or [{}])[0]
    if not edicoes or not imagens.get("image_url"):
        return None
    ataque, defesa = dados.get("atk"), dados.get("def")
    # Este preço é o da carta, sem distinguir a edição que o vendedor ainda vai escolher.
    precos = (dados.get("card_prices") or [{}])[0]
    return CartaDoCatalogo(
        jogo=Ygoprodeck.jogo,
        id=str(dados["id"]),
        nome=dados["name"],
        codigo=str(dados["id"]).zfill(8),
        edicoes=edicoes,
        especificacoes=especificacoes(
            ("Tipo de carta", dados.get("type")),
            ("Tipo", dados.get("race")),
            ("Atributo", dados.get("attribute")),
            ("Nível", dados.get("level")),
            ("ATK/DEF", f"{ataque}/{defesa}" if ataque is not None and defesa is not None else ataque),
            ("Arquétipo", dados.get("archetype")),
        ),
        texto=dados.get("desc") or "",
        miniatura=imagens.get("image_url_small") or imagens["image_url"],
        imagem=imagens["image_url"],
        preco=(preco_medio(precos.get("tcgplayer_price"), "USD", "TCGplayer")
               or preco_medio(precos.get("cardmarket_price"), "EUR", "Cardmarket")),
    )
