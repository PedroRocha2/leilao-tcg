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
RF21), reoferta ao segundo colocado (RF21) e o filtro por tempo restante (RF06). O único e-mail
que a loja manda é o do código de retirada, quando o pagamento do arremate é confirmado. O pagamento é
cobrado pelo Mercado Pago quando a credencial dele está configurada; sem ela, um gateway local confirma na
hora e não cobra de verdade. As classes Deposito, Pagamento, Retirada e Notificacao do diagrama não foram criadas: o depósito,
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
leilão e os lances de outros clientes, com prazos contados a partir daquele momento. Um banco da versão 4
do esquema é atualizado sozinho para a versão atual, sem perder contas, leilões nem carteiras; um banco mais
antigo que isso é recriado. Para recomeçar, com os prazos contados a partir de agora e sem nenhuma conta criada:

```bash
flask --app run reiniciar-dados
```

Criar leilão consulta as APIs públicas de cartas e por isso precisa de internet.

### Administrador

A conta do lojista é criada junto com o banco: usuário **`admin-jiujitsu`**, senha **`osscachorro`**.
Entre com esses dados na tela **Entrar** para abrir a **Administração**. Para usar outros, defina as
variáveis de ambiente `LEILAO_ADMIN_LOGIN` e `LEILAO_ADMIN_SENHA` antes da primeira execução ou antes
de `reiniciar-dados`. Como a senha padrão está neste repositório, troque-a antes de qualquer uso real.

### Mercado Pago (RF11)

Sem configuração nenhuma, o pagamento do arremate usa o gateway local, que confirma na hora e não cobra
ninguém. Para cobrar pelo Mercado Pago (Checkout Pro, com Pix e cartão):

1. Crie uma aplicação em <https://www.mercadopago.com.br/developers/panel/app> e copie o **Access Token**.
   Para testar sem dinheiro de verdade, use as credenciais de teste da aplicação e pague com uma conta de
   teste de comprador, em uma janela anônima.
2. Defina a variável de ambiente antes de subir a loja:

   ```powershell
   $env:MERCADOPAGO_ACCESS_TOKEN = "APP_USR-..."       # Linux/macOS: export MERCADOPAGO_ACCESS_TOKEN=...
   flask --app run run
   ```

3. Opcional, mas recomendado: informe o endereço **https** pelo qual a internet alcança a loja (em
   desenvolvimento, o de um túnel como `ngrok http 5000`):

   ```powershell
   $env:LEILAO_URL_PUBLICA = "https://sua-loja.exemplo.com"
   ```

   Com ele, o Mercado Pago devolve o comprador para a loja depois do pagamento e avisa a loja em
   `/pagamentos/mercado-pago` (webhook), que é o que confirma um Pix pago com o navegador já fechado. Sem
   ele (o Mercado Pago não aceita `localhost` nem `http`), o comprador paga em outra aba e clica em **Já
   paguei: conferir pagamento**.

A credencial fica só na variável de ambiente: não entra no repositório nem no banco.

### E-mail do código de retirada

Sem configuração nenhuma, a loja não manda e-mail: o código de retirada aparece só em **Minha Conta ›
Arremates**. Com um servidor SMTP configurado, o comprador também recebe o código por e-mail assim que o
pagamento do arremate é confirmado. Com uma conta do Gmail, que é gratuita:

1. Ative a verificação em duas etapas da conta e crie uma **senha de app** em
   <https://myaccount.google.com/apppasswords>. A senha normal da conta não funciona.
2. Defina as variáveis de ambiente antes de subir a loja:

   ```powershell
   $env:LEILAO_SMTP_SERVIDOR = "smtp.gmail.com"
   $env:LEILAO_SMTP_USUARIO = "sua-loja@gmail.com"
   $env:LEILAO_SMTP_SENHA = "a senha de app"
   flask --app run run
   ```

| Variável | Para que serve |
|---|---|
| `LEILAO_SMTP_SERVIDOR` | endereço do servidor SMTP; é ela que liga o envio |
| `LEILAO_SMTP_PORTA` | porta; o padrão é `587` (STARTTLS), e `465` abre a conexão já cifrada |
| `LEILAO_SMTP_USUARIO`, `LEILAO_SMTP_SENHA` | a conta que envia; a senha só vai por conexão cifrada |
| `LEILAO_EMAIL_REMETENTE` | o remetente que o cliente vê, como `Leilão TCG <sua-loja@gmail.com>`; o padrão é o usuário |

Se o servidor de e-mail falhar, o pagamento continua valendo e a falha fica no log da aplicação. Com
`LEILAO_URL_PUBLICA` definida, o e-mail leva também o endereço de Arremates.

### Testes

```bash
pytest                                  # 617 testes
pytest tests/test_regras_lance.py -v    # só as regras do lance (unitários do domínio)
pytest tests/test_rnf01_responsivo.py   # RNF01 no navegador; gera evidencias/rnf01/
```

