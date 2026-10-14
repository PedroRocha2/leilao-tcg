"""Testes unitários das regras do lance, no domínio (sem Flask nem banco).

Cada regra tem o caso válido e as violações. Leilão padrão: lance inicial R$ 100,00,
incremento mínimo R$ 5,00, aberto de ontem até amanhã.
"""

import dataclasses
from datetime import timedelta
from decimal import Decimal

import pytest

from apoio import AGORA, novo_cliente, novo_leilao
from app.dominio.leiloes import (
    JANELA_DE_PRORROGACAO,
    PRORROGACAO,
    Lance,
    LanceRecusado,
    MotivoRecusa,
    StatusLeilao,
)

VALOR = Decimal


@pytest.fixture
def vendedor():
    return novo_cliente(1, "100200300")


@pytest.fixture
def ana():
    return novo_cliente(2, "200300400")


@pytest.fixture
def bruno():
    return novo_cliente(3, "300400500")


@pytest.fixture
def leilao(vendedor):
    return novo_leilao(vendedor)


def recusa(cliente, leilao, valor, agora=AGORA) -> LanceRecusado:
    with pytest.raises(LanceRecusado) as erro:
        cliente.darLance(leilao, VALOR(valor), agora)
    return erro.value


# ---------- RN01: calcularLanceMinimo() e validarLance(valor) ----------

def test_sem_lances_o_minimo_e_o_lance_inicial(leilao):
    assert leilao.getMaiorLance() is None
    assert leilao.calcularLanceMinimo() == VALOR("100.00")


def test_com_lances_o_minimo_e_o_maior_lance_mais_o_incremento(leilao, ana):
    ana.darLance(leilao, VALOR("130.00"), AGORA)
    assert leilao.calcularLanceMinimo() == VALOR("135.00")


def test_validar_lance_aceita_o_proprio_minimo(leilao, ana):
    ana.darLance(leilao, VALOR("130.00"), AGORA)
    assert leilao.validarLance(VALOR("135.00"), AGORA) is True


def test_validar_lance_aceita_acima_do_minimo(leilao):
    assert leilao.validarLance(VALOR("100.01"), AGORA) is True
    assert leilao.validarLance(VALOR("999.00"), AGORA) is True


@pytest.mark.parametrize("valor", ["134.99", "131.00", "130.00", "50.00"])
def test_validar_lance_recusa_abaixo_do_minimo(leilao, ana, bruno, valor):
    ana.darLance(leilao, VALOR("130.00"), AGORA)
    assert leilao.validarLance(VALOR(valor), AGORA) is False
    assert recusa(bruno, leilao, valor).motivo is MotivoRecusa.ABAIXO_DO_MINIMO


def test_primeiro_lance_igual_ao_lance_inicial_e_aceito(leilao, ana):
    lance = ana.darLance(leilao, VALOR("100.00"), AGORA)
    assert leilao.getMaiorLance() is lance


def test_primeiro_lance_abaixo_do_lance_inicial_e_recusado(leilao, ana):
    erro = recusa(ana, leilao, "99.99")
    assert erro.motivo is MotivoRecusa.ABAIXO_DO_MINIMO
    assert "R$ 100,00" in erro.mensagem


def test_recusa_explica_o_minimo_o_maior_lance_e_o_incremento(leilao, ana, bruno):
    ana.darLance(leilao, VALOR("130.00"), AGORA)
    mensagem = recusa(bruno, leilao, "134.00").mensagem
    for trecho in ("R$ 135,00", "R$ 130,00", "R$ 5,00"):
        assert trecho in mensagem


@pytest.mark.parametrize("valor", ["0", "-10.00"])
def test_recusa_valor_zero_ou_negativo(leilao, ana, valor):
    assert recusa(ana, leilao, valor).motivo is MotivoRecusa.VALOR_INVALIDO


