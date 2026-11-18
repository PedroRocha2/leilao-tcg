from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from apoio import (ADMIN_LOGIN, ADMIN_SENHA, AGORA, CSRF, aprovar_leilao, avancar_relogio, criar_conta, criar_leilao,
                   entrar, lance_json, leiloes_criados, navegador_admin, novo_cliente, novo_leilao, outro_navegador)
from app.carga_inicial import CLIENTES
from app.dominio.financeiro import (Carteira, OperacaoRecusada, StatusSaque, StatusTransacao,
                                    novo_codigo_de_retirada)
from app.dominio.leiloes import StatusCarta, StatusLeilao
from app.dominio.loja import ConfiguracaoLoja

VALOR = Decimal
FIM = AGORA + timedelta(days=1)


@pytest.fixture
def vendedora():
    return novo_cliente(1, "100200300")


@pytest.fixture
def comprador():
    return novo_cliente(2, "200300400")


@pytest.fixture
def arremate(vendedora, comprador):
    """Um leilão encerrado com o lance de R$ 200,00 do comprador."""
    leilao = novo_leilao(vendedora, fim=FIM)
    comprador.darLance(leilao, VALOR("200.00"), AGORA)
    return leilao.encerrar(FIM)


def test_arremate_sai_com_taxa_valor_liquido_codigo_e_prazo(arremate):
    """RF13 e RN09: taxa de 10% sobre o valor final. RF10: código de retirada. RN06: prazo de pagamento."""
    assert (arremate.taxa, arremate.valorLiquido) == (VALOR("20.00"), VALOR("180.00"))
    assert len(arremate.codigoRetirada) == 8 and arremate.codigoRetirada.isalnum()
    assert arremate.prazoPagamento == FIM + timedelta(hours=48)
    assert arremate.status == StatusTransacao.AGUARDANDO_PAGAMENTO


def test_taxa_usa_o_percentual_gravado_no_leilao_e_arredonda_para_centavos(vendedora, comprador):
    leilao = novo_leilao(vendedora, fim=FIM)
    leilao.taxaPercentual = VALOR("12.5")
    comprador.darLance(leilao, VALOR("133.33"), AGORA)
    arremate = leilao.encerrar(FIM, timedelta(hours=24))
    assert (arremate.taxa, arremate.valorLiquido) == (VALOR("16.67"), VALOR("116.66"))
    assert arremate.prazoPagamento == FIM + timedelta(hours=24)


def test_codigos_de_retirada_nao_se_repetem_nem_usam_caracteres_ambiguos():
    codigos = {novo_codigo_de_retirada() for _ in range(500)}
    assert len(codigos) == 500
    assert not set("".join(codigos)) & set("ILO01")


def test_pagamento_pelo_gateway_marca_o_arremate_como_pago(arremate, comprador):
    comprador.pagarArremate(arremate, VALOR("0.00"), VALOR("200.00"), "pix", FIM + timedelta(hours=1))
    assert arremate.status == StatusTransacao.PAGO and arremate.dataPagamento == FIM + timedelta(hours=1)
    assert (arremate.pagoComSaldo, arremate.pagoNoGateway, arremate.formaDePagamento) == (
        VALOR("0.00"), VALOR("200.00"), "pix")


def test_rn18_saldo_da_carteira_e_debitado_so_quando_o_pagamento_e_confirmado(arremate, comprador):
    comprador.carteira = Carteira(saldo=VALOR("50.00"))
    with pytest.raises(OperacaoRecusada, match="prazo de pagamento"):
        comprador.pagarArremate(arremate, VALOR("50.00"), VALOR("150.00"), "cartão", arremate.prazoPagamento)
    assert comprador.carteira.saldo == VALOR("50.00") and comprador.carteira.movimentacoes == []

    comprador.pagarArremate(arremate, VALOR("50.00"), VALOR("150.00"), "cartão", FIM)
    assert comprador.carteira.saldo == VALOR("0.00")
    (debito,) = comprador.carteira.movimentacoes
    assert (debito.tipo, debito.valor) == ("débito", VALOR("-50.00"))
    assert (arremate.pagoComSaldo, arremate.pagoNoGateway) == (VALOR("50.00"), VALOR("150.00"))


def test_pagamento_recusado_quando_falta_saldo_nao_e_do_comprador_ou_ja_foi_pago(arremate, comprador, vendedora):
    with pytest.raises(OperacaoRecusada, match="saldo disponível"):
        comprador.pagarArremate(arremate, VALOR("200.00"), VALOR("0.00"), None, FIM)
    with pytest.raises(OperacaoRecusada, match="quem arrematou"):
        vendedora.pagarArremate(arremate, VALOR("0.00"), VALOR("200.00"), "pix", FIM)
    with pytest.raises(ValueError, match="exatamente"):
        comprador.pagarArremate(arremate, VALOR("0.00"), VALOR("199.99"), "pix", FIM)
    assert arremate.status == StatusTransacao.AGUARDANDO_PAGAMENTO

    comprador.pagarArremate(arremate, VALOR("0.00"), VALOR("200.00"), "pix", FIM)
    with pytest.raises(OperacaoRecusada, match="não está aguardando pagamento"):
        comprador.pagarArremate(arremate, VALOR("0.00"), VALOR("200.00"), "pix", FIM)


