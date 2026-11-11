import re
import unicodedata
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.db import para_texto
from app.dominio.contas import Cliente
from app.dominio.cpf import mascarar_cpf
from app.dominio.dinheiro import NBSP, formatar_numero, formatar_reais, para_centavos
from app.dominio.financeiro import StatusTransacao
from app.dominio.leiloes import Carta, Leilao, StatusCarta, StatusLeilao

FUSO_DA_LOJA = ZoneInfo("America/Sao_Paulo")
_DETALHE_DA_FOTO = {"frente": "frente da carta", "arte": "detalhe da arte", "canto": "detalhe do canto inferior"}
# RF14: como o vendedor lê o status de cada carta.
_SITUACAO_DA_CARTA = {StatusCarta.APROVADA: "Aprovada (aguardando início)",
                      StatusCarta.ARREMATADA: "Arrematada (aguardando pagamento)",
                      StatusCarta.PAGA: "Paga (aguardando retirada)",
                      StatusCarta.ENTREGUE: "Entregue (repasse efetuado)"}
_SITUACAO_DO_ARREMATE = {StatusTransacao.PAGO: "Pago, aguardando retirada",
                         StatusTransacao.NAO_PAGA: "Não pago no prazo"}
# As moedas em que os catálogos de cartas informam o preço.
_MOEDAS = {"USD": ("US$", "dólares"), "EUR": ("€", "euros")}


def data(dia: date) -> str:
    return dia.strftime("%d/%m/%Y")


def percentual(valor) -> str:
    return f"{formatar_numero(valor)}%"


def data_hora(momento: datetime) -> str:
    return momento.astimezone(FUSO_DA_LOJA).strftime("%d/%m/%Y %H:%M:%S")


def data_hora_curta(momento: datetime) -> str:
    return momento.astimezone(FUSO_DA_LOJA).strftime("%d/%m %H:%M")


def quando_termina(momento: datetime, agora: datetime) -> str:
    local, hoje = momento.astimezone(FUSO_DA_LOJA), agora.astimezone(FUSO_DA_LOJA).date()
    hora = local.strftime("%H:%M")
    dias = (local.date() - hoje).days
    if dias == 0:
        return f"hoje às {hora}"
    if dias == 1:
        return f"amanhã às {hora}"
    if local.year != hoje.year:
        return f"{local.strftime('%d/%m/%Y')} às {hora}"
    return f"{local.strftime('%d/%m')} às {hora}"


