# Leilão TCG · v2

Projeto da disciplina Engenharia de Software I (UFSC). É uma fatia funcional do **Sistema de Leilão de
Cartas TCG** descrito na *Especificação de Requisitos* do grupo (Rafael Brunetti Mussi, Pedro Rocha e
Gustavo Panchiniak), construída sobre o **diagrama de classes** do sistema.

**Escopo da v2:** ver leilões ativos, dar lance e criar conta/entrar. Classes do diagrama implementadas:

| Pacote do diagrama | Classes |
|---|---|
| Contas e Acesso | `Usuario` (abstrata), `Cliente` |
| Cartas e Leilões | `Jogo`, `Carta`, `Leilao`, `Lance` |
| Financeiro (só consulta) | `Carteira`, `MovimentacaoCarteira` |

Ficaram fora, sem telas: Administrador, Deposito, Transacao, Pagamento, Retirada, Saque, Notificacao,
ConfiguracaoLoja e LogOperacao.

## Como rodar

Requisitos: Python 3.12 ou mais recente. Os testes de navegador usam o Google Chrome ou o Microsoft Edge instalados.

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

flask --app run run              # http://127.0.0.1:5000
```

Na primeira execução, o banco SQLite é criado em `instance/leilao.sqlite3` com 3 jogos, 15 cartas em
leilão e os lances de outros clientes, com prazos contados a partir daquele momento. Um banco da v1 é
reconhecido pela versão do esquema e recriado automaticamente. Para recomeçar, com os prazos contados a
partir de agora e sem nenhuma conta criada:

```bash
flask --app run reiniciar-dados
```

### Testes

```bash
pytest                                  # 176 testes
pytest tests/test_regras_lance.py -v    # só as regras do lance (unitários do domínio)
pytest tests/test_rnf01_responsivo.py   # RNF01 no navegador; gera evidencias/rnf01/
```

| Arquivo | Testes | O que cobre |
|---|---|---|
| [tests/test_regras_lance.py](tests/test_regras_lance.py) | 39 | RN01, RN02, RN03, RN05, RN11, RN12, RN13, RN15 e RN17 no domínio |
| [tests/test_dominio_contas.py](tests/test_dominio_contas.py) | 33 | Usuario abstrata, Cliente, `autenticar()`, hash de senha, CPF e Carteira |
| [tests/test_dinheiro.py](tests/test_dinheiro.py) | 24 | leitura e formatação de valores em reais |
| [tests/test_cadastro.py](tests/test_cadastro.py) | 20 | criar conta: e-mail e CPF únicos, dígitos do CPF, senha ≥ 8, valores iniciais, carteira 1:1 |
| [tests/test_rotas_leiloes.py](tests/test_rotas_leiloes.py) | 26 | lista e chips, página do leilão, lance por JSON e por formulário, concorrência |
| [tests/test_rotas_contas.py](tests/test_rotas_contas.py) | 11 | cadastro, login, sessão (amarrada à conta), sair, redirecionamento seguro |
| [tests/test_minha_conta.py](tests/test_minha_conta.py) | 8 | Perfil, Carteira e Meus lances |
| [tests/test_interface.py](tests/test_interface.py) | 5 | navegador: abas, galeria, lance sem recarregar, lance de outra pessoa, RN02 |
| [tests/test_rnf01_responsivo.py](tests/test_rnf01_responsivo.py) | 10 | navegador: RNF01 em 360, 390 e 768 px e menu no celular |

O resultado da última execução está em [evidencias/resultado-testes.txt](evidencias/resultado-testes.txt).

## Como verificar

1. Abra a lista. Ela mostra só os leilões ativos, com os que terminam primeiro no topo. Os chips
   filtram por jogo, e o filtro fica no endereço (`/leiloes?jogo=pokemon`).
2. Abra **Charizard** sem entrar. O lance atual é R$ 2.350,00 e o incremento é R$ 5,00. No lugar do
   campo aparece **Entrar para dar lance**.
3. Clique em **Criar conta** e cadastre-se com um CPF válido, como `529.982.247-25`. Teste também as
   recusas: CPF com dígito errado, e-mail repetido, senha com menos de 8 caracteres e confirmação
   diferente. Depois do cadastro, você volta ao Charizard já logado.
4. O campo já vem com **2.355,00**, o resultado de `calcularLanceMinimo()`. Troque por `2.354,99` e clique
   em **Dar lance**: o motivo aparece logo abaixo do campo e nada é gravado.
5. Volte para `2.355,00` e dê o lance. A página não recarrega: o lance entra no topo da tabela como
   "Você", o mínimo vira R$ 2.360,00 e o resultado é anunciado ao leitor de tela.
6. Recarregue a página (F5). A sessão continua e o lance continua gravado.
7. Em **Minha Conta**, veja o Perfil (CPF mascarado), a Carteira (saldo R$ 0,00, só leitura) e Meus
   lances ("Você lidera").
8. **RN02:** o leilão do Dark Magician termina cerca de 25 minutos depois da carga. Com
   `flask --app run reiniciar-dados`, espere faltarem menos de 3 minutos e dê um lance: o prazo
   ganha 3 minutos e o cronômetro se atualiza na hora.
9. **RNF01:** no DevTools, use o modo dispositivo em 360 px. Não há rolagem horizontal, o menu recolhe
   no botão **Menu** e campo e botão ficam inteiros. A medição automática está em
   [evidencias/rnf01/](evidencias/rnf01/).

## Rastreabilidade

| Requisito / RN | Classe do diagrama | Arquivo | Como verificar |
|---|---|---|---|
| **RF01** · cadastro e autenticação de clientes | `Usuario` (`senhaHash`, `dataCadastro`, `ativo`, `autenticar()`), `Cliente` (`cpf`, `bloqueado`, `descumprimentos`), `Carteira` | [app/cadastro.py:27](app/cadastro.py#L27), [app/rotas/contas.py:27](app/rotas/contas.py#L27) (criar), [:55](app/rotas/contas.py#L55) (entrar), [:77](app/rotas/contas.py#L77) (sair), [app/dominio/contas.py:37](app/dominio/contas.py#L37) (`autenticar`), [app/repositorios/clientes.py:24](app/repositorios/clientes.py#L24) | [tests/test_cadastro.py](tests/test_cadastro.py), [tests/test_rotas_contas.py](tests/test_rotas_contas.py); roteiro, passos 3 e 6 |
| **RF06** · listagem de leilões ativos com filtro por jogo | `Leilao`, `Carta`, `Jogo` | [app/rotas/leiloes.py:20](app/rotas/leiloes.py#L20), [app/repositorios/leiloes.py:32](app/repositorios/leiloes.py#L32), [app/templates/leiloes.html](app/templates/leiloes.html) | `test_lista_mostra_os_leiloes_ativos…`, `test_lista_nao_mostra_leilao_encerrado…`, `test_chips_filtram_por_jogo`; roteiro, passo 1 |
| **RF07** · lance de usuário logado em leilão em andamento | `Cliente.darLance()`, `Leilao`, `Lance` | [app/dominio/contas.py:59](app/dominio/contas.py#L59), [app/rotas/leiloes.py:91](app/rotas/leiloes.py#L91), [app/repositorios/leiloes.py:160](app/repositorios/leiloes.py#L160), [app/static/js/app.js:216](app/static/js/app.js#L216) (envio sem recarregar) | `test_lance_valido_e_gravado_e_o_minimo_recalculado`, `test_formulario_sem_javascript_tambem_aplica_as_regras`, `test_visitante_nao_da_lance`, `test_lance_atualiza_a_pagina_sem_recarregar`; roteiro, passos 4 e 5 |
| **RF08** · cronômetro e maior lance atual para todos | `Leilao.getMaiorLance()`, `Leilao.dataFimPrevista` | [app/apresentacao.py:119](app/apresentacao.py#L119), [app/static/js/app.js:342](app/static/js/app.js#L342) (atualização a cada 5 s) | `test_lance_de_outra_pessoa_aparece_e_e_anunciado`, `test_estado_json_traz_o_painel_e_a_tabela` |
| **RF17** · carteira e extrato (só consulta) | `Carteira` (`saldo`, `gerarExtrato()`), `MovimentacaoCarteira` | [app/dominio/financeiro.py:29](app/dominio/financeiro.py#L29), [app/rotas/minha_conta.py:20](app/rotas/minha_conta.py#L20) | `test_carteira_mostra_saldo_zero_e_extrato_vazio`, `test_carteira_lista_as_movimentacoes_gravadas`, `test_gerar_extrato…` |
| **RN01** · mínimo = lance inicial ou maior lance + incremento | `Leilao.calcularLanceMinimo()`, `Leilao.validarLance(valor)` | [app/dominio/leiloes.py:130](app/dominio/leiloes.py#L130), [:137](app/dominio/leiloes.py#L137) | [test_regras_lance.py:54–112](tests/test_regras_lance.py#L54): mínimo aceito, abaixo recusado, primeiro lance, mensagem; `test_primeiro_lance_usa_o_lance_inicial` |
| **RN02** · lance com menos de 3 min prorroga o fim em 3 min | `Leilao.dataFimPrevista` (`receberLance`, auxiliar) | [app/dominio/leiloes.py:180](app/dominio/leiloes.py#L180) | [test_regras_lance.py:193–219](tests/test_regras_lance.py#L193); `test_rn02_lance_nos_ultimos_3_minutos_prorroga_o_fim`; `test_rn02_prorrogacao_atualiza_o_cronometro` |
| **RN03** · lance irrevogável | `Lance` (imutável) | [app/dominio/leiloes.py:83](app/dominio/leiloes.py#L83), gatilhos em [app/schema.sql:92](app/schema.sql#L92) | `test_lance_registrado_nao_pode_ser_alterado`, `test_cliente_nao_reduz_o_proprio_lance`, `test_rn03_banco_recusa_alterar_ou_apagar_lance` |
| **RN05** · leilão com início e fim previsto | `Leilao.dataInicio`, `Leilao.dataFimPrevista` | [app/dominio/leiloes.py:115](app/dominio/leiloes.py#L115), [app/schema.sql:74](app/schema.sql#L74) | `test_rn05_fim_previsto_precisa_ser_depois_do_inicio` |
| **RN11** · sem lance no próprio leilão | `Cliente.darLance()` (vendedor da `Carta`) | [app/dominio/contas.py:59](app/dominio/contas.py#L59) | `test_vendedor_nao_da_lance_no_proprio_leilao` (domínio e HTTP) |
| **RN12** · só leilão ativo, dentro do prazo, recebe lance | `Leilao.status`, `Leilao.validarLance(valor)` | [app/dominio/leiloes.py:145](app/dominio/leiloes.py#L145) | [test_regras_lance.py:116–150](tests/test_regras_lance.py#L116); `test_leilao_fora_do_prazo_nao_recebe_lance`, `test_leilao_que_nao_esta_ativo_nao_recebe_lance` |
| **RN13** · empate: vale o lance registrado primeiro (ms) | `Leilao.getMaiorLance()` | [app/dominio/leiloes.py:121](app/dominio/leiloes.py#L121), transação `BEGIN IMMEDIATE` em [app/rotas/leiloes.py:108](app/rotas/leiloes.py#L108) | `test_empate_de_valor_vale_o_lance_registrado_primeiro`, `test_rn13_dois_lances_simultaneos_de_mesmo_valor_so_um_e_aceito` |
| **RN15** · conta bloqueada não dá lance | `Cliente.podeDarLance()` | [app/dominio/contas.py:55](app/dominio/contas.py#L55) | [test_regras_lance.py:154–177](tests/test_regras_lance.py#L154); `test_cliente_bloqueado_nao_da_lance` |
| **RN17** · incremento da loja gravado em cada leilão | `Leilao.incrementoMinimo` | [app/carga_inicial.py:19](app/carga_inicial.py#L19) | `test_usa_o_incremento_gravado_no_leilao` |
| **RNF01** · leilão e área de lance responsivos | — | [app/static/css/app.css](app/static/css/app.css) (breakpoints em 1080, 900 e 767 px), [app/static/js/app.js:19](app/static/js/app.js#L19) (menu) | [tests/test_rnf01_responsivo.py](tests/test_rnf01_responsivo.py) → [evidencias/rnf01/](evidencias/rnf01/) |
| **RNF03** · dados persistentes em banco | todas as classes do escopo | [app/schema.sql](app/schema.sql), [app/repositorios/](app/repositorios/) | os testes de rotas gravam e releem pelo SQLite |
| **RNF04** · senha com hash, nunca em texto puro | `Usuario.senhaHash` | [app/dominio/senhas.py:24](app/dominio/senhas.py#L24) | `test_grava_so_o_hash_da_senha`, `test_hash_nao_contem_a_senha_e_tem_salt` |
| **RNF05** · implementado em Python | — | Flask + Jinja + SQLite | — |
| **RNF06** · LGPD (minimização de dados) | `Lance` → licitante anônimo; `Cliente.cpf` mascarado | [app/apresentacao.py:93](app/apresentacao.py#L93), [app/dominio/cpf.py](app/dominio/cpf.py) | `test_licitantes_aparecem_anonimizados`, `test_perfil_mostra_dados…_com_cpf_mascarado` |
| **RNF07** · autorização verificada no servidor | — | regras no domínio, chamadas em cada POST; CSRF em [app/rotas/__init__.py:19](app/rotas/__init__.py#L19); login exigido em [app/rotas/comum.py:69](app/rotas/comum.py#L69) | `test_lance_sem_token_csrf_e_recusado`, `test_exige_login`, `test_sair_exige_post_com_token` |

## Classes do diagrama no código

Classes, atributos e métodos usam os nomes do diagrama (camelCase) para a rastreabilidade ficar direta.
Rotas, repositórios e templates seguem o padrão do Python (snake_case).

| Classe | Arquivo | Implementado | Fora da v2 (depende de classes fora do escopo) |
|---|---|---|---|
| `Usuario` (abstrata) | [app/dominio/contas.py:21](app/dominio/contas.py#L21) | todos os atributos; `autenticar()`. Não pode ser instanciada | `alterarSenha`, `atualizarPerfil`, `desativar` (sem telas no escopo) |
| `Cliente` | [app/dominio/contas.py:47](app/dominio/contas.py#L47) | `cpf`, `bloqueado`, `descumprimentos`; `podeDarLance()`, `darLance()`; Carteira composta (1:1) | `cadastrarCarta`, `criarLeilao`, `pagarArremate`, `registrarDescumprimento` |
| `Jogo` | [app/dominio/leiloes.py:59](app/dominio/leiloes.py#L59) | `id`, `nome`; 1 Jogo → 0..* Carta | — |
| `Carta` | [app/dominio/leiloes.py:65](app/dominio/leiloes.py#L65) | todos os atributos, `fotos` como lista; `adicionarFoto()`; Cliente 1 → 0..* Carta | `atualizarStatus`, `estaDisponivel` |
| `Leilao` | [app/dominio/leiloes.py:96](app/dominio/leiloes.py#L96) | todos os atributos; `calcularLanceMinimo()`, `validarLance()`, `getMaiorLance()`; Carta 1 → 0..* Leilao; composição com Lance | `iniciar`, `encerrar`, `reofertarSegundoColocado`, `cancelar` |
| `Lance` | [app/dominio/leiloes.py:83](app/dominio/leiloes.py#L83) | `id`, `valor`, `dataHora`; Cliente 1 → 0..* Lance | — |
| `Carteira` | [app/dominio/financeiro.py:22](app/dominio/financeiro.py#L22) | `id`, `saldo`; `gerarExtrato()`; composição com MovimentacaoCarteira | `creditar`, `debitar`, `possuiSaldo`, `solicitarSaque` |
| `MovimentacaoCarteira` | [app/dominio/financeiro.py:13](app/dominio/financeiro.py#L13) | todos os atributos | — |

**Tipos:** BigDecimal é `decimal.Decimal` com duas casas (no banco, centavos inteiros); DateTime é
`datetime` em UTC com milissegundos; Date é `date`.

**Métodos auxiliares, fora do diagrama:**
- `Leilao.estaAberto` (status ativo e dentro do prazo);
- `Leilao.motivoDeRecusa` e `Leilao.explicarRecusa` (qual regra o valor viola e a mensagem para a tela);
- `Leilao.receberLance` (o "recebe" da composição, que aplica a RN02);
- `Usuario.ehOMesmo` (a mesma pessoa, ainda que carregada em objetos diferentes).

**O que divergia da v1 e foi corrigido:** o jogo era um texto solto na carta e passou a ser a classe
`Jogo`. A carta tinha uma imagem só e agora tem `fotos`. Cada carta só podia ter um leilão (1:1) e agora
pode ter vários (Carta 1 → 0..* Leilao). O lance mínimo inicial, o incremento e as datas passaram a
se chamar `lanceInicial`, `incrementoMinimo`, `dataInicio` e `dataFimPrevista`. Usuario e Cliente deixaram de ser um campo `perfil` e viraram herança, com a Carteira composta.

## Da v1 para a v2

| Tema | v1 | v2 |
|---|---|---|
| Escopo | RF07 + RN01 + RNF01 | ver leilões ativos, dar lance, criar conta/entrar e Minha Conta |
| Domínio | funções soltas (`validar_lance`) | classes do diagrama: Usuario, Cliente, Jogo, Carta, Leilao, Lance, Carteira, MovimentacaoCarteira |
| Regras do lance | RN01 (estrita) e RN11 | RN01, RN02, RN03, RN05, RN11, RN12, RN13, RN15 e RN17 |
| RN01 | "superior a": o lance igual a atual + incremento era recusado | `calcularLanceMinimo()` = maior lance + incremento, e esse valor é aceito (o campo já vem preenchido com ele) |
| Login | um seletor de usuário simulava o login | cadastro e login reais, com senha em hash, sessão e Sair |
| Navegação | menu lateral com 12 itens desabilitados de telas futuras | menu superior fixo: Leilões, Entrar/Criar conta ou Minha Conta; recolhe no celular |
| Lista | leilões em andamento e agendados | só ativos, com filtro por jogo em chips |
| Página do leilão | título, foto, ficha e painel | trilha, galeria com miniaturas e foto ampliada, painel de lance, abas Lances/Detalhes/Descrição e "Outros leilões de {Jogo}" |
| Participantes | "Ana S." | "Licitante 1, 2, 3…"; o próprio cliente vê "Você" |
| Visual | tema claro Wise (verde-limão) | tema escuro com os 10 tokens da v2 ([DESIGN.md](DESIGN.md)) |
| Persistência | SQL dentro do serviço | repositórios ([app/repositorios/](app/repositorios/)); esquema versionado (`PRAGMA user_version`) |
| Testes | 65 | 176 |

## Decisões

- **Hash de senha no servidor.** O enunciado pedia Web Crypto e repositório em localStorage *caso não
  houvesse backend*. Como há (Flask), o hash é gerado no servidor com PBKDF2-HMAC-SHA256 (o mesmo
  algoritmo do Web Crypto), `hashlib` da biblioteca padrão, salt aleatório de 16 bytes e 600 mil
  iterações; só `senhaHash` é gravado. **Em produção, o recomendado é bcrypt ou argon2 no servidor.** Gerar
  o hash no navegador faria do próprio hash a senha: quem lesse o banco entraria com ele.
- **Sessão:** cookie assinado do Flask (`HttpOnly`, `SameSite=Lax`), renovado a cada login. Sobrevive ao
  recarregamento. Em produção, o cookie também precisa de `Secure` e o site precisa de HTTPS (RNF07).
- **Login sem dica:** e-mail inexistente e senha errada recebem a mesma mensagem e levam o mesmo tempo.
- **Carga inicial:** jogos, cartas, leilões e lances de outros clientes. Esses clientes não têm senha
  utilizável (ninguém entra com eles) e nas telas aparecem só como "Licitante N". Os lances da carga passam
  por `Cliente.darLance()`, então já respeitam as regras.
- **Status exibido:** o encerramento automático (RF09) está fora do escopo, então o status gravado
  continua "ativo" depois do prazo. A tela mostra "Encerrado" e o domínio recusa o lance (RN12).
- **Erro e sucesso sem cores novas:** a paleta é monocromática; o estado é dito por ícone, texto e borda (ver DESIGN.md).
- **Fotos:** cada carta tem três fotos (frente, detalhe da arte e detalhe do canto), recortadas da imagem
  em alta resolução e normalizadas na proporção 63:88.
- **Lance e carteira:** o lance não consulta o saldo da Carteira, como no diagrama (há um teste para isso).

## Skills usadas

`design-taste-frontend`, `image-to-code` e `web-design-guidelines` (da v1) e `redesign-existing-projects`
(nova). O diagnóstico, o plano e a referência visual aprovados estão em
[docs/v2/etapa1-plano.md](docs/v2/etapa1-plano.md) e [docs/v2/referencia/](docs/v2/referencia/). A auditoria
das telas novas e a revalidação do RNF01 estão em [evidencias/auditoria-interface.md](evidencias/auditoria-interface.md).

## Créditos das imagens

As imagens das cartas são marcas e propriedade das respectivas editoras (The Pokémon Company, Wizards of
the Coast e Konami). Foram usadas aqui só como exemplo das fotos que um vendedor enviaria, em um projeto
acadêmico sem fins comerciais. Fontes: [pokemontcg.io](https://pokemontcg.io), [Scryfall](https://scryfall.com)
e [YGOPRODeck](https://ygoprodeck.com). A fonte Inter (SIL Open Font License) é servida localmente.