def test_rn07_entrega_exige_o_codigo_de_retirada_e_o_pagamento(arremate, comprador):
    with pytest.raises(OperacaoRecusada, match="depois do pagamento"):
        arremate.registrarEntrega(arremate.codigoRetirada, FIM)
    comprador.pagarArremate(arremate, VALOR("0.00"), VALOR("200.00"), "pix", FIM)
    with pytest.raises(OperacaoRecusada, match="não confere"):
        arremate.registrarEntrega("ERRADO99", FIM)
    assert arremate.status == StatusTransacao.PAGO

    arremate.registrarEntrega(f"  {arremate.codigoRetirada.lower()} ", FIM + timedelta(hours=2))
    assert arremate.status == StatusTransacao.ENTREGUE and arremate.dataEntrega == FIM + timedelta(hours=2)
    with pytest.raises(OperacaoRecusada, match="já foi entregue"):
        arremate.registrarEntrega(arremate.codigoRetirada, FIM)


def test_rn06_arremate_nao_pago_no_prazo_expira_e_marca_descumprimento(arremate, comprador):
    with pytest.raises(ValueError):
        arremate.expirar(arremate.prazoPagamento - timedelta(seconds=1))
    arremate.expirar(arremate.prazoPagamento)
    comprador.registrarDescumprimento()
    assert arremate.status == StatusTransacao.NAO_PAGA and comprador.descumprimentos == 1
    with pytest.raises(OperacaoRecusada):
        comprador.pagarArremate(arremate, VALOR("0.00"), VALOR("200.00"), "pix", FIM)


def test_rn16_e_rn19_saque_bloqueia_o_valor_ate_a_resposta_da_loja():
    carteira = Carteira()
    carteira.creditar(VALOR("180.00"), "Repasse da venda de Charizard", AGORA)
    assert carteira.possuiSaldo(VALOR("180.00")) and not carteira.possuiSaldo(VALOR("180.01"))

    with pytest.raises(OperacaoRecusada, match="saldo disponível"):
        carteira.solicitarSaque(VALOR("180.01"), "ana@pix.com", AGORA)
    with pytest.raises(OperacaoRecusada, match="chave Pix"):
        carteira.solicitarSaque(VALOR("10.00"), "  ", AGORA)
    with pytest.raises(OperacaoRecusada, match="maior que zero"):
        carteira.solicitarSaque(VALOR("0.00"), "ana@pix.com", AGORA)

    saque = carteira.solicitarSaque(VALOR("100.00"), "ana@pix.com", AGORA)
    assert (carteira.saldo, carteira.bloqueado, carteira.disponivel) == (
        VALOR("180.00"), VALOR("100.00"), VALOR("80.00"))
    with pytest.raises(OperacaoRecusada, match="saldo disponível"):
        carteira.solicitarSaque(VALOR("80.01"), "ana@pix.com", AGORA)

    carteira.pagarSaque(saque, AGORA + timedelta(hours=1))
    assert (saque.status, carteira.saldo, carteira.bloqueado) == (StatusSaque.PAGO, VALOR("80.00"), VALOR("0.00"))
    assert carteira.movimentacoes[-1].valor == VALOR("-100.00")
    with pytest.raises(OperacaoRecusada, match="já foi respondido"):
        carteira.recusarSaque(saque, AGORA)

    recusado = carteira.solicitarSaque(VALOR("80.00"), "ana@pix.com", AGORA)
    carteira.recusarSaque(recusado, AGORA)
    assert (recusado.status, carteira.disponivel) == (StatusSaque.RECUSADO, VALOR("80.00"))


def test_debito_maior_que_o_saldo_disponivel_e_recusado():
    carteira = Carteira(saldo=VALOR("50.00"), bloqueado=VALOR("30.00"))
    with pytest.raises(OperacaoRecusada):
        carteira.debitar(VALOR("20.01"), "Pagamento de arremate", AGORA)
    carteira.debitar(VALOR("20.00"), "Pagamento de arremate", AGORA)
    assert carteira.saldo == VALOR("30.00")


def test_rf05_recusa_exige_motivo_e_so_vale_para_leilao_pendente(vendedora):
    leilao = novo_leilao(vendedora, status=StatusLeilao.PENDENTE)
    with pytest.raises(ValueError, match="motivo"):
        leilao.recusar("   ")
    leilao.recusar(" Carta diferente da anunciada ")
    assert (leilao.status, leilao.motivoRecusa) == (StatusLeilao.CANCELADO, "Carta diferente da anunciada")
    assert leilao.carta.status == StatusCarta.RECUSADA
    with pytest.raises(ValueError, match="aguarda aprovação"):
        leilao.recusar("De novo")


@pytest.mark.parametrize("valores", [{"taxaPercentual": VALOR("100")}, {"taxaPercentual": VALOR("-1")},
                                     {"incrementoMinimo": VALOR("0")}, {"prazoPagamentoHoras": 0},
                                     {"prazoReofertaHoras": 0}])
def test_configuracao_da_loja_recusa_valores_sem_sentido(valores):
    with pytest.raises(ValueError):
        ConfiguracaoLoja(**valores)


# --- Pela aplicação ---

GET_DO_ADMIN = ["/admin", "/admin/leiloes", "/admin/entregas", "/admin/entregas/1", "/admin/saques", "/admin/usuarios",
                "/admin/usuarios/2", "/admin/cartas", "/admin/cartas/1", "/admin/historico", "/admin/financeiro",
                "/admin/configuracoes", "/admin/auditoria"]
POST_DO_ADMIN = ["/admin/leiloes/1/aprovar", "/admin/leiloes/1/recusar", "/admin/entregas/1", "/admin/saques/1/pagar",
                 "/admin/saques/1/recusar", "/admin/usuarios/2", "/admin/usuarios/2/bloquear", "/admin/cartas/1",
                 "/admin/cartas/1/remover", "/admin/configuracoes"]


