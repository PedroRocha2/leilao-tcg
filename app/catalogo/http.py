import http.client
import json
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from app.catalogo.base import CatalogoIndisponivel

# O servidor só fala com estes endereços, mesmo que uma API devolva outro ou redirecione.
HOSTS_PERMITIDOS = frozenset({
    "api.scryfall.com", "cards.scryfall.io",
    "api.tcgdex.net", "assets.tcgdex.net",
    "db.ygoprodeck.com", "images.ygoprodeck.com",
    "optcgapi.com",
})
EXTENSOES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
TEMPO_LIMITE = 12
TAMANHO_MAXIMO = 8 * 1024 * 1024


def conferir_endereco(url: str) -> None:
    partes = urlsplit(url)
    if partes.scheme != "https" or partes.hostname not in HOSTS_PERMITIDOS:
        raise CatalogoIndisponivel(f"Endereço fora dos catálogos de cartas: {url}")


class _RedirecionamentoConferido(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        conferir_endereco(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Transporte:
    def __init__(self, user_agent: str, abrir=None):
        self.user_agent = user_agent
        self._abrir = abrir or urllib.request.build_opener(_RedirecionamentoConferido).open

    def json(self, url: str, corpo: dict | None = None, vazio: tuple[int, ...] = (404,)):
        """O JSON da resposta, ou None quando a API responde que não achou nada (status em `vazio`)."""
        conteudo, _ = self._pedir(url, "application/json", corpo, vazio)
        if conteudo is None:
            return None
        try:
            return json.loads(conteudo)
        except ValueError as erro:
            raise CatalogoIndisponivel(f"{urlsplit(url).hostname} não respondeu em JSON") from erro

    def imagem(self, url: str) -> tuple[bytes, str]:
        conteudo, tipo = self._pedir(url, "image/*")
        if tipo not in EXTENSOES or not conteudo:
            raise CatalogoIndisponivel(f"{urlsplit(url).hostname} não devolveu uma imagem")
        return conteudo, tipo

    def _pedir(self, url, aceitar, corpo=None, vazio=()):
        conferir_endereco(url)
        cabecalhos = {"User-Agent": self.user_agent, "Accept": aceitar}
        dados = None
        if corpo is not None:
            dados = json.dumps(corpo).encode()
            cabecalhos["Content-Type"] = "application/json"
        pedido = urllib.request.Request(url, data=dados, headers=cabecalhos)
        try:
            with self._abrir(pedido, timeout=TEMPO_LIMITE) as resposta:
                conteudo = resposta.read(TAMANHO_MAXIMO + 1)
                tipo = resposta.headers.get_content_type()
        except urllib.error.HTTPError as erro:
            if erro.code in vazio:
                return None, None
            raise CatalogoIndisponivel(f"{urlsplit(url).hostname} respondeu {erro.code}") from erro
        except (OSError, http.client.HTTPException) as erro:
            raise CatalogoIndisponivel(f"{urlsplit(url).hostname} não respondeu: {erro}") from erro
        if len(conteudo) > TAMANHO_MAXIMO:
            raise CatalogoIndisponivel(f"{urlsplit(url).hostname} devolveu uma resposta grande demais")
        return conteudo, tipo