def tempo_restante(momento: datetime, agora: datetime) -> str:
    segundos = max(0, int((momento - agora).total_seconds()))
    dias, resto = divmod(segundos, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, segundos = divmod(resto, 60)
    if dias:
        return f"{dias} d {horas} h {minutos} min"
    if horas:
        return f"{horas} h {minutos:02d} min"
    return f"{minutos} min {segundos:02d} s"


def slug(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


def descricao_da_foto(leilao: Leilao, url: str, posicao: int) -> str:
    carta = leilao.carta
    tipo = url.rsplit("/", 1)[-1].rsplit(".", 1)[0].rsplit("-", 1)[-1]
    detalhe = _DETALHE_DA_FOTO.get(tipo, f"foto {posicao}")
    return f"{carta.nome}, {carta.edicao}: {detalhe}"


def situacao(leilao: Leilao, agora: datetime) -> str:
    if leilao.status == StatusLeilao.CANCELADO:
        return "Cancelado"
    if leilao.status == StatusLeilao.PENDENTE:
        return "Aguardando aprovação"
    if leilao.status == StatusLeilao.ENCERRADO or agora >= leilao.dataFimPrevista:
        return "Encerrado"
    if leilao.status == StatusLeilao.APROVADO or agora < leilao.dataInicio:
        return "Agendado"
    return "Ativo"


def situacao_da_carta(carta: Carta) -> str:
    return _SITUACAO_DA_CARTA.get(carta.status, carta.status.capitalize())


def licitantes(leilao: Leilao) -> dict[int, str]:
    rotulos: dict[int, str] = {}
    for lance in sorted(leilao.lances, key=lambda l: l.dataHora):
        rotulos.setdefault(lance.cliente.id, f"Licitante {len(rotulos) + 1}")
    return rotulos


def resultado(leilao: Leilao, cliente: Cliente | None) -> str | None:
    if leilao.status != StatusLeilao.ENCERRADO:
        return None
    arremate = leilao.transacao
    if arremate is None:
        return None if leilao.lances else "Leilão encerrado sem lances. A carta não foi arrematada."
    voce = cliente is not None and arremate.comprador.ehOMesmo(cliente)
    quem = "Você" if voce else licitantes(leilao)[arremate.comprador.id]
    return f"{quem} arrematou esta carta por {formatar_reais(arremate.valor)}."


def nao_iniciado(leilao: Leilao, agora: datetime) -> bool:
    return (leilao.status in (StatusLeilao.PENDENTE, StatusLeilao.APROVADO)
            or (leilao.status == StatusLeilao.ATIVO and agora < leilao.dataInicio))


def aviso(leilao: Leilao, agora: datetime, cliente: Cliente | None) -> str:
    """O que o painel diz quando o leilão não está recebendo lances."""
    if leilao.status == StatusLeilao.PENDENTE:
        return "Este leilão ainda não começou: aguarda o depósito da carta na loja e a aprovação."
    if nao_iniciado(leilao, agora):
        return f"Este leilão começa em {data_hora(leilao.dataInicio)}."
    return resultado(leilao, cliente) or "Este leilão não recebe mais lances."


def cartao(leilao: Leilao, agora: datetime) -> dict:
    maior = leilao.getMaiorLance()
    carta = leilao.carta
    return {
        "id": leilao.id,
        "nome": carta.nome,
        "edicao": carta.edicao,
        "foto": carta.fotos[0] if carta.fotos else None,
        "rotulo_valor": "Lance atual" if maior else "Lance inicial",
        "valor": formatar_reais(maior.valor if maior else leilao.lanceInicial),
        "fim_iso": para_texto(leilao.dataFimPrevista),
        "restante": tempo_restante(leilao.dataFimPrevista, agora),
    }


def estado(leilao: Leilao, agora: datetime, cliente: Cliente | None) -> dict:
    maior = leilao.getMaiorLance()
    minimo = leilao.calcularLanceMinimo()
    arremate = leilao.transacao
    rotulos = licitantes(leilao)
    ordenados = sorted(leilao.lances, key=lambda l: (-l.valor, l.dataHora))
    linhas = [
        {
            "quem": "Você" if cliente and lance.cliente.ehOMesmo(cliente) else rotulos[lance.cliente.id],
            "seu": bool(cliente and lance.cliente.ehOMesmo(cliente)),
            "maior": lance is maior,
            "valor": formatar_reais(lance.valor),
            "iso": para_texto(lance.dataHora),
            "quando": data_hora(lance.dataHora),
            "quando_curto": data_hora_curta(lance.dataHora),
        }
        for lance in ordenados
    ]
    valor = maior.valor if maior else leilao.lanceInicial
    return {
        "id": leilao.id,
        "aberto": leilao.estaAberto(agora),
        "situacao": situacao(leilao, agora),
        "tem_lances": maior is not None,
        "arrematado": arremate is not None,
        "voce_arrematou": bool(cliente and arremate and arremate.comprador.ehOMesmo(cliente)),
        "resultado": resultado(leilao, cliente),
        "aviso": aviso(leilao, agora, cliente),
        "nao_iniciado": nao_iniciado(leilao, agora),
        "inicio_data_hora": data_hora(leilao.dataInicio),
        "rotulo_valor": "Valor do arremate" if arremate else "Lance atual" if maior else "Lance inicial",
        "valor": formatar_reais(valor),
        "valor_centavos": para_centavos(valor),
        "lance_inicial": formatar_reais(leilao.lanceInicial),
        "lance_inicial_centavos": para_centavos(leilao.lanceInicial),
        "incremento": formatar_reais(leilao.incrementoMinimo),
        "total_lances": len(leilao.lances),
        "minimo": formatar_reais(minimo),
        "minimo_centavos": para_centavos(minimo),
        "minimo_numero": formatar_numero(minimo),
        "fim_iso": para_texto(leilao.dataFimPrevista),
        "fim_quando": quando_termina(leilao.dataFimPrevista, agora),
        "fim_data_hora": data_hora(leilao.dataFimPrevista),
        "restante": tempo_restante(leilao.dataFimPrevista, agora),
        "voce_lidera": bool(cliente and maior and maior.cliente.ehOMesmo(cliente)),
        "proprio": bool(cliente and leilao.carta.vendedor.ehOMesmo(cliente)),
        "pode_dar_lance": bool(cliente and cliente.podeDarLance()),
        "linhas": linhas,
    }


def ficha(leilao: Leilao, agora: datetime) -> list[tuple[str, str]]:
    carta = leilao.carta
    itens = [
        ("Jogo", carta.jogo.nome),
        ("Edição", carta.edicao),
        ("Condição", carta.condicao),
        ("Status da carta", situacao_da_carta(carta)),
        ("Fotos", str(len(carta.fotos))),
        ("Lance inicial", formatar_reais(leilao.lanceInicial)),
        ("Incremento mínimo", formatar_reais(leilao.incrementoMinimo)),
        ("Início", data_hora(leilao.dataInicio)),
        ("Fim previsto", data_hora(leilao.dataFimPrevista)),
    ]
    if leilao.dataFimReal:
        itens.append(("Fim real", data_hora(leilao.dataFimReal)))
    itens += [("Status do leilão", situacao(leilao, agora)), ("Lances", str(len(leilao.lances)))]
    return itens


def meu_lance(leilao: Leilao, cliente: Cliente, agora: datetime) -> dict:
    meus = [lance for lance in leilao.lances if lance.cliente.ehOMesmo(cliente)]
    maior = leilao.getMaiorLance()
    aberto = leilao.estaAberto(agora)
    lidera = maior is not None and maior.cliente.ehOMesmo(cliente)
    if leilao.transacao is not None and leilao.transacao.comprador.ehOMesmo(cliente):
        posicao = "Você arrematou"
    elif lidera:
        posicao = "Você lidera" if aberto else "Seu lance é o maior"
    else:
        posicao = "Superado"
    return {
        **cartao(leilao, agora),
        "seu_maior": formatar_reais(max(lance.valor for lance in meus)),
        "seus_lances": len(meus),
        "atual": formatar_reais(maior.valor),
        "lidera": lidera,
        "posicao": posicao,
        "aberto": aberto,
        "situacao": situacao(leilao, agora),
        "fim_quando": quando_termina(leilao.dataFimPrevista, agora),
        "fim_iso": para_texto(leilao.dataFimPrevista),
    }


def arremate(leilao: Leilao, agora: datetime) -> dict:
    """O arremate para quem comprou: quanto deve, até quando paga e o código para retirar a carta (RF10)."""
    carta, transacao = leilao.carta, leilao.transacao
    aguardando = transacao.status == StatusTransacao.AGUARDANDO_PAGAMENTO
    return {
        "id": leilao.id,
        "nome": carta.nome,
        "edicao": carta.edicao,
        "foto": carta.fotos[0] if carta.fotos else None,
        "valor": formatar_reais(transacao.valor),
        "quando": data_hora(transacao.dataHora),
        "situacao": _SITUACAO_DO_ARREMATE.get(transacao.status, transacao.status.capitalize()),
        "prazo": data_hora(transacao.prazoPagamento),
        "pode_pagar": aguardando and agora < transacao.prazoPagamento,
        # O código só serve para retirar a carta paga; depois da entrega ou do prazo perdido, some.
        "codigo": transacao.codigoRetirada if aguardando or transacao.status == StatusTransacao.PAGO else None,
        "entregue_em": data_hora(transacao.dataEntrega) if transacao.dataEntrega else None,
    }


def anuncio(leilao: Leilao, agora: datetime) -> dict:
    """Uma carta do vendedor na lista de Vender, com o status do RF14."""
    carta, maior = leilao.carta, leilao.getMaiorLance()
    if leilao.transacao is not None:
        rotulo, valor = "Valor do arremate", formatar_reais(leilao.transacao.valor)
    else:
        rotulo, valor = "Maior lance", formatar_reais(maior.valor) if maior else "Nenhum lance"
    return {
        "id": leilao.id,
        "nome": carta.nome,
        "edicao": carta.edicao,
        "foto": carta.fotos[0] if carta.fotos else None,
        "situacao": situacao_da_carta(carta),
        "motivo_recusa": leilao.motivoRecusa,
        "liquido": formatar_reais(leilao.transacao.valorLiquido) if leilao.transacao else None,
        "em_andamento": leilao.estaAberto(agora),
        "lance_inicial": formatar_reais(leilao.lanceInicial),
        "rotulo_valor": rotulo,
        "valor": valor,
        "inicio": quando_termina(leilao.dataInicio, agora),
        "fim": quando_termina(leilao.dataFimPrevista, agora),
    }


def preco_de_mercado(preco) -> dict | None:
    """O valor médio da carta no mercado, para o vendedor ter uma referência ao definir o lance mínimo inicial."""
    if preco is None:
        return None
    simbolo, moeda = _MOEDAS[preco.moeda]
    return {"valor": f"{simbolo}{NBSP}{formatar_numero(preco.valor)}", "moeda": moeda, "fonte": preco.fonte}


def descricao_sugerida(especificacoes: tuple[tuple[str, str], ...]) -> str:
    """As especificações do catálogo em uma frase, para o vendedor completar com o estado da carta."""
    return "; ".join(f"{rotulo}: {valor}" for rotulo, valor in especificacoes) + "." if especificacoes else ""


def perfil(cliente: Cliente) -> list[tuple[str, str]]:
    telefone = cliente.telefone
    telefone = (f"({telefone[:2]}) {telefone[2:-4]}-{telefone[-4:]}" if len(telefone) in (10, 11)
                else telefone)
    if not cliente.ativo:
        conta = "Desativada"
    elif cliente.bloqueado:
        conta = "Bloqueada para lances"
    else:
        conta = "Ativa, liberada para lances"
    return [
        ("Nome", cliente.nome),
        ("E-mail", cliente.email),
        ("Telefone", telefone),
        ("CPF", mascarar_cpf(cliente.cpf)),
        ("Cliente desde", data(cliente.dataCadastro)),
        ("Situação da conta", conta),
        ("Descumprimentos", str(cliente.descumprimentos)),
    ]
