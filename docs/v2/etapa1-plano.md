# Leilão TCG v2 · Etapa 1: diagnóstico e plano

**Situação:** aprovado em 14/10/2026, com o diagrama de classes recebido na mesma data. Este documento
registra o plano como foi aprovado. O mapeamento final das classes (nomes, tipos e multiplicidades
conferidos no diagrama) e o resumo do que mudou estão no [README](../../README.md).

## Etapa 0: diretrizes de interface

| Diretrizes | Situação |
|---|---|
| `design-taste-frontend`, `image-to-code`, `web-design-guidelines` | diretrizes de usabilidade consolidadas da v1 |
| `redesign-existing-projects` | guia de boas práticas para redesign e acessibilidade |

## 1. Diagnóstico do projeto

**Scan.** Flask 3.1 com templates Jinja, SQLite e um único `app.css` sem framework, com os tokens em
`:root`. O JavaScript não tem dependências e só melhora o que já funciona sem ele. A fonte Inter é servida
localmente. São quatro telas: lista de leilões, leilão, erro e o menu lateral com 12 itens "em breve".

### Sai

| Item | Onde está hoje | Motivo |
|---|---|---|
| Menu lateral (sidebar), gaveta no celular e foco preso na gaveta | `base.html`, `app.css` (`.lateral`, `.fundo-menu`), `app.js` (`iniciarMenu`) | A navegação passa a ser um menu superior fixo |
| Os 12 itens "em breve" e a constante `MENU` com os códigos de RF | `rotas.py`, `base.html` | Fora do escopo; não fica nenhum item "em breve" |
| Login simulado: seletor de usuário, rota `POST /sessao`, `usuarios_de_demonstracao`, aviso "Você está usando o sistema como…" e a nota "Simula o login" | `rotas.py`, `leiloes.py`, `base.html`, `leilao.html` | Dá lugar a cadastro e login reais |
| Todo texto com "demo" ou "demonstração" | `db.py` (`popular_demonstracao`, mensagem da CLI), README (roteiro de demonstração) | Pedido do enunciado |
| Seção "Começam em breve" com os leilões agendados | `leiloes.html`, `listar_leiloes` | A lista mostra só leilões ativos |
| Sugestões de valor em pílulas (R$ 112 / 117 / 122) | `_resumo_lance.html`, `app.js` | O campo já vem preenchido com o mínimo; as pílulas eram ruído visual |
| Paleta Wise (verde-limão sobre sálvia claro) e o conteúdo atual do DESIGN.md | `app.css`, `DESIGN.md` | Substituídos pelos tokens escuros da v2 |
| Tabela `config_loja` e o perfil `admin` | `schema.sql`, `db.py` | ConfiguracaoLoja e Administrador ficam fora do escopo |
| Ficha ao lado da foto e o link "← Todos os leilões" | `leilao.html` | Dão lugar à aba Detalhes e à trilha (breadcrumb) |
| Destaque amarelo de "últimos minutos" | `app.css` (`[data-urgente]`) | Uma cor de destaque só; a urgência passa a ser dita em texto |

### Fica

| Item | Por quê |
|---|---|
| Python + Flask + Jinja + SQLite (RNF05, RNF03), CSS e JS sem framework | A especificação mantém a stack. Pela skill, não se migra a stack num redesign |
| Melhoria progressiva: o lance funciona por formulário (POST + redirecionamento 303) e por `fetch` com JSON | O lance continua valendo sem JavaScript; a regra é sempre conferida no servidor |
| Token CSRF por sessão em todo POST | Segurança, sem custo visual |
| Transação `BEGIN IMMEDIATE` ao gravar o lance | Garante a RN13: dois lances simultâneos não são validados contra o mesmo maior lance |
| Dinheiro em centavos inteiros e o leitor de valores em formato brasileiro (`ler_reais`) | Evita erro de ponto flutuante e aceita "2.355,00", "2355" e "R$ 2.355" |
| Fonte Inter local, escala de espaçamento 4–48 px, alvos de toque ≥ 44 px, fonte do campo ≥ 16 px | O enunciado permite manter tipografia e espaçamento |
| Link "Pular para o conteúdo", `:focus-visible`, `prefers-reduced-motion`, `text-wrap: balance` nos títulos | Itens que a skill cobra e a v1 já tem |
| Cronômetro acertado pelo relógio do servidor e atualização do maior lance a cada 5 s | O RF08 continua valendo |
| Valores com `tabular-nums` | A skill pede algarismos tabulares em interfaces com números |
| Página de erro própria (404/400) | Só ganha o tema novo |
| Infraestrutura de testes (pytest + Playwright no Chrome/Edge instalado) | O teste do RNF01 é refeito para o layout novo |

