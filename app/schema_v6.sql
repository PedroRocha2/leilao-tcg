-- Versão 6: atributos das cartas para os filtros. A carta de duas cores tem uma linha por cor.
CREATE TABLE carta_atributos (
    carta_id INTEGER NOT NULL REFERENCES cartas (id) ON DELETE CASCADE,
    chave    TEXT NOT NULL,
    valor    TEXT NOT NULL,
    PRIMARY KEY (carta_id, chave, valor)
);

CREATE INDEX idx_carta_atributos_chave ON carta_atributos (chave, valor);