@pytest.fixture
def ana(cliente_http):
    criar_conta(cliente_http)
    return cliente_http


@pytest.fixture
def admin(app):
    return navegador_admin(app)


def id_de(banco, email):
    return banco.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone()["id"]


def carteira_de(banco, email):
    linha = banco.execute("SELECT saldo_centavos, bloqueado_centavos FROM carteiras WHERE cliente_id = ?",
                          (id_de(banco, email),)).fetchone()
    return linha["saldo_centavos"], linha["bloqueado_centavos"]


def transacao_de(banco, numero):
    return banco.execute("SELECT * FROM transacoes WHERE leilao_id = ?", (numero,)).fetchone()


def operacoes(banco):
    return [linha["operacao"] for linha in banco.execute("SELECT operacao FROM log_operacoes ORDER BY id")]


def vender(app, ana, banco, lance="200,00"):
    """Ana cria o leilão do Charizard, a loja aprova, Bruno dá o lance e o prazo do leilão termina."""
    criar_leilao(ana, app, lance_inicial="100,00")
    numero = leiloes_criados(banco)[0]["id"]
    aprovar_leilao(app, numero)
    bruno = outro_navegador(app)
    assert lance_json(bruno, numero, lance).status_code == 201
    avancar_relogio(app, days=3, hours=1)
    bruno.get("/minha-conta/arremates")
    return numero, bruno


def pagar(navegador, numero, follow_redirects=False, **dados):
    return navegador.post(f"/minha-conta/arremates/{numero}/pagar", follow_redirects=follow_redirects,
                          data={"csrf_token": CSRF, "forma": "pix", **dados})


def entregar(admin, numero, codigo):
    return admin.post(f"/admin/entregas/{numero}", data={"csrf_token": CSRF, "codigo": codigo},
                      follow_redirects=True).get_data(as_text=True)


def pedir_saque(navegador, valor, chave="ana@pix.com"):
    return navegador.post("/minha-conta/carteira/saque", data={"csrf_token": CSRF, "valor": valor, "chave_pix": chave})


def test_lojista_entra_com_usuario_e_senha_e_cai_na_administracao(cliente_http):
    resposta = entrar(cliente_http, ADMIN_LOGIN, ADMIN_SENHA)
    assert (resposta.status_code, resposta.headers["Location"]) == (303, "/admin/leiloes")
    pagina = cliente_http.get("/admin/leiloes").get_data(as_text=True)
    for trecho in ("Administração", "Leilões aguardando aprovação", ">Entregas</a>", ">Saques</a>",
                   ">Usuários</a>", ">Cartas</a>", ">Histórico</a>", ">Financeiro</a>", ">Configurações</a>", ">Auditoria</a>"):
        assert trecho in pagina
    assert 'href="/admin/leiloes" aria-current="page"' in pagina
    menu = cliente_http.get("/leiloes").get_data(as_text=True)
    assert 'href="/admin/leiloes"' in menu and "Minha Conta" not in menu and 'href="/vender"' not in menu


def test_senha_errada_do_lojista_nao_entra(cliente_http):
    assert entrar(cliente_http, ADMIN_LOGIN, "osscachorro1").status_code == 401
    assert cliente_http.get("/admin/leiloes").status_code == 302


def test_tela_de_entrar_aceita_nome_de_usuario(cliente_http):
    pagina = cliente_http.get("/entrar").get_data(as_text=True)
    assert "E-mail ou usuário" in pagina and 'type="email"' not in pagina


@pytest.mark.parametrize("url", GET_DO_ADMIN)
def test_rn14_visitante_e_mandado_para_o_login(cliente_http, url):
    resposta = cliente_http.get(url)
    assert resposta.status_code == 302 and resposta.headers["Location"].startswith("/entrar?proximo=")


@pytest.mark.parametrize("url", GET_DO_ADMIN)
def test_rn14_cliente_nao_acessa_as_telas_do_administrador(ana, url):
    resposta = ana.get(url)
    assert resposta.status_code == 403
    assert "Área restrita ao administrador" in resposta.get_data(as_text=True)


@pytest.mark.parametrize("url", POST_DO_ADMIN)
def test_rnf07_cliente_nao_executa_acoes_do_administrador(ana, banco, url):
    antes = [banco.execute(sql).fetchall() for sql in (
        "SELECT status FROM leiloes", "SELECT bloqueado, nome FROM usuarios u JOIN clientes c ON c.usuario_id = u.id",
        "SELECT nome FROM cartas", "SELECT * FROM configuracao_loja")]
    resposta = ana.post(url, data={"csrf_token": CSRF, "motivo": "x", "codigo": "ABCDEFGH", "nome": "Outro",
                                   "taxa": "1", "incremento": "1", "prazo_pagamento": "1", "prazo_reoferta": "1"})
    assert resposta.status_code == 403
    assert antes == [banco.execute(sql).fetchall() for sql in (
        "SELECT status FROM leiloes", "SELECT bloqueado, nome FROM usuarios u JOIN clientes c ON c.usuario_id = u.id",
        "SELECT nome FROM cartas", "SELECT * FROM configuracao_loja")]


