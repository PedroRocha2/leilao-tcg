"""RF11 com o gateway externo: a cobrança aberta no Mercado Pago e a confirmação do pagamento.

Nenhum teste usa a rede: `ApiFalsa` responde como a API do Mercado Pago.
"""
import io
import json
import urllib.error
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import pytest

from apoio import (CSRF, ITERACOES_DE_TESTE, CorreioFalso, aprovar_leilao, avancar_relogio, catalogo_de_teste,
                   criar_conta, criar_leilao, lance_json, leiloes_criados, outro_navegador)
from app import create_app
from app.db import conectar
from app.dominio.dinheiro import formatar_reais
from app.mercado_pago import GatewayIndisponivel, MercadoPago
from app.pagamento import GatewayLocal

LOJA = "https://loja.exemplo.com"


class ApiFalsa:
    """Guarda as cobranças abertas e os pagamentos feitos, e responde aos pedidos como api.mercadopago.com."""

    def __init__(self):
        self.pedidos: list[tuple[str, str]] = []
        self.preferencias: list[dict] = []
        self.pagamentos: dict[str, dict] = {}
        self.fora_do_ar = False
        self.busca_atrasada = False

    def pagar(self, referencia: str, valor: float, status="approved", tipo="bank_transfer", moeda="BRL") -> str:
        """O comprador pagou no checkout; devolve o número do pagamento."""
        numero = str(1000 + len(self.pagamentos))
        self.pagamentos[numero] = {"id": int(numero), "status": status, "external_reference": referencia,
                                   "transaction_amount": valor, "currency_id": moeda, "payment_type_id": tipo}
        return numero

    def __call__(self, pedido, timeout=None):
        partes = urlsplit(pedido.full_url)
        self.pedidos.append((pedido.get_method(), partes.path))
        assert pedido.get_header("Authorization") == "Bearer APP_USR-teste"
        assert partes.hostname == "api.mercadopago.com" and timeout
        if self.fora_do_ar:
            raise urllib.error.URLError("sem rede (teste)")
        if partes.path == "/checkout/preferences":
            corpo = json.loads(pedido.data)
            self.preferencias.append(corpo)
            numero = len(self.preferencias)
            return self._resposta({"id": f"pref-{numero}", "init_point": f"https://mp.exemplo/pagar/{numero}",
                                   "sandbox_init_point": f"https://sandbox.mp.exemplo/pagar/{numero}"})
        if partes.path == "/v1/payments/search":
            referencia = parse_qs(partes.query)["external_reference"][0]
            achados = [] if self.busca_atrasada else [
                p for p in self.pagamentos.values() if p["external_reference"] == referencia]
            return self._resposta({"paging": {"total": len(achados)}, "results": achados})
        numero = partes.path.rsplit("/", 1)[-1]
        if numero not in self.pagamentos:
            raise urllib.error.HTTPError(pedido.full_url, 404, "Not Found", {}, io.BytesIO(b'{"status": 404}'))
        return self._resposta(self.pagamentos[numero])

    @staticmethod
    def _resposta(dados):
        return io.BytesIO(json.dumps(dados).encode())


@pytest.fixture
def api():
    return ApiFalsa()


@pytest.fixture
def app(tmp_path, api):
    """A loja com o Mercado Pago configurado e um endereço público, como em produção."""
    return create_app({
        "TESTING": True, "DATABASE": str(tmp_path / "teste.sqlite3"), "SECRET_KEY": "chave-de-teste",
        "PBKDF2_ITERACOES": ITERACOES_DE_TESTE, "CATALOGO": catalogo_de_teste(),
        "PASTA_DE_FOTOS": str(tmp_path / "fotos"), "PASTA_DO_CATALOGO": str(tmp_path / "catalogo"),
        "GATEWAY": MercadoPago("APP_USR-teste", abrir=api), "URL_PUBLICA": LOJA,
    })


@pytest.fixture
def banco(app):
    conexao = conectar(app.config["DATABASE"])
    yield conexao
    conexao.close()


