"""Casos de uso do lojista (RN14)."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.anuncio import apagar_fotos
from app.cadastro import conferir_contato
from app.db import transacao
from app.dominio.contas import Cliente
from app.dominio.dinheiro import ValorMonetarioInvalido, ler_reais
from app.dominio.financeiro import OperacaoRecusada, Saque, StatusSaque, StatusTransacao
from app.dominio.leiloes import CONDICOES, Leilao, StatusCarta, StatusLeilao
from app.dominio.loja import ConfiguracaoLoja
from app.repositorios import RepositorioClientes, RepositorioLeiloes, RepositorioLoja


@dataclass
class DadosInvalidos(Exception):
    erros: dict[str, str] = field(default_factory=dict)


def _leilao(leiloes: RepositorioLeiloes, numero: int) -> Leilao:
    leilao = leiloes.por_id(numero)
    if leilao is None:
        raise OperacaoRecusada(f"Não existe leilão {numero}.")
    return leilao


def aprovar_leilao(leiloes: RepositorioLeiloes, numero: int, agora: datetime) -> Leilao:
    """RF05: registra o depósito e aprova; se o início já chegou, o leilão começa."""
    with transacao(leiloes.conexao, imediata=True):
        leilao = _leilao(leiloes, numero)
        try:
            leilao.aprovar(agora)
            if leilao.dataInicio <= agora:
                leilao.iniciar(agora)
        except ValueError as erro:
            raise OperacaoRecusada(str(erro)) from erro
        leiloes.salvar_status(leilao)
    return leilao


def recusar_leilao(leiloes: RepositorioLeiloes, numero: int, motivo: str) -> Leilao:
    """RF05: recusa o leilão com o motivo, que o vendedor vê."""
    with transacao(leiloes.conexao, imediata=True):
        leilao = _leilao(leiloes, numero)
        try:
            leilao.recusar(motivo)
        except ValueError as erro:
            raise OperacaoRecusada(str(erro)) from erro
        leiloes.salvar_status(leilao)
    return leilao


def atualizar_cliente(clientes: RepositorioClientes, cliente: Cliente, nome: str, email: str,
                      telefone: str) -> Cliente:
    """RF02."""
    dados, erros = conferir_contato(clientes, nome, email, telefone, exceto=cliente.id)
    if erros:
        raise DadosInvalidos(erros)
    cliente.nome, cliente.email, cliente.telefone = dados["nome"], dados["email"], dados["telefone"]
    clientes.atualizar(cliente)
    return cliente


def definir_bloqueio(clientes: RepositorioClientes, cliente: Cliente, bloqueado: bool) -> Cliente:
    """RF02: conta bloqueada não dá lances nem cria leilões (RN15)."""
    cliente.bloqueado = bloqueado
    clientes.atualizar(cliente)
    return cliente


def atualizar_carta(leiloes: RepositorioLeiloes, leilao: Leilao, nome: str, jogo_id: str, edicao: str,
                    condicao: str) -> Leilao:
    """RF04."""
    nome, edicao = " ".join((nome or "").split()), " ".join((edicao or "").split())
    jogo = next((j for j in leiloes.jogos() if str(j.id) == str(jogo_id)), None)
    erros: dict[str, str] = {}
    if not nome:
        erros["nome"] = "Informe o nome da carta."
    if jogo is None:
        erros["jogo"] = "Escolha o jogo da carta."
    if not edicao:
        erros["edicao"] = "Informe a edição da carta."
    if condicao not in CONDICOES:
        erros["condicao"] = "Escolha a condição da carta."
    if erros:
        raise DadosInvalidos(erros)
    carta = leilao.carta
    carta.nome, carta.jogo, carta.edicao, carta.condicao = nome, jogo, edicao, condicao
    leiloes.salvar_carta(carta)
    return leilao


def pode_remover(leilao: Leilao) -> bool:
    """Só sem lances: lances são irrevogáveis (RN03)."""
    return leilao.status in (StatusLeilao.PENDENTE, StatusLeilao.CANCELADO) and not leilao.lances


def remover_carta(leiloes: RepositorioLeiloes, leilao: Leilao, pasta_de_fotos: Path) -> None:
    """RF04: remove o cadastro inválido, com leilão e fotos."""
    if not pode_remover(leilao):
        raise OperacaoRecusada(
            "Só dá para remover a carta cujo leilão ainda aguarda aprovação, foi recusado ou foi cancelado.")
    leiloes.remover(leilao)
    apagar_fotos(leilao.carta, pasta_de_fotos)


def configurar_loja(loja: RepositorioLoja, taxa: str, incremento: str, prazo_pagamento: str,
                    prazo_reoferta: str) -> ConfiguracaoLoja:
    """RF15: taxa e incremento só valem para leilões novos (RN17)."""
    erros: dict[str, str] = {}
    valores: dict[str, object] = {}
    try:
        valores["taxaPercentual"] = Decimal((taxa or "").strip().replace("%", "").replace(",", "."))
        if not Decimal("0") <= valores["taxaPercentual"] < Decimal("100"):
            raise InvalidOperation
    except InvalidOperation:
        erros["taxa"] = "Informe a taxa em porcentagem, de 0 a menos de 100, como 10 ou 12,5."
    try:
        valores["incrementoMinimo"] = ler_reais(incremento)
        if valores["incrementoMinimo"] <= 0:
            erros["incremento"] = "O incremento mínimo precisa ser maior que zero."
    except ValorMonetarioInvalido:
        erros["incremento"] = "Informe o incremento mínimo em reais, como 5,00."
    for campo, atributo, texto in (("prazo_pagamento", "prazoPagamentoHoras", prazo_pagamento),
                                   ("prazo_reoferta", "prazoReofertaHoras", prazo_reoferta)):
        if (texto or "").strip().isdigit() and 1 <= int(texto) <= 720:
            valores[atributo] = int(texto)
        else:
            erros[campo] = "Informe o prazo em horas inteiras, de 1 a 720."
    if erros:
        raise DadosInvalidos(erros)
    configuracao = ConfiguracaoLoja(**valores)
    loja.salvar_configuracao(configuracao)
    return configuracao


def registrar_entrega(leiloes: RepositorioLeiloes, clientes: RepositorioClientes, numero: int, codigo: str,
                      agora: datetime) -> Leilao:
    """RF12: entrega com o código de retirada e a transação paga (RN07); o repasse só acontece aqui (RN08)."""
    if not (codigo or "").strip():
        raise OperacaoRecusada("Informe o código de retirada que o comprador apresentou.")
    with transacao(leiloes.conexao, imediata=True):
        leilao = _leilao(leiloes, numero)
        arremate = leilao.transacao
        if arremate is None:
            raise OperacaoRecusada(f"O leilão {numero} não tem arremate.")
        arremate.registrarEntrega(codigo, agora)
        leilao.carta.atualizarStatus(StatusCarta.ENTREGUE)
        arremate.vendedor.carteira.creditar(
            arremate.valorLiquido, f"Repasse da venda de {leilao.carta.nome}", agora)
        leiloes.salvar_transacao(leilao)
        clientes.salvar_carteira(arremate.vendedor)
    return leilao


def responder_saque(clientes: RepositorioClientes, saque_id: int, pagar: bool,
                    agora: datetime) -> tuple[Saque, Cliente]:
    """RF22: marca o saque como pago ou recusa (RN19)."""
    with transacao(clientes.conexao, imediata=True):
        par = next(((saque, cliente) for saque, cliente in clientes.saques() if saque.id == saque_id), None)
        if par is None:
            raise OperacaoRecusada("Saque não encontrado.")
        saque, cliente = par
        if pagar:
            cliente.carteira.pagarSaque(saque, agora)
        else:
            cliente.carteira.recusarSaque(saque, agora)
        clientes.salvar_carteira(cliente)
    return saque, cliente


def desfecho(leilao: Leilao) -> str:
    """RF16."""
    if leilao.status == StatusLeilao.CANCELADO:
        if leilao.carta.status == StatusCarta.CANCELADA:
            return "Cancelado pelo vendedor"
        return "Cancelado (recusado pela loja)" if leilao.motivoRecusa else "Cancelado"
    arremate = leilao.transacao
    if arremate is None:
        return "Devolvido (sem lances)"
    return {StatusTransacao.ENTREGUE: "Concluído", StatusTransacao.NAO_PAGA: "Devolvido (não pago)",
            StatusTransacao.PAGO: "Pago, aguardando retirada"}.get(arremate.status, "Aguardando pagamento")


def extrato_financeiro(leiloes: RepositorioLeiloes, clientes: RepositorioClientes, inicio: datetime,
                       fim: datetime) -> dict:
    """RF18."""
    def no_periodo(momento: datetime | None) -> bool:
        return momento is not None and inicio <= momento < fim

    lancamentos = []
    totais = dict.fromkeys(("arremates", "pagamentos", "taxas", "repasses", "saques"), Decimal("0.00"))
    for leilao in leiloes.com_transacao():
        arremate, carta = leilao.transacao, leilao.carta.nome
        if no_periodo(arremate.dataHora):
            totais["arremates"] += arremate.valor
            lancamentos.append((arremate.dataHora, "Arremate", f"{carta} (leilão {leilao.id})", arremate.valor))
        if no_periodo(arremate.dataPagamento):
            totais["pagamentos"] += arremate.valor
            lancamentos.append((arremate.dataPagamento, "Pagamento recebido", carta, arremate.valor))
        if no_periodo(arremate.dataEntrega):
            totais["taxas"] += arremate.taxa
            totais["repasses"] += arremate.valorLiquido
            lancamentos.append((arremate.dataEntrega, "Taxa retida", carta, arremate.taxa))
            lancamentos.append((arremate.dataEntrega, "Repasse ao vendedor",
                                f"{carta}, para {arremate.vendedor.nome}", arremate.valorLiquido))
    for saque, cliente in clientes.saques():
        if saque.status == StatusSaque.PAGO and no_periodo(saque.dataResposta):
            totais["saques"] += saque.valor
            lancamentos.append((saque.dataResposta, "Saque pago", f"{cliente.nome}, Pix {saque.chavePix}",
                                saque.valor))
    return {"totais": totais, "lancamentos": sorted(lancamentos, key=lambda item: item[0], reverse=True)}
