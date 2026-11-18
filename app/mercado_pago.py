"""Mercado Pago (Checkout Pro): a aprovação é sempre conferida na API."""
import http.client
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urlencode

from app.dominio.dinheiro import reais

API = "https://api.mercadopago.com"
TEMPO_LIMITE = 15
TAMANHO_MAXIMO = 2 * 1024 * 1024
MOEDA = "BRL"
_FORMAS = {"credit_card": "cartão", "debit_card": "cartão", "prepaid_card": "cartão", "bank_transfer": "pix",
           "account_money": "saldo do Mercado Pago"}
# Boleto leva dias para compensar: não cabe no prazo de pagamento.
_TIPOS_EXCLUIDOS = ("ticket",)


class GatewayIndisponivel(Exception):
    pass


@dataclass(frozen=True)
class Checkout:
    id: str
    url: str


@dataclass(frozen=True)
class PagamentoNoGateway:
    id: str
    status: str
    referencia: str
    valor: Decimal
    moeda: str
    forma: str

    @property
    def aprovado(self) -> bool:
        return self.status == "approved"


class MercadoPago:
    externo = True
    nome = "Mercado Pago"

    def __init__(self, token: str, abrir=None):
        self._token = token
        self._abrir = abrir or urllib.request.urlopen

    def criar_checkout(self, *, referencia: str, titulo: str, valor: Decimal, expira: datetime,
                       retorno: str | None = None, notificacao: str | None = None) -> Checkout:
        """`retorno` e `notificacao` precisam ser endereços https públicos."""
        corpo = {
            "items": [{"id": referencia, "title": titulo, "quantity": 1, "currency_id": MOEDA,
                       "unit_price": float(valor)}],
            "external_reference": referencia,
            "payment_methods": {"excluded_payment_types": [{"id": tipo} for tipo in _TIPOS_EXCLUIDOS]},
            "expires": True,
            "expiration_date_to": expira.isoformat(timespec="milliseconds"),
        }
        if retorno:
            corpo["back_urls"] = {"success": retorno, "pending": retorno, "failure": retorno}
            corpo["auto_return"] = "approved"
        if notificacao:
            corpo["notification_url"] = notificacao
        resposta = self._pedir("/checkout/preferences", corpo)
        # Credenciais de teste antigas (TEST-…) pagam no sandbox.
        campo = "sandbox_init_point" if self._token.startswith("TEST-") else "init_point"
        url = (resposta or {}).get(campo) or (resposta or {}).get("init_point")
        if not resposta or not resposta.get("id") or not url:
            raise GatewayIndisponivel("o Mercado Pago não devolveu o endereço de pagamento")
        return Checkout(id=str(resposta["id"]), url=url)

    def pagamento(self, id_do_pagamento: str) -> PagamentoNoGateway | None:
        dados = self._pedir(f"/v1/payments/{quote(str(id_do_pagamento), safe='')}", vazio=(400, 404))
        return _ler_pagamento(dados) if dados else None

    def pagamentos(self, referencia: str) -> list[PagamentoNoGateway]:
        consulta = urlencode({"external_reference": referencia, "sort": "date_created", "criteria": "desc",
                              "range": "date_created", "begin_date": "NOW-30DAYS", "end_date": "NOW"})
        dados = self._pedir(f"/v1/payments/search?{consulta}")
        resultados = dados.get("results") if isinstance(dados, dict) else dados
        lidos = (_ler_pagamento(item) for item in resultados or [] if isinstance(item, dict))
        return [pagamento for pagamento in lidos if pagamento is not None]

    def _pedir(self, caminho: str, corpo: dict | None = None, vazio: tuple[int, ...] = ()):
        cabecalhos = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        dados = None
        if corpo is not None:
            dados = json.dumps(corpo).encode()
            cabecalhos["Content-Type"] = "application/json"
        pedido = urllib.request.Request(API + caminho, data=dados, headers=cabecalhos)
        try:
            with self._abrir(pedido, timeout=TEMPO_LIMITE) as resposta:
                conteudo = resposta.read(TAMANHO_MAXIMO + 1)
        except urllib.error.HTTPError as erro:
            if erro.code in vazio:
                return None
            detalhe = erro.read(500).decode("utf-8", "replace") if erro.fp else ""
            raise GatewayIndisponivel(f"o Mercado Pago respondeu {erro.code}: {detalhe}") from erro
        except (OSError, http.client.HTTPException) as erro:
            raise GatewayIndisponivel(f"o Mercado Pago não respondeu: {erro}") from erro
        if len(conteudo) > TAMANHO_MAXIMO:
            raise GatewayIndisponivel("o Mercado Pago devolveu uma resposta grande demais")
        try:
            return json.loads(conteudo)
        except ValueError as erro:
            raise GatewayIndisponivel("o Mercado Pago não respondeu em JSON") from erro


def _ler_pagamento(dados: dict) -> PagamentoNoGateway | None:
    try:
        valor = reais(Decimal(str(dados.get("transaction_amount"))))
    except InvalidOperation:
        return None
    if dados.get("id") is None:
        return None
    tipo = str(dados.get("payment_type_id") or "")
    return PagamentoNoGateway(
        id=str(dados["id"]), status=str(dados.get("status") or ""),
        referencia=str(dados.get("external_reference") or ""), valor=valor,
        moeda=str(dados.get("currency_id") or ""), forma=_FORMAS.get(tipo, tipo or "outro"))