def test_usa_o_incremento_gravado_no_leilao(vendedor, ana, bruno):
    # RN17: o incremento é o da loja quando o leilão foi criado, gravado no próprio leilão.
    leilao = novo_leilao(vendedor, incremento="10.00")
    ana.darLance(leilao, VALOR("100.00"), AGORA)
    assert recusa(bruno, leilao, "109.99").motivo is MotivoRecusa.ABAIXO_DO_MINIMO
    bruno.darLance(leilao, VALOR("110.00"), AGORA)


# ---------- RN12 e RF07: status ativo e dentro do prazo ----------

@pytest.mark.parametrize("status", [StatusLeilao.PENDENTE, StatusLeilao.APROVADO,
                                    StatusLeilao.ENCERRADO, StatusLeilao.CANCELADO])
def test_so_leilao_ativo_recebe_lance(vendedor, ana, status):
    leilao = novo_leilao(vendedor, status=status)
    assert leilao.validarLance(VALOR("500.00"), AGORA) is False
    assert recusa(ana, leilao, "500.00").motivo is MotivoRecusa.LEILAO_INATIVO


def test_leilao_ativo_dentro_do_prazo_recebe_lance(leilao):
    assert leilao.estaAberto(AGORA)
    assert leilao.validarLance(VALOR("100.00"), AGORA) is True


def test_recusa_no_instante_exato_do_fim_previsto(vendedor, ana):
    leilao = novo_leilao(vendedor, fim=AGORA)
    assert recusa(ana, leilao, "500.00").motivo is MotivoRecusa.PRAZO_ENCERRADO


def test_recusa_depois_do_fim_previsto(vendedor, ana):
    leilao = novo_leilao(vendedor, fim=AGORA - timedelta(seconds=1))
    assert recusa(ana, leilao, "500.00").motivo is MotivoRecusa.PRAZO_ENCERRADO


def test_aceita_no_ultimo_milissegundo_antes_do_fim(vendedor, ana):
    leilao = novo_leilao(vendedor, fim=AGORA + timedelta(milliseconds=1))
    ana.darLance(leilao, VALOR("100.00"), AGORA)


def test_recusa_antes_da_data_de_inicio(vendedor, ana):
    leilao = novo_leilao(vendedor, inicio=AGORA + timedelta(minutes=1))
    assert recusa(ana, leilao, "500.00").motivo is MotivoRecusa.LEILAO_NAO_INICIADO


def test_rn05_fim_previsto_precisa_ser_depois_do_inicio(vendedor):
    with pytest.raises(ValueError, match="RN05"):
        novo_leilao(vendedor, inicio=AGORA, fim=AGORA)


# ---------- RN15: Cliente.podeDarLance() ----------

def test_cliente_sem_bloqueio_pode_dar_lance(ana, leilao):
    assert ana.podeDarLance() is True
    ana.darLance(leilao, VALOR("100.00"), AGORA)


def test_cliente_bloqueado_nao_pode_dar_lance(leilao):
    bloqueada = novo_cliente(4, "400500600", bloqueado=True)
    assert bloqueada.podeDarLance() is False
    erro = recusa(bloqueada, leilao, "500.00")
    assert erro.motivo is MotivoRecusa.CLIENTE_BLOQUEADO
    assert leilao.lances == []


def test_cliente_desativado_nao_pode_dar_lance(leilao):
    desativado = novo_cliente(5, "500600700", ativo=False)
    assert desativado.podeDarLance() is False
    assert recusa(desativado, leilao, "500.00").motivo is MotivoRecusa.CLIENTE_BLOQUEADO


def test_o_lance_nao_depende_do_saldo_da_carteira(ana, leilao):
    # Pelo diagrama, darLance não consulta a Carteira: saldo zero não impede o lance.
    assert ana.carteira.saldo == VALOR("0.00")
    ana.darLance(leilao, VALOR("5000.00"), AGORA)


# ---------- RN11: ninguém dá lance no próprio leilão ----------