@pytest.fixture
def arremate(app, banco):
    """Ana vende o Charizard e Bruno arremata por R$ 200,00. Devolve o número do leilão e o navegador dele."""
    ana = app.test_client()
    with ana.session_transaction() as sessao:
        sessao["csrf"] = CSRF
    criar_conta(ana)
    criar_leilao(ana, app, lance_inicial="100,00")
    numero = leiloes_criados(banco)[0]["id"]
    aprovar_leilao(app, numero)
    bruno = outro_navegador(app)
    assert lance_json(bruno, numero, "200,00").status_code == 201
    avancar_relogio(app, days=3, hours=1)
    bruno.get("/minha-conta/arremates")
    return numero, bruno


def pagar(navegador, numero, **dados):
    return navegador.post(f"/minha-conta/arremates/{numero}/pagar", data={"csrf_token": CSRF, **dados})


def conferir(navegador, numero):
    return navegador.post(f"/minha-conta/arremates/{numero}/pagamento", data={"csrf_token": CSRF})


def transacao_de(banco, numero):
    return banco.execute("SELECT * FROM transacoes WHERE leilao_id = ?", (numero,)).fetchone()


def cobrancas_de(banco, numero):
    return banco.execute("SELECT * FROM cobrancas WHERE leilao_id = ? ORDER BY id", (numero,)).fetchall()


def carteira_de(banco, email="bruno@teste.com"):
    return banco.execute(
        "SELECT c.saldo_centavos FROM carteiras c JOIN usuarios u ON u.id = c.cliente_id WHERE u.email = ?",
        (email,)).fetchone()["saldo_centavos"]


def dar_saldo(banco, centavos, email="bruno@teste.com"):
    banco.execute("UPDATE carteiras SET saldo_centavos = ? WHERE cliente_id = (SELECT id FROM usuarios WHERE"
                  " email = ?)", (centavos, email))


def avisar(app, numero_do_pagamento, **extras):
    """O aviso (webhook) do Mercado Pago, que chega sem sessão e sem token CSRF."""
    return app.test_client().post("/pagamentos/mercado-pago", query_string=extras.pop("consulta", None),
                                  json={"type": "payment", "action": "payment.updated",
                                        "data": {"id": numero_do_pagamento}, **extras})


def test_sem_credencial_a_loja_usa_o_gateway_local(tmp_path, monkeypatch):
    opcoes = {"TESTING": True, "DATABASE": str(tmp_path / "b.sqlite3"), "SECRET_KEY": "x",
              "PBKDF2_ITERACOES": ITERACOES_DE_TESTE, "CATALOGO": catalogo_de_teste()}
    monkeypatch.delenv("MERCADOPAGO_ACCESS_TOKEN", raising=False)
    assert isinstance(create_app(opcoes).config["GATEWAY"], GatewayLocal)
    monkeypatch.setenv("MERCADOPAGO_ACCESS_TOKEN", " APP_USR-da-maquina ")
    gateway = create_app(opcoes).config["GATEWAY"]
    assert isinstance(gateway, MercadoPago) and gateway.externo and gateway.nome == "Mercado Pago"


def test_tela_de_pagamento_explica_que_o_pagamento_e_no_mercado_pago(arremate):
    numero, bruno = arremate
    tela = bruno.get(f"/minha-conta/arremates/{numero}/pagar").get_data(as_text=True)
    assert "é feito no Mercado Pago, com Pix ou cartão" in tela and f"Pagar {formatar_reais(200)}" in tela
    assert 'name="forma"' not in tela and "não faz cobrança de verdade" not in tela
    assert "Pagamento iniciado" not in tela


