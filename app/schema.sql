PRAGMA foreign_keys = ON;

CREATE TABLE usuarios (
    id            INTEGER PRIMARY KEY,
    nome          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    senha_hash    TEXT NOT NULL,
    telefone      TEXT NOT NULL,
    data_cadastro TEXT NOT NULL,
    ativo         INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1))
);

CREATE TABLE clientes (
    usuario_id      INTEGER PRIMARY KEY REFERENCES usuarios (id) ON DELETE CASCADE,
    cpf             TEXT NOT NULL UNIQUE CHECK (length(cpf) = 11),
    bloqueado       INTEGER NOT NULL DEFAULT 0 CHECK (bloqueado IN (0, 1)),
    descumprimentos INTEGER NOT NULL DEFAULT 0 CHECK (descumprimentos >= 0)
);

CREATE TABLE administradores (
    usuario_id INTEGER PRIMARY KEY REFERENCES usuarios (id) ON DELETE CASCADE
);

-- bloqueado_centavos: parte do saldo reservada por saques solicitados (RN19).
CREATE TABLE carteiras (
    id                 INTEGER PRIMARY KEY,
    cliente_id         INTEGER NOT NULL UNIQUE REFERENCES clientes (usuario_id) ON DELETE CASCADE,
    saldo_centavos     INTEGER NOT NULL DEFAULT 0 CHECK (saldo_centavos >= 0),
    bloqueado_centavos INTEGER NOT NULL DEFAULT 0 CHECK (bloqueado_centavos BETWEEN 0 AND saldo_centavos)
);

CREATE TABLE saques (
    id               INTEGER PRIMARY KEY,
    carteira_id      INTEGER NOT NULL REFERENCES carteiras (id) ON DELETE CASCADE,
    valor_centavos   INTEGER NOT NULL CHECK (valor_centavos > 0),
    chave_pix        TEXT NOT NULL,
    data_solicitacao TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('solicitado', 'pago', 'recusado')),
    data_resposta    TEXT
);

CREATE INDEX idx_saques_status ON saques (status, data_solicitacao);

-- RF15: uma linha só, com o que o lojista configura.
CREATE TABLE configuracao_loja (
    id                        INTEGER PRIMARY KEY CHECK (id = 1),
    taxa_percentual           TEXT NOT NULL,
    incremento_minimo_centavos INTEGER NOT NULL CHECK (incremento_minimo_centavos > 0),
    prazo_pagamento_horas     INTEGER NOT NULL CHECK (prazo_pagamento_horas > 0),
    prazo_reoferta_horas      INTEGER NOT NULL CHECK (prazo_reoferta_horas > 0)
);

CREATE TABLE movimentacoes_carteira (
    id             INTEGER PRIMARY KEY,
    carteira_id    INTEGER NOT NULL REFERENCES carteiras (id) ON DELETE CASCADE,
    tipo           TEXT NOT NULL,
    valor_centavos INTEGER NOT NULL,
    data_hora      TEXT NOT NULL,
    descricao      TEXT NOT NULL
);

CREATE TABLE jogos (
    id   INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE
);

CREATE TABLE cartas (
    id          INTEGER PRIMARY KEY,
    jogo_id     INTEGER NOT NULL REFERENCES jogos (id),
    vendedor_id INTEGER NOT NULL REFERENCES clientes (usuario_id),
    nome        TEXT NOT NULL,
    edicao      TEXT NOT NULL,
    condicao    TEXT NOT NULL,
    descricao   TEXT NOT NULL,
    status      TEXT NOT NULL
);

CREATE TABLE carta_fotos (
    carta_id INTEGER NOT NULL REFERENCES cartas (id) ON DELETE CASCADE,
    ordem    INTEGER NOT NULL,
    url      TEXT NOT NULL,
    PRIMARY KEY (carta_id, ordem)
);

CREATE TABLE leiloes (
    id                         INTEGER PRIMARY KEY,
    carta_id                   INTEGER NOT NULL REFERENCES cartas (id),
    lance_inicial_centavos     INTEGER NOT NULL CHECK (lance_inicial_centavos > 0),
    incremento_minimo_centavos INTEGER NOT NULL CHECK (incremento_minimo_centavos > 0),
    data_inicio                TEXT NOT NULL,
    data_fim_prevista          TEXT NOT NULL,
    data_fim_real              TEXT,
    status                     TEXT NOT NULL
        CHECK (status IN ('pendente', 'aprovado', 'ativo', 'encerrado', 'cancelado')),
    -- RN17: a taxa da loja vale como estava quando o leilão foi criado.
    taxa_percentual            TEXT NOT NULL,
    motivo_recusa              TEXT,
    CHECK (data_fim_prevista > data_inicio)
);

CREATE INDEX idx_leiloes_status_fim ON leiloes (status, data_fim_prevista);

CREATE TABLE lances (
    id             INTEGER PRIMARY KEY,
    leilao_id      INTEGER NOT NULL REFERENCES leiloes (id),
    cliente_id     INTEGER NOT NULL REFERENCES clientes (usuario_id),
    valor_centavos INTEGER NOT NULL CHECK (valor_centavos > 0),
    data_hora      TEXT NOT NULL
);

CREATE INDEX idx_lances_leilao ON lances (leilao_id, valor_centavos DESC, data_hora);
CREATE INDEX idx_lances_cliente ON lances (cliente_id);

CREATE TRIGGER lances_irrevogaveis_update BEFORE UPDATE ON lances
BEGIN
    SELECT RAISE(ABORT, 'RN03: o lance é irrevogável');
END;

CREATE TRIGGER lances_irrevogaveis_delete BEFORE DELETE ON lances
BEGIN
    SELECT RAISE(ABORT, 'RN03: o lance é irrevogável');
END;

-- O arremate. UNIQUE em leilao_id: um leilão encerrado gera no máximo uma transação.
CREATE TABLE transacoes (
    id             INTEGER PRIMARY KEY,
    leilao_id      INTEGER NOT NULL UNIQUE REFERENCES leiloes (id),
    comprador_id   INTEGER NOT NULL REFERENCES clientes (usuario_id),
    valor_centavos INTEGER NOT NULL CHECK (valor_centavos > 0),
    data_hora      TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('aguardando pagamento', 'pago', 'entregue', 'não paga')),
    taxa_centavos    INTEGER NOT NULL CHECK (taxa_centavos >= 0),
    liquido_centavos INTEGER NOT NULL CHECK (liquido_centavos = valor_centavos - taxa_centavos),
    codigo_retirada  TEXT NOT NULL UNIQUE,
    prazo_pagamento  TEXT NOT NULL,
    data_pagamento   TEXT,
    data_entrega     TEXT,
    pago_saldo_centavos   INTEGER NOT NULL DEFAULT 0,
    pago_gateway_centavos INTEGER NOT NULL DEFAULT 0,
    forma_pagamento       TEXT
);

CREATE INDEX idx_transacoes_comprador ON transacoes (comprador_id);
CREATE INDEX idx_transacoes_status ON transacoes (status, prazo_pagamento);

-- RF19: log de auditoria. usuario_id nulo quando a operação é do próprio sistema.
CREATE TABLE log_operacoes (
    id             INTEGER PRIMARY KEY,
    usuario_id     INTEGER REFERENCES usuarios (id) ON DELETE SET NULL,
    operacao       TEXT NOT NULL,
    valor_centavos INTEGER,
    ip             TEXT,
    data_hora      TEXT NOT NULL,
    detalhe        TEXT NOT NULL DEFAULT ''
);