def test_vendedor_nao_da_lance_no_proprio_leilao(vendedor, leilao):
    assert recusa(vendedor, leilao, "500.00").motivo is MotivoRecusa.PROPRIO_LEILAO


def test_vendedor_e_reconhecido_mesmo_carregado_em_outro_objeto(leilao):
    # O banco devolve objetos diferentes para a mesma pessoa: vale o id.
    mesmo_vendedor = novo_cliente(1, "100200300")
    assert recusa(mesmo_vendedor, leilao, "500.00").motivo is MotivoRecusa.PROPRIO_LEILAO


# ---------- RN02: prorrogação nos últimos 3 minutos ----------

def test_lance_com_menos_de_3_minutos_para_o_fim_prorroga_3_minutos(vendedor, ana):
    fim = AGORA + JANELA_DE_PRORROGACAO - timedelta(seconds=1)  # faltam 2 min 59 s
    leilao = novo_leilao(vendedor, fim=fim)
    ana.darLance(leilao, VALOR("100.00"), AGORA)
    assert leilao.dataFimPrevista == fim + PRORROGACAO


def test_lance_com_exatamente_3_minutos_para_o_fim_nao_prorroga(vendedor, ana):
    fim = AGORA + JANELA_DE_PRORROGACAO
    leilao = novo_leilao(vendedor, fim=fim)
    ana.darLance(leilao, VALOR("100.00"), AGORA)
    assert leilao.dataFimPrevista == fim


def test_lance_longe_do_fim_nao_prorroga(leilao, ana):
    fim = leilao.dataFimPrevista
    ana.darLance(leilao, VALOR("100.00"), AGORA)
    assert leilao.dataFimPrevista == fim


def test_lance_recusado_nao_prorroga(vendedor, ana):
    fim = AGORA + timedelta(minutes=1)
    leilao = novo_leilao(vendedor, fim=fim)
    recusa(ana, leilao, "50.00")
    assert leilao.dataFimPrevista == fim


# ---------- RN03: lance irrevogável ----------

def test_lance_registrado_nao_pode_ser_alterado(leilao, ana):
    lance = ana.darLance(leilao, VALOR("100.00"), AGORA)
    with pytest.raises(dataclasses.FrozenInstanceError):
        lance.valor = VALOR("1.00")


def test_cliente_nao_reduz_o_proprio_lance(leilao, ana):
    ana.darLance(leilao, VALOR("150.00"), AGORA)
    assert recusa(ana, leilao, "120.00").motivo is MotivoRecusa.ABAIXO_DO_MINIMO
    assert [lance.valor for lance in leilao.lances] == [VALOR("150.00")]


def test_lance_aceito_entra_na_lista_do_leilao(leilao, ana, bruno):
    primeiro = ana.darLance(leilao, VALOR("100.00"), AGORA)
    segundo = bruno.darLance(leilao, VALOR("105.00"), AGORA + timedelta(seconds=1))
    assert leilao.lances == [primeiro, segundo]
    assert segundo.cliente is bruno and segundo.valor == VALOR("105.00")


# ---------- RN13: empate de valor, vale o registrado primeiro ----------

def test_empate_de_valor_vale_o_lance_registrado_primeiro(leilao, ana, bruno):
    depois = Lance(valor=VALOR("200.00"), dataHora=AGORA + timedelta(milliseconds=5), cliente=bruno)
    antes = Lance(valor=VALOR("200.00"), dataHora=AGORA + timedelta(milliseconds=4), cliente=ana)
    leilao.lances.extend([depois, antes])
    assert leilao.getMaiorLance() is antes


def test_segundo_lance_de_mesmo_valor_e_recusado(leilao, ana, bruno):
    ana.darLance(leilao, VALOR("200.00"), AGORA)
    assert recusa(bruno, leilao, "200.00", AGORA + timedelta(milliseconds=1)).motivo is MotivoRecusa.ABAIXO_DO_MINIMO
