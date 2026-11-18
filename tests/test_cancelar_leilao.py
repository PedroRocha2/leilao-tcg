from datetime import timedelta
from decimal import Decimal

import pytest

from apoio import (AGORA, CSRF, aprovar_leilao as aprovar, avancar_relogio, criar_conta, criar_leilao, lance_json,
                   leiloes_criados, navegador_admin, no_fuso_da_loja, novo_cliente, novo_leilao, outro_navegador)
from app.dominio.leiloes import LanceRecusado, MotivoRecusa, StatusCarta, StatusLeilao


@pytest.fixture
def ana():
    return novo_cliente(1, "100200300")


@pytest.fixture
def bruno():
    return novo_cliente(2, "200300400")


@pytest.mark.parametrize("status", [StatusLeilao.PENDENTE, StatusLeilao.APROVADO, StatusLeilao.ATIVO])
def test_rf20_leilao_sem_lances_e_cancelado_e_a_carta_fica_cancelada(ana, status):
    leilao = novo_leilao(ana, status=status)
    assert leilao.podeSerCancelado(AGORA) is True
    leilao.cancelar(AGORA)
    assert (leilao.status, leilao.carta.status) == (StatusLeilao.CANCELADO, StatusCarta.CANCELADA)
    assert leilao.dataFimReal == AGORA and leilao.motivoRecusa is None


def test_rf20_leilao_com_lance_nao_e_cancelado(ana, bruno):
    """RN03: o lance é irrevogável, então o vendedor não o desfaz cancelando o leilão."""
    leilao = novo_leilao(ana)
    bruno.darLance(leilao, Decimal("100"), AGORA)
    assert leilao.podeSerCancelado(AGORA) is False
    with pytest.raises(ValueError, match="já recebeu lances"):
        leilao.cancelar(AGORA)
    assert (leilao.status, leilao.carta.status) == (StatusLeilao.ATIVO, "em leilão")
    assert leilao.dataFimReal is None and len(leilao.lances) == 1


@pytest.mark.parametrize("status", [StatusLeilao.ENCERRADO, StatusLeilao.CANCELADO])
def test_rf20_leilao_que_ja_terminou_nao_e_cancelado(ana, status):
    leilao = novo_leilao(ana, status=status)
    assert leilao.podeSerCancelado(AGORA) is False
    with pytest.raises(ValueError, match="já terminou"):
        leilao.cancelar(AGORA)
    assert leilao.status == status


def test_rf20_leilao_ativo_com_o_prazo_vencido_nao_e_cancelado(ana):
    leilao = novo_leilao(ana)
    with pytest.raises(ValueError, match="já terminou"):
        leilao.cancelar(leilao.dataFimPrevista)
    leilao.cancelar(leilao.dataFimPrevista - timedelta(milliseconds=1))
    assert leilao.status == StatusLeilao.CANCELADO


def test_leilao_cancelado_nao_comeca_nem_recebe_lance(ana, bruno):
    leilao = novo_leilao(ana, status=StatusLeilao.APROVADO)
    leilao.cancelar(AGORA)
    with pytest.raises(ValueError, match="aprovado"):
        leilao.iniciar(AGORA)
    with pytest.raises(LanceRecusado) as erro:
        bruno.darLance(leilao, Decimal("100"), AGORA)
    assert erro.value.motivo is MotivoRecusa.LEILAO_INATIVO


@pytest.fixture
def logado(cliente_http):
    criar_conta(cliente_http)
    return cliente_http


def cancelar(navegador, numero: int, **opcoes):
    return navegador.post(f"/vender/{numero}/cancelar", data={"csrf_token": CSRF}, **opcoes)


def situacao_no_banco(banco) -> tuple[str, str]:
    (leilao,) = leiloes_criados(banco)
    return leilao["status"], leilao["status_da_carta"]


def operacoes(banco) -> list[str]:
    return [linha["operacao"] for linha in banco.execute("SELECT operacao FROM log_operacoes ORDER BY id")]


def test_rf20_vendedor_cancela_o_leilao_que_aguarda_aprovacao(logado, app, banco):
    criar_leilao(logado, app)
    numero = leiloes_criados(banco)[0]["id"]
    vender = logado.get("/vender").get_data(as_text=True)
    assert f'action="/vender/{numero}/cancelar"' in vender and "Sim, cancelar o leilão" in vender

    resposta = cancelar(logado, numero)
    assert resposta.status_code == 303 and resposta.headers["Location"] == "/vender"
    assert situacao_no_banco(banco) == ("cancelado", "cancelada")
    (leilao,) = leiloes_criados(banco)
    assert leilao["data_fim_real"] is not None and leilao["motivo_recusa"] is None

    vender = logado.get("/vender").get_data(as_text=True)
    for trecho in ("Leilão de Charizard cancelado.", "Cancelada"):
        assert trecho in vender
    assert "/cancelar" not in vender and "Motivo da recusa" not in vender
    assert "cancelamento de leilão" in operacoes(banco)

    admin = navegador_admin(app)
    assert "Nenhum leilão aguardando aprovação." in admin.get("/admin/leiloes").get_data(as_text=True)
    assert "Cancelado pelo vendedor" in admin.get("/admin/historico").get_data(as_text=True)
    assert "aguarda aprovação" in aprovar(app, numero)


