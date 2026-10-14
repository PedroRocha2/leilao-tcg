"""Rotas: leilões (ver e dar lance), contas (criar, entrar, sair) e Minha Conta."""

from flask import abort, jsonify, render_template, request

from app.db import para_texto
from app.rotas.comum import agora, caminho_atual, cliente_atual, csrf_valido, quer_json, token_csrf


def registrar(app) -> None:
    from app.rotas.contas import bp as contas
    from app.rotas.leiloes import bp as leiloes
    from app.rotas.minha_conta import bp as minha_conta

    app.register_blueprint(leiloes)
    app.register_blueprint(contas)
    app.register_blueprint(minha_conta)

    @app.before_request
    def verificar_csrf():
        if request.method == "POST" and not csrf_valido():
            mensagem = "Sua sessão expirou. Recarregue a página e tente de novo."
            if quer_json():
                return jsonify(ok=False, mensagem=mensagem), 400
            abort(400, mensagem)

    @app.context_processor
    def contexto_comum():
        return {
            "cliente": cliente_atual(),
            "csrf_token": token_csrf(),
            "agora_iso": para_texto(agora()),
            "caminho_atual": caminho_atual(),
        }

    @app.errorhandler(404)
    def nao_encontrado(_erro):
        return render_template("erro.html", titulo="Página não encontrada",
                               texto="O endereço não corresponde a nenhuma página do Leilão TCG."), 404

    @app.errorhandler(400)
    def requisicao_invalida(erro):
        return render_template("erro.html", titulo="Não foi possível concluir", texto=erro.description), 400

    @app.errorhandler(405)
    def metodo_nao_permitido(_erro):
        return render_template("erro.html", titulo="Ação não disponível por este endereço",
                               texto="Use os botões da página para fazer esta ação."), 405