| Arquivo | Testes | O que cobre |
|---|---|---|
| [tests/test_regras_lance.py](tests/test_regras_lance.py) | 39 | RN01, RN02, RN03, RN05, RN11, RN12, RN13, RN15 e RN17 no domínio |
| [tests/test_dominio_contas.py](tests/test_dominio_contas.py) | 33 | Usuario abstrata, Cliente, `autenticar()`, hash de senha, CPF e Carteira |
| [tests/test_dinheiro.py](tests/test_dinheiro.py) | 24 | leitura e formatação de valores em reais |
| [tests/test_cadastro.py](tests/test_cadastro.py) | 20 | criar conta: e-mail e CPF únicos, dígitos do CPF, senha ≥ 8, valores iniciais, carteira 1:1 |
| [tests/test_admin.py](tests/test_admin.py) | 82 | área do administrador (RF02, RF04, RF05, RF12, RF15, RF16, RF18, RF19, RF22), acesso por perfil (RN14), pagamento (RF11), código de retirada, repasse, saque e descumprimento |
| [tests/test_criar_leilao.py](tests/test_criar_leilao.py) | 84 | `cadastrarCarta()`, `criarLeilao()`, RN04, RN05, RN12 e RN15; sugestões, filtro pelo nome e pelo código e formulário de Vender, com o valor médio de mercado; aprovação pelo lojista; da criação ao arremate |
| [tests/test_filtros.py](tests/test_filtros.py) | 53 | filtros pelas características das cartas dos quatro jogos: o que cada jogo filtra, os atributos tirados das especificações, o que vai para cada API, a página do jogo (opções com total, combinação de filtros, busca junto), a busca de Criar leilão e a atualização de um banco antigo |
| [tests/test_fotos_do_vendedor.py](tests/test_fotos_do_vendedor.py) | 20 | fotos que o vendedor anexa ao criar o leilão: formato conferido pelo conteúdo, limites de quantidade e tamanho, gravação depois da imagem do catálogo, conferência pelo lojista, galeria do anúncio e remoção |
| [tests/test_mercado_pago.py](tests/test_mercado_pago.py) | 31 | pagamento pelo Mercado Pago com a API simulada (sem rede): cobrança aberta, volta do comprador, aviso (webhook), conferência pelo botão, saldo + gateway (RN18), pagamento repetido, fora do prazo ou no valor errado, gateway fora do ar, e-mail do código de retirada na confirmação |
| [tests/test_correio.py](tests/test_correio.py) | 12 | e-mail do código de retirada com o servidor SMTP simulado (sem rede): enviado ao comprador quando o pagamento é confirmado, uma vez só; falha do envio não desfaz o pagamento; conexão cifrada, senha e remetente; assunto sem quebra de linha |
| [tests/test_cancelar_leilao.py](tests/test_cancelar_leilao.py) | 17 | `Leilao.cancelar()` e o cancelamento pelo vendedor em Vender (RF20): sem lances cancela; com lance, encerrado ou de outro vendedor, não. A exclusão do leilão cancelado: apaga carta, fotos e leilão; não vale para leilão recusado, ativo ou de outro vendedor |
| [tests/test_catalogo.py](tests/test_catalogo.py) | 82 | as quatro APIs de cartas com respostas gravadas (sem rede): nome, código, edição, especificações, imagem e preço; sugestões; busca pelo código (Pokémon e One Piece); falhas; endereços permitidos |
| [tests/test_encerramento.py](tests/test_encerramento.py) | 28 | `Leilao.encerrar()`, encerramento automático, arremate (`Transacao`), resultado nas telas, concorrência |
| [tests/test_rotas_leiloes.py](tests/test_rotas_leiloes.py) | 46 | página inicial, busca do topo pelo nome ou código, página de cada jogo, página do leilão, lance por JSON e por formulário, concorrência |
| [tests/test_rotas_contas.py](tests/test_rotas_contas.py) | 11 | cadastro, login, sessão (amarrada à conta), sair, redirecionamento seguro |
| [tests/test_minha_conta.py](tests/test_minha_conta.py) | 8 | Perfil, Carteira e Meus lances (Arremates está em `test_encerramento.py`) |
| [tests/test_interface.py](tests/test_interface.py) | 11 | navegador: página inicial ("Quero comprar", jogos e busca do topo), abas, galeria, lance sem recarregar, lance de outra pessoa, RN02, leilão que encerra na tela, criar leilão pelo catálogo, vendedor cancelando o leilão, lojista aprovando e percorrendo a administração, lojista confirmando a entrega pelo card |
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
    recentes) já aparecem. Ao lado fica o painel **Filtros**, o mesmo da página de leilões do jogo, com as
    características das cartas daquele jogo (em One Piece: cor, tipo de carta, custo, poder, atributo e
    raridade; em Pokémon: categoria, tipo, estágio e raridade; em Magic: cor, tipo e raridade; em Yu-Gi-Oh!:
    tipo de carta, atributo, tipo e nível): marque quantas opções quiser e as cartas mudam, com ou sem nome
    digitado. Digite no filtro o nome em inglês, como
    `charizard`, e as cartas mudam enquanto
    você digita. Em Pokémon e One Piece o filtro também acha pelo código impresso na carta, como `90/112` e
    `OP02-025`. Cada carta traz a imagem, o nome, a edição, o código e as especificações que a API do jogo
    devolve. Escolha uma carta: o formulário mostra o **valor médio de mercado** dela, em dólares ou euros,
    como referência. Informe a condição, o lance mínimo inicial e o período, anexe em **Fotos da sua carta**
    até 6 fotos (frente, verso, cantos) e clique em **Criar leilão**. As fotos são opcionais; as de celular
    são reduzidas no navegador antes do envio. Em Yu-Gi-Oh! o formulário também pede a edição, porque a mesma carta sai em várias. Teste as recusas:
    lance `0`, fim antes do início.
11. **Aprovação da loja (RF05, RN12):** a carta aparece em **Vender** como "Aguardando depósito" e ainda não
    está na lista de leilões. Saia da conta e entre como `admin-jiujitsu` / `osscachorro`. Em
    **Administração › Leilões**, o card do leilão mostra as **fotos tiradas pelo vendedor** (clique em uma
    para abri-la inteira) ao lado dos dados da carta. Clique em **Aprovar e registrar depósito**: o leilão
    entra na lista, e a página dele mostra a imagem do catálogo seguida das fotos do vendedor. Para ver
    a recusa, crie outro leilão e recuse com um motivo; o vendedor lê o motivo em **Vender**. O administrador
    não dá lances; a conta que criou o leilão também não (RN11). **Cancelamento (RF20):** como vendedor, em
    **Vender**, um leilão que ainda não recebeu lances tem o botão **Cancelar leilão**, que pede uma
    confirmação; a carta fica "Cancelada" e o leilão sai da lista. Depois do primeiro lance, o botão some.
12. **Configurações (RF15, RN17):** em **Administração › Configurações**, mude a taxa para `12,5` e o
    incremento para `10,00`. Um leilão criado depois sai com o incremento novo; os que já existiam continuam
    com R$ 5,00.
13. **Pagamento (RF11):** com uma segunda conta de cliente, dê um lance no leilão aprovado e espere o
    fim do prazo (use um fim próximo ao criar o leilão). Em **Minha Conta › Arremates** aparecem o valor e o
    prazo de pagamento. Clique em **Pagar**, escolha Pix ou cartão e confirme: só então aparece o **código
    de retirada**. Com o Mercado Pago configurado (seção **Mercado Pago**), **Pagar** abre a cobrança e leva
    à página do Mercado Pago; o arremate fica pago quando ele confirma, e o código aparece em seguida. Com
    o servidor de e-mail configurado (seção **E-mail do código de retirada**), o código chega também no
    e-mail da conta que pagou.