def test_pagar_abre_a_cobranca_e_leva_o_comprador_ao_mercado_pago(arremate, api, banco, app):
    numero, bruno = arremate
    resposta = pagar(bruno, numero)
    assert (resposta.status_code, resposta.headers["Location"]) == (303, "https://mp.exemplo/pagar/1")

    (preferencia,) = api.preferencias
    (cobranca,) = cobrancas_de(banco, numero)
    assert preferencia["external_reference"] == cobranca["referencia"]
    assert cobranca["referencia"].startswith(f"leilao-{numero}-") and len(cobranca["referencia"]) > 20
    (item,) = preferencia["items"]
    assert (item["unit_price"], item["quantity"], item["currency_id"]) == (200.0, 1, "BRL")
    assert "Charizard" in item["title"]
    retorno = f"{LOJA}/minha-conta/arremates/{numero}/pagamento"
    assert preferencia["back_urls"] == {"success": retorno, "pending": retorno, "failure": retorno}
    assert preferencia["auto_return"] == "approved"
    assert preferencia["notification_url"] == f"{LOJA}/pagamentos/mercado-pago"
    assert preferencia["payment_methods"] == {"excluded_payment_types": [{"id": "ticket"}]}
    assert preferencia["expires"] is True
    assert preferencia["expiration_date_to"] == transacao_de(banco, numero)["prazo_pagamento"]

    assert (cobranca["status"], cobranca["valor_centavos"], cobranca["saldo_centavos"]) == ("pendente", 20000, 0)
    assert (cobranca["checkout_id"], cobranca["checkout_url"]) == ("pref-1", "https://mp.exemplo/pagar/1")
    assert transacao_de(banco, numero)["status"] == "aguardando pagamento"
    assert "cobrança aberta no gateway" in [
        linha["operacao"] for linha in banco.execute("SELECT operacao FROM log_operacoes")]


def test_pagar_de_novo_reaproveita_a_cobranca_pendente(arremate, api, banco):
    numero, bruno = arremate
    pagar(bruno, numero)
    assert pagar(bruno, numero).headers["Location"] == "https://mp.exemplo/pagar/1"
    assert len(api.preferencias) == 1 and len(cobrancas_de(banco, numero)) == 1

    tela = bruno.get(f"/minha-conta/arremates/{numero}/pagar").get_data(as_text=True)
    assert "Pagamento iniciado no Mercado Pago" in tela and 'href="https://mp.exemplo/pagar/1"' in tela
    assert "Já paguei: conferir pagamento" in tela


def test_volta_do_mercado_pago_com_pagamento_aprovado_quita_o_arremate(arremate, api, banco):
    numero, bruno = arremate
    pagar(bruno, numero)
    referencia = cobrancas_de(banco, numero)[0]["referencia"]
    pagamento = api.pagar(referencia, 200.0, tipo="credit_card")

    resposta = bruno.get(f"/minha-conta/arremates/{numero}/pagamento", query_string={
        "payment_id": pagamento, "status": "approved", "external_reference": referencia})
    assert (resposta.status_code, resposta.headers["Location"]) == (303, "/minha-conta/arremates")

    paga = transacao_de(banco, numero)
    assert (paga["status"], paga["pago_gateway_centavos"], paga["pago_saldo_centavos"], paga["forma_pagamento"]) == (
        "pago", 20000, 0, "cartão")
    assert leiloes_criados(banco)[0]["status_da_carta"] == "paga"
    (cobranca,) = cobrancas_de(banco, numero)
    assert (cobranca["status"], cobranca["pagamento_id"]) == ("paga", pagamento)
    assert cobranca["data_resposta"] is not None

    pagina = bruno.get("/minha-conta/arremates").get_data(as_text=True)
    assert f"Retire Charizard na loja com o código {paga['codigo_retirada']}." in pagina
    registro = banco.execute("SELECT * FROM log_operacoes WHERE operacao = 'pagamento de arremate'").fetchone()
    assert registro["valor_centavos"] == 20000 and f"Mercado Pago, pagamento {pagamento}" in registro["detalhe"]


def test_o_que_vem_no_endereco_de_volta_nao_vale_sem_a_confirmacao_da_api(arremate, api, banco):
    numero, bruno = arremate
    pagar(bruno, numero)
    referencia = cobrancas_de(banco, numero)[0]["referencia"]

    for consulta in ({"status": "approved", "external_reference": referencia, "payment_id": "999999"},
                     {"status": "approved", "collection_status": "approved"},
                     {"payment_id": "abc; DROP TABLE cobrancas", "external_reference": referencia}):
        resposta = bruno.get(f"/minha-conta/arremates/{numero}/pagamento", query_string=consulta,
                             follow_redirects=True)
        assert "O Mercado Pago ainda não confirmou o pagamento." in resposta.get_data(as_text=True)
    assert transacao_de(banco, numero)["status"] == "aguardando pagamento"