def test_administrador_nao_compra_nem_vende(admin, banco):
    for url in ("/minha-conta", "/minha-conta/arremates", "/vender", "/vender/novo"):
        resposta = admin.get(url)
        assert (resposta.status_code, resposta.headers["Location"]) == (302, "/admin/leiloes")
    assert lance_json(admin, 1, "9.999,00").status_code == 401
    pagina = admin.get("/leiloes/1").get_data(as_text=True)
    assert "O administrador acompanha os leilões, mas não dá lances." in pagina
    assert "data-form-lance" not in pagina and "Entrar para dar lance" not in pagina
    assert banco.execute("SELECT COUNT(*) FROM lances WHERE leilao_id = 1").fetchone()[0] == 4


def test_rf05_lojista_recusa_o_leilao_e_o_vendedor_ve_o_motivo(app, ana, admin, banco):
    criar_leilao(ana, app)
    numero = leiloes_criados(banco)[0]["id"]

    sem_motivo = admin.post(f"/admin/leiloes/{numero}/recusar", data={"csrf_token": CSRF, "motivo": " "},
                            follow_redirects=True).get_data(as_text=True)
    assert "Informe o motivo da recusa." in sem_motivo and leiloes_criados(banco)[0]["status"] == "pendente"

    pagina = admin.post(f"/admin/leiloes/{numero}/recusar",
                        data={"csrf_token": CSRF, "motivo": "Carta com dobra não informada"},
                        follow_redirects=True).get_data(as_text=True)
    assert f"Leilão {numero} (Charizard) recusado." in pagina
    (leilao,) = leiloes_criados(banco)
    assert (leilao["status"], leilao["status_da_carta"], leilao["motivo_recusa"]) == (
        "cancelado", "recusada", "Carta com dobra não informada")

    vender_ = ana.get("/vender").get_data(as_text=True)
    assert "Recusada" in vender_ and "Motivo da recusa: Carta com dobra não informada" in vender_
    assert "aguarda aprovação" in aprovar_leilao(app, numero)
    assert "Cancelado (recusado pela loja)" in admin.get("/admin/historico").get_data(as_text=True)


def test_rf02_lojista_consulta_e_edita_os_dados_do_cliente(app, ana, admin, banco):
    lista = admin.get("/admin/usuarios").get_data(as_text=True)
    for nome in ("Ana Souza", *(nome for nome, *_ in CLIENTES)):
        assert nome in lista
    assert "Administrador da loja</a>" not in lista

    cliente = id_de(banco, "ana@teste.com")
    detalhe = admin.get(f"/admin/usuarios/{cliente}").get_data(as_text=True)
    for trecho in ("529.982.247-25", "Descumprimentos", 'value="ana@teste.com"', "Bloquear conta"):
        assert trecho in detalhe

    repetido = admin.post(f"/admin/usuarios/{cliente}", data={
        "csrf_token": CSRF, "nome": "Ana", "email": "rafaela.moura@correio.invalid", "telefone": "48999990000"})
    assert repetido.status_code == 422 and "Este e-mail já tem uma conta." in repetido.get_data(as_text=True)

    salvo = admin.post(f"/admin/usuarios/{cliente}", data={
        "csrf_token": CSRF, "nome": "Ana Maria Souza", "email": "Ana.Maria@Teste.com", "telefone": "(48) 98888-7777"})
    assert salvo.status_code == 303
    linha = banco.execute("SELECT nome, email, telefone FROM usuarios WHERE id = ?", (cliente,)).fetchone()
    assert tuple(linha) == ("Ana Maria Souza", "ana.maria@teste.com", "48988887777")
    assert entrar(app.test_client(), "ana.maria@teste.com").status_code in (303, 400)
    assert "edição de usuário" in operacoes(banco)


def test_rf02_lojista_bloqueia_e_desbloqueia_a_conta(ana, admin, banco):
    cliente = id_de(banco, "ana@teste.com")
    pagina = admin.post(f"/admin/usuarios/{cliente}/bloquear", data={"csrf_token": CSRF},
                        follow_redirects=True).get_data(as_text=True)
    assert "Conta de Ana Souza bloqueada." in pagina and "Desbloquear conta" in pagina
    assert "Bloqueada" in admin.get("/admin/usuarios").get_data(as_text=True)
    recusa = lance_json(ana, 1, "2.355,00")
    assert recusa.status_code == 422 and recusa.get_json()["motivo"] == "cliente_bloqueado"
    assert ana.get("/vender/novo").status_code == 403

    admin.post(f"/admin/usuarios/{cliente}/desbloquear", data={"csrf_token": CSRF})
    assert lance_json(ana, 1, "2.355,00").status_code == 201
    assert operacoes(banco).count("bloqueio de conta") == 1 and "desbloqueio de conta" in operacoes(banco)


def test_rf04_lojista_corrige_os_dados_da_carta(app, ana, admin, banco):
    criar_leilao(ana, app)
    numero = leiloes_criados(banco)[0]["id"]
    assert ">Charizard</a>" in admin.get("/admin/cartas").get_data(as_text=True)
    magic = banco.execute("SELECT id FROM jogos WHERE nome = 'Magic: The Gathering'").fetchone()["id"]

    invalido = admin.post(f"/admin/cartas/{numero}", data={
        "csrf_token": CSRF, "nome": " ", "jogo": "999", "edicao": "", "condicao": "Perfeita"})
    assert invalido.status_code == 422
    for mensagem in ("Informe o nome da carta.", "Escolha o jogo da carta.", "Informe a edição da carta.",
                     "Escolha a condição da carta."):
        assert mensagem in invalido.get_data(as_text=True)

    salvo = admin.post(f"/admin/cartas/{numero}", data={
        "csrf_token": CSRF, "nome": "Charizard  Holo", "jogo": str(magic), "edicao": "Base Set 2 (4/130)",
        "condicao": "Lightly Played (LP)"})
    assert salvo.status_code == 303
    (leilao,) = leiloes_criados(banco)
    assert (leilao["nome"], leilao["jogo"], leilao["edicao"], leilao["condicao"]) == (
        "Charizard Holo", "Magic: The Gathering", "Base Set 2 (4/130)", "Lightly Played (LP)")
    assert "Charizard Holo" in ana.get(f"/leiloes/{numero}").get_data(as_text=True)


