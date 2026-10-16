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

CREATE TABLE carteiras (
    id             INTEGER PRIMARY KEY,
    cliente_id     INTEGER NOT NULL UNIQUE REFERENCES clientes (usuario_id) ON DELETE CASCADE,
    saldo_centavos INTEGER NOT NULL DEFAULT 0
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
