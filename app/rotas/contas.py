"""Criar conta, entrar e sair (RF01). A senha é conferida por Usuario.autenticar()."""

from functools import cache

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from app.apresentacao import FUSO_DA_LOJA
from app.cadastro import CadastroInvalido, criar_conta as cadastrar, normalizar_email
from app.dominio import senhas
from app.rotas.comum import agora, cliente_atual, destino_seguro, iniciar_sessao, repositorios

bp = Blueprint("contas", __name__)


@cache
def _hash_de_comparacao(iteracoes: int) -> str:
    """E-mail sem conta também calcula um hash: a resposta leva o mesmo tempo nos dois casos."""
    return senhas.gerar_hash("senha-que-nao-existe", iteracoes)


def _ja_logado():
    destino = destino_seguro(request.args.get("proximo"), url_for("minha_conta.perfil"))
    return redirect(destino) if cliente_atual() else None


@bp.route("/criar-conta", methods=["GET", "POST"])
def criar_conta():
    if (redirecionar := _ja_logado()) is not None:
        return redirecionar
    proximo = request.values.get("proximo", "")
    dados = {campo: request.form.get(campo, "") for campo in ("nome", "email", "telefone", "cpf")}
    erros: dict[str, str] = {}

    if request.method == "POST":
        clientes, _ = repositorios()
        try:
            novo = cadastrar(
                clientes, **dados,
                senha=request.form.get("senha", ""), confirmacao=request.form.get("confirmacao", ""),
                hoje=agora().astimezone(FUSO_DA_LOJA).date(),  # dataCadastro = agora
                iteracoes=current_app.config["PBKDF2_ITERACOES"],
            )
        except CadastroInvalido as invalido:
            erros = invalido.erros
        else:
            iniciar_sessao(novo)
            flash("Conta criada. Você já pode dar lances.", "sucesso")
            return redirect(destino_seguro(proximo, url_for("minha_conta.perfil")), code=303)

    return render_template("contas/criar_conta.html", dados=dados, erros=erros, proximo=proximo), (
        422 if erros else 200)


@bp.route("/entrar", methods=["GET", "POST"])
def entrar():
    if (redirecionar := _ja_logado()) is not None:
        return redirecionar
    proximo = request.values.get("proximo", "")
    email = normalizar_email(request.form.get("email"))
    erro = None

    if request.method == "POST":
        senha = request.form.get("senha", "")
        clientes, _ = repositorios()
        cliente = clientes.por_email(email) if email else None
        if cliente is not None and cliente.autenticar(senha):
            iniciar_sessao(cliente)
            return redirect(destino_seguro(proximo, url_for("leiloes.listar")), code=303)
        if cliente is None:
            senhas.conferir(senha, _hash_de_comparacao(current_app.config["PBKDF2_ITERACOES"]))
        erro = "E-mail ou senha incorretos. Confira os dois e tente de novo."

    return render_template("contas/entrar.html", email=email, erro=erro, proximo=proximo), (401 if erro else 200)


@bp.post("/sair")
def sair():
    session.clear()
    flash("Você saiu da sua conta.", "info")
    return redirect(url_for("leiloes.listar"), code=303)
