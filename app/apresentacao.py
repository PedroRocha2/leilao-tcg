import re
import unicodedata
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.db import para_texto
from app.dominio.contas import Cliente
from app.dominio.cpf import mascarar_cpf
from app.dominio.dinheiro import formatar_numero, formatar_reais, para_centavos
from app.dominio.leiloes import Leilao, StatusLeilao

FUSO_DA_LOJA = ZoneInfo("America/Sao_Paulo")
_DETALHE_DA_FOTO = {"frente": "frente da carta", "arte": "detalhe da arte", "canto": "detalhe do canto inferior"}


def data(dia: date) -> str:
    return dia.strftime("%d/%m/%Y")


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


def licitantes(leilao: Leilao) -> dict[int, str]:
    rotulos: dict[int, str] = {}
    for lance in sorted(leilao.lances, key=lambda l: l.dataHora):
        rotulos.setdefault(lance.cliente.id, f"Licitante {len(rotulos) + 1}")
    return rotulos


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
        "rotulo_valor": "Lance atual" if maior else "Lance inicial",
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
        ("Status da carta", carta.status.capitalize()),
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
    return {
        **cartao(leilao, agora),
        "seu_maior": formatar_reais(max(lance.valor for lance in meus)),
        "seus_lances": len(meus),
        "atual": formatar_reais(maior.valor),
        "lidera": lidera,
        "posicao": ("Você lidera" if aberto else "Seu lance é o maior") if lidera else "Superado",
        "aberto": aberto,
        "situacao": situacao(leilao, agora),
        "fim_quando": quando_termina(leilao.dataFimPrevista, agora),
        "fim_iso": para_texto(leilao.dataFimPrevista),
    }


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
