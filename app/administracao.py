"""O que o lojista faz no sistema (RN14): cada função é um caso de uso da área de administração."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.anuncio import PREFIXO_DAS_FOTOS
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
    """RF05: a loja conferiu a carta, registra o depósito e aprova. Se o início já chegou, o leilão começa."""
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
    """RF05: a loja recusa o leilão e registra o motivo, que o vendedor vê em Vender."""
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
    """RF02: o administrador corrige os dados de cadastro do cliente."""
    dados, erros = conferir_contato(clientes, nome, email, telefone, exceto=cliente.id)
    if erros:
        raise DadosInvalidos(erros)
    cliente.nome, cliente.email, cliente.telefone = dados["nome"], dados["email"], dados["telefone"]
    clientes.atualizar(cliente)
    return cliente


def definir_bloqueio(clientes: RepositorioClientes, cliente: Cliente, bloqueado: bool) -> Cliente:
    """RF02: bloqueia ou desbloqueia a conta. Bloqueada, ela não dá lances nem cria leilões (RN15)."""
    cliente.bloqueado = bloqueado
    clientes.atualizar(cliente)
    return cliente


def atualizar_carta(leiloes: RepositorioLeiloes, leilao: Leilao, nome: str, jogo_id: str, edicao: str,
                    condicao: str) -> Leilao:
    """RF04: o administrador corrige nome, jogo, edição e condição depois de conferir a carta."""
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
    """Só sai do sistema a carta cujo leilão não chegou a acontecer: lances são irrevogáveis (RN03)."""
    return leilao.status in (StatusLeilao.PENDENTE, StatusLeilao.CANCELADO) and not leilao.lances


def remover_carta(leiloes: RepositorioLeiloes, leilao: Leilao, pasta_de_fotos: Path) -> None:
    """RF04: remove um cadastro inválido, com o leilão e as fotos da carta."""
    if not pode_remover(leilao):
        raise OperacaoRecusada("Só dá para remover a carta cujo leilão ainda aguarda aprovação ou foi recusado.")
    leiloes.remover(leilao)
    for foto in leilao.carta.fotos:
        if foto.startswith(PREFIXO_DAS_FOTOS):
            (pasta_de_fotos / foto.removeprefix(PREFIXO_DAS_FOTOS)).unlink(missing_ok=True)


def configurar_loja(loja: RepositorioLoja, taxa: str, incremento: str, prazo_pagamento: str,
                    prazo_reoferta: str) -> ConfiguracaoLoja:
    """RF15: taxa percentual, incremento mínimo e prazos. Taxa e incremento valem para leilões novos (RN17)."""
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


def registrar_entrega(leiloes: RepositorioLeiloes, clientes: RepositorioClientes, codigo: str,
                      agora: datetime) -> Leilao:
    """RF12: entrega a carta a quem apresenta o código de retirada e repassa o valor líquido ao vendedor.

    RN07: só com a transação paga. RN08: o repasse acontece aqui, e só aqui.
    """
    with transacao(leiloes.conexao, imediata=True):
        leilao = leiloes.por_codigo_de_retirada(codigo or "")
        if leilao is None:
            raise OperacaoRecusada("Nenhum arremate tem este código de retirada.")
        arremate = leilao.transacao
        arremate.registrarEntrega(codigo, agora)
        leilao.carta.atualizarStatus(StatusCarta.ENTREGUE)
        arremate.vendedor.carteira.creditar(
            arremate.valorLiquido, f"Repasse da venda de {leilao.carta.nome}", agora)
        leiloes.salvar_transacao(leilao)
        clientes.salvar_carteira(arremate.vendedor)
    return leilao


def responder_saque(clientes: RepositorioClientes, saque_id: int, pagar: bool,
                    agora: datetime) -> tuple[Saque, Cliente]:
    """RF22: o lojista registra a transferência feita por Pix (saque pago) ou recusa o saque (RN19)."""
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
    """RF16: como o leilão finalizado terminou."""
    if leilao.status == StatusLeilao.CANCELADO:
        return "Cancelado (recusado pela loja)" if leilao.motivoRecusa else "Cancelado"
    arremate = leilao.transacao
    if arremate is None:
        return "Devolvido (sem lances)"
    return {StatusTransacao.ENTREGUE: "Concluído", StatusTransacao.NAO_PAGA: "Devolvido (não pago)",
            StatusTransacao.PAGO: "Pago, aguardando retirada"}.get(arremate.status, "Aguardando pagamento")


def extrato_financeiro(leiloes: RepositorioLeiloes, clientes: RepositorioClientes, inicio: datetime,
                       fim: datetime) -> dict:
    """RF18: arremates, pagamentos, taxas retidas, repasses e saques pagos entre `inicio` e `fim`."""
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