@pytest.mark.parametrize("mudanca", [
    {"status": "pending"}, {"status": "rejected"}, {"valor": 20.0}, {"moeda": "USD"},
    {"referencia": "leilao-999-outra"},
])
def test_pagamento_que_nao_e_a_cobranca_aprovada_no_valor_certo_nao_quita(arremate, api, banco, app, mudanca):
    numero, bruno = arremate
    pagar(bruno, numero)
    dados = {"referencia": cobrancas_de(banco, numero)[0]["referencia"], "valor": 200.0, **mudanca}
    pagamento = api.pagar(dados.pop("referencia"), dados.pop("valor"), **dados)

    assert avisar(app, pagamento).status_code == 200
    conferir(bruno, numero)
    bruno.get(f"/minha-conta/arremates/{numero}/pagamento", query_string={
        "payment_id": pagamento, "external_reference": cobrancas_de(banco, numero)[0]["referencia"]})
    assert transacao_de(banco, numero)["status"] == "aguardando pagamento"
    assert cobrancas_de(banco, numero)[0]["status"] == "pendente"


def test_aviso_do_mercado_pago_quita_o_arremate_sem_sessao_nem_csrf(arremate, api, banco, app):
    numero, bruno = arremate
    pagar(bruno, numero)
    pagamento = api.pagar(cobrancas_de(banco, numero)[0]["referencia"], 200.0)

    assert avisar(app, pagamento).status_code == 200
    paga = transacao_de(banco, numero)
    assert (paga["status"], paga["forma_pagamento"]) == ("pago", "pix")
    assert avisar(app, pagamento).status_code == 200
    resposta = bruno.get(f"/minha-conta/arremates/{numero}/pagamento", query_string={"payment_id": pagamento})
    assert resposta.headers["Location"] == "/minha-conta/arremates"
    assert banco.execute("SELECT COUNT(*) FROM log_operacoes WHERE operacao = 'pagamento de arremate'"
                         ).fetchone()[0] == 1
    assert carteira_de(banco) == 0


def test_aviso_tambem_e_lido_do_endereco_e_ignora_o_que_nao_e_pagamento(arremate, api, banco, app):
    numero, bruno = arremate
    pagar(bruno, numero)
    pagamento = api.pagar(cobrancas_de(banco, numero)[0]["referencia"], 200.0)
    visitante = app.test_client()

    assert visitante.post("/pagamentos/mercado-pago", json={"type": "merchant_order", "data": {"id": "1"}}
                          ).status_code == 200
    assert visitante.post("/pagamentos/mercado-pago", data="isto não é json").status_code == 200
    assert visitante.post("/pagamentos/mercado-pago?type=payment&data.id=777").status_code == 200
    assert transacao_de(banco, numero)["status"] == "aguardando pagamento"
    assert visitante.post(f"/pagamentos/mercado-pago?topic=payment&id={pagamento}").status_code == 200
    assert transacao_de(banco, numero)["status"] == "pago"


def test_aviso_responde_erro_quando_o_mercado_pago_nao_responde_para_ele_avisar_de_novo(arremate, api, banco, app):
    numero, bruno = arremate
    pagar(bruno, numero)
    pagamento = api.pagar(cobrancas_de(banco, numero)[0]["referencia"], 200.0)
    api.fora_do_ar = True
    assert avisar(app, pagamento).status_code == 503
    assert transacao_de(banco, numero)["status"] == "aguardando pagamento"
    api.fora_do_ar = False
    assert avisar(app, pagamento).status_code == 200
    assert transacao_de(banco, numero)["status"] == "pago"


def test_comprador_confere_o_pagamento_pelo_botao(arremate, api, banco):
    numero, bruno = arremate
    pagar(bruno, numero)
    ainda_nao = conferir(bruno, numero)
    assert ainda_nao.headers["Location"] == f"/minha-conta/arremates/{numero}/pagar"

    api.pagar(cobrancas_de(banco, numero)[0]["referencia"], 200.0)
    assert conferir(bruno, numero).headers["Location"] == "/minha-conta/arremates"
    assert transacao_de(banco, numero)["status"] == "pago"