14. **Entrega e repasse (RF12, RF13):** como administrador, a página **Leilões** mostra um card **Entrega
    pendente** para cada carta paga (a aba **Entregas** lista os mesmos cards). Clique no card: a página
    mostra o comprador, o valor, a taxa da loja e o repasse, e pede o código de retirada que o comprador
    apresenta. Com um código errado, nada é registrado (RN07). Com o código certo, **Confirmar entrega e
    repassar ao vendedor** credita o valor líquido na carteira do vendedor e o card some.
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
| **RF01** · cadastro e autenticação de clientes | `Usuario` (`senhaHash`, `dataCadastro`, `ativo`, `autenticar()`), `Cliente` (`cpf`, `bloqueado`, `descumprimentos`), `Carteira` | [app/cadastro.py:49](app/cadastro.py#L49), [app/rotas/contas.py:28](app/rotas/contas.py#L28) (criar), [:57](app/rotas/contas.py#L57) (entrar), [:82](app/rotas/contas.py#L82) (sair), [app/dominio/contas.py:31](app/dominio/contas.py#L31) (`autenticar`), [app/repositorios/clientes.py:22](app/repositorios/clientes.py#L22) | [tests/test_cadastro.py](tests/test_cadastro.py), [tests/test_rotas_contas.py](tests/test_rotas_contas.py); roteiro, passos 3 e 6 |
| **RF02** · o administrador consulta e edita usuários, bloqueia e desbloqueia contas e vê os descumprimentos | `Administrador`, `Cliente.bloqueado`, `Cliente.descumprimentos` | [app/rotas/admin.py:141](app/rotas/admin.py#L141) (lista), [:156](app/rotas/admin.py#L156) (dados), [:175](app/rotas/admin.py#L175) (bloqueio), [app/administracao.py:56](app/administracao.py#L56), [:67](app/administracao.py#L67) | `test_rf02_lojista_consulta_e_edita_os_dados_do_cliente`, `test_rf02_lojista_bloqueia_e_desbloqueia_a_conta`; roteiro, passo 16 |
| **RF03** · o vendedor cadastra a carta e cria o leilão dela, com lance mínimo inicial, início e fim previsto | `Cliente.cadastrarCarta()`, `Cliente.criarLeilao()`, `Carta`, `Leilao`, `Jogo` | [app/dominio/contas.py:70](app/dominio/contas.py#L70) (`cadastrarCarta`), [:81](app/dominio/contas.py#L81) (`criarLeilao`), [app/anuncio.py:66](app/anuncio.py#L66), [app/rotas/anuncios.py:49](app/rotas/anuncios.py#L49), [app/catalogo/](app/catalogo/) (as quatro APIs), [buscar.html](app/templates/anuncios/buscar.html), [carta.html](app/templates/anuncios/carta.html); fotos do vendedor em [app/anuncio.py:39](app/anuncio.py#L39) e [app/static/js/app.js:440](app/static/js/app.js#L440) | [tests/test_criar_leilao.py](tests/test_criar_leilao.py): `test_busca_mostra_imagem_nome_codigo_edicao_e_especificacoes`, `test_filtro_de_jogo_busca_no_catalogo_daquele_jogo`, `test_criar_leilao_cadastra_a_carta_e_o_leilao_pendente`, `test_nome_edicao_e_foto_vem_do_catalogo_e_nao_do_formulario`; [tests/test_catalogo.py](tests/test_catalogo.py); `test_vendedor_cria_leilao_pelo_catalogo_e_ve_a_aprovacao_na_tela`; [tests/test_fotos_do_vendedor.py](tests/test_fotos_do_vendedor.py): `test_fotos_do_vendedor_sao_gravadas_depois_da_imagem_do_catalogo`, `test_anuncio_mostra_a_imagem_do_catalogo_e_as_fotos_do_vendedor`; roteiro, passo 10 |
| **RF04** · o administrador edita os dados das cartas e remove cadastros inválidos | `Carta` | [app/rotas/admin.py:186](app/rotas/admin.py#L186) (lista), [:201](app/rotas/admin.py#L201) (edição), [:225](app/rotas/admin.py#L225) (remoção), [app/administracao.py:74](app/administracao.py#L74), [:101](app/administracao.py#L101) | `test_rf04_lojista_corrige_os_dados_da_carta`, `test_rf04_lojista_remove_cadastro_invalido_mas_nao_carta_com_leilao_em_andamento`; roteiro, passo 16 |
| **RF05** · o administrador aprova (registrando o depósito) ou recusa o leilão, com o motivo — **sem a notificação** | `Leilao.aprovar()`, `Leilao.recusar()`, `Leilao.motivoRecusa` | [app/rotas/admin.py:55](app/rotas/admin.py#L55), [:69](app/rotas/admin.py#L69), [app/administracao.py:30](app/administracao.py#L30), [:44](app/administracao.py#L44), [app/dominio/leiloes.py:194](app/dominio/leiloes.py#L194) | `test_lojista_ve_o_leilao_pendente_e_aprova`, `test_rf05_lojista_recusa_o_leilao_e_o_vendedor_ve_o_motivo`, `test_lojista_entra_aprova_o_leilao_e_percorre_a_administracao`; roteiro, passo 11. O motivo aparece para o vendedor em Vender; falta a notificação (RF23) |
| **RF06** · listagem de leilões ativos com filtro por jogo | `Leilao`, `Carta`, `Jogo` | [app/rotas/leiloes.py:37](app/rotas/leiloes.py#L37), [app/repositorios/leiloes.py:42](app/repositorios/leiloes.py#L42), [app/templates/leiloes.html](app/templates/leiloes.html), [jogo.html](app/templates/jogo.html), [_leiloes.html](app/templates/_leiloes.html) | `test_lista_mostra_os_leiloes_ativos…`, `test_lista_nao_mostra_leilao_encerrado…`, `test_pagina_do_jogo_lista_so_os_leiloes_ativos_dele`, `test_busca_do_topo_acha_pelo_nome_ou_pelo_codigo`; filtros pelas características das cartas na página de cada jogo: [app/rotas/leiloes.py:50](app/rotas/leiloes.py#L50), [app/repositorios/leiloes.py:61](app/repositorios/leiloes.py#L61), [app/catalogo/base.py](app/catalogo/base.py) (`Filtro`), [app/schema_v6.sql](app/schema_v6.sql), [tests/test_filtros.py](tests/test_filtros.py): `test_filtros_da_pagina_do_jogo`, `test_painel_mostra_so_as_opcoes_que_algum_leilao_ativo_tem_com_o_total`; roteiro, passo 1 |
| **RF07** · lance de usuário logado em leilão em andamento | `Cliente.darLance()`, `Leilao`, `Lance` | [app/dominio/contas.py:53](app/dominio/contas.py#L53), [app/rotas/leiloes.py:131](app/rotas/leiloes.py#L131), [app/repositorios/leiloes.py:274](app/repositorios/leiloes.py#L274), [app/static/js/app.js:285](app/static/js/app.js#L285) (envio sem recarregar) | `test_lance_valido_e_gravado_e_o_minimo_recalculado`, `test_formulario_sem_javascript_tambem_aplica_as_regras`, `test_visitante_nao_da_lance`, `test_lance_atualiza_a_pagina_sem_recarregar`; roteiro, passos 4 e 5 |
| **RF08** · cronômetro e maior lance atual para todos | `Leilao.getMaiorLance()`, `Leilao.dataFimPrevista` | [app/apresentacao.py:152](app/apresentacao.py#L152), [app/static/js/app.js:330](app/static/js/app.js#L330) (atualização a cada 5 s) | `test_lance_de_outra_pessoa_aparece_e_e_anunciado`, `test_estado_json_traz_o_painel_e_a_tabela` |
| **RF09** · encerrar os lances quando o cronômetro zera e fixar o maior lance como vencedor | `Leilao.encerrar()`, `Leilao.status`, `Leilao.dataFimReal`, `Carta.atualizarStatus()`, `Transacao` | [app/dominio/leiloes.py:236](app/dominio/leiloes.py#L236) (`encerrar`), [app/dominio/financeiro.py:126](app/dominio/financeiro.py#L126) (`Transacao`), [app/andamento.py:16](app/andamento.py#L16) e [app/rotas/__init__.py:46](app/rotas/__init__.py#L46) (encerramento automático), [app/repositorios/leiloes.py:293](app/repositorios/leiloes.py#L293), [app/schema.sql:125](app/schema.sql#L125), [app/apresentacao.py:111](app/apresentacao.py#L111) (resultado), [app/rotas/minha_conta.py:82](app/rotas/minha_conta.py#L82) (Arremates) | [tests/test_encerramento.py](tests/test_encerramento.py): `test_encerrar_gera_o_arremate_para_o_maior_lance`, `test_leilao_e_encerrado_sozinho_quando_o_prazo_termina`, `test_leilao_sem_lances_encerra_sem_arremate…`, `test_quem_deu_o_maior_lance_arremata_e_ve_o_arremate_em_minha_conta`, `test_pedidos_simultaneos_geram_um_unico_arremate_por_leilao`; `test_leilao_encerra_na_tela_e_mostra_o_arremate_a_quem_venceu`; roteiro, passo 9 |
| **RF10** · ao encerrar, gerar o código de retirada e informar ao vencedor o valor e o prazo — **sem a notificação** | `Transacao.codigoRetirada`, `Transacao.prazoPagamento` | [app/dominio/financeiro.py:20](app/dominio/financeiro.py#L20), [app/dominio/leiloes.py:236](app/dominio/leiloes.py#L236), [app/apresentacao.py:247](app/apresentacao.py#L247) | `test_arremate_sai_com_taxa_valor_liquido_codigo_e_prazo`, `test_rf10_arremate_mostra_ao_vencedor_valor_e_prazo_e_o_codigo_de_retirada_so_depois_de_pagar`. O código é gerado no encerramento, mas o vencedor só o vê em Arremates depois de pagar; antes disso vê o valor e o prazo. O vendedor acompanha em Vender; falta a notificação na central e por e-mail (RF23) |
| **RF11** · o vencedor paga com o saldo da carteira, por Pix ou cartão, ou com os dois | `Cliente.pagarArremate()`, `Transacao.confirmarPagamento()`, `Carteira.debitar()` | [app/pagamento.py:32](app/pagamento.py#L32), [:15](app/pagamento.py#L15) (gateway), [app/dominio/contas.py:95](app/dominio/contas.py#L95), [app/dominio/financeiro.py:148](app/dominio/financeiro.py#L148), [app/rotas/minha_conta.py:100](app/rotas/minha_conta.py#L100); Mercado Pago: [app/mercado_pago.py](app/mercado_pago.py), [app/pagamento.py:55](app/pagamento.py#L55) (`abrir_cobranca`), [:106](app/pagamento.py#L106) (confirmação), [app/rotas/pagamentos.py](app/rotas/pagamentos.py) (webhook), [app/schema_v5.sql](app/schema_v5.sql) | `test_rf11_comprador_paga_pelo_gateway_e_a_transacao_fica_paga`, `test_rf11_e_rn18_pagamento_usa_o_saldo_da_carteira_e_completa_no_gateway`, `test_rf11_pagamento_integral_com_saldo_dispensa_o_gateway`; [tests/test_mercado_pago.py](tests/test_mercado_pago.py): `test_pagar_abre_a_cobranca_e_leva_o_comprador_ao_mercado_pago`, `test_volta_do_mercado_pago_com_pagamento_aprovado_quita_o_arremate`, `test_aviso_do_mercado_pago_quita_o_arremate_sem_sessao_nem_csrf`; roteiro, passo 13. Sem a credencial do Mercado Pago, o gateway é local e não cobra de verdade. Com o pagamento confirmado, o código de retirada vai por e-mail ao comprador: [app/correio.py](app/correio.py), [app/rotas/comum.py:152](app/rotas/comum.py#L152), [tests/test_correio.py](tests/test_correio.py) |
| **RF12** · o lojista registra a entrega com o código de retirada e o sistema faz o repasse | `Transacao.registrarEntrega()`, `Carteira.creditar()` | [app/rotas/admin.py:82](app/rotas/admin.py#L82) (entregas pendentes), [:90](app/rotas/admin.py#L90) (confirmação), [app/administracao.py:140](app/administracao.py#L140), [app/dominio/financeiro.py:161](app/dominio/financeiro.py#L161), [_entregas_pendentes.html](app/templates/admin/_entregas_pendentes.html), [entrega.html](app/templates/admin/entrega.html) | `test_rf12_entrega_com_o_codigo_repassa_o_valor_liquido_ao_vendedor`, `test_rn07_entrega_exige_o_codigo_de_retirada_e_o_pagamento`, `test_lojista_abre_o_card_da_entrega_pendente_e_confirma_com_o_codigo`; roteiro, passo 14 |
| **RF13** · taxa da loja e valor líquido do vendedor calculados a cada arremate | `Transacao.taxa`, `Transacao.valorLiquido`, `Leilao.taxaPercentual` | [app/dominio/leiloes.py:236](app/dominio/leiloes.py#L236), [app/dominio/financeiro.py:144](app/dominio/financeiro.py#L144) | `test_arremate_sai_com_taxa_valor_liquido_codigo_e_prazo`, `test_taxa_usa_o_percentual_gravado_no_leilao_e_arredonda_para_centavos` |
| **RF14** · status de cada carta para o vendedor — **parcial** | `Carta.status` | [app/dominio/leiloes.py:33](app/dominio/leiloes.py#L33), [app/apresentacao.py:100](app/apresentacao.py#L100), [app/rotas/anuncios.py:40](app/rotas/anuncios.py#L40), [meus_leiloes.html](app/templates/anuncios/meus_leiloes.html) | Feitos: aguardando depósito, recusada, aprovada, em leilão, arrematada, devolvida ao vendedor, cancelada, paga e entregue. `test_vendedor_acompanha_a_carta_ate_o_arremate`, `test_rf12_entrega_com_o_codigo_repassa_o_valor_liquido_ao_vendedor`, `test_rf20_vendedor_cancela_o_leilao_que_aguarda_aprovacao`. **Falta** reofertada (RF21) |
| **RF15** · o lojista configura taxa, incremento mínimo, prazo de pagamento e prazo de aceite da reoferta | `ConfiguracaoLoja` | [app/rotas/admin.py:268](app/rotas/admin.py#L268), [app/administracao.py:110](app/administracao.py#L110), [app/dominio/loja.py:9](app/dominio/loja.py#L9), [app/schema.sql:45](app/schema.sql#L45) | `test_rf15_e_rn17_configuracao_vale_para_os_leiloes_criados_depois`, `test_rf15_configuracao_invalida_nao_e_gravada`; roteiro, passo 12. O prazo da reoferta fica gravado, mas ainda não é usado |
| **RF16** · histórico dos leilões finalizados, com vencedor, valor, taxa, datas e desfecho | `Leilao`, `Transacao` | [app/rotas/admin.py:238](app/rotas/admin.py#L238), [app/administracao.py:175](app/administracao.py#L175) | `test_rf16_historico_lista_os_leiloes_finalizados_com_o_desfecho`; roteiro, passo 17. Sem o desfecho "reofertado" |
| **RF17** · carteira e extrato (só consulta) | `Carteira` (`saldo`, `gerarExtrato()`), `MovimentacaoCarteira` | [app/dominio/financeiro.py:66](app/dominio/financeiro.py#L66), [app/rotas/minha_conta.py:44](app/rotas/minha_conta.py#L44) | `test_carteira_mostra_saldo_zero_e_extrato_vazio`, `test_carteira_lista_as_movimentacoes_gravadas`, `test_gerar_extrato…` |
| **RF18** · extrato financeiro por período: arremates, taxas retidas, repasses e saques | `Transacao`, `Saque` | [app/rotas/admin.py:253](app/rotas/admin.py#L253), [app/administracao.py:188](app/administracao.py#L188) | `test_rf18_extrato_financeiro_soma_o_periodo`; roteiro, passo 17 |
| **RF19** · log das operações com usuário, operação, valor, IP e hora, consultado pelo administrador | `LogOperacao` | [app/rotas/comum.py:125](app/rotas/comum.py#L125), [app/repositorios/loja.py:38](app/repositorios/loja.py#L38), [app/rotas/admin.py:294](app/rotas/admin.py#L294), [app/schema.sql:147](app/schema.sql#L147) | `test_rf19_log_registra_usuario_operacao_valor_ip_e_hora`, `test_lance_recusado_nao_entra_no_log`; roteiro, passo 17 |
| **RF20** · o vendedor cancela o leilão que criou | `Leilao.cancelar()`, `Leilao.status`, `Carta.atualizarStatus()` | [app/dominio/leiloes.py:216](app/dominio/leiloes.py#L216), [app/anuncio.py:135](app/anuncio.py#L135), [app/rotas/anuncios.py:139](app/rotas/anuncios.py#L139), [meus_leiloes.html](app/templates/anuncios/meus_leiloes.html) | [tests/test_cancelar_leilao.py](tests/test_cancelar_leilao.py): `test_rf20_leilao_sem_lances_e_cancelado_e_a_carta_fica_cancelada`, `test_rf20_leilao_com_lance_nao_e_cancelado`, `test_rf20_vendedor_cancela_o_leilao_ativo_que_nao_recebeu_lances`, `test_rf20_so_o_vendedor_cancela_o_proprio_leilao`; `test_vendedor_cancela_o_leilao_depois_de_confirmar`; roteiro, passo 11. Regra adotada: só o vendedor cancela, e só enquanto o leilão não tem lances |
| **RF21** · prazo de pagamento vencido — **parcial** | `Transacao.expirar()`, `Cliente.registrarDescumprimento()` | [app/andamento.py:22](app/andamento.py#L22), [app/dominio/financeiro.py:172](app/dominio/financeiro.py#L172), [app/dominio/contas.py:106](app/dominio/contas.py#L106) | Feito: (a) o descumprimento e (c) a devolução da carta ao vendedor. `test_rf21_prazo_de_pagamento_vencido_marca_descumprimento_e_devolve_a_carta`. **Falta** (b), a reoferta ao segundo colocado, e as notificações |
| **RF22** · o cliente solicita o saque com a chave Pix; o lojista registra a transferência ou recusa | `Carteira.solicitarSaque()`, `Saque` | [app/rotas/minha_conta.py:50](app/rotas/minha_conta.py#L50), [app/rotas/admin.py:113](app/rotas/admin.py#L113), [:124](app/rotas/admin.py#L124), [app/administracao.py:159](app/administracao.py#L159), [app/dominio/financeiro.py:86](app/dominio/financeiro.py#L86) | `test_rf22_cliente_pede_saque_e_o_lojista_paga_ou_recusa`; roteiro, passo 15 |
| **RN01** · mínimo = lance inicial ou maior lance + incremento | `Leilao.calcularLanceMinimo()`, `Leilao.validarLance(valor)` | [app/dominio/leiloes.py:127](app/dominio/leiloes.py#L127), [:133](app/dominio/leiloes.py#L133) | [test_regras_lance.py:46–93](tests/test_regras_lance.py#L46): mínimo aceito, abaixo recusado, primeiro lance, mensagem; `test_primeiro_lance_usa_o_lance_inicial` |
| **RN02** · lance com menos de 3 min prorroga o fim em 3 min | `Leilao.dataFimPrevista` (`receberLance`, auxiliar) | [app/dominio/leiloes.py:175](app/dominio/leiloes.py#L175) | [test_regras_lance.py:174–198](tests/test_regras_lance.py#L174); `test_rn02_lance_nos_ultimos_3_minutos_prorroga_o_fim`; `test_rn02_prorrogacao_atualiza_o_cronometro` |
| **RN03** · lance irrevogável | `Lance` (imutável) | [app/dominio/leiloes.py:91](app/dominio/leiloes.py#L91), gatilhos em [app/schema.sql:114](app/schema.sql#L114) | `test_lance_registrado_nao_pode_ser_alterado`, `test_cliente_nao_reduz_o_proprio_lance`, `test_rn03_banco_recusa_alterar_ou_apagar_lance` |
| **RN04** · carta válida para leilão tem nome, jogo, edição, condição, lance mínimo inicial e fotos | `Cliente.cadastrarCarta()`, `Leilao.lanceInicial` | [app/dominio/contas.py:70](app/dominio/contas.py#L70), [app/anuncio.py:66](app/anuncio.py#L66) | `test_rn04_carta_sem_um_dado_obrigatorio_e_recusada`, `test_rn04_lance_minimo_inicial_tem_de_ser_maior_que_zero`, `test_dado_invalido_e_apontado_no_campo_e_nada_e_criado`, `test_pokemon_sem_imagem_no_catalogo_fica_fora_da_busca`, `test_foto_invalida_e_apontada_no_campo_e_nada_e_criado` |
| **RN05** · leilão com início e fim previsto | `Leilao.dataInicio`, `Leilao.dataFimPrevista` | [app/dominio/leiloes.py:113](app/dominio/leiloes.py#L113), [app/schema.sql:98](app/schema.sql#L98) | `test_rn05_fim_previsto_precisa_ser_depois_do_inicio`, `test_rn05_fim_previsto_tem_de_ser_depois_do_inicio_e_estar_no_futuro`, `test_rn05_datas_do_leilao_sao_conferidas` |
| **RN06** · prazo para pagar; vencido, descumprimento e reoferta — **parcial** | `Transacao.prazoPagamento`, `Transacao.expirar()` | [app/andamento.py:22](app/andamento.py#L22), [app/dominio/financeiro.py:172](app/dominio/financeiro.py#L172) | `test_rn06_arremate_nao_pago_no_prazo_expira_e_marca_descumprimento`. Sem a reoferta: a carta volta direto ao vendedor |
| **RN07** · a carta só é entregue com o código de retirada e a transação paga | `Transacao.registrarEntrega()` | [app/dominio/financeiro.py:161](app/dominio/financeiro.py#L161) | `test_rn07_entrega_exige_o_codigo_de_retirada_e_o_pagamento`, `test_rf12_entrega_com_o_codigo_repassa_o_valor_liquido_ao_vendedor` |
| **RN08** · o repasse acontece quando o lojista registra a entrega, e só aí | `Carteira.creditar()` | [app/administracao.py:140](app/administracao.py#L140) | `test_rf12_entrega_com_o_codigo_repassa_o_valor_liquido_ao_vendedor` (saldo zero antes da entrega, R$ 180,00 depois, e nada de novo ao repetir) |
| **RN09** · a taxa da loja incide sobre o valor final e sai do repasse | `Transacao.valorLiquido` | [app/dominio/financeiro.py:144](app/dominio/financeiro.py#L144) | `test_arremate_sai_com_taxa_valor_liquido_codigo_e_prazo` |
| **RN11** · sem lance no próprio leilão | `Cliente.darLance()` (vendedor da `Carta`) | [app/dominio/contas.py:53](app/dominio/contas.py#L53) | `test_vendedor_nao_da_lance_no_proprio_leilao` (domínio e HTTP), `test_rn11_vendedor_nao_da_lance_no_leilao_que_criou` |
| **RN12** · o leilão só entra em andamento com a carta depositada na loja e aprovada | `Leilao.status` (pendente → aprovado → ativo), `Leilao.iniciar()`, `Leilao.validarLance(valor)` | [app/dominio/leiloes.py:184](app/dominio/leiloes.py#L184) (`aprovar`), [:226](app/dominio/leiloes.py#L226) (`iniciar`), [:139](app/dominio/leiloes.py#L139) (só o ativo recebe lance), [app/andamento.py:10](app/andamento.py#L10), [app/administracao.py:30](app/administracao.py#L30) e [app/rotas/admin.py:55](app/rotas/admin.py#L55) (aprovação pelo lojista) | `test_rn12_leilao_so_entra_em_andamento_depois_de_aprovado`, `test_rn12_leilao_pendente_so_e_visto_pelo_vendedor`, `test_lojista_ve_o_leilao_pendente_e_aprova`, `test_leilao_aprovado_antes_do_inicio_fica_agendado_e_comeca_sozinho`; [test_regras_lance.py:103–133](tests/test_regras_lance.py#L103); `test_leilao_fora_do_prazo_nao_recebe_lance`, `test_leilao_que_nao_esta_ativo_nao_recebe_lance`; roteiro, passo 11 |
| **RN13** · empate: vale o lance registrado primeiro (ms) | `Leilao.getMaiorLance()` | [app/dominio/leiloes.py:119](app/dominio/leiloes.py#L119), transação `BEGIN IMMEDIATE` em [app/rotas/leiloes.py:145](app/rotas/leiloes.py#L145) | `test_empate_de_valor_vale_o_lance_registrado_primeiro`, `test_rn13_dois_lances_simultaneos_de_mesmo_valor_so_um_e_aceito`, `test_empate_de_valor_arremata_quem_deu_o_lance_primeiro` |
| **RN14** · só o administrador acessa as funções administrativas | `Administrador` | [app/rotas/comum.py:174](app/rotas/comum.py#L174), [app/dominio/contas.py:39](app/dominio/contas.py#L39) | `test_rn14_visitante_e_mandado_para_o_login`, `test_rn14_cliente_nao_acessa_as_telas_do_administrador`, `test_rnf07_cliente_nao_executa_acoes_do_administrador`, `test_administrador_nao_compra_nem_vende` |
| **RN15** · conta bloqueada não dá lance nem cria leilão | `Cliente.podeDarLance()`, `Cliente.criarLeilao()` | [app/dominio/contas.py:50](app/dominio/contas.py#L50), [:67](app/dominio/contas.py#L67), [app/rotas/anuncios.py:54](app/rotas/anuncios.py#L54) | [test_regras_lance.py:141–157](tests/test_regras_lance.py#L141); `test_cliente_bloqueado_nao_da_lance`; `test_rn15_conta_bloqueada_nao_cria_leilao`, `test_rn15_conta_bloqueada_nao_ve_a_busca_nem_cria_leilao`. O bloqueio não impede a conta de cancelar o próprio leilão (RF20) |
| **RN16** · saque só até o saldo disponível | `Carteira.solicitarSaque()`, `Carteira.disponivel` | [app/dominio/financeiro.py:86](app/dominio/financeiro.py#L86) | `test_rn16_e_rn19_saque_bloqueia_o_valor_ate_a_resposta_da_loja`, `test_rf22_cliente_pede_saque_e_o_lojista_paga_ou_recusa` |
| **RN17** · incremento e taxa da loja valem para os leilões criados depois da mudança | `Leilao.incrementoMinimo`, `Leilao.taxaPercentual`, `ConfiguracaoLoja` | [app/anuncio.py:125](app/anuncio.py#L125), [app/dominio/leiloes.py:18](app/dominio/leiloes.py#L18) (valores iniciais) | `test_rf15_e_rn17_configuracao_vale_para_os_leiloes_criados_depois`, `test_usa_o_incremento_gravado_no_leilao`, `test_criar_leilao_nasce_pendente_com_o_incremento_da_loja` |
| **RN18** · o saldo paga arremates, no todo ou em parte, e só é debitado na confirmação | `Cliente.pagarArremate()`, `Carteira.debitar()` | [app/dominio/contas.py:95](app/dominio/contas.py#L95), [app/pagamento.py:32](app/pagamento.py#L32) | `test_rn18_saldo_da_carteira_e_debitado_so_quando_o_pagamento_e_confirmado`, `test_rf11_e_rn18_pagamento_usa_o_saldo_da_carteira_e_completa_no_gateway`, `test_rn18_saldo_completa_o_pagamento_e_so_e_debitado_na_confirmacao` |
| **RN19** · o valor do saque fica bloqueado e volta ao saldo se o saque for recusado | `Carteira.bloqueado`, `Carteira.recusarSaque()` | [app/dominio/financeiro.py:106](app/dominio/financeiro.py#L106), [app/schema.sql:32](app/schema.sql#L32) | `test_rn16_e_rn19_saque_bloqueia_o_valor_ate_a_resposta_da_loja`, `test_rf22_cliente_pede_saque_e_o_lojista_paga_ou_recusa` |
| **RNF01** · leilão e área de lance responsivos | — | [app/static/css/app.css](app/static/css/app.css) (breakpoints em 1080, 1000, 900 e 767 px), [app/static/js/app.js:15](app/static/js/app.js#L15) (menu) | [tests/test_rnf01_responsivo.py](tests/test_rnf01_responsivo.py) → [evidencias/rnf01/](evidencias/rnf01/) |
| **RNF03** · dados persistentes em banco | todas as classes do escopo | [app/schema.sql](app/schema.sql), [app/repositorios/](app/repositorios/) | os testes de rotas gravam e releem pelo SQLite |
| **RNF04** · senha com hash, nunca em texto puro | `Usuario.senhaHash` | [app/dominio/senhas.py:15](app/dominio/senhas.py#L15) | `test_grava_so_o_hash_da_senha`, `test_hash_nao_contem_a_senha_e_tem_salt` |
| **RNF05** · implementado em Python | — | Flask + Jinja + SQLite | — |
| **RNF06** · LGPD (minimização de dados) | `Lance` → licitante anônimo; `Cliente.cpf` mascarado | [app/apresentacao.py:104](app/apresentacao.py#L104), [app/dominio/cpf.py](app/dominio/cpf.py) | `test_licitantes_aparecem_anonimizados`, `test_perfil_mostra_dados…_com_cpf_mascarado` |
| **RNF07** · autorização verificada no servidor | — | regras no domínio, chamadas em cada POST; CSRF em [app/rotas/__init__.py:37](app/rotas/__init__.py#L37); perfil de administrador em [app/rotas/comum.py:174](app/rotas/comum.py#L174); login exigido em [app/rotas/comum.py:161](app/rotas/comum.py#L161) | `test_lance_sem_token_csrf_e_recusado`, `test_exige_login`, `test_sair_exige_post_com_token`, `test_rnf07_cliente_nao_executa_acoes_do_administrador` |

## Classes do diagrama no código

Classes, atributos e métodos usam os nomes do diagrama (camelCase) para a rastreabilidade ficar direta.
Rotas, repositórios e templates seguem o padrão do Python (snake_case).

| Classe | Arquivo | Implementado | Fora da v2 (depende de classes fora do escopo) |
|---|---|---|---|
| `Usuario` (abstrata) | [app/dominio/contas.py:17](app/dominio/contas.py#L17) | todos os atributos; `autenticar()`. Não pode ser instanciada | `alterarSenha`, `atualizarPerfil`, `desativar` (sem telas no escopo) |
| `Administrador` | [app/dominio/contas.py:39](app/dominio/contas.py#L39) | herda de `Usuario`; entra com nome de usuário; as operações dele estão em [app/administracao.py](app/administracao.py) | métodos próprios do diagrama (não conferidos) |
| `Cliente` | [app/dominio/contas.py:44](app/dominio/contas.py#L44) | `cpf`, `bloqueado`, `descumprimentos`; `podeDarLance()`, `darLance()`, `cadastrarCarta()`, `criarLeilao()`, `pagarArremate()`, `registrarDescumprimento()`; Carteira composta (1:1) | — |
| `Jogo` | [app/dominio/leiloes.py:64](app/dominio/leiloes.py#L64) | `id`, `nome`; 1 Jogo → 0..* Carta | — |
| `Carta` | [app/dominio/leiloes.py:70](app/dominio/leiloes.py#L70) | todos os atributos, `fotos` como lista; `adicionarFoto()`, `atualizarStatus()`; Cliente 1 → 0..* Carta. A mais que o diagrama: `atributos`, os pares (filtro, valor) pelos quais os leilões do jogo são filtrados | `estaDisponivel` |
| `Leilao` | [app/dominio/leiloes.py:99](app/dominio/leiloes.py#L99) | todos os atributos; `calcularLanceMinimo()`, `validarLance()`, `getMaiorLance()`, `iniciar()`, `encerrar()`, `cancelar()`; Carta 1 → 0..* Leilao; composição com Lance; Leilao 1 → 0..1 Transacao | `reofertarSegundoColocado` |
| `Lance` | [app/dominio/leiloes.py:91](app/dominio/leiloes.py#L91) | `id`, `valor`, `dataHora`; Cliente 1 → 0..* Lance | — |
| `Carteira` | [app/dominio/financeiro.py:54](app/dominio/financeiro.py#L54) | `id`, `saldo`, `bloqueado`; `gerarExtrato()`, `creditar()`, `debitar()`, `possuiSaldo()`, `solicitarSaque()`; composição com MovimentacaoCarteira e Saque | — |
| `MovimentacaoCarteira` | [app/dominio/financeiro.py:29](app/dominio/financeiro.py#L29) | todos os atributos | — |
| `Transacao` | [app/dominio/financeiro.py:126](app/dominio/financeiro.py#L126) | `valor`, `taxa`, `valorLiquido`, `codigoRetirada`, `prazoPagamento`, `dataPagamento`, `dataEntrega`, `status`; `confirmarPagamento()`, `registrarEntrega()`, `expirar()`; comprador e vendedor (`Cliente`) | reoferta; atributos escolhidos sem o diagrama |
| `Saque` | [app/dominio/financeiro.py:44](app/dominio/financeiro.py#L44) | `valor`, `chavePix`, `dataSolicitacao`, `status`, `dataResposta` | — |
| `ConfiguracaoLoja` | [app/dominio/loja.py:9](app/dominio/loja.py#L9) | `taxaPercentual`, `incrementoMinimo`, `prazoPagamentoHoras`, `prazoReofertaHoras` | — |
| `LogOperacao` | [app/dominio/loja.py:30](app/dominio/loja.py#L30) | `usuarioId`, `operacao`, `valor`, `ip`, `dataHora`, `detalhe` | — |

**Tipos:** BigDecimal é `decimal.Decimal` com duas casas (no banco, centavos inteiros); DateTime é
`datetime` em UTC com milissegundos; Date é `date`.

**Métodos auxiliares, fora do diagrama:**
- `Leilao.estaAberto` (status ativo e dentro do prazo);
- `Leilao.motivoDeRecusa` e `Leilao.explicarRecusa` (qual regra o valor viola e a mensagem para a tela);
- `Leilao.receberLance` (o "recebe" da composição, que aplica a RN02);
- `Leilao.podeSerCancelado` e `Leilao.impedimentoParaCancelar` (se o leilão ainda pode ser cancelado e, se
  não pode, a mensagem para a tela);
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
| Visual | tema claro Wise (verde-limão) | tema escuro em azul e dourado, com a paleta complementar do Adobe Color, degradês e sombras ([DESIGN.md](DESIGN.md), v4) |
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
  encerra os leilões ativos cujo prazo terminou ([app/rotas/__init__.py:45](app/rotas/__init__.py#L45)),
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
  catálogo, por isso One Piece aparece mesmo sem leilão.
- **Filtros das cartas:** cada jogo declara, no módulo dele em [app/catalogo/](app/catalogo/), as
  características pelas quais as cartas são filtradas (`Filtro`: chave, rótulo, opções e de qual
  especificação o valor sai). A mesma definição serve às duas telas. Na **página de cada jogo**, o painel
  mostra só as opções que algum leilão ativo tem, com o total de leilões; dentro de um filtro vale qualquer
  opção marcada e, entre filtros, a carta precisa atender a todos. Para isso cada carta leiloada guarda os
  pares (filtro, valor) na tabela `carta_atributos`, tirados das especificações do catálogo quando o leilão
  é criado. Na **busca de Criar leilão** o painel é o mesmo ([_filtros.html](app/templates/_filtros.html)),
  com todas as opções do jogo e sem os totais; as opções marcadas vão para a API do jogo e valem com ou sem
  nome digitado. As APIs não são uniformes: o GraphQL do TCGdex não filtra pelo tipo do Pokémon (a lista
  filtrada vem da API REST dele, que aceita várias opções separadas por "|", e os dados das cartas vêm do
  GraphQL); o Scryfall recebe as opções como "(c:r or c:u)"; o YGOPRODeck aceita listas separadas por
  vírgula, menos no nível, que vira um pedido por nível; e a OPTCG API aceita um valor por filtro e ignora
  alguns quando vêm combinados, então o primeiro filtro com várias opções vira um pedido por opção. Por
  isso a loja confere, carta a carta, o que cada API devolve antes de mostrar. Sem JavaScript, as duas telas filtram pelo botão do formulário; com ele, a lista muda a cada
  escolha, sem recarregar. Os valores aparecem como vêm nas cartas em inglês (Fire, Spellcaster, Slash); as
  cores do Magic e a categoria do Pokémon, que a loja já traduzia, ficam em português.
- **Cartas de antes dos filtros:** ao atualizar um banco que já existia, as cartas da carga inicial recebem
  os atributos conhecidos, e as cadastradas por vendedores, os que ainda estiverem no começo da descrição
  ("Tipo: Fire; Raridade: Rare."), que é onde as especificações do catálogo foram gravadas. Nas cartas de
  Magic antigas, a cor sai do custo de mana. O que o vendedor apagou da descrição não tem como voltar.
- **Capas dos jogos:** são recortes quadrados da arte de uma carta de cada jogo, em
  `app/static/img/jogos/<slug>.webp`. Três vêm das fotos da carga inicial; a de One Piece vem da imagem
  oficial da carta OP01-003 em onepiece-cardgame.com, recortada acima da marca "SAMPLE". Um jogo sem
  arquivo de capa aparece só com o nome.
- **Logos dos jogos:** nos quadrados da página inicial, a logo oficial de cada jogo fica no lugar do nome
  (`app/static/img/jogos/logos/<slug>.webp`), e o nome continua como texto alternativo da imagem. As de
  Pokémon Trading Card Game e Magic: The Gathering vêm do Wikimedia Commons; as de Yu-Gi-Oh! Trading Card
  Game e One Piece Card Game, da Wikipédia em inglês. Foram convertidas para WebP com fundo transparente, e a
  do One Piece, que é preta, vai em branco para aparecer sobre a capa. Um jogo sem arquivo de logo aparece
  com o nome escrito.
- **Imagens do catálogo:** a imagem grande é baixada e vira a foto da carta (`instance/fotos/`); as
  miniaturas da busca são baixadas uma vez e servidas pela loja (`instance/catalogo/`). Nenhuma página
  aponta direto para os sites das APIs, o que o YGOPRODeck exige. Em Yu-Gi-Oh! a API devolve a carta com
  todas as edições em que saiu, e o vendedor escolhe a sua.
- **Aprovação da loja (RN12):** o leilão nasce "pendente", visível só para o vendedor e para o
  administrador. O lojista aprova (o que registra o depósito) ou recusa com um motivo, em
  **Administração › Leilões**. O leilão aprovado começa sozinho na data de início; se a aprovação sair
  depois dela, começa na aprovação.
- **Cancelamento (RF20):** só o vendedor cancela, em **Vender**, e só enquanto o leilão não tem lances:
  aguardando aprovação, agendado ou já ativo. Com lance não há cancelamento, porque o lance é irrevogável
  (RN03). O leilão fica "cancelado", a carta fica "cancelada" e `dataFimReal` guarda o instante do
  cancelamento. O botão abre uma confirmação antes de enviar, sem JavaScript (`<details>`). A conferência
  roda com o banco travado, então um lance que chega junto com o cancelamento impede o cancelamento. Se a
  carta já estava na loja, o vendedor a retira no balcão; essa devolução não é registrada no sistema.
- **Exclusão do leilão cancelado:** depois de cancelar, o vendedor pode **Excluir do site** aquele leilão,
  em **Vender**, com uma confirmação. A carta, as fotos enviadas, os atributos e o leilão são apagados do
  banco e do disco, e o leilão some também do histórico da loja. Só vale para o leilão que o próprio
  vendedor cancelou, que por isso nunca teve lances nem arremate: o recusado pela loja continua na lista,
  com o motivo da recusa. O que fica é uma linha no log de auditoria (RF19), com o número do leilão e o
  nome da carta, que só a loja vê. A regra foi pedida pelo dono do projeto, sem um requisito numerado.
- **Data de início:** o formulário vem preenchido com o horário em que foi aberto, e um início até 15
  minutos no passado é aceito, para não barrar quem demora a preencher.
- **Administrador (RN14):** é um `Usuario` de outro tipo, não um cliente com permissão a mais: não compra,
  não vende e não tem carteira. Entra com um nome de usuário, guardado no campo de e-mail. Toda rota de
  `/admin` confere o perfil no servidor; cliente recebe 403 e visitante vai para o login.
- **Pagamento (RF11):** o saldo da carteira e o gateway podem ser combinados. Sem credencial configurada, o
  gateway é um objeto local ([app/pagamento.py](app/pagamento.py)) que confirma na hora, sem cobrar. As
  regras são conferidas antes da cobrança, e o saldo só é debitado com o pagamento confirmado (RN18).
- **Mercado Pago:** com `MERCADOPAGO_ACCESS_TOKEN`, a loja usa o Checkout Pro
  ([app/mercado_pago.py](app/mercado_pago.py)), falando com a API por HTTPS, sem SDK. **Pagar** grava uma
  cobrança (tabela `cobrancas`) com uma referência aleatória e leva o comprador à página do Mercado Pago,
  onde ele escolhe Pix ou cartão (boleto fica de fora, porque leva dias para compensar, e a cobrança expira
  junto com o prazo de pagamento do arremate). O arremate só fica pago quando a loja consulta a API do
  Mercado Pago e ela responde que o pagamento daquela referência foi aprovado, em reais e no valor certo: o
  que vem no endereço de volta e no aviso (webhook) serve só para saber qual pagamento consultar, então
  ninguém quita um arremate forjando um endereço ou um aviso. Por isso o webhook dispensa login e token
  CSRF, e a assinatura do aviso não é conferida. A confirmação roda com o banco travado: a volta do
  comprador e o aviso, que chegam quase juntos, pagam uma vez só. Se o dinheiro entra e o arremate não pode
  mais ser quitado (prazo vencido, arremate já pago por outra cobrança, saldo combinado usado em outra
  coisa), o valor recebido é creditado na carteira do comprador, em vez de se perder. A forma de pagamento
  registrada é a que o Mercado Pago informa.
- **E-mail do código de retirada:** quando o pagamento é confirmado (na hora, pela volta do comprador, pelo
  botão de conferir ou pelo aviso do Mercado Pago), a loja manda ao e-mail do comprador o código de retirada
  ([app/correio.py](app/correio.py)), por SMTP, com a biblioteca padrão. O envio roda depois de o pagamento
  estar gravado: uma falha do servidor de e-mail vai para o log e não desfaz nada, porque o código continua
  em Arremates. Como só quem resolve a cobrança manda o e-mail, o aviso repetido do Mercado Pago não manda
  outro; um pagamento que vira crédito na carteira não manda nenhum. O código vai no texto e não no
  assunto, que aparece nas notificações do celular. Sem servidor configurado, um objeto local faz o papel
  dele e não manda nada. A função foi pedida pelo dono do projeto; é uma parte do RF23, que continua sem a
  central de notificações e sem os outros avisos.
- **Entrega e repasse:** o código de retirada tem 8 caracteres, sem os que se confundem ao ditar (I, L, O,
  0 e 1). Ele é gerado no encerramento, mas o comprador só o vê depois de pagar, porque antes disso não
  serve para nada. O lojista nunca vê o código: cada carta paga vira um card de entrega pendente na página
  Leilões e na aba Entregas, e a página da entrega pede o código que o comprador apresenta e o confere com
  aquele arremate. O repasse do valor líquido acontece dentro do registro da entrega, na mesma transação
  do banco (RN08).
- **Prazo de pagamento sem reoferta:** vencido o prazo, o sistema marca o descumprimento e devolve a carta
  ao vendedor. A reoferta ao segundo colocado (RF21) não foi feita; o prazo de aceite dela já é
  configurável, mas ainda não tem efeito.
- **Log de auditoria (RF19):** cada operação de cliente ou do lojista grava usuário, valor, IP e hora. O
  que o sistema faz sozinho (iniciar, encerrar, expirar) entra sem usuário e sem IP. Lance recusado não
  entra no log.
- **Visual (v4 do DESIGN.md):** a paleta é a harmonia complementar montada no Adobe Color, com cinco cores:
  o azul profundo `#000881` (botões e itens ativos), o marinho `#111442` (cards), o azul claro `#8088FF`
  (links, foco e contornos), o dourado `#D7B948` (valores em dinheiro) e o dourado escuro `#826700` (o filete
  dourado). As demais são tons dessas cinco. Verde, vermelho e o vermelho dos botões de cancelar e excluir
  ficam só para estado e ação. As superfícies têm degradê, contorno fino e sombra. A mudança foi só de cores e estilos
  ([app/static/css/app.css](app/static/css/app.css)): a estrutura das páginas e as medidas são as mesmas.
- **Marca CardHammer:** o topo do site e a aba do navegador mostram o símbolo da CardHammer, recolorido
  para a paleta do site, com o nome ao lado no topo ([app/static/img/marca/](app/static/img/marca/),
  [base.html](app/templates/base.html)). O título das páginas e o rodapé continuam com "Leilão TCG", o nome
  do projeto na especificação.
- **Erro e sucesso:** vermelho e verde reforçam o estado, que continua dito também por ícone e texto (ver
  DESIGN.md).
- **Fotos:** cada carta da carga inicial tem três fotos (frente, detalhe da arte e detalhe do canto),
  recortadas da imagem em alta resolução e normalizadas na proporção 63:88.
- **Fotos do vendedor:** ao criar o leilão, o vendedor anexa até 6 fotos da carta dele (JPEG, PNG ou WebP,
  até 8 MB cada). Elas são opcionais, porque a carta sempre passa pela conferência no balcão (RN12), e
  entram depois da imagem do catálogo, que continua sendo a capa nas listas. O formato é reconhecido pelos
  primeiros bytes do arquivo, e o nome gravado é gerado pela loja: o nome e o tipo que o navegador manda não
  são usados. O navegador reduz as fotos grandes para 1600 px antes do envio; sem JavaScript, vai o arquivo
  original. O lojista vê as fotos no card do leilão pendente e na página da carta; na página do leilão elas
  aparecem inteiras (sem o corte na proporção da carta), em uma galeria um pouco menor que a anterior, cuja
  coluna de miniaturas rola quando há muitas fotos.
- **Esquema do banco:** [app/schema.sql](app/schema.sql) cria a versão 4; o que mudou depois fica em um
  arquivo por versão ([app/schema_v5.sql](app/schema_v5.sql), as cobranças do Mercado Pago, e
  [app/schema_v6.sql](app/schema_v6.sql), os atributos das cartas), aplicado também nos bancos que já existem.
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

As logos de Pokémon, Magic: The Gathering, Yu-Gi-Oh! e One Piece Card Game são marcas registradas das mesmas
empresas. Aparecem na página inicial só para identificar cada jogo, neste projeto acadêmico sem fins
comerciais, e não indicam vínculo nem endosso delas. Fontes dos arquivos:
[Wikimedia Commons](https://commons.wikimedia.org) e [Wikipédia](https://en.wikipedia.org).