def test_rf04_lojista_remove_cadastro_invalido_mas_nao_carta_com_leilao_em_andamento(app, ana, admin, banco):
    criar_leilao(ana, app)
    numero = leiloes_criados(banco)[0]["id"]
    foto = Path(app.config["PASTA_DE_FOTOS"]) / leiloes_criados(banco)[0]["foto"].removeprefix("fotos/")
    assert foto.exists()

    pagina = admin.post(f"/admin/cartas/{numero}/remover", data={"csrf_token": CSRF},
                        follow_redirects=True).get_data(as_text=True)
    assert "Cadastro de Charizard removido." in pagina
    assert leiloes_criados(banco) == [] and not foto.exists()
    assert banco.execute("SELECT COUNT(*) FROM cartas").fetchone()[0] == 15
    assert "Você ainda não anunciou nenhuma carta." in ana.get("/vender").get_data(as_text=True)

    recusado = admin.post("/admin/cartas/1/remover", data={"csrf_token": CSRF},
                          follow_redirects=True).get_data(as_text=True)
    assert "Só dá para remover a carta cujo leilão ainda aguarda aprovação, foi recusado ou foi cancelado." in recusado
    assert banco.execute("SELECT COUNT(*) FROM leiloes WHERE id = 1").fetchone()[0] == 1


def test_rf15_e_rn17_configuracao_vale_para_os_leiloes_criados_depois(app, ana, admin, banco):
    pagina = admin.get("/admin/configuracoes").get_data(as_text=True)
    for valor in ('value="10,00"', 'value="5,00"', 'value="48"', 'value="24"'):
        assert valor in pagina

    salvo = admin.post("/admin/configuracoes", data={
        "csrf_token": CSRF, "taxa": "12,5", "incremento": "10,00", "prazo_pagamento": "24", "prazo_reoferta": "12"})
    assert salvo.status_code == 303
    assert tuple(banco.execute("SELECT * FROM configuracao_loja").fetchone()) == (1, "12.5", 1000, 24, 12)

    assert "O incremento mínimo entre lances é R$ 10,00" in ana.get(
        "/vender/novo?jogo=pokemon&carta=base1-4").get_data(as_text=True)
    criar_leilao(ana, app)
    (novo,) = leiloes_criados(banco)
    assert (novo["incremento_minimo_centavos"], Decimal(novo["taxa_percentual"])) == (1000, Decimal("12.5"))
    antigo = banco.execute("SELECT incremento_minimo_centavos, taxa_percentual FROM leiloes WHERE id = 1").fetchone()
    assert tuple(antigo) == (500, "10.00")


@pytest.mark.parametrize("campo, valor, mensagem", [
    ("taxa", "100", "Informe a taxa em porcentagem"), ("taxa", "dez", "Informe a taxa em porcentagem"),
    ("incremento", "0", "O incremento mínimo precisa ser maior que zero."),
    ("incremento", "", "Informe o incremento mínimo em reais"),
    ("prazo_pagamento", "0", "Informe o prazo em horas inteiras"),
    ("prazo_reoferta", "1,5", "Informe o prazo em horas inteiras"),
])
def test_rf15_configuracao_invalida_nao_e_gravada(admin, banco, campo, valor, mensagem):
    dados = {"csrf_token": CSRF, "taxa": "10", "incremento": "5,00", "prazo_pagamento": "48", "prazo_reoferta": "24"}
    resposta = admin.post("/admin/configuracoes", data={**dados, campo: valor})
    assert resposta.status_code == 422 and mensagem in resposta.get_data(as_text=True)
    assert tuple(banco.execute("SELECT * FROM configuracao_loja").fetchone()) == (1, "10.00", 500, 48, 24)


def test_rf10_arremate_mostra_ao_vencedor_valor_e_prazo_e_o_codigo_de_retirada_so_depois_de_pagar(app, ana, banco):
    numero, bruno = vender(app, ana, banco)
    arremate = transacao_de(banco, numero)
    assert (arremate["valor_centavos"], arremate["taxa_centavos"], arremate["liquido_centavos"]) == (20000, 2000, 18000)
    assert arremate["status"] == "aguardando pagamento" and len(arremate["codigo_retirada"]) == 8

    pagina = bruno.get("/minha-conta/arremates").get_data(as_text=True)
    for trecho in ("R$ 200,00", "Aguardando pagamento", "Pague até",
                   "O código de retirada aparece aqui depois do pagamento.",
                   f'href="/minha-conta/arremates/{numero}/pagar"'):
        assert trecho in pagina
    codigo = arremate["codigo_retirada"]
    assert codigo not in pagina
    assert codigo not in bruno.get(f"/minha-conta/arremates/{numero}/pagar").get_data(as_text=True)
    assert codigo not in bruno.get(f"/leiloes/{numero}").get_data(as_text=True)

    confirmacao = pagar(bruno, numero, follow_redirects=True).get_data(as_text=True)
    assert f"Retire Charizard na loja com o código {codigo}." in confirmacao
    paga = bruno.get("/minha-conta/arremates").get_data(as_text=True)
    assert f'translate="no">{codigo}</strong>. Apresente na loja para retirar a carta.' in paga
    assert codigo not in ana.get("/vender").get_data(as_text=True)


