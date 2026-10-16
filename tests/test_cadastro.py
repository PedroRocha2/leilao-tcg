from datetime import date

import pytest

from apoio import ITERACOES_DE_TESTE, SENHA
from app.cadastro import CadastroInvalido, criar_conta
from app.repositorios import RepositorioClientes

HOJE = date(2026, 10, 14)


@pytest.fixture
def repositorio(banco):
    return RepositorioClientes(banco)


def cadastrar(repositorio, **campos):
    dados = {"nome": "Ana Souza", "email": "ana@teste.com", "telefone": "(48) 99123-4567",
             "cpf": "529.982.247-25", "senha": SENHA, "confirmacao": SENHA}
    dados.update(campos)
    return criar_conta(repositorio, **dados, hoje=HOJE, iteracoes=ITERACOES_DE_TESTE)


def erros_de(repositorio, **campos) -> dict:
    with pytest.raises(CadastroInvalido) as erro:
        cadastrar(repositorio, **campos)
    return erro.value.erros


def test_cria_cliente_com_os_valores_iniciais_do_enunciado(repositorio):
    cliente = cadastrar(repositorio, email="  Ana@Teste.com ")
    gravado = repositorio.por_id(cliente.id)
    assert gravado.dataCadastro == HOJE
    assert gravado.ativo is True
    assert gravado.bloqueado is False
    assert gravado.descumprimentos == 0
    assert gravado.email == "ana@teste.com"
    assert gravado.cpf == "52998224725"
    assert gravado.telefone == "48991234567"


def test_cria_a_carteira_com_saldo_zero_junto_com_o_cliente(repositorio, banco):
    cliente = cadastrar(repositorio)
    carteiras = banco.execute("SELECT saldo_centavos FROM carteiras WHERE cliente_id = ?", (cliente.id,)).fetchall()
    assert [linha["saldo_centavos"] for linha in carteiras] == [0]
    assert repositorio.por_id(cliente.id).carteira.saldo == 0


def test_grava_so_o_hash_da_senha(repositorio, banco):
    cliente = cadastrar(repositorio)
    hash_gravado = banco.execute("SELECT senha_hash FROM usuarios WHERE id = ?", (cliente.id,)).fetchone()[0]
    assert SENHA not in hash_gravado
    assert hash_gravado.startswith("pbkdf2_sha256$")
    assert repositorio.por_id(cliente.id).autenticar(SENHA)


def test_email_ja_cadastrado_e_recusado_sem_diferenciar_maiusculas(repositorio):
    cadastrar(repositorio)
    erros = erros_de(repositorio, email="ANA@teste.com", cpf="111.444.777-35")
    assert set(erros) == {"email"}


def test_cpf_ja_cadastrado_e_recusado_mesmo_com_outra_pontuacao(repositorio):
    cadastrar(repositorio)
    erros = erros_de(repositorio, email="outra@teste.com", cpf="52998224725")
    assert set(erros) == {"cpf"}


@pytest.mark.parametrize("cpf", ["529.982.247-24", "111.111.111-11", "123", "abc.def.ghi-jk"])
def test_cpf_com_digitos_verificadores_errados_e_recusado(repositorio, cpf):
    assert "não é válido" in erros_de(repositorio, cpf=cpf)["cpf"]


def test_senha_com_menos_de_8_caracteres_e_recusada(repositorio):
    erros = erros_de(repositorio, senha="1234567", confirmacao="1234567")
    assert set(erros) == {"senha"}


def test_senha_com_8_caracteres_e_aceita(repositorio):
    assert cadastrar(repositorio, senha="12345678", confirmacao="12345678").id is not None


def test_confirmacao_diferente_da_senha_e_recusada(repositorio):
    assert set(erros_de(repositorio, confirmacao=SENHA + "x")) == {"confirmacao"}


def test_campos_obrigatorios_vazios(repositorio):
    erros = erros_de(repositorio, nome=" ", email="", telefone="", cpf="", senha="", confirmacao="")
    assert set(erros) == {"nome", "email", "telefone", "cpf", "senha"}


@pytest.mark.parametrize("email", ["ana", "ana@", "ana@teste", "ana teste@x.com"])
def test_email_mal_formado(repositorio, email):
    assert "email" in erros_de(repositorio, email=email)


@pytest.mark.parametrize("telefone", ["9912-3456", "(48) 99123-45678"])
def test_telefone_precisa_de_ddd_e_numero(repositorio, telefone):
    assert "telefone" in erros_de(repositorio, telefone=telefone)


def test_cadastro_recusado_nao_grava_nada(repositorio, banco):
    antes = banco.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    erros_de(repositorio, cpf="529.982.247-24")
    assert banco.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == antes