def test_rf20_vendedor_cancela_o_leilao_ativo_que_nao_recebeu_lances(logado, app, banco):
    criar_leilao(logado, app)
    numero = leiloes_criados(banco)[0]["id"]
    aprovar(app, numero)
    assert logado.get("/leiloes").get_data(as_text=True).count('class="cartao"') == 16

    pagina = cancelar(logado, numero, follow_redirects=True).get_data(as_text=True)
    assert "Leilão de Charizard cancelado." in pagina and "retire-a no balcão" in pagina
    assert situacao_no_banco(banco) == ("cancelado", "cancelada")
    assert logado.get("/leiloes").get_data(as_text=True).count('class="cartao"') == 15

    bruno = outro_navegador(app)
    detalhe = bruno.get(f"/leiloes/{numero}").get_data(as_text=True)
    assert "Este leilão foi cancelado pelo vendedor." in detalhe and "data-form-lance" not in detalhe
    recusa = lance_json(bruno, numero, "50,00")
    assert recusa.status_code == 422 and recusa.get_json()["motivo"] == "leilao_inativo"


def test_rf20_leilao_agendado_cancelado_nao_comeca_na_data_de_inicio(logado, app, banco):
    criar_leilao(logado, app, inicio=no_fuso_da_loja(app, hours=2))
    numero = leiloes_criados(banco)[0]["id"]
    aprovar(app, numero)
    assert situacao_no_banco(banco) == ("aprovado", "aprovada")

    assert cancelar(logado, numero).status_code == 303
    avancar_relogio(app, hours=2, minutes=1)
    assert f'href="/leiloes/{numero}"' not in logado.get("/leiloes").get_data(as_text=True)
    assert situacao_no_banco(banco) == ("cancelado", "cancelada")


def test_rf20_leilao_com_lance_nao_pode_ser_cancelado(logado, app, banco):
    criar_leilao(logado, app)
    numero = leiloes_criados(banco)[0]["id"]
    aprovar(app, numero)
    assert lance_json(outro_navegador(app), numero, "50,00").status_code == 201

    assert "/cancelar" not in logado.get("/vender").get_data(as_text=True)
    pagina = cancelar(logado, numero, follow_redirects=True).get_data(as_text=True)
    assert "Este leilão já recebeu lances e não pode mais ser cancelado." in pagina
    assert situacao_no_banco(banco) == ("ativo", "em leilão")
    assert "cancelamento de leilão" not in operacoes(banco)


def test_rf20_leilao_encerrado_nao_pode_ser_cancelado(logado, app, banco):
    criar_leilao(logado, app)
    numero = leiloes_criados(banco)[0]["id"]
    aprovar(app, numero)
    avancar_relogio(app, days=4)

    assert "/cancelar" not in logado.get("/vender").get_data(as_text=True)
    pagina = cancelar(logado, numero, follow_redirects=True).get_data(as_text=True)
    assert "Este leilão já terminou e não pode mais ser cancelado." in pagina
    assert situacao_no_banco(banco) == ("encerrado", "devolvida ao vendedor")


def test_rf20_so_o_vendedor_cancela_o_proprio_leilao(logado, app, banco):
    criar_leilao(logado, app)
    numero = leiloes_criados(banco)[0]["id"]

    assert cancelar(outro_navegador(app), numero).status_code == 404
    assert cancelar(logado, 1).status_code == 404, "leilão da carga inicial, de outro vendedor"
    assert cancelar(logado, 999).status_code == 404
    assert cancelar(navegador_admin(app), numero).headers["Location"] == "/admin/leiloes"

    visitante = app.test_client()
    with visitante.session_transaction() as sessao:
        sessao["csrf"] = CSRF
    assert cancelar(visitante, numero).headers["Location"].startswith("/entrar?proximo=")
    assert logado.post(f"/vender/{numero}/cancelar").status_code == 400, "sem o token CSRF"
    assert logado.get(f"/vender/{numero}/cancelar").status_code == 405

    assert situacao_no_banco(banco) == ("pendente", "aguardando depósito")
    assert banco.execute("SELECT status FROM leiloes WHERE id = 1").fetchone()["status"] == "ativo"


