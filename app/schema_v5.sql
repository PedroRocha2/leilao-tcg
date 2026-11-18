-- Versão 5: cobranças no gateway externo (RF11). saldo_centavos sai da carteira só na confirmação (RN18).
CREATE TABLE cobrancas (
    id             INTEGER PRIMARY KEY,
    leilao_id      INTEGER NOT NULL REFERENCES leiloes (id) ON DELETE CASCADE,
    referencia     TEXT NOT NULL UNIQUE,
    valor_centavos INTEGER NOT NULL CHECK (valor_centavos > 0),
    saldo_centavos INTEGER NOT NULL DEFAULT 0 CHECK (saldo_centavos >= 0),
    checkout_id    TEXT NOT NULL,
    checkout_url   TEXT NOT NULL,
    -- 'creditada': pago fora do prazo ou em duplicidade; o valor foi para a carteira.
    status         TEXT NOT NULL CHECK (status IN ('pendente', 'paga', 'creditada')),
    pagamento_id   TEXT UNIQUE,
    data_criacao   TEXT NOT NULL,
    data_resposta  TEXT
);

CREATE INDEX idx_cobrancas_leilao ON cobrancas (leilao_id, status);
