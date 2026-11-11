# Leilão TCG · v2

Projeto da disciplina Engenharia de Software I (UFSC). É uma fatia funcional do **Sistema de Leilão de
Cartas TCG** descrito na *Especificação de Requisitos* do grupo (Rafael Brunetti Mussi, Pedro Rocha e
Gustavo Panchiniak), construída sobre o **diagrama de classes** do sistema.

**Escopo da v2:** ver leilões ativos, dar lance e criar conta/entrar. **Etapas seguintes:** encerramento
automático do leilão com o arremate (RF09), criação de leilão pelo vendedor com a carta escolhida no
catálogo de cada jogo (RF03) e a área do administrador, com o que ela precisa do lado do cliente:
pagamento do arremate, código de retirada e saque. Classes do diagrama implementadas:

| Pacote do diagrama | Classes |
|---|---|
| Contas e Acesso | `Usuario` (abstrata), `Cliente`, `Administrador` |
| Cartas e Leilões | `Jogo`, `Carta`, `Leilao`, `Lance` |
| Financeiro | `Carteira`, `MovimentacaoCarteira`, `Transacao` (o arremate), `Saque` |
| Loja | `ConfiguracaoLoja`, `LogOperacao` |

Ainda não existem: notificações na central e por e-mail (RF23, e com elas os avisos de RF05, RF08, RF10 e
RF21), reoferta ao segundo colocado (RF21), cancelamento do leilão pelo vendedor (RF20) e os filtros por
nome e tempo restante (RF06). O pagamento usa um gateway local, que confirma na hora e não cobra de
verdade. As classes Deposito, Pagamento, Retirada e Notificacao do diagrama não foram criadas: o depósito,
o pagamento e a retirada ficam registrados no status da carta e na `Transacao`.

## Como rodar

Requisitos: Python 3.12 ou mais recente. Os testes de navegador usam o Google Chrome ou o Microsoft Edge instalados.

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