# --- Exclusão do leilão cancelado ---

def excluir(navegador, numero: int, **opcoes):
    return navegador.post(f"/vender/{numero}/excluir", data={"csrf_token": CSRF}, **opcoes)


def contagens(banco) -> tuple[int, ...]:
    return tuple(banco.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
                 for tabela in ("leiloes", "cartas", "carta_fotos", "carta_atributos"))


def test_vendedor_exclui_do_site_o_leilao_que_cancelou(logado, app, banco):
    import io
    from pathlib import Path

    antes = contagens(banco)
    foto = b"\xff\xd8\xff\xe0" + b"\x00" * 64
    criar_leilao(logado, app, fotos=[(io.BytesIO(foto), "frente.jpg")])
    numero = leiloes_criados(banco)[0]["id"]
    pasta = Path(app.config["PASTA_DE_FOTOS"])
    assert len(list(pasta.iterdir())) == 2 and contagens(banco) != antes

    assert "/excluir" not in logado.get("/vender").get_data(as_text=True)
    cancelado = cancelar(logado, numero, follow_redirects=True).get_data(as_text=True)
    assert "Para tirar o leilão do site, use Excluir do site." in cancelado
    assert f'action="/vender/{numero}/excluir"' in cancelado and "Sim, excluir" in cancelado
    assert "não dá para desfazer" in cancelado and "/cancelar" not in cancelado

    resposta = excluir(logado, numero)
    assert (resposta.status_code, resposta.headers["Location"]) == (303, "/vender")
    assert leiloes_criados(banco) == [] and contagens(banco) == antes
    assert list(pasta.iterdir()) == []

    vender = logado.get("/vender").get_data(as_text=True)
    assert "Leilão de Charizard excluído do site." in vender and "Você ainda não anunciou nenhuma carta." in vender
    assert logado.get(f"/leiloes/{numero}").status_code == 404
    assert "Cancelado pelo vendedor" not in navegador_admin(app).get("/admin/historico").get_data(as_text=True)
    # RF19
    feitas = operacoes(banco)
    assert feitas.index("cancelamento de leilão") < feitas.index("exclusão de leilão")
    assert excluir(logado, numero).status_code == 404, "o leilão não existe mais"


def test_so_o_leilao_cancelado_pelo_vendedor_pode_ser_excluido(logado, app, banco):
    criar_leilao(logado, app)
    pendente = leiloes_criados(banco)[0]["id"]
    recusa = excluir(logado, pendente, follow_redirects=True).get_data(as_text=True)
    assert "Só dá para excluir um leilão que você cancelou." in recusa

    navegador_admin(app).post(f"/admin/leiloes/{pendente}/recusar",
                              data={"csrf_token": CSRF, "motivo": "Carta diferente da anunciada"})
    assert situacao_no_banco(banco) == ("cancelado", "recusada")
    vender = logado.get("/vender").get_data(as_text=True)
    assert "Motivo da recusa" in vender and "/excluir" not in vender
    assert "Só dá para excluir" in excluir(logado, pendente, follow_redirects=True).get_data(as_text=True)
    assert len(leiloes_criados(banco)) == 1

    criar_leilao(logado, app)
    ativo = leiloes_criados(banco)[1]["id"]
    aprovar(app, ativo)
    assert "Só dá para excluir" in excluir(logado, ativo, follow_redirects=True).get_data(as_text=True)
    avancar_relogio(app, days=4)
    assert "Só dá para excluir" in excluir(logado, ativo, follow_redirects=True).get_data(as_text=True)
    assert len(leiloes_criados(banco)) == 2
    assert "exclusão de leilão" not in operacoes(banco)


def test_so_o_vendedor_exclui_o_proprio_leilao_cancelado(logado, app, banco):
    criar_leilao(logado, app)
    numero = leiloes_criados(banco)[0]["id"]
    cancelar(logado, numero)

    assert excluir(outro_navegador(app), numero).status_code == 404
    assert excluir(logado, 1).status_code == 404, "leilão da carga inicial, de outro vendedor"
    assert excluir(navegador_admin(app), numero).headers["Location"] == "/admin/leiloes"
    visitante = app.test_client()
    with visitante.session_transaction() as sessao:
        sessao["csrf"] = CSRF
    assert excluir(visitante, numero).headers["Location"].startswith("/entrar?proximo=")
    assert logado.post(f"/vender/{numero}/excluir").status_code == 400, "sem o token CSRF"
    assert logado.get(f"/vender/{numero}/excluir").status_code == 405

    assert situacao_no_banco(banco) == ("cancelado", "cancelada")
    assert banco.execute("SELECT COUNT(*) FROM leiloes WHERE id = 1").fetchone()[0] == 1