### Muda

| Item | De → para |
|---|---|
| Navegação | Sidebar → barra superior fixa (`--surface`): marca à esquerda, **Leilões**; à direita **Entrar** e **Criar conta**, ou **Minha Conta** para quem está logado. No celular vira um botão "Menu" (`aria-expanded`/`aria-controls`, Esc fecha e o foco volta ao botão). O item ativo tem fundo `--accent` com texto branco |
| Cores | Tema claro Wise → tema escuro com os 10 tokens da v2. `--accent`/`--accent-hover`/`--border` nunca em texto ou ícone. O azul de texto e ícone é sempre `--text-link`, que também é o anel de foco |
| Raios | 24 px em tudo → 6 px nos controles, 8 px nas mídias e 12 px nos contêineres. A skill pede raios variados |
| Hierarquia de tipos | Peso 900 nos títulos → 700 com tracking negativo. Rótulos em 500/600 e valores em 600/700 tabulares |
| Lista de leilões | Duas seções → uma grade só com leilões ativos e filtro por **Jogo** em chips no topo (links `?jogo=…`, que funcionam sem JS). O chip ativo usa o mesmo tratamento do item ativo do menu |
| Página do leilão | Refeita do zero (seção 4): trilha, galeria com miniaturas e ampliação, coluna de lance, abas Lances/Detalhes/Descrição e "Outros leilões de {Jogo}" |
| Erro e sucesso do lance | Caixas verde/vermelho claro → sem cores novas: ícone + texto em `--text` e campo com borda de 2 px em `--text` no erro; check em `--text-link` no sucesso. Tudo é anunciado por `aria-live` |
| Participantes na tabela | "Ana S." → **Licitante 1, 2, 3…**, numerados pela ordem do primeiro lance naquele leilão. O próprio usuário vê "Você". É mais anônimo que a v1 (LGPD, RNF06) |
| Estados vazios | Novos: lista filtrada sem leilões, "Meus lances" sem lances e extrato sem movimentações |
| Favicon e `<meta name="description">` | Não existem → passam a existir. A skill aponta a falta |
| Domínio | Funções soltas (`SituacaoLeilao`, `validar_lance`) → classes do diagrama (seção 2) |
| Persistência | SQL dentro de `leiloes.py` → repositórios por agregado, com o SQL isolado num só lugar |

### Onde a skill e o enunciado discordam (vale o enunciado)

- **Fundo `#000000`:** a skill pede um preto suavizado, mas a paleta da v2 fixa `--bg: #000000`. A
  profundidade vem do degrau para `--surface`.
- **Acento saturado:** `#0038D7` tem 100% de saturação e a skill pede menos de 80%. Ele fica, mas só como
  fundo: botão primário, item ativo do menu e chip ativo.
- **Trocar a Inter:** a skill sugere outra fonte; o enunciado permite manter a tipografia. Fica a Inter, já
  servida localmente e sem dependência nova.
- **Textura, ruído e imagens de fundo:** contrariam o pedido de visual limpo sem gradientes. Não entram.
- **Linhas finas:** a `design-taste-frontend` proíbe divisórias, mas a paleta tem `--border` para isso. O uso
  fica restrito a: blocos do painel de lance, base da lista de abas, ficha de detalhes, rodapé e menu
  aberto no celular.

## 2. Classes do diagrama × código

> **O diagrama de classes não chegou.** A mensagem trouxe só o texto, e a paleta eu achei no print de hoje
> (10:20). A tabela abaixo usa os nomes de classes, atributos e métodos citados no enunciado. Atributos,
> tipos e multiplicidades serão conferidos no diagrama antes de qualquer código.

| Classe | Na v1 | Situação | Na v2 |
|---|---|---|---|
| **Usuario** (abstrata) | tabela `usuarios` (id, nome, email, perfil), sem classe | diverge | classe abstrata com `nome`, `email`, `telefone`, `senhaHash`, `dataCadastro`, `ativo` e `autenticar()`. O campo `perfil` sai |
| **Cliente** | `perfil = 'cliente'` | falta | subclasse com `cpf`, `bloqueado`, `descumprimentos` e `podeDarLance()`. Composição 1:1 com Carteira |
| **Jogo** | texto solto em `cartas.jogo` | diverge | classe e tabela próprias; 1 Jogo → N Cartas; é a base dos chips |
| **Carta** | tabela `cartas` com uma `imagem` | diverge | `fotos` vira coleção (galeria com miniaturas); o jogo vira associação |
| **Leilao** | tabela `leiloes` (`lance_minimo`, `incremento`, `inicio`, `fim`) e funções soltas | diverge nos nomes; faltam `status` e os métodos | `lanceInicial`, `incrementoMinimo`, `dataInicio`, `dataFimPrevista`, `status`, `calcularLanceMinimo()`, `validarLance(valor)`, `getMaiorLance()` |
| **Lance** | tabela `lances` (`valor_centavos`, `criado_em`, `usuario_id`) | diverge nos nomes | classe com `valor`, `dataHora` e o Cliente licitante |
| **Carteira** | não existe | falta | `saldo`; criada com saldo 0 junto com o Cliente |
| **MovimentacaoCarteira** | não existe | falta | N por Carteira; só leitura (extrato) |
| Administrador | perfil `admin` (a loja no seed) | sai | fora do escopo |
| ConfiguracaoLoja | tabela `config_loja` (nome, incremento) | sai | fora do escopo; o incremento fica gravado em cada Leilao, como já pede a RN17 |
| Deposito, Transacao, Pagamento, Retirada, Saque, Notificacao, LogOperacao | não existem | continuam fora | sem telas e sem tabelas |

