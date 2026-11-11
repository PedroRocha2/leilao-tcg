from functools import cache

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from app.apresentacao import FUSO_DA_LOJA
from app.cadastro import CadastroInvalido, criar_conta as cadastrar, normalizar_email
from app.dominio import senhas
from app.dominio.contas import Administrador
from app.rotas.comum import (administrador_atual, agora, destino_seguro, iniciar_sessao, registrar_operacao,
                             repositorios, usuario_atual)

bp = Blueprint("contas", __name__)


@cache
def _hash_de_comparacao(iteracoes: int) -> str:
    return senhas.gerar_hash("senha-que-nao-existe", iteracoes)


def _ja_logado():
    if administrador_atual() is not None:
        return redirect(url_for("admin.leiloes"))
    destino = destino_seguro(request.args.get("proximo"), url_for("minha_conta.perfil"))
    return redirect(destino) if usuario_atual() else None


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
                hoje=agora().astimezone(FUSO_DA_LOJA).date(),
                iteracoes=current_app.config["PBKDF2_ITERACOES"],
            )
        except CadastroInvalido as invalido:
            erros = invalido.erros
        else:
            iniciar_sessao(novo)
            registrar_operacao("cadastro de cliente")
            flash("Conta criada. Você já pode dar lances.", "sucesso")
            return redirect(destino_seguro(proximo, url_for("minha_conta.perfil")), code=303)

    return render_template("contas/criar_conta.html", dados=dados, erros=erros, proximo=proximo), (
        422 if erros else 200)


@bp.route("/entrar", methods=["GET", "POST"])
def entrar():
    if (redirecionar := _ja_logado()) is not None:
        return redirecionar
    proximo = request.values.get("proximo", "")
    login = normalizar_email(request.form.get("email"))
    erro = None

    if request.method == "POST":
        senha = request.form.get("senha", "")
        clientes, _ = repositorios()
        usuario = clientes.usuario_por_login(login) if login else None
        if usuario is not None and usuario.autenticar(senha):
            iniciar_sessao(usuario)
            registrar_operacao("login")
            if isinstance(usuario, Administrador):
                return redirect(url_for("admin.leiloes"), code=303)
            return redirect(destino_seguro(proximo, url_for("leiloes.listar")), code=303)
        if usuario is None:
            senhas.conferir(senha, _hash_de_comparacao(current_app.config["PBKDF2_ITERACOES"]))
        erro = "E-mail ou senha incorretos. Confira os dois e tente de novo."

    return render_template("contas/entrar.html", email=login, erro=erro, proximo=proximo), (401 if erro else 200)


@bp.post("/sair")
def sair():
    if usuario_atual() is not None:
        registrar_operacao("logout")
    session.clear()
    flash("Você saiu da sua conta.", "info")
    return redirect(url_for("leiloes.listar"), code=303)
