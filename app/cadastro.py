import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date

from app.dominio import senhas
from app.dominio.contas import Cliente
from app.dominio.cpf import cpf_valido, somente_digitos
from app.repositorios.clientes import RepositorioClientes

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class CadastroInvalido(Exception):
    erros: dict[str, str] = field(default_factory=dict)


def normalizar_email(email: str | None) -> str:
    return (email or "").strip().lower()


def criar_conta(repositorio: RepositorioClientes, *, nome: str, email: str, telefone: str, cpf: str,
                senha: str, confirmacao: str, hoje: date, iteracoes: int) -> Cliente:
    nome = " ".join((nome or "").split())
    email = normalizar_email(email)
    telefone = somente_digitos(telefone)
    erros: dict[str, str] = {}

    if not nome:
        erros["nome"] = "Informe seu nome."
    elif len(nome) > 120:
        erros["nome"] = "Use no máximo 120 caracteres."

    if not email:
        erros["email"] = "Informe seu e-mail."
    elif not _EMAIL.match(email) or len(email) > 254:
        erros["email"] = "Informe um e-mail válido, como nome@provedor.com."
    elif repositorio.email_em_uso(email):
        erros["email"] = "Este e-mail já tem uma conta. Entre com ele ou use outro."

    if not telefone:
        erros["telefone"] = "Informe seu telefone com DDD."
    elif len(telefone) not in (10, 11):
        erros["telefone"] = "Use o DDD e o número: 10 ou 11 dígitos, como (48) 99123-4567."

    if not (cpf or "").strip():
        erros["cpf"] = "Informe seu CPF."
    elif not cpf_valido(cpf):
        erros["cpf"] = "Este CPF não é válido. Confira os 11 dígitos."
    elif repositorio.cpf_em_uso(somente_digitos(cpf)):
        erros["cpf"] = "Este CPF já tem uma conta."

    if len(senha or "") < senhas.TAMANHO_MINIMO:
        erros["senha"] = f"A senha precisa ter pelo menos {senhas.TAMANHO_MINIMO} caracteres."
    if (confirmacao or "") != (senha or ""):
        erros["confirmacao"] = "A confirmação não é igual à senha."

    if erros:
        raise CadastroInvalido(erros)

    cliente = Cliente(
        nome=nome, email=email, telefone=telefone, cpf=somente_digitos(cpf),
        senhaHash=senhas.gerar_hash(senha, iteracoes), dataCadastro=hoje,
    )
    try:
        return repositorio.adicionar(cliente)
    except sqlite3.IntegrityError as erro:
        # Outro cadastro com o mesmo e-mail ou CPF entrou entre a verificação e a gravação.
        campo = "cpf" if "cpf" in str(erro) else "email"
        mensagem = "Este CPF já tem uma conta." if campo == "cpf" else "Este e-mail já tem uma conta."
        raise CadastroInvalido({campo: mensagem}) from erro
