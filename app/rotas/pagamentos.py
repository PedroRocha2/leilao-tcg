from flask import Blueprint, abort, current_app, request

from app.mercado_pago import GatewayIndisponivel
from app.pagamento import confirmar_pagamento
from app.repositorios.cobrancas import StatusCobranca
from app.rotas.comum import (agora, avisar_pagamento_confirmado, cobrancas, registrar_pagamento_no_gateway,
                             repositorios)

bp = Blueprint("pagamentos", __name__, url_prefix="/pagamentos")


@bp.post("/mercado-pago")
def notificacao():
    """Webhook do Mercado Pago: só vale a consulta à API, por isso dispensa CSRF e login."""
    gateway = current_app.config["GATEWAY"]
    if not gateway.externo:
        abort(404)
    corpo = request.get_json(silent=True)
    corpo = corpo if isinstance(corpo, dict) else {}
    dados = corpo.get("data") if isinstance(corpo.get("data"), dict) else {}
    tipo = corpo.get("type") or request.args.get("type") or request.args.get("topic")
    numero = str(dados.get("id") or request.args.get("data.id") or request.args.get("id") or "")
    if tipo != "payment" or not numero.isdigit():
        return "", 200

    clientes, leiloes = repositorios()
    try:
        cobranca = confirmar_pagamento(leiloes, clientes, cobrancas(), gateway, numero, agora())
    except GatewayIndisponivel as falha:
        # Resposta de erro: o Mercado Pago manda o aviso de novo mais tarde.
        current_app.logger.warning("Pagamento %s não conferido: %s", numero, falha)
        return "", 503
    if cobranca is not None:
        leilao = leiloes.por_id(cobranca.leilaoId)
        registrar_pagamento_no_gateway(cobranca, leilao, gateway)
        if cobranca.status == StatusCobranca.PAGA:
            avisar_pagamento_confirmado(leilao)
    return "", 200
