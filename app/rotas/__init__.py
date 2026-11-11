from flask import abort, jsonify, render_template, request

from app.db import para_texto
from app.andamento import encerrar_leiloes_vencidos, expirar_pagamentos, iniciar_leiloes_aprovados
from app.apresentacao import data, data_hora, percentual
from app.dominio.cpf import formatar_cpf
from app.dominio.dinheiro import formatar_reais
from app.rotas.comum import (administrador_atual, agora, busca_do_topo, caminho_atual, cliente_atual, csrf_valido,
                             loja, quer_json, repositorios, token_csrf, url_da_foto)

# Pedidos de imagem não leem leilões: não precisam conferir o relógio.
_SO_ARQUIVOS = ("static", "leiloes.foto", "anuncios.miniatura")


def registrar(app) -> None:
    from app.rotas.admin import bp as admin
    from app.rotas.anuncios import bp as anuncios
    from app.rotas.contas import bp as contas
    from app.rotas.leiloes import bp as leiloes
    from app.rotas.minha_conta import bp as minha_conta

    app.register_blueprint(leiloes)
    app.register_blueprint(contas)
    app.register_blueprint(minha_conta)
    app.register_blueprint(anuncios)
    app.register_blueprint(admin)
    app.add_template_global(url_da_foto)
    for nome, filtro in (("reais", formatar_reais), ("data_hora", data_hora), ("data", data),
                         ("cpf", formatar_cpf), ("percentual", percentual)):
        app.add_template_filter(filtro, nome)

    @app.before_request
    def verificar_csrf():
        if request.method == "POST" and not csrf_valido():
            mensagem = "Sua sessão expirou. Recarregue a página e tente de novo."
            if quer_json():
                return jsonify(ok=False, mensagem=mensagem), 400
            abort(400, mensagem)

    @app.before_request
    def atualizar_leiloes():
        if request.endpoint in _SO_ARQUIVOS:
            return
        clientes, leiloes = repositorios()
        momento, registro = agora(), loja()
        # RF19: o que o sistema faz sozinho também entra no log, sem usuário e sem IP.
        for leilao in iniciar_leiloes_aprovados(leiloes, momento):
            registro.registrar("início automático de leilão", momento, detalhe=f"leilão {leilao.id}")
        for leilao in encerrar_leiloes_vencidos(leiloes, momento, registro.configuracao().prazoDePagamento):
            arremate = leilao.transacao
            registro.registrar("encerramento automático de leilão", momento,
                               valor=arremate.valor if arremate else None,
                               detalhe=f"leilão {leilao.id}: " + ("arrematado" if arremate else "sem lances"))
        for leilao in expirar_pagamentos(leiloes, clientes, momento):
            registro.registrar("prazo de pagamento expirado", momento, leilao.transacao.comprador.id,
                               leilao.transacao.valor, detalhe=f"leilão {leilao.id}: descumprimento registrado")

    @app.context_processor
    def contexto_comum():
        return {
            "cliente": cliente_atual(),
            "administrador": administrador_atual(),
            "csrf_token": token_csrf(),
            "agora_iso": para_texto(agora()),
            "caminho_atual": caminho_atual(),
            "busca": busca_do_topo(),
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