def test_vendedor_ve_o_arremate_e_quanto_vai_receber(app, ana, banco):
    vender(app, ana, banco)
    vendedora = ana.get("/vender").get_data(as_text=True)
    assert "Arrematada (aguardando pagamento)" in vendedora and "Você recebe R$ 180,00" in vendedora


def test_rf11_comprador_paga_pelo_gateway_e_a_transacao_fica_paga(app, ana, banco):
    numero, bruno = vender(app, ana, banco)
    tela = bruno.get(f"/minha-conta/arremates/{numero}/pagar").get_data(as_text=True)
    assert "Pagar R$ 200,00" in tela and 'value="pix"' in tela and 'value="cartão"' in tela
    assert 'name="usar_saldo"' not in tela

    assert pagar(bruno, numero, forma="boleto").status_code == 422
    assert transacao_de(banco, numero)["status"] == "aguardando pagamento"

    resposta = pagar(bruno, numero, forma="cartão")
    assert (resposta.status_code, resposta.headers["Location"]) == (303, "/minha-conta/arremates")
    arremate = transacao_de(banco, numero)
    assert (arremate["status"], arremate["pago_gateway_centavos"], arremate["pago_saldo_centavos"],
            arremate["forma_pagamento"]) == ("pago", 20000, 0, "cartão")
    assert arremate["data_pagamento"] is not None
    assert leiloes_criados(banco)[0]["status_da_carta"] == "paga"

    pagina = bruno.get("/minha-conta/arremates").get_data(as_text=True)
    assert "Pago, aguardando retirada" in pagina and "Apresente na loja para retirar a carta." in pagina
    assert f'href="/minha-conta/arremates/{numero}/pagar"' not in pagina
    assert "Paga (aguardando retirada)" in ana.get("/vender").get_data(as_text=True)
    assert pagar(bruno, numero).status_code == 302


def test_rf11_e_rn18_pagamento_usa_o_saldo_da_carteira_e_completa_no_gateway(app, ana, banco):
    numero, bruno = vender(app, ana, banco)
    banco.execute("UPDATE carteiras SET saldo_centavos = 5000 WHERE cliente_id = ?", (id_de(banco, "bruno@teste.com"),))
    tela = bruno.get(f"/minha-conta/arremates/{numero}/pagar").get_data(as_text=True)
    assert "Usar o saldo da carteira (R$ 50,00 disponíveis); faltam R$ 150,00" in tela

    assert pagar(bruno, numero, usar_saldo="sim", forma="pix").status_code == 303
    arremate = transacao_de(banco, numero)
    assert (arremate["status"], arremate["pago_saldo_centavos"], arremate["pago_gateway_centavos"]) == (
        "pago", 5000, 15000)
    assert carteira_de(banco, "bruno@teste.com") == (0, 0)
    extrato = bruno.get("/minha-conta/carteira").get_data(as_text=True)
    assert "Pagamento de arremate" in extrato and "-R$ 50,00" in extrato


def test_rf11_pagamento_integral_com_saldo_dispensa_o_gateway(app, ana, banco):
    numero, bruno = vender(app, ana, banco)
    banco.execute("UPDATE carteiras SET saldo_centavos = 30000 WHERE cliente_id = ?",
                  (id_de(banco, "bruno@teste.com"),))
    assert pagar(bruno, numero, usar_saldo="sim", forma="").status_code == 303
    arremate = transacao_de(banco, numero)
    assert (arremate["status"], arremate["pago_saldo_centavos"], arremate["pago_gateway_centavos"],
            arremate["forma_pagamento"]) == ("pago", 20000, 0, None)
    assert carteira_de(banco, "bruno@teste.com") == (10000, 0)


def test_so_o_comprador_ve_e_paga_o_proprio_arremate(app, ana, banco):
    numero, _ = vender(app, ana, banco)
    assert ana.get(f"/minha-conta/arremates/{numero}/pagar").status_code == 404
    assert pagar(ana, numero).status_code == 404
    assert pagar(ana, 999).status_code == 404
    assert transacao_de(banco, numero)["status"] == "aguardando pagamento"