**Convenção de nomes:** no domínio, classes, atributos e métodos usam exatamente os nomes do diagrama
(camelCase), para a rastreabilidade ficar direta. Rotas, repositórios e templates continuam em
snake_case, como é o padrão do Python.

### Regras de negócio do lance

Não achei um arquivo chamado "Declaração de Escopo". Por isso usei as RNs da *Especificação de Requisitos*
(RN01–RN19) que tratam de lance. Todas ficam no domínio, com teste unitário do caso válido e de cada
violação.

| RN | Regra | Onde fica | Casos de teste |
|---|---|---|---|
| RN01 | Sem lances, o mínimo é o `lanceInicial`; com lances, é o maior lance + `incrementoMinimo`. Valor abaixo do mínimo é recusado | `Leilao.calcularLanceMinimo()`, `Leilao.validarLance(valor)` | igual ao mínimo (aceito), acima (aceito), 1 centavo abaixo (recusado), primeiro lance, valor ≤ 0 |
| RN12 + RF07 | Lance só com `status` ativo, depois de `dataInicio` e antes de `dataFimPrevista` | `Leilao.validarLance` | status diferente de ativo, antes do início, no instante do fim, 1 ms antes do fim |
| RN15 | Cliente bloqueado não dá lance | `Cliente.podeDarLance()` | `bloqueado` true e false |
| RN11 | Ninguém dá lance no próprio leilão | `Leilao.validarLance` | o vendedor é recusado |
| RN02 | Lance válido com menos de 3 min para o fim prorroga `dataFimPrevista` em 3 min | `Leilao`, ao registrar o lance | faltando 2:59 prorroga, faltando 3:00 não, lance recusado não prorroga |
| RN03 | Lance irrevogável | `Lance` imutável, sem cancelar nem editar em nenhuma camada | alterar um Lance falha; lance menor que o próprio é recusado |
| RN13 | Empate de valor: vale o registrado primeiro (milissegundos) | `Leilao.getMaiorLance()` + transação | empate → o mais antigo; dois lances simultâneos → um aceito e um recusado |

- **Mudança em relação à v1:** a v1 lia a RN01 de forma estrita ("superior a": com lance atual de R$ 100 e
  incremento de R$ 5, o lance de R$ 105,00 era recusado). A v2 segue o enunciado: o mínimo é o maior lance
  + incremento, e esse valor é aceito (é ele que vem preenchido no campo). A mudança será registrada no README.
- O lance não depende do saldo da Carteira.

## 3. Mapa do site

```
Menu fixo:  [Leilão TCG → /leiloes]  [Leilões]  ·········  [Entrar] [Criar conta]   (visitante)
                                                ·········  [Minha Conta]           (logado)

/                              → redireciona para /leiloes
/leiloes                       Leilões ativos em grade; chips por Jogo (?jogo=pokemon | magic | yu-gi-oh)
/leiloes/<id>                  Página do leilão
    POST /leiloes/<id>/lances  Dar lance (formulário com 303 ou JSON)
    GET  /leiloes/<id>/estado  JSON com o maior lance, o mínimo e a tabela (a cada 5 s)
/entrar                        E-mail + senha (Usuario.autenticar); ?proximo= devolve à página de origem
/criar-conta                   Nome, e-mail, telefone, CPF, senha e confirmação; entra logado ao concluir
/minha-conta                   Aba Perfil (dados de Usuario e Cliente; CPF mascarado)
/minha-conta/carteira          Aba Carteira: saldo e extrato de MovimentacaoCarteira (só leitura)
/minha-conta/lances            Aba Meus lances: carta, seu maior lance, lance atual, se lidera e o status do leilão
    POST /sair                 Botão "Sair" na barra de abas de Minha Conta
404 / 400                      Página de erro no tema novo
```