def test_volta_do_comprador_vale_mesmo_quando_a_busca_ainda_nao_enxerga_o_pagamento(arremate, api, banco):
    numero, bruno = arremate
    pagar(bruno, numero)
    referencia = cobrancas_de(banco, numero)[0]["referencia"]
    pagamento = api.pagar(referencia, 200.0)
    api.busca_atrasada = True
    bruno.get(f"/minha-conta/arremates/{numero}/pagamento", query_string={
        "payment_id": pagamento, "external_reference": referencia})
    assert transacao_de(banco, numero)["status"] == "pago"


def test_rn18_saldo_completa_o_pagamento_e_so_e_debitado_na_confirmacao(arremate, api, banco, app):
    numero, bruno = arremate
    dar_saldo(banco, 5000)
    tela = bruno.get(f"/minha-conta/arremates/{numero}/pagar").get_data(as_text=True)
    assert f"Usar o saldo da carteira ({formatar_reais(50)} disponíveis); faltam {formatar_reais(150)}" in tela
    assert "O que o saldo não cobrir é feito no Mercado Pago" in tela

    pagar(bruno, numero, usar_saldo="sim")
    (cobranca,) = cobrancas_de(banco, numero)
    assert (cobranca["valor_centavos"], cobranca["saldo_centavos"]) == (15000, 5000)
    assert api.preferencias[0]["items"][0]["unit_price"] == 150.0
    assert carteira_de(banco) == 5000

    avisar(app, api.pagar(cobranca["referencia"], 150.0))
    paga = transacao_de(banco, numero)
    assert (paga["status"], paga["pago_saldo_centavos"], paga["pago_gateway_centavos"]) == ("pago", 5000, 15000)
    assert carteira_de(banco) == 0


def test_saldo_que_cobre_o_arremate_inteiro_dispensa_o_mercado_pago(arremate, api, banco):
    numero, bruno = arremate
    dar_saldo(banco, 30000)
    resposta = pagar(bruno, numero, usar_saldo="sim")
    assert (resposta.status_code, resposta.headers["Location"]) == (303, "/minha-conta/arremates")
    assert transacao_de(banco, numero)["status"] == "pago" and carteira_de(banco) == 10000
    assert api.pedidos == [] and cobrancas_de(banco, numero) == []


def test_pagamento_confirmado_sem_o_saldo_combinado_vira_credito_na_carteira(arremate, api, banco, app):
    numero, bruno = arremate
    dar_saldo(banco, 5000)
    pagar(bruno, numero, usar_saldo="sim")
    dar_saldo(banco, 0)

    avisar(app, api.pagar(cobrancas_de(banco, numero)[0]["referencia"], 150.0))
    assert transacao_de(banco, numero)["status"] == "aguardando pagamento"
    assert cobrancas_de(banco, numero)[0]["status"] == "creditada"
    assert carteira_de(banco) == 15000
    extrato = bruno.get("/minha-conta/carteira").get_data(as_text=True)
    assert "Pagamento pelo Mercado Pago não aplicado ao arremate de Charizard" in extrato
    assert "pagamento creditado na carteira" in [
        linha["operacao"] for linha in banco.execute("SELECT operacao FROM log_operacoes")]
    dar_saldo(banco, 20000)
    assert pagar(bruno, numero, usar_saldo="sim").headers["Location"] == "/minha-conta/arremates"
    assert transacao_de(banco, numero)["status"] == "pago"


def test_pagamento_que_chega_depois_do_prazo_vira_credito_na_carteira(arremate, api, banco, app):
    numero, bruno = arremate
    pagar(bruno, numero)
    pagamento = api.pagar(cobrancas_de(banco, numero)[0]["referencia"], 200.0)
    avancar_relogio(app, days=6)

    assert avisar(app, pagamento).status_code == 200
    assert transacao_de(banco, numero)["status"] == "não paga"
    assert cobrancas_de(banco, numero)[0]["status"] == "creditada" and carteira_de(banco) == 20000
    resposta = conferir(bruno, numero)
    assert resposta.headers["Location"] == "/minha-conta/carteira"


