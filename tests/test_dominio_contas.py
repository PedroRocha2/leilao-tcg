"""Usuario (abstrata), Cliente, Carteira e as peças de cadastro: CPF e hash de senha."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from apoio import ITERACOES_DE_TESTE, SENHA, novo_cliente
from app.dominio import senhas
from app.dominio.contas import Usuario
from app.dominio.cpf import completar_cpf, cpf_valido, formatar_cpf, mascarar_cpf
from app.dominio.financeiro import Carteira, MovimentacaoCarteira


# ---------- Usuario e Cliente ----------

def test_usuario_e_abstrata():
    with pytest.raises(TypeError, match="abstrata"):
        Usuario(nome="Ana", email="ana@x.com", senhaHash="!", telefone="48", dataCadastro=date.today())


def test_cliente_novo_nasce_ativo_sem_bloqueio_e_com_carteira_zerada():
    cliente = novo_cliente(1)
    assert isinstance(cliente, Usuario)
    assert cliente.ativo is True
    assert cliente.bloqueado is False
    assert cliente.descumprimentos == 0
    assert cliente.carteira.saldo == Decimal("0.00")


def test_cada_cliente_tem_a_propria_carteira():
    assert novo_cliente(1).carteira is not novo_cliente(2).carteira


def test_autenticar_com_a_senha_certa():
    assert novo_cliente(1).autenticar(SENHA) is True


@pytest.mark.parametrize("senha", ["errada", "", SENHA.upper(), SENHA + " "])
def test_autenticar_com_senha_errada(senha):
    assert novo_cliente(1).autenticar(senha) is False


def test_conta_desativada_nao_autentica():
    assert novo_cliente(1, ativo=False).autenticar(SENHA) is False


# ---------- senhaHash ----------

def test_hash_nao_contem_a_senha_e_tem_salt():
    primeiro = senhas.gerar_hash(SENHA, ITERACOES_DE_TESTE)
    segundo = senhas.gerar_hash(SENHA, ITERACOES_DE_TESTE)
    assert SENHA not in primeiro
    assert primeiro != segundo  # salt diferente a cada hash
    assert primeiro.startswith(f"pbkdf2_sha256${ITERACOES_DE_TESTE}$")
    assert senhas.conferir(SENHA, primeiro) and senhas.conferir(SENHA, segundo)


@pytest.mark.parametrize("hash_", ["", "!abc", "md5$1$x$y", "pbkdf2_sha256$x$y$z", "pbkdf2_sha256$10$@@$@@"])
def test_hash_em_formato_desconhecido_nunca_confere(hash_):
    assert senhas.conferir(SENHA, hash_) is False


def test_senha_inutilizavel_nao_confere_com_nada():
    assert senhas.conferir("", senhas.senha_inutilizavel()) is False


# ---------- CPF ----------

@pytest.mark.parametrize("cpf", ["529.982.247-25", "52998224725", " 529 982 247 25 ", "111.444.777-35"])
def test_cpf_valido(cpf):
    assert cpf_valido(cpf)


@pytest.mark.parametrize("cpf", [
    "529.982.247-24",  # segundo dígito errado
    "529.982.247-15",  # primeiro dígito errado
    "111.111.111-11",  # todos iguais passam no cálculo, mas não são CPF
    "000.000.000-00",
    "5299822472",      # 10 dígitos
    "529982247255",    # 12 dígitos
    "529a982b247c25",  # letras no meio
    "",
    None,
])
def test_cpf_invalido(cpf):
    assert not cpf_valido(cpf)


def test_completar_cpf_gera_os_digitos_verificadores():
    assert completar_cpf("529982247") == "52998224725"
    assert cpf_valido(completar_cpf("123456789"))


def test_formatar_e_mascarar_cpf():
    assert formatar_cpf("52998224725") == "529.982.247-25"
    assert mascarar_cpf("52998224725") == "***.982.247-**"


# ---------- Carteira e MovimentacaoCarteira (consulta) ----------

def test_gerar_extrato_mostra_da_movimentacao_mais_recente_para_a_mais_antiga():
    agora = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
    antiga = MovimentacaoCarteira("credito", Decimal("50.00"), agora - timedelta(days=2), "Repasse")
    recente = MovimentacaoCarteira("debito", Decimal("-20.00"), agora, "Pagamento")
    carteira = Carteira(saldo=Decimal("30.00"), movimentacoes=[antiga, recente])
    assert carteira.gerarExtrato() == [recente, antiga]


def test_extrato_de_carteira_nova_e_vazio():
    assert Carteira().gerarExtrato() == []