- Item ativo: **Leilões** em `/leiloes` e na página do leilão; **Minha Conta** em `/minha-conta/*`.
- As abas de Minha Conta são links com `aria-current="page"`: cada uma tem seu endereço, o que funciona
  no voltar do navegador, no recarregar e sem JS. As abas da página do leilão seguem o padrão ARIA de
  abas (setas do teclado); sem JS, as três seções aparecem empilhadas.
- `/minha-conta/*` sem login leva a `/entrar?proximo=…`.

## 4. Referência visual da página do leilão (image-to-code)

Este ambiente não tem gerador de imagens. Por isso montei um mockup estático em HTML/CSS com os tokens
da v2, a fonte Inter e as fotos reais das cartas, e capturei as telas no Edge headless. A estrutura segue
a página de produto do MYP Cards (trilha, foto à esquerda, compra à direita, abas embaixo, relacionados
no fim), sem levar logo, textos nem cores dela.

| Imagem | O que mostra |
|---|---|
| [leilao-desktop.png](referencia/leilao-desktop.png) | Primeira tela em 1440 × 900, logado |
| [leilao-desktop-pagina-inteira.png](referencia/leilao-desktop-pagina-inteira.png) | Página inteira: abas (Lances aberta) e "Outros leilões de Pokémon" |
| [leilao-mobile.png](referencia/leilao-mobile.png) | Primeira tela em 390 px: título, galeria, lance atual e cronômetro |
| [leilao-mobile-pagina-inteira.png](referencia/leilao-mobile-pagina-inteira.png) | Página inteira em 390 px |
| [detalhe-painel-estados.png](referencia/detalhe-painel-estados.png) | Painel de lance: visitante ("Entrar para dar lance"), lance recusado com motivo junto ao campo, lance aceito |
| [detalhe-menu.png](referencia/detalhe-menu.png) | Menu superior: visitante, logado e celular com o menu aberto |
| [detalhe-ampliacao.png](referencia/detalhe-ampliacao.png) | Foto ampliada (`<dialog>`) com a navegação entre as fotos |

Decisões que aparecem nas imagens:
- **Desktop:** miniaturas em coluna à esquerda da foto. À direita, nesta ordem: h1, edição e condição,
  badge de status, painel com lance atual (lance inicial e incremento menores), cronômetro e número de
  lances, campo preenchido com `calcularLanceMinimo()` e o botão **Dar lance**.
- **Celular:** título antes da galeria, para o lance atual e o cronômetro aparecerem na primeira tela.
  Campo e botão ficam empilhados, com largura total.
- **Maior lance na tabela:** negrito, barra à esquerda e a etiqueta "Maior lance" em `--text-link`.
- **Fotos (`Carta.fotos`):** cada carta do seed terá frente e dois detalhes (holográfico e canto),
  recortados da imagem em alta resolução.

## 5. Decisões para aprovar

1. **Diagrama de classes:** preciso dele (imagem ou caminho do arquivo) para fechar a seção 2.
2. **Hash da senha:** o enunciado pede Web Crypto e repositório em localStorage *se não houver backend*.
   Aqui há backend, então proponho gerar o hash **no servidor**, com PBKDF2-SHA256 (o mesmo algoritmo do
   Web Crypto, pela `hashlib` da biblioteca padrão), salt aleatório de 16 bytes e 600 mil iterações,
   gravando só `senhaHash`. O README registra que em produção seria bcrypt/argon2. Gerar o hash no
   navegador faria do próprio hash a senha (quem lesse o banco entraria com ele) e o login passaria a
   depender de JS.
3. **Sigo por padrão, salvo objeção:** RN01 com mínimo inclusivo; RN02, RN03, RN11 e RN13 incluídas; Inter
   mantida; erro e sucesso sem cores novas. O README pode descrever a carga inicial do banco para quem for
   avaliar; nenhuma tela fala dela.

## 6. Ordem de execução depois da aprovação

1. Domínio (classes do diagrama) e testes unitários de cada RN.
2. Persistência: esquema novo, repositórios e seed (Jogo, Carta, Leilao e lances de outros clientes).
3. Contas: cadastro com validações (e-mail e CPF únicos, dígitos do CPF, senha ≥ 8), login, sessão,
   "Sair" e Minha Conta (Perfil, Carteira e Meus lances).
4. Telas: menu superior, lista com chips e página do leilão fiel à referência; DESIGN.md com os tokens novos.
5. Auditoria com a web-design-guidelines nas telas novas e correção de tudo o que ela apontar.
6. RNF01 revalidado em 360, 390 e 768 px, com as evidências atualizadas.
7. README: tabela de rastreabilidade (requisito/RN → classe → arquivo → como verificar) e resumo da v1
   para a v2.