def test_duas_cobrancas_pagas_quitam_uma_vez_e_creditam_a_outra(arremate, api, banco, app):
    numero, bruno = arremate
    pagar(bruno, numero)
    dar_saldo(banco, 5000)
    pagar(bruno, numero, usar_saldo="sim")
    inteira, parcial = cobrancas_de(banco, numero)
    assert (inteira["valor_centavos"], parcial["valor_centavos"]) == (20000, 15000)

    avisar(app, api.pagar(inteira["referencia"], 200.0))
    avisar(app, api.pagar(parcial["referencia"], 150.0))
    assert [c["status"] for c in cobrancas_de(banco, numero)] == ["paga", "creditada"]
    assert transacao_de(banco, numero)["pago_gateway_centavos"] == 20000
    assert carteira_de(banco) == 5000 + 15000


def test_aviso_do_mercado_pago_manda_o_codigo_de_retirada_por_email_uma_vez_so(arremate, api, banco, app):
    numero, bruno = arremate
    correio = app.config["CORREIO"] = CorreioFalso()
    pagar(bruno, numero)
    pagamento = api.pagar(cobrancas_de(banco, numero)[0]["referencia"], 200.0)
    assert correio.enviados == []

    assert avisar(app, pagamento).status_code == 200
    avisar(app, pagamento)
    bruno.get(f"/minha-conta/arremates/{numero}/pagamento", query_string={"payment_id": pagamento})
    ((destinatario, assunto, texto),) = correio.enviados
    assert (destinatario, assunto) == ("bruno@teste.com", "Pagamento confirmado: Charizard")
    assert f"Código de retirada: {transacao_de(banco, numero)['codigo_retirada']}" in texto
    assert f"{LOJA}/minha-conta/arremates" in texto


def test_volta_do_comprador_manda_o_email_e_a_falha_do_envio_nao_desfaz_o_pagamento(arremate, api, banco, app):
    numero, bruno = arremate
    correio = app.config["CORREIO"] = CorreioFalso()
    pagar(bruno, numero)
    referencia = cobrancas_de(banco, numero)[0]["referencia"]
    correio.fora_do_ar = True
    resposta = bruno.get(f"/minha-conta/arremates/{numero}/pagamento", query_string={
        "payment_id": api.pagar(referencia, 200.0), "external_reference": referencia})
    assert resposta.headers["Location"] == "/minha-conta/arremates"
    assert transacao_de(banco, numero)["status"] == "pago" and correio.enviados == []


def test_comprador_que_confere_pelo_botao_recebe_o_email(arremate, api, banco, app):
    numero, bruno = arremate
    correio = app.config["CORREIO"] = CorreioFalso()
    pagar(bruno, numero)
    conferir(bruno, numero)
    assert correio.enviados == []
    api.pagar(cobrancas_de(banco, numero)[0]["referencia"], 200.0)
    conferir(bruno, numero)
    assert [destinatario for destinatario, _, _ in correio.enviados] == ["bruno@teste.com"]


def test_pagamento_creditado_na_carteira_nao_manda_o_codigo_de_retirada(arremate, api, banco, app):
    numero, bruno = arremate
    correio = app.config["CORREIO"] = CorreioFalso()
    pagar(bruno, numero)
    pagamento = api.pagar(cobrancas_de(banco, numero)[0]["referencia"], 200.0)
    avancar_relogio(app, days=6)
    assert avisar(app, pagamento).status_code == 200
    assert cobrancas_de(banco, numero)[0]["status"] == "creditada" and correio.enviados == []


def test_mercado_pago_fora_do_ar_nao_abre_a_cobranca_e_avisa(arremate, api, banco):
    numero, bruno = arremate
    api.fora_do_ar = True
    resposta = pagar(bruno, numero)
    assert resposta.status_code == 502
    assert "Não foi possível falar com o Mercado Pago agora." in resposta.get_data(as_text=True)
    assert cobrancas_de(banco, numero) == []

    api.fora_do_ar = False
    pagar(bruno, numero)
    api.fora_do_ar = True
    pagina = conferir(bruno, numero)
    assert pagina.headers["Location"] == f"/minha-conta/arremates/{numero}/pagar"
    assert transacao_de(banco, numero)["status"] == "aguardando pagamento"