def test_rf12_entrega_com_o_codigo_repassa_o_valor_liquido_ao_vendedor(app, ana, admin, banco):
    numero, bruno = vender(app, ana, banco)
    codigo = transacao_de(banco, numero)["codigo_retirada"]

    card = f'<a class="entrega-pendente" href="/admin/entregas/{numero}">'
    assert "A carta só pode ser entregue depois do pagamento do arremate." in entregar(admin, numero, codigo)
    nao_pago = admin.get(f"/admin/entregas/{numero}").get_data(as_text=True)
    assert "ainda não foi pago" in nao_pago and 'name="codigo"' not in nao_pago
    for url in ("/admin/leiloes", "/admin/entregas"):
        assert card not in admin.get(url).get_data(as_text=True), "sem pagamento, não há entrega pendente"
    pagar(bruno, numero)

    for url in ("/admin/leiloes", "/admin/entregas"):
        lista = admin.get(url).get_data(as_text=True)
        for trecho in (card, "Entrega pendente", "Charizard", "Ana Souza pagou R$\xa0200,00", ">Entregas&nbsp;<span"):
            assert trecho in lista, (url, trecho)
        assert codigo not in lista and 'name="codigo"' not in lista
    assert "Entregas pendentes" in admin.get("/admin/leiloes").get_data(as_text=True)

    consulta = admin.get(f"/admin/entregas/{numero}").get_data(as_text=True)
    assert codigo not in consulta, "o código fica só com o comprador"
    for trecho in ("Ana Souza", "111.444.777-35", 'name="codigo"', "R$ 200,00", "R$ 20,00", "R$ 180,00",
                   "Confirmar entrega e repassar ao vendedor"):
        assert trecho in consulta

    for errado, mensagem in (("ZZZZ9999", "O código de retirada não confere com este arremate."),
                             ("  ", "Informe o código de retirada que o comprador apresentou.")):
        assert mensagem in entregar(admin, numero, errado)
    sem_lances = banco.execute(
        "SELECT id FROM leiloes WHERE id NOT IN (SELECT leilao_id FROM transacoes) LIMIT 1").fetchone()["id"]
    for sem_arremate in (sem_lances, 999):
        assert admin.get(f"/admin/entregas/{sem_arremate}").status_code == 404
        assert admin.post(f"/admin/entregas/{sem_arremate}",
                          data={"csrf_token": CSRF, "codigo": codigo}).status_code == 404
    assert transacao_de(banco, numero)["status"] == "pago" and carteira_de(banco, "ana@teste.com") == (0, 0)

    registrada = entregar(admin, numero, f" {codigo.lower()} ")
    assert "Entrega de Charizard registrada." in registrada and card not in registrada
    assert "Leilões aguardando aprovação" in registrada, "depois da entrega, o lojista volta para a página de leilões"
    arremate = transacao_de(banco, numero)
    assert arremate["status"] == "entregue" and arremate["data_entrega"] is not None
    assert leiloes_criados(banco)[0]["status_da_carta"] == "entregue"
    assert carteira_de(banco, "ana@teste.com") == (18000, 0)

    carteira = ana.get("/minha-conta/carteira").get_data(as_text=True)
    assert "R$ 180,00" in carteira and "Repasse da venda de Charizard" in carteira
    assert "Entregue (repasse efetuado)" in ana.get("/vender").get_data(as_text=True)
    assert "Carta retirada em" in bruno.get("/minha-conta/arremates").get_data(as_text=True)

    assert "Esta carta já foi entregue." in entregar(admin, numero, codigo)
    assert carteira_de(banco, "ana@teste.com") == (18000, 0)
    entregue = admin.get(f"/admin/entregas/{numero}").get_data(as_text=True)
    assert "Carta entregue em" in entregue and 'name="codigo"' not in entregue
    assert "Nenhuma carta paga aguardando retirada." in admin.get("/admin/entregas").get_data(as_text=True)


def test_rf21_prazo_de_pagamento_vencido_marca_descumprimento_e_devolve_a_carta(app, ana, admin, banco):
    numero, bruno = vender(app, ana, banco)
    avancar_relogio(app, days=5, hours=2)
    pagina = bruno.get("/minha-conta/arremates").get_data(as_text=True)
    assert "Não pago no prazo" in pagina and f'href="/minha-conta/arremates/{numero}/pagar"' not in pagina
    assert transacao_de(banco, numero)["codigo_retirada"] not in pagina

    assert transacao_de(banco, numero)["status"] == "não paga"
    assert leiloes_criados(banco)[0]["status_da_carta"] == "devolvida ao vendedor"
    cliente = id_de(banco, "bruno@teste.com")
    assert banco.execute("SELECT descumprimentos FROM clientes WHERE usuario_id = ?", (cliente,)).fetchone()[0] == 1
    assert pagar(bruno, numero).status_code == 302
    assert "Este arremate não foi pago no prazo" in admin.get(f"/admin/entregas/{numero}").get_data(as_text=True)

    assert "Devolvida ao vendedor" in ana.get("/vender").get_data(as_text=True)
    assert "Devolvido (não pago)" in admin.get("/admin/historico").get_data(as_text=True)
    assert "prazo de pagamento expirado" in operacoes(banco)


def test_rf22_cliente_pede_saque_e_o_lojista_paga_ou_recusa(app, ana, admin, banco):
    numero, bruno = vender(app, ana, banco)
    pagar(bruno, numero)
    entregar(admin, numero, transacao_de(banco, numero)["codigo_retirada"])

    assert "Solicitar saque" in ana.get("/minha-conta/carteira").get_data(as_text=True)
    demais = pedir_saque(ana, "180,01")
    assert demais.status_code == 422 and "não pode passar do saldo disponível" in demais.get_data(as_text=True)
    assert pedir_saque(ana, "abc").status_code == 422 and pedir_saque(ana, "50,00", " ").status_code == 422
    assert carteira_de(banco, "ana@teste.com") == (18000, 0)

    assert pedir_saque(ana, "100,00").status_code == 303
    assert carteira_de(banco, "ana@teste.com") == (18000, 10000)
    carteira = ana.get("/minha-conta/carteira").get_data(as_text=True)
    assert "R$ 80,00" in carteira and "R$ 100,00 bloqueados" in carteira and "Solicitado" in carteira
    assert pedir_saque(ana, "80,01").status_code == 422

    fila = admin.get("/admin/saques").get_data(as_text=True)
    assert "Ana Souza" in fila and "ana@pix.com" in fila and "R$ 100,00" in fila
    saque = banco.execute("SELECT id FROM saques").fetchone()["id"]
    pago = admin.post(f"/admin/saques/{saque}/pagar", data={"csrf_token": CSRF},
                      follow_redirects=True).get_data(as_text=True)
    assert "saque de Ana Souza pago" in pago and "Nenhum saque aguardando resposta." in pago
    assert carteira_de(banco, "ana@teste.com") == (8000, 0)
    assert "Saque por Pix para ana@pix.com" in ana.get("/minha-conta/carteira").get_data(as_text=True)
    assert "já foi respondido" in admin.post(f"/admin/saques/{saque}/recusar", data={"csrf_token": CSRF},
                                             follow_redirects=True).get_data(as_text=True)

    assert pedir_saque(ana, "80,00").status_code == 303
    outro = banco.execute("SELECT id FROM saques ORDER BY id DESC").fetchone()["id"]
    admin.post(f"/admin/saques/{outro}/recusar", data={"csrf_token": CSRF})
    assert carteira_de(banco, "ana@teste.com") == (8000, 0)
    assert [linha["status"] for linha in banco.execute("SELECT status FROM saques ORDER BY id")] == ["pago", "recusado"]
    assert "Saque não encontrado." in admin.post("/admin/saques/999/pagar", data={"csrf_token": CSRF},
                                                 follow_redirects=True).get_data(as_text=True)