flask --app run run              # http://127.0.0.1:5000
```

Na primeira execução, o banco SQLite é criado em `instance/leilao.sqlite3` com 3 jogos, 15 cartas em
leilão e os lances de outros clientes, com prazos contados a partir daquele momento. Um banco de uma
versão anterior é reconhecido pela versão do esquema e recriado automaticamente. Para recomeçar, com os prazos contados a
partir de agora e sem nenhuma conta criada:

```bash
flask --app run reiniciar-dados
```

Criar leilão consulta as APIs públicas de cartas e por isso precisa de internet.

### Administrador

A conta do lojista é criada junto com o banco: usuário **`admin-jiujitsu`**, senha **`osscachorro`**.
Entre com esses dados na tela **Entrar** para abrir a **Administração**. Para usar outros, defina as
variáveis de ambiente `LEILAO_ADMIN_LOGIN` e `LEILAO_ADMIN_SENHA` antes da primeira execução ou antes
de `reiniciar-dados`. Como a senha padrão está neste repositório, troque-a antes de qualquer uso real.

### Testes

```bash
pytest                                  # 478 testes
pytest tests/test_regras_lance.py -v    # só as regras do lance (unitários do domínio)
pytest tests/test_rnf01_responsivo.py   # RNF01 no navegador; gera evidencias/rnf01/
```

| Arquivo | Testes | O que cobre |
|---|---|---|
| [tests/test_regras_lance.py](tests/test_regras_lance.py) | 39 | RN01, RN02, RN03, RN05, RN11, RN12, RN13, RN15 e RN17 no domínio |
| [tests/test_dominio_contas.py](tests/test_dominio_contas.py) | 33 | Usuario abstrata, Cliente, `autenticar()`, hash de senha, CPF e Carteira |
| [tests/test_dinheiro.py](tests/test_dinheiro.py) | 24 | leitura e formatação de valores em reais |
| [tests/test_cadastro.py](tests/test_cadastro.py) | 20 | criar conta: e-mail e CPF únicos, dígitos do CPF, senha ≥ 8, valores iniciais, carteira 1:1 |
| [tests/test_admin.py](tests/test_admin.py) | 79 | área do administrador (RF02, RF04, RF05, RF12, RF15, RF16, RF18, RF19, RF22), acesso por perfil (RN14), pagamento (RF11), código de retirada, repasse, saque e descumprimento |
| [tests/test_criar_leilao.py](tests/test_criar_leilao.py) | 84 | `cadastrarCarta()`, `criarLeilao()`, RN04, RN05, RN12 e RN15; sugestões, filtro pelo nome e pelo código e formulário de Vender, com o valor médio de mercado; aprovação pelo lojista; da criação ao arremate |
| [tests/test_catalogo.py](tests/test_catalogo.py) | 82 | as quatro APIs de cartas com respostas gravadas (sem rede): nome, código, edição, especificações, imagem e preço; sugestões; busca pelo código (Pokémon e One Piece); falhas; endereços permitidos |
| [tests/test_encerramento.py](tests/test_encerramento.py) | 28 | `Leilao.encerrar()`, encerramento automático, arremate (`Transacao`), resultado nas telas, concorrência |
| [tests/test_rotas_leiloes.py](tests/test_rotas_leiloes.py) | 45 | página inicial, busca do topo pelo nome ou código, página de cada jogo, página do leilão, lance por JSON e por formulário, concorrência |
| [tests/test_rotas_contas.py](tests/test_rotas_contas.py) | 11 | cadastro, login, sessão (amarrada à conta), sair, redirecionamento seguro |
| [tests/test_minha_conta.py](tests/test_minha_conta.py) | 8 | Perfil, Carteira e Meus lances (Arremates está em `test_encerramento.py`) |
| [tests/test_interface.py](tests/test_interface.py) | 9 | navegador: página inicial ("Quero comprar", jogos e busca do topo), abas, galeria, lance sem recarregar, lance de outra pessoa, RN02, leilão que encerra na tela, criar leilão pelo catálogo, lojista aprovando e percorrendo a administração |
| [tests/test_rnf01_responsivo.py](tests/test_rnf01_responsivo.py) | 16 | navegador: RNF01 em 360, 390 e 768 px, página inicial, busca do topo, menu, abas de Minha Conta, criar leilão e administração no celular |

O resultado da última execução está em [evidencias/resultado-testes.txt](evidencias/resultado-testes.txt).

## Como verificar

1. Abra a página inicial (`/`). **Quero comprar** rola até os leilões ativos, que ficam abaixo do destaque,
   com os que terminam primeiro no topo. **Quero vender** leva a Criar leilão ou, para quem não entrou, à
   tela de Entrar. Cada jogo do destaque abre a página dele (`/jogos/pokemon`), só com os leilões ativos
   daquele jogo. Na busca do topo, escolha o jogo e digite o nome ou o código da carta, como `dragon` ou
   `4/102`: o resultado sai em `/leiloes?q=…` ou, com um jogo escolhido, na página do jogo.
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
9. **Encerramento e arremate:** continue na página do Dark Magician depois do lance do passo 8. Quando o
   cronômetro zera, a página se atualiza sozinha: o status vira **Encerrado**, o painel mostra o **Valor do
   arremate** e "Você arrematou esta carta por R$ …", e a tabela marca o **Lance vencedor**. Em
   **Minha Conta › Arremates**, a carta aparece com o valor e a situação "Aguardando pagamento"; em
   **Meus lances**, a situação vira "Você arrematou". O leilão sai da lista de leilões ativos, e quem não
   é o vencedor vê "Licitante N arrematou esta carta por R$ …".
10. **Criar leilão (RF03):** no menu, entre em **Vender** e clique em **Criar leilão**. Escolha o jogo
    (Pokémon, Magic: The Gathering, Yu-Gi-Oh! ou One Piece Card Game): as sugestões do jogo (os lançamentos
    recentes) já aparecem. Digite no filtro o nome em inglês, como `charizard`, e as cartas mudam enquanto
    você digita. Em Pokémon e One Piece o filtro também acha pelo código impresso na carta, como `90/112` e
    `OP02-025`. Cada carta traz a imagem, o nome, a edição, o código e as especificações que a API do jogo
    devolve. Escolha uma carta: o formulário mostra o **valor médio de mercado** dela, em dólares ou euros,
    como referência. Informe a condição, o lance mínimo inicial e o período, e clique em **Criar leilão**.
    Em Yu-Gi-Oh! o formulário também pede a edição, porque a mesma carta sai em várias. Teste as recusas:
    lance `0`, fim antes do início.
11. **Aprovação da loja (RF05, RN12):** a carta aparece em **Vender** como "Aguardando depósito" e ainda não
    está na lista de leilões. Saia da conta e entre como `admin-jiujitsu` / `osscachorro`. Em
    **Administração › Leilões**, clique em **Aprovar e registrar depósito**: o leilão entra na lista. Para ver
    a recusa, crie outro leilão e recuse com um motivo; o vendedor lê o motivo em **Vender**. O administrador
    não dá lances; a conta que criou o leilão também não (RN11).
12. **Configurações (RF15, RN17):** em **Administração › Configurações**, mude a taxa para `12,5` e o
    incremento para `10,00`. Um leilão criado depois sai com o incremento novo; os que já existiam continuam
    com R$ 5,00.
13. **Pagamento (RF11):** com uma segunda conta de cliente, dê um lance no leilão aprovado e espere o
    fim do prazo (use um fim próximo ao criar o leilão). Em **Minha Conta › Arremates** aparecem o valor, o
    prazo de pagamento e o código de retirada. Clique em **Pagar**, escolha Pix ou cartão e confirme.
14. **Entrega e repasse (RF12, RF13):** como administrador, em **Entregas**, digite o código de retirada do
    comprador. A tela mostra o comprador, o valor, a taxa da loja e o repasse. **Registrar entrega** credita o
    valor líquido na carteira do vendedor. Antes do pagamento, o mesmo código é recusado (RN07).
15. **Saque (RF22):** como vendedor, em **Minha Conta › Carteira**, solicite um saque com uma chave Pix: o
    valor fica bloqueado. Como administrador, em **Saques**, registre a transferência ou recuse.
16. **Usuários e cartas (RF02, RF04):** em **Usuários**, abra um cliente, edite os dados e bloqueie a conta:
    ela deixa de dar lances e de criar leilões. Em **Cartas**, corrija os dados de uma carta ou remova o
    cadastro de um leilão que ainda aguarda aprovação.
17. **Histórico, financeiro e auditoria (RF16, RF18, RF19):** o **Histórico** lista os leilões finalizados
    com o desfecho; o **Financeiro** soma arremates, pagamentos, taxas retidas, repasses e saques do período;
    a **Auditoria** mostra quem fez cada operação, o valor, o IP e a hora.
18. **Descumprimento (RF21, parcial):** um arremate que passa do prazo sem pagamento fica "Não pago no
    prazo", a carta volta ao vendedor e o comprador ganha um descumprimento, visível em **Usuários**.
19. **RNF01:** no DevTools, use o modo dispositivo em 360 px. Não há rolagem horizontal, o menu recolhe
    no botão **Menu** e campo e botão ficam inteiros. A medição automática está em
    [evidencias/rnf01/](evidencias/rnf01/).

## Rastreabilidade

| Requisito / RN | Classe do diagrama | Arquivo | Como verificar |
|---|---|---|---|
| **RF01** · cadastro e autenticação de clientes | `Usuario` (`senhaHash`, `dataCadastro`, `ativo`, `autenticar()`), `Cliente` (`cpf`, `bloqueado`, `descumprimentos`), `Carteira` | [app/cadastro.py:52](app/cadastro.py#L52), [app/rotas/contas.py:28](app/rotas/contas.py#L28) (criar), [:57](app/rotas/contas.py#L57) (entrar), [:82](app/rotas/contas.py#L82) (sair), [app/dominio/contas.py:30](app/dominio/contas.py#L30) (`autenticar`), [app/repositorios/clientes.py:22](app/repositorios/clientes.py#L22) | [tests/test_cadastro.py](tests/test_cadastro.py), [tests/test_rotas_contas.py](tests/test_rotas_contas.py); roteiro, passos 3 e 6 |
| **RF02** · o administrador consulta e edita usuários, bloqueia e desbloqueia contas e vê os descumprimentos | `Administrador`, `Cliente.bloqueado`, `Cliente.descumprimentos` | [app/rotas/admin.py:131](app/rotas/admin.py#L131) (lista), [:146](app/rotas/admin.py#L146) (dados), [:165](app/rotas/admin.py#L165) (bloqueio), [app/administracao.py:56](app/administracao.py#L56), [:67](app/administracao.py#L67) | `test_rf02_lojista_consulta_e_edita_os_dados_do_cliente`, `test_rf02_lojista_bloqueia_e_desbloqueia_a_conta`; roteiro, passo 16 |
| **RF03** · o vendedor cadastra a carta e cria o leilão dela, com lance mínimo inicial, início e fim previsto | `Cliente.cadastrarCarta()`, `Cliente.criarLeilao()`, `Carta`, `Leilao`, `Jogo` | [app/dominio/contas.py:69](app/dominio/contas.py#L69) (`cadastrarCarta`), [:79](app/dominio/contas.py#L79) (`criarLeilao`), [app/anuncio.py:34](app/anuncio.py#L34), [app/rotas/anuncios.py:46](app/rotas/anuncios.py#L46), [app/catalogo/](app/catalogo/) (as quatro APIs), [buscar.html](app/templates/anuncios/buscar.html), [carta.html](app/templates/anuncios/carta.html) | [tests/test_criar_leilao.py](tests/test_criar_leilao.py): `test_busca_mostra_imagem_nome_codigo_edicao_e_especificacoes`, `test_filtro_de_jogo_busca_no_catalogo_daquele_jogo`, `test_criar_leilao_cadastra_a_carta_e_o_leilao_pendente`, `test_nome_edicao_e_foto_vem_do_catalogo_e_nao_do_formulario`; [tests/test_catalogo.py](tests/test_catalogo.py); `test_vendedor_cria_leilao_pelo_catalogo_e_ve_a_aprovacao_na_tela`; roteiro, passo 10 |
| **RF04** · o administrador edita os dados das cartas e remove cadastros inválidos | `Carta` | [app/rotas/admin.py:176](app/rotas/admin.py#L176) (lista), [:191](app/rotas/admin.py#L191) (edição), [:215](app/rotas/admin.py#L215) (remoção), [app/administracao.py:74](app/administracao.py#L74), [:101](app/administracao.py#L101) | `test_rf04_lojista_corrige_os_dados_da_carta`, `test_rf04_lojista_remove_cadastro_invalido_mas_nao_carta_com_leilao_em_andamento`; roteiro, passo 16 |
| **RF05** · o administrador aprova (registrando o depósito) ou recusa o leilão, com o motivo — **sem a notificação** | `Leilao.aprovar()`, `Leilao.recusar()`, `Leilao.motivoRecusa` | [app/rotas/admin.py:54](app/rotas/admin.py#L54), [:68](app/rotas/admin.py#L68), [app/administracao.py:30](app/administracao.py#L30), [:44](app/administracao.py#L44), [app/dominio/leiloes.py:192](app/dominio/leiloes.py#L192) | `test_lojista_ve_o_leilao_pendente_e_aprova`, `test_rf05_lojista_recusa_o_leilao_e_o_vendedor_ve_o_motivo`, `test_lojista_entra_aprova_o_leilao_e_percorre_a_administracao`; roteiro, passo 11. O motivo aparece para o vendedor em Vender; falta a notificação (RF23) |
| **RF06** · listagem de leilões ativos com filtro por jogo | `Leilao`, `Carta`, `Jogo` | [app/rotas/leiloes.py:41](app/rotas/leiloes.py#L41), [app/repositorios/leiloes.py:42](app/repositorios/leiloes.py#L42), [app/templates/leiloes.html](app/templates/leiloes.html), [jogo.html](app/templates/jogo.html), [_leiloes.html](app/templates/_leiloes.html) | `test_lista_mostra_os_leiloes_ativos…`, `test_lista_nao_mostra_leilao_encerrado…`, `test_pagina_do_jogo_lista_so_os_leiloes_ativos_dele`, `test_busca_do_topo_acha_pelo_nome_ou_pelo_codigo`; roteiro, passo 1 |
| **RF07** · lance de usuário logado em leilão em andamento | `Cliente.darLance()`, `Leilao`, `Lance` | [app/dominio/contas.py:52](app/dominio/contas.py#L52), [app/rotas/leiloes.py:133](app/rotas/leiloes.py#L133), [app/repositorios/leiloes.py:255](app/repositorios/leiloes.py#L255), [app/static/js/app.js:281](app/static/js/app.js#L281) (envio sem recarregar) | `test_lance_valido_e_gravado_e_o_minimo_recalculado`, `test_formulario_sem_javascript_tambem_aplica_as_regras`, `test_visitante_nao_da_lance`, `test_lance_atualiza_a_pagina_sem_recarregar`; roteiro, passos 4 e 5 |
| **RF08** · cronômetro e maior lance atual para todos | `Leilao.getMaiorLance()`, `Leilao.dataFimPrevista` | [app/apresentacao.py:142](app/apresentacao.py#L142), [app/static/js/app.js:326](app/static/js/app.js#L326) (atualização a cada 5 s) | `test_lance_de_outra_pessoa_aparece_e_e_anunciado`, `test_estado_json_traz_o_painel_e_a_tabela` |
| **RF09** · encerrar os lances quando o cronômetro zera e fixar o maior lance como vencedor | `Leilao.encerrar()`, `Leilao.status`, `Leilao.dataFimReal`, `Carta.atualizarStatus()`, `Transacao` | [app/dominio/leiloes.py:212](app/dominio/leiloes.py#L212) (`encerrar`), [app/dominio/financeiro.py:130](app/dominio/financeiro.py#L130) (`Transacao`), [app/andamento.py:16](app/andamento.py#L16) e [app/rotas/__init__.py:41](app/rotas/__init__.py#L41) (encerramento automático), [app/repositorios/leiloes.py:274](app/repositorios/leiloes.py#L274), [app/schema.sql:125](app/schema.sql#L125), [app/apresentacao.py:102](app/apresentacao.py#L102) (resultado), [app/rotas/minha_conta.py:78](app/rotas/minha_conta.py#L78) (Arremates) | [tests/test_encerramento.py](tests/test_encerramento.py): `test_encerrar_gera_o_arremate_para_o_maior_lance`, `test_leilao_e_encerrado_sozinho_quando_o_prazo_termina`, `test_leilao_sem_lances_encerra_sem_arremate…`, `test_quem_deu_o_maior_lance_arremata_e_ve_o_arremate_em_minha_conta`, `test_pedidos_simultaneos_geram_um_unico_arremate_por_leilao`; `test_leilao_encerra_na_tela_e_mostra_o_arremate_a_quem_venceu`; roteiro, passo 9 |
| **RF10** · ao encerrar, gerar o código de retirada e informar ao vencedor o valor e o prazo — **sem a notificação** | `Transacao.codigoRetirada`, `Transacao.prazoPagamento` | [app/dominio/financeiro.py:20](app/dominio/financeiro.py#L20), [app/dominio/leiloes.py:212](app/dominio/leiloes.py#L212), [app/apresentacao.py:237](app/apresentacao.py#L237) | `test_arremate_sai_com_taxa_valor_liquido_codigo_e_prazo`, `test_rf10_arremate_mostra_ao_vencedor_valor_prazo_e_codigo_de_retirada`. O vencedor vê tudo em Arremates e o vendedor em Vender; falta a notificação na central e por e-mail (RF23) |
| **RF11** · o vencedor paga com o saldo da carteira, por Pix ou cartão, ou com os dois | `Cliente.pagarArremate()`, `Transacao.confirmarPagamento()`, `Carteira.debitar()` | [app/pagamento.py:23](app/pagamento.py#L23), [:12](app/pagamento.py#L12) (gateway), [app/dominio/contas.py:93](app/dominio/contas.py#L93), [app/dominio/financeiro.py:152](app/dominio/financeiro.py#L152), [app/rotas/minha_conta.py:87](app/rotas/minha_conta.py#L87) | `test_rf11_comprador_paga_pelo_gateway_e_a_transacao_fica_paga`, `test_rf11_e_rn18_pagamento_usa_o_saldo_da_carteira_e_completa_no_gateway`, `test_rf11_pagamento_integral_com_saldo_dispensa_o_gateway`; roteiro, passo 13. O gateway é local e não cobra de verdade |
| **RF12** · o lojista registra a entrega com o código de retirada e o sistema faz o repasse | `Transacao.registrarEntrega()`, `Carteira.creditar()` | [app/rotas/admin.py:81](app/rotas/admin.py#L81), [app/administracao.py:141](app/administracao.py#L141), [app/dominio/financeiro.py:165](app/dominio/financeiro.py#L165) | `test_rf12_entrega_com_o_codigo_repassa_o_valor_liquido_ao_vendedor`, `test_rn07_entrega_exige_o_codigo_de_retirada_e_o_pagamento`; roteiro, passo 14 |
| **RF13** · taxa da loja e valor líquido do vendedor calculados a cada arremate | `Transacao.taxa`, `Transacao.valorLiquido`, `Leilao.taxaPercentual` | [app/dominio/leiloes.py:212](app/dominio/leiloes.py#L212), [app/dominio/financeiro.py:148](app/dominio/financeiro.py#L148) | `test_arremate_sai_com_taxa_valor_liquido_codigo_e_prazo`, `test_taxa_usa_o_percentual_gravado_no_leilao_e_arredonda_para_centavos` |
| **RF14** · status de cada carta para o vendedor — **parcial** | `Carta.status` | [app/dominio/leiloes.py:34](app/dominio/leiloes.py#L34), [app/apresentacao.py:91](app/apresentacao.py#L91), [app/rotas/anuncios.py:37](app/rotas/anuncios.py#L37), [meus_leiloes.html](app/templates/anuncios/meus_leiloes.html) | Feitos: aguardando depósito, recusada, aprovada, em leilão, arrematada, devolvida ao vendedor, paga e entregue. `test_vendedor_acompanha_a_carta_ate_o_arremate`, `test_rf12_entrega_com_o_codigo_repassa_o_valor_liquido_ao_vendedor`. **Faltam** cancelada (RF20) e reofertada (RF21) |
| **RF15** · o lojista configura taxa, incremento mínimo, prazo de pagamento e prazo de aceite da reoferta | `ConfiguracaoLoja` | [app/rotas/admin.py:258](app/rotas/admin.py#L258), [app/administracao.py:111](app/administracao.py#L111), [app/dominio/loja.py:9](app/dominio/loja.py#L9), [app/schema.sql:45](app/schema.sql#L45) | `test_rf15_e_rn17_configuracao_vale_para_os_leiloes_criados_depois`, `test_rf15_configuracao_invalida_nao_e_gravada`; roteiro, passo 12. O prazo da reoferta fica gravado, mas ainda não é usado |
| **RF16** · histórico dos leilões finalizados, com vencedor, valor, taxa, datas e desfecho | `Leilao`, `Transacao` | [app/rotas/admin.py:228](app/rotas/admin.py#L228), [app/administracao.py:177](app/administracao.py#L177) | `test_rf16_historico_lista_os_leiloes_finalizados_com_o_desfecho`; roteiro, passo 17. Sem o desfecho "reofertado" |
| **RF17** · carteira e extrato (só consulta) | `Carteira` (`saldo`, `gerarExtrato()`), `MovimentacaoCarteira` | [app/dominio/financeiro.py:68](app/dominio/financeiro.py#L68), [app/rotas/minha_conta.py:40](app/rotas/minha_conta.py#L40) | `test_carteira_mostra_saldo_zero_e_extrato_vazio`, `test_carteira_lista_as_movimentacoes_gravadas`, `test_gerar_extrato…` |
| **RF18** · extrato financeiro por período: arremates, taxas retidas, repasses e saques | `Transacao`, `Saque` | [app/rotas/admin.py:243](app/rotas/admin.py#L243), [app/administracao.py:188](app/administracao.py#L188) | `test_rf18_extrato_financeiro_soma_o_periodo`; roteiro, passo 17 |
| **RF19** · log das operações com usuário, operação, valor, IP e hora, consultado pelo administrador | `LogOperacao` | [app/rotas/comum.py:122](app/rotas/comum.py#L122), [app/repositorios/loja.py:38](app/repositorios/loja.py#L38), [app/rotas/admin.py:284](app/rotas/admin.py#L284), [app/schema.sql:147](app/schema.sql#L147) | `test_rf19_log_registra_usuario_operacao_valor_ip_e_hora`, `test_lance_recusado_nao_entra_no_log`; roteiro, passo 17 |
| **RF21** · prazo de pagamento vencido — **parcial** | `Transacao.expirar()`, `Cliente.registrarDescumprimento()` | [app/andamento.py:23](app/andamento.py#L23), [app/dominio/financeiro.py:176](app/dominio/financeiro.py#L176), [app/dominio/contas.py:104](app/dominio/contas.py#L104) | Feito: (a) o descumprimento e (c) a devolução da carta ao vendedor. `test_rf21_prazo_de_pagamento_vencido_marca_descumprimento_e_devolve_a_carta`. **Falta** (b), a reoferta ao segundo colocado, e as notificações |
| **RF22** · o cliente solicita o saque com a chave Pix; o lojista registra a transferência ou recusa | `Carteira.solicitarSaque()`, `Saque` | [app/rotas/minha_conta.py:46](app/rotas/minha_conta.py#L46), [app/rotas/admin.py:103](app/rotas/admin.py#L103), [:114](app/rotas/admin.py#L114), [app/administracao.py:161](app/administracao.py#L161), [app/dominio/financeiro.py:89](app/dominio/financeiro.py#L89) | `test_rf22_cliente_pede_saque_e_o_lojista_paga_ou_recusa`; roteiro, passo 15 |
| **RN01** · mínimo = lance inicial ou maior lance + incremento | `Leilao.calcularLanceMinimo()`, `Leilao.validarLance(valor)` | [app/dominio/leiloes.py:125](app/dominio/leiloes.py#L125), [:131](app/dominio/leiloes.py#L131) | [test_regras_lance.py:46–93](tests/test_regras_lance.py#L46): mínimo aceito, abaixo recusado, primeiro lance, mensagem; `test_primeiro_lance_usa_o_lance_inicial` |
| **RN02** · lance com menos de 3 min prorroga o fim em 3 min | `Leilao.dataFimPrevista` (`receberLance`, auxiliar) | [app/dominio/leiloes.py:173](app/dominio/leiloes.py#L173) | [test_regras_lance.py:174–198](tests/test_regras_lance.py#L174); `test_rn02_lance_nos_ultimos_3_minutos_prorroga_o_fim`; `test_rn02_prorrogacao_atualiza_o_cronometro` |
| **RN03** · lance irrevogável | `Lance` (imutável) | [app/dominio/leiloes.py:89](app/dominio/leiloes.py#L89), gatilhos em [app/schema.sql:114](app/schema.sql#L114) | `test_lance_registrado_nao_pode_ser_alterado`, `test_cliente_nao_reduz_o_proprio_lance`, `test_rn03_banco_recusa_alterar_ou_apagar_lance` |
| **RN04** · carta válida para leilão tem nome, jogo, edição, condição, lance mínimo inicial e fotos | `Cliente.cadastrarCarta()`, `Leilao.lanceInicial` | [app/dominio/contas.py:69](app/dominio/contas.py#L69), [app/anuncio.py:34](app/anuncio.py#L34) | `test_rn04_carta_sem_um_dado_obrigatorio_e_recusada`, `test_rn04_lance_minimo_inicial_tem_de_ser_maior_que_zero`, `test_dado_invalido_e_apontado_no_campo_e_nada_e_criado`, `test_pokemon_sem_imagem_no_catalogo_fica_fora_da_busca` |
| **RN05** · leilão com início e fim previsto | `Leilao.dataInicio`, `Leilao.dataFimPrevista` | [app/dominio/leiloes.py:111](app/dominio/leiloes.py#L111), [app/schema.sql:98](app/schema.sql#L98) | `test_rn05_fim_previsto_precisa_ser_depois_do_inicio`, `test_rn05_fim_previsto_tem_de_ser_depois_do_inicio_e_estar_no_futuro`, `test_rn05_datas_do_leilao_sao_conferidas` |
| **RN06** · prazo para pagar; vencido, descumprimento e reoferta — **parcial** | `Transacao.prazoPagamento`, `Transacao.expirar()` | [app/andamento.py:23](app/andamento.py#L23), [app/dominio/financeiro.py:176](app/dominio/financeiro.py#L176) | `test_rn06_arremate_nao_pago_no_prazo_expira_e_marca_descumprimento`. Sem a reoferta: a carta volta direto ao vendedor |
| **RN07** · a carta só é entregue com o código de retirada e a transação paga | `Transacao.registrarEntrega()` | [app/dominio/financeiro.py:165](app/dominio/financeiro.py#L165) | `test_rn07_entrega_exige_o_codigo_de_retirada_e_o_pagamento`, `test_rf12_entrega_com_o_codigo_repassa_o_valor_liquido_ao_vendedor` |
| **RN08** · o repasse acontece quando o lojista registra a entrega, e só aí | `Carteira.creditar()` | [app/administracao.py:141](app/administracao.py#L141) | `test_rf12_entrega_com_o_codigo_repassa_o_valor_liquido_ao_vendedor` (saldo zero antes da entrega, R$ 180,00 depois, e nada de novo ao repetir) |
| **RN09** · a taxa da loja incide sobre o valor final e sai do repasse | `Transacao.valorLiquido` | [app/dominio/financeiro.py:148](app/dominio/financeiro.py#L148) | `test_arremate_sai_com_taxa_valor_liquido_codigo_e_prazo` |
| **RN11** · sem lance no próprio leilão | `Cliente.darLance()` (vendedor da `Carta`) | [app/dominio/contas.py:52](app/dominio/contas.py#L52) | `test_vendedor_nao_da_lance_no_proprio_leilao` (domínio e HTTP), `test_rn11_vendedor_nao_da_lance_no_leilao_que_criou` |
| **RN12** · o leilão só entra em andamento com a carta depositada na loja e aprovada | `Leilao.status` (pendente → aprovado → ativo), `Leilao.iniciar()`, `Leilao.validarLance(valor)` | [app/dominio/leiloes.py:182](app/dominio/leiloes.py#L182) (`aprovar`), [:202](app/dominio/leiloes.py#L202) (`iniciar`), [:137](app/dominio/leiloes.py#L137) (só o ativo recebe lance), [app/andamento.py:10](app/andamento.py#L10), [app/administracao.py:30](app/administracao.py#L30) e [app/rotas/admin.py:54](app/rotas/admin.py#L54) (aprovação pelo lojista) | `test_rn12_leilao_so_entra_em_andamento_depois_de_aprovado`, `test_rn12_leilao_pendente_so_e_visto_pelo_vendedor`, `test_lojista_ve_o_leilao_pendente_e_aprova`, `test_leilao_aprovado_antes_do_inicio_fica_agendado_e_comeca_sozinho`; [test_regras_lance.py:103–133](tests/test_regras_lance.py#L103); `test_leilao_fora_do_prazo_nao_recebe_lance`, `test_leilao_que_nao_esta_ativo_nao_recebe_lance`; roteiro, passo 11 |
| **RN13** · empate: vale o lance registrado primeiro (ms) | `Leilao.getMaiorLance()` | [app/dominio/leiloes.py:117](app/dominio/leiloes.py#L117), transação `BEGIN IMMEDIATE` em [app/rotas/leiloes.py:147](app/rotas/leiloes.py#L147) | `test_empate_de_valor_vale_o_lance_registrado_primeiro`, `test_rn13_dois_lances_simultaneos_de_mesmo_valor_so_um_e_aceito`, `test_empate_de_valor_arremata_quem_deu_o_lance_primeiro` |
| **RN14** · só o administrador acessa as funções administrativas | `Administrador` | [app/rotas/comum.py:142](app/rotas/comum.py#L142), [app/dominio/contas.py:38](app/dominio/contas.py#L38) | `test_rn14_visitante_e_mandado_para_o_login`, `test_rn14_cliente_nao_acessa_as_telas_do_administrador`, `test_rnf07_cliente_nao_executa_acoes_do_administrador`, `test_administrador_nao_compra_nem_vende` |
| **RN15** · conta bloqueada não dá lance nem cria leilão | `Cliente.podeDarLance()`, `Cliente.criarLeilao()` | [app/dominio/contas.py:49](app/dominio/contas.py#L49), [:66](app/dominio/contas.py#L66), [app/rotas/anuncios.py:51](app/rotas/anuncios.py#L51) | [test_regras_lance.py:141–157](tests/test_regras_lance.py#L141); `test_cliente_bloqueado_nao_da_lance`; `test_rn15_conta_bloqueada_nao_cria_leilao`, `test_rn15_conta_bloqueada_nao_ve_a_busca_nem_cria_leilao`. Cancelar leilão (RF20) não existe ainda |
| **RN16** · saque só até o saldo disponível | `Carteira.solicitarSaque()`, `Carteira.disponivel` | [app/dominio/financeiro.py:89](app/dominio/financeiro.py#L89) | `test_rn16_e_rn19_saque_bloqueia_o_valor_ate_a_resposta_da_loja`, `test_rf22_cliente_pede_saque_e_o_lojista_paga_ou_recusa` |
| **RN17** · incremento e taxa da loja valem para os leilões criados depois da mudança | `Leilao.incrementoMinimo`, `Leilao.taxaPercentual`, `ConfiguracaoLoja` | [app/anuncio.py:85](app/anuncio.py#L85), [app/dominio/leiloes.py:19](app/dominio/leiloes.py#L19) (valores iniciais) | `test_rf15_e_rn17_configuracao_vale_para_os_leiloes_criados_depois`, `test_usa_o_incremento_gravado_no_leilao`, `test_criar_leilao_nasce_pendente_com_o_incremento_da_loja` |
| **RN18** · o saldo paga arremates, no todo ou em parte, e só é debitado na confirmação | `Cliente.pagarArremate()`, `Carteira.debitar()` | [app/dominio/contas.py:93](app/dominio/contas.py#L93), [app/pagamento.py:23](app/pagamento.py#L23) | `test_rn18_saldo_da_carteira_e_debitado_so_quando_o_pagamento_e_confirmado`, `test_rf11_e_rn18_pagamento_usa_o_saldo_da_carteira_e_completa_no_gateway` |
| **RN19** · o valor do saque fica bloqueado e volta ao saldo se o saque for recusado | `Carteira.bloqueado`, `Carteira.recusarSaque()` | [app/dominio/financeiro.py:110](app/dominio/financeiro.py#L110), [app/schema.sql:32](app/schema.sql#L32) | `test_rn16_e_rn19_saque_bloqueia_o_valor_ate_a_resposta_da_loja`, `test_rf22_cliente_pede_saque_e_o_lojista_paga_ou_recusa` |
| **RNF01** · leilão e área de lance responsivos | — | [app/static/css/app.css](app/static/css/app.css) (breakpoints em 1080, 1000, 900 e 767 px), [app/static/js/app.js:15](app/static/js/app.js#L15) (menu) | [tests/test_rnf01_responsivo.py](tests/test_rnf01_responsivo.py) → [evidencias/rnf01/](evidencias/rnf01/) |
| **RNF03** · dados persistentes em banco | todas as classes do escopo | [app/schema.sql](app/schema.sql), [app/repositorios/](app/repositorios/) | os testes de rotas gravam e releem pelo SQLite |
| **RNF04** · senha com hash, nunca em texto puro | `Usuario.senhaHash` | [app/dominio/senhas.py:15](app/dominio/senhas.py#L15) | `test_grava_so_o_hash_da_senha`, `test_hash_nao_contem_a_senha_e_tem_salt` |
| **RNF05** · implementado em Python | — | Flask + Jinja + SQLite | — |
| **RNF06** · LGPD (minimização de dados) | `Lance` → licitante anônimo; `Cliente.cpf` mascarado | [app/apresentacao.py:95](app/apresentacao.py#L95), [app/dominio/cpf.py](app/dominio/cpf.py) | `test_licitantes_aparecem_anonimizados`, `test_perfil_mostra_dados…_com_cpf_mascarado` |
| **RNF07** · autorização verificada no servidor | — | regras no domínio, chamadas em cada POST; CSRF em [app/rotas/__init__.py:32](app/rotas/__init__.py#L32); perfil de administrador em [app/rotas/comum.py:142](app/rotas/comum.py#L142); login exigido em [app/rotas/comum.py:129](app/rotas/comum.py#L129) | `test_lance_sem_token_csrf_e_recusado`, `test_exige_login`, `test_sair_exige_post_com_token`, `test_rnf07_cliente_nao_executa_acoes_do_administrador` |

## Classes do diagrama no código

Classes, atributos e métodos usam os nomes do diagrama (camelCase) para a rastreabilidade ficar direta.
Rotas, repositórios e templates seguem o padrão do Python (snake_case).

| Classe | Arquivo | Implementado | Fora da v2 (depende de classes fora do escopo) |
|---|---|---|---|
| `Usuario` (abstrata) | [app/dominio/contas.py:16](app/dominio/contas.py#L16) | todos os atributos; `autenticar()`. Não pode ser instanciada | `alterarSenha`, `atualizarPerfil`, `desativar` (sem telas no escopo) |
| `Administrador` | [app/dominio/contas.py:38](app/dominio/contas.py#L38) | herda de `Usuario`; entra com nome de usuário; as operações dele estão em [app/administracao.py](app/administracao.py) | métodos próprios do diagrama (não conferidos) |
| `Cliente` | [app/dominio/contas.py:43](app/dominio/contas.py#L43) | `cpf`, `bloqueado`, `descumprimentos`; `podeDarLance()`, `darLance()`, `cadastrarCarta()`, `criarLeilao()`, `pagarArremate()`, `registrarDescumprimento()`; Carteira composta (1:1) | — |
| `Jogo` | [app/dominio/leiloes.py:64](app/dominio/leiloes.py#L64) | `id`, `nome`; 1 Jogo → 0..* Carta | — |
| `Carta` | [app/dominio/leiloes.py:70](app/dominio/leiloes.py#L70) | todos os atributos, `fotos` como lista; `adicionarFoto()`, `atualizarStatus()`; Cliente 1 → 0..* Carta | `estaDisponivel` |
| `Leilao` | [app/dominio/leiloes.py:97](app/dominio/leiloes.py#L97) | todos os atributos; `calcularLanceMinimo()`, `validarLance()`, `getMaiorLance()`, `iniciar()`, `encerrar()`; Carta 1 → 0..* Leilao; composição com Lance; Leilao 1 → 0..1 Transacao | `reofertarSegundoColocado`, `cancelar` |
| `Lance` | [app/dominio/leiloes.py:89](app/dominio/leiloes.py#L89) | `id`, `valor`, `dataHora`; Cliente 1 → 0..* Lance | — |
| `Carteira` | [app/dominio/financeiro.py:55](app/dominio/financeiro.py#L55) | `id`, `saldo`, `bloqueado`; `gerarExtrato()`, `creditar()`, `debitar()`, `possuiSaldo()`, `solicitarSaque()`; composição com MovimentacaoCarteira e Saque | — |
| `MovimentacaoCarteira` | [app/dominio/financeiro.py:29](app/dominio/financeiro.py#L29) | todos os atributos | — |
| `Transacao` | [app/dominio/financeiro.py:130](app/dominio/financeiro.py#L130) | `valor`, `taxa`, `valorLiquido`, `codigoRetirada`, `prazoPagamento`, `dataPagamento`, `dataEntrega`, `status`; `confirmarPagamento()`, `registrarEntrega()`, `expirar()`; comprador e vendedor (`Cliente`) | reoferta; atributos escolhidos sem o diagrama |
| `Saque` | [app/dominio/financeiro.py:45](app/dominio/financeiro.py#L45) | `valor`, `chavePix`, `dataSolicitacao`, `status`, `dataResposta` | — |
| `ConfiguracaoLoja` | [app/dominio/loja.py:9](app/dominio/loja.py#L9) | `taxaPercentual`, `incrementoMinimo`, `prazoPagamentoHoras`, `prazoReofertaHoras` | — |
| `LogOperacao` | [app/dominio/loja.py:30](app/dominio/loja.py#L30) | `usuarioId`, `operacao`, `valor`, `ip`, `dataHora`, `detalhe` | — |

**Tipos:** BigDecimal é `decimal.Decimal` com duas casas (no banco, centavos inteiros); DateTime é
`datetime` em UTC com milissegundos; Date é `date`.

**Métodos auxiliares, fora do diagrama:**
- `Leilao.estaAberto` (status ativo e dentro do prazo);
- `Leilao.motivoDeRecusa` e `Leilao.explicarRecusa` (qual regra o valor viola e a mensagem para a tela);
- `Leilao.receberLance` (o "recebe" da composição, que aplica a RN02);
- `Usuario.ehOMesmo` (a mesma pessoa, ainda que carregada em objetos diferentes);
- `Leilao.aprovar` e `Leilao.recusar` (a decisão da loja, RF05), `Cliente.podeCriarLeilao` (RN15) e
  `Carteira.pagarSaque`/`recusarSaque` (a resposta do lojista ao saque, RF22).

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
| Navegação | menu lateral com 12 itens desabilitados de telas futuras | topo fixo com o título, a busca (jogo e nome ou código da carta), Meus lances e Entrar/Criar conta ou Minha Conta; o menu recolhe no celular |
| Lista | leilões em andamento e agendados | só ativos, na página inicial, na busca e na página de cada jogo |
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
- **Encerramento automático:** não há um processo agendado. Antes de atender qualquer pedido, o servidor
  encerra os leilões ativos cujo prazo terminou ([app/rotas/__init__.py:40](app/rotas/__init__.py#L40)),
  então nenhuma tela mostra como ativo um leilão vencido. `dataFimReal` e a data do arremate recebem o
  instante em que o prazo terminou, não o do processamento. O encerramento roda numa transação
  `BEGIN IMMEDIATE` que relê os leilões com o banco travado: um lance que prorrogou o prazo (RN02) adia o
  encerramento, e dois pedidos simultâneos geram um único arremate (há ainda `UNIQUE` em `transacoes.leilao_id`).
- **Arremate:** vence o maior lance; no empate, o registrado primeiro (RN13). O leilão sem lances é
  encerrado sem arremate e a carta fica "devolvida ao vendedor". O arremate já sai com a taxa da loja, o
  valor líquido do vendedor, o código de retirada e o prazo de pagamento.
- **Catálogo de cartas:** quem cria o leilão não digita os dados da carta: escolhe a carta no catálogo do
  jogo. As fontes são o TCGdex (Pokémon), o Scryfall (Magic), o YGOPRODeck (Yu-Gi-Oh!) e a OPTCG API
  (One Piece). A pokemontcg.io, de onde vieram as fotos da carga inicial, respondia com erro a buscas com
  mais de uma palavra ("dark charizard"), por isso a busca de Pokémon usa o TCGdex. O formulário envia só o
  jogo e o identificador da carta; o servidor busca de novo no catálogo o nome, a edição e a imagem, então
  ninguém cadastra uma carta com dados alterados no navegador. O servidor só fala com os endereços dessas
  APIs ([app/catalogo/http.py](app/catalogo/http.py)).
- **Sugestões e filtro:** ao escolher o jogo, a tela já mostra os lançamentos recentes dele, que ficam
  guardados por seis horas para não consultar a API a cada visita. O filtro consulta o catálogo inteiro do
  jogo, não só as sugestões. Em Pokémon o código é o número da carta e o total da coleção (`90/112`); em
  One Piece, o código da carta ou o começo dele (`OP02`, `OP02-025`). Magic e Yu-Gi-Oh! filtram só pelo nome.
- **Valor médio de mercado:** vem da mesma API da carta e aparece no formulário na moeda de origem, sem
  conversão para reais: o preço de mercado do TCGplayer, em dólares, e, quando ele falta, o do Cardmarket,
  em euros. É só uma referência: não entra no leilão, e o formulário abre mesmo sem ele.
- **Página inicial, busca e página de jogo:** a página inicial, a busca (`/leiloes`) e a página de cada
  jogo (`/jogos/<slug>`) usam a mesma lista ([_leiloes.html](app/templates/_leiloes.html)). A busca do topo
  procura no nome da carta e no código, que é o trecho entre parênteses da edição; o nome da coleção fica
  de fora, para "dragon" não trazer as cartas da "Legend of Blue Eyes White Dragon". Os jogos são os do
  catálogo, por isso One Piece aparece mesmo sem leilão. A página de jogo já tem o lugar do painel de
  filtros próprio de cada jogo: basta criar o template e registrá-lo em `FILTROS_POR_JOGO`
  ([app/rotas/leiloes.py](app/rotas/leiloes.py)); nenhum filtro foi implementado ainda.
- **Capas dos jogos:** são recortes quadrados da arte de uma carta de cada jogo, em
  `app/static/img/jogos/<slug>.webp`. Três vêm das fotos da carga inicial; a de One Piece vem da imagem
  oficial da carta OP01-003 em onepiece-cardgame.com, recortada acima da marca "SAMPLE". Um jogo sem
  arquivo de capa aparece só com o nome.
- **Imagens do catálogo:** a imagem grande é baixada e vira a foto da carta (`instance/fotos/`); as
  miniaturas da busca são baixadas uma vez e servidas pela loja (`instance/catalogo/`). Nenhuma página
  aponta direto para os sites das APIs, o que o YGOPRODeck exige. Em Yu-Gi-Oh! a API devolve a carta com
  todas as edições em que saiu, e o vendedor escolhe a sua.
- **Aprovação da loja (RN12):** o leilão nasce "pendente", visível só para o vendedor e para o
  administrador. O lojista aprova (o que registra o depósito) ou recusa com um motivo, em
  **Administração › Leilões**. O leilão aprovado começa sozinho na data de início; se a aprovação sair
  depois dela, começa na aprovação.
- **Data de início:** o formulário vem preenchido com o horário em que foi aberto, e um início até 15
  minutos no passado é aceito, para não barrar quem demora a preencher.
- **Administrador (RN14):** é um `Usuario` de outro tipo, não um cliente com permissão a mais: não compra,
  não vende e não tem carteira. Entra com um nome de usuário, guardado no campo de e-mail. Toda rota de
  `/admin` confere o perfil no servidor; cliente recebe 403 e visitante vai para o login.
- **Pagamento (RF11):** o saldo da carteira e o gateway podem ser combinados. O gateway é um objeto local
  ([app/pagamento.py](app/pagamento.py)) que confirma na hora, sem cobrar; para cobrar de verdade troca-se
  só esse objeto. As regras são conferidas antes da cobrança, e o saldo só é debitado com o pagamento
  confirmado (RN18).
- **Entrega e repasse:** o código de retirada tem 8 caracteres, sem os que se confundem ao ditar (I, L, O,
  0 e 1). A lista de cartas pagas não mostra o código: só quem o apresenta retira a carta. O repasse do
  valor líquido acontece dentro do registro da entrega, na mesma transação do banco (RN08).
- **Prazo de pagamento sem reoferta:** vencido o prazo, o sistema marca o descumprimento e devolve a carta
  ao vendedor. A reoferta ao segundo colocado (RF21) não foi feita; o prazo de aceite dela já é
  configurável, mas ainda não tem efeito.
- **Log de auditoria (RF19):** cada operação de cliente ou do lojista grava usuário, valor, IP e hora. O
  que o sistema faz sozinho (iniciar, encerrar, expirar) entra sem usuário e sem IP. Lance recusado não
  entra no log.
- **Erro e sucesso sem cores novas:** a paleta é monocromática; o estado é dito por ícone, texto e borda (ver DESIGN.md).
- **Fotos:** cada carta tem três fotos (frente, detalhe da arte e detalhe do canto), recortadas da imagem
  em alta resolução e normalizadas na proporção 63:88.
- **Lance e carteira:** o lance não consulta o saldo da Carteira, como no diagrama (há um teste para isso).

## Referências de design e usabilidade

Diretrizes de interface e boas práticas de acessibilidade e usabilidade aplicadas no projeto.
O diagnóstico, o plano e a referência visual aprovados estão em
[docs/v2/etapa1-plano.md](docs/v2/etapa1-plano.md) e [docs/v2/referencia/](docs/v2/referencia/). A auditoria
das telas novas e a validação do RNF01 estão em [evidencias/auditoria-interface.md](evidencias/auditoria-interface.md).

## Créditos das imagens

As imagens das cartas são marcas e propriedade das respectivas editoras (The Pokémon Company, Wizards of
the Coast, Konami e Bandai). Foram usadas aqui só como exemplo das fotos que um vendedor enviaria, em um projeto
acadêmico sem fins comerciais. Fontes: [pokemontcg.io](https://pokemontcg.io), [TCGdex](https://tcgdex.dev),
[Scryfall](https://scryfall.com), [YGOPRODeck](https://ygoprodeck.com) e [OPTCG API](https://optcgapi.com). A fonte Inter (SIL Open Font License) é servida localmente.