def test_so_o_comprador_abre_e_confere_a_cobranca_do_arremate(arremate, api, banco, app):
    numero, bruno = arremate
    carla = outro_navegador(app, email="carla@teste.com", cpf="390.533.447-05")
    assert pagar(carla, numero).status_code == 404
    assert conferir(carla, numero).status_code == 404
    assert carla.get(f"/minha-conta/arremates/{numero}/pagamento").status_code == 404
    visitante = app.test_client()
    assert visitante.get(f"/minha-conta/arremates/{numero}/pagamento").status_code == 302
    assert api.pedidos == []


def test_sem_endereco_publico_o_comprador_paga_em_outra_aba_e_confere_pelo_botao(arremate, api, banco, app):
    numero, bruno = arremate
    app.config["URL_PUBLICA"] = ""
    resposta = pagar(bruno, numero)
    assert (resposta.status_code, resposta.headers["Location"]) == (303, f"/minha-conta/arremates/{numero}/pagar")
    (preferencia,) = api.preferencias
    assert not {"back_urls", "auto_return", "notification_url"} & preferencia.keys()

    tela = bruno.get(f"/minha-conta/arremates/{numero}/pagar").get_data(as_text=True)
    assert "Cobrança aberta. Pague no Mercado Pago e volte aqui para conferir o pagamento." in tela
    assert 'href="https://mp.exemplo/pagar/1" target="_blank"' in tela


def test_com_o_gateway_local_o_aviso_do_mercado_pago_nao_existe(tmp_path):
    local = create_app({"TESTING": True, "DATABASE": str(tmp_path / "local.sqlite3"), "SECRET_KEY": "x",
                        "PBKDF2_ITERACOES": ITERACOES_DE_TESTE, "CATALOGO": catalogo_de_teste(),
                        "MERCADO_PAGO_TOKEN": ""})
    resposta = local.test_client().post("/pagamentos/mercado-pago", json={"type": "payment", "data": {"id": "1"}})
    assert resposta.status_code == 404


def test_credencial_de_teste_antiga_usa_o_endereco_de_testes(api):
    api_de_teste = ApiFalsa()

    def abrir(pedido, timeout=None):
        assert pedido.get_header("Authorization") == "Bearer TEST-123"
        pedido.add_header("Authorization", "Bearer APP_USR-teste")
        return api_de_teste(pedido, timeout)

    checkout = MercadoPago("TEST-123", abrir=abrir).criar_checkout(
        referencia="leilao-1-abc", titulo="Carta", valor=Decimal("10.00"),
        expira=datetime(2026, 11, 20, 12, 0, tzinfo=UTC) + timedelta(hours=1))
    assert (checkout.id, checkout.url) == ("pref-1", "https://sandbox.mp.exemplo/pagar/1")
    assert api_de_teste.preferencias[0]["expiration_date_to"] == "2026-11-20T13:00:00.000+00:00"


def test_resposta_que_nao_da_para_ler_vira_gateway_indisponivel():
    def erro_401(pedido, timeout=None):
        raise urllib.error.HTTPError(pedido.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"message": "invalid"}'))

    for abrir, trecho in ((lambda pedido, timeout=None: io.BytesIO(b"<html>"), "JSON"),
                          (lambda pedido, timeout=None: io.BytesIO(b"{}"), "endereço de pagamento"),
                          (erro_401, "401")):
        with pytest.raises(GatewayIndisponivel, match=trecho):
            MercadoPago("APP_USR-x", abrir=abrir).criar_checkout(
                referencia="r", titulo="t", valor=Decimal("1.00"), expira=datetime(2026, 11, 20, tzinfo=UTC))
    assert MercadoPago("APP_USR-x", abrir=lambda p, timeout=None: io.BytesIO(b'{"results": [{"id": 1}]}')
                       ).pagamentos("r") == []