def test_carteira_sem_saldo_nao_oferece_saque(ana):
    pagina = ana.get("/minha-conta/carteira").get_data(as_text=True)
    assert "Solicitar saque" not in pagina
    assert pedir_saque(ana, "10,00").status_code == 422


def test_rf16_historico_lista_os_leiloes_finalizados_com_o_desfecho(app, ana, admin, banco):
    assert "Nenhum leilão finalizado ainda." in admin.get("/admin/historico").get_data(as_text=True)
    numero, bruno = vender(app, ana, banco)
    pagar(bruno, numero)
    entregar(admin, numero, transacao_de(banco, numero)["codigo_retirada"])

    pagina = admin.get("/admin/historico").get_data(as_text=True)
    linha = pagina[pagina.index(f'href="/leiloes/{numero}"'):]
    linha = linha[:linha.index("</tr>")]
    for trecho in ("Charizard", "Ana Souza","R$ 200,00", "R$ 20,00", "Concluído"):
        assert trecho in linha
    assert "Devolvido (sem lances)" in pagina and "Aguardando pagamento" in pagina


def test_rf18_extrato_financeiro_soma_o_periodo(app, ana, admin, banco):
    numero, bruno = vender(app, ana, banco)
    pagar(bruno, numero)
    entregar(admin, numero, transacao_de(banco, numero)["codigo_retirada"])
    pedir_saque(ana, "100,00")
    admin.post(f"/admin/saques/{banco.execute('SELECT id FROM saques').fetchone()['id']}/pagar",
               data={"csrf_token": CSRF})

    pagina = admin.get("/admin/financeiro?de=2000-01-01&ate=2100-01-01").get_data(as_text=True)
    totais = pagina[pagina.index('class="totais"'):pagina.index("</dl>", pagina.index('class="totais"'))]
    for rotulo, valor in (("Pagamentos recebidos", "R$ 200,00"), ("Taxas retidas", "R$ 20,00"),
                          ("Repasses aos vendedores", "R$ 180,00"), ("Saques pagos", "R$ 100,00")):
        assert f"<dt>{rotulo}</dt><dd>{valor}</dd>" in totais
    for lancamento in ("Arremate", "Pagamento recebido", "Taxa retida", "Repasse ao vendedor", "Saque pago"):
        assert f"<td>{lancamento}</td>" in pagina

    vazio = admin.get("/admin/financeiro?de=2001-01-01&ate=2001-01-31").get_data(as_text=True)
    assert "Nenhum lançamento neste período." in vazio and "<dt>Taxas retidas</dt><dd>R$ 0,00</dd>" in vazio
    assert admin.get("/admin/financeiro").status_code == 200
    assert admin.get("/admin/financeiro?de=amanha&ate=2001-13-45").status_code == 200


def test_rf19_log_registra_usuario_operacao_valor_ip_e_hora(app, ana, admin, banco):
    numero, bruno = vender(app, ana, banco)
    pagar(bruno, numero)
    entregar(admin, numero, transacao_de(banco, numero)["codigo_retirada"])

    registradas = operacoes(banco)
    for operacao in ("cadastro de cliente", "login", "criação de leilão", "aprovação de leilão", "lance",
                     "encerramento automático de leilão", "pagamento de arremate", "entrega e repasse"):
        assert operacao in registradas

    lance = banco.execute("SELECT * FROM log_operacoes WHERE operacao = 'lance'").fetchone()
    assert (lance["usuario_id"], lance["valor_centavos"], lance["ip"]) == (id_de(banco, "bruno@teste.com"), 20000,
                                                                           "127.0.0.1")
    assert lance["data_hora"] and f"leilão {numero}" in lance["detalhe"]
    do_sistema = banco.execute(
        "SELECT usuario_id, ip FROM log_operacoes WHERE operacao = 'encerramento automático de leilão'").fetchone()
    assert tuple(do_sistema) == (None, None)

    pagina = admin.get("/admin/auditoria").get_data(as_text=True)
    for trecho in ("entrega e repasse", "Administrador da loja", "Sistema", "127.0.0.1", "R$ 200,00",
                   f"leilão {numero}: Charizard"):
        assert trecho in pagina


def test_lance_recusado_nao_entra_no_log(ana, banco):
    assert lance_json(ana, 1, "1,00").status_code == 422
    assert "lance" not in operacoes(banco)
