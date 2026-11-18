---
version: 4
name: Leilao-TCG-azul-e-dourado
description: Tema escuro do Leilão TCG sobre a harmonia complementar escolhida no Adobe Color — o azul profundo #000881, o marinho #111442 e o azul claro #8088FF de um lado, o dourado #D7B948 e o dourado escuro #826700 do outro. As demais cores são tons desses cinco; verde e vermelho ficam só para sucesso, erro e a ação que cancela ou apaga. Superfícies em degradê, com contorno fino e sombra. A tipografia (Inter) e a escala de espaçamento vêm da v1.

colors:
  bg: "#090B26"
  surface: "#111442"
  surface-2: "#1A1E5C"
  surface-3: "#242A78"
  campo: "#0B0D30"
  border: "#2B3080"
  accent: "#000881"
  accent-claro: "#4650EE"
  accent-hover: "#1017A8"
  on-accent: "#FFFFFF"
  text: "#F4F5FF"
  text-muted: "#ADB2DC"
  text-link: "#8088FF"
  border-input: "#858BC9"
  ouro: "#D7B948"
  ouro-escuro: "#826700"
  sucesso: "#4ADE9F"
  erro: "#FF8A94"
  perigo: "#B3202F"
  perigo-claro: "#D63646"

gradients:
  accent: linear-gradient(180deg, {colors.accent-claro}, {colors.accent})
  accent-hover: linear-gradient(180deg, #5560F5, {colors.accent-hover})
  marca: linear-gradient(90deg, {colors.accent-claro}, {colors.text-link})
  ouro: linear-gradient(90deg, {colors.ouro-escuro}, {colors.ouro})
  cartao: linear-gradient(180deg, #181C56, {colors.surface})

shadows:
  sombra-1: 0 1px 2px rgba(0,0,0,.4), 0 12px 24px -14px rgba(0,0,0,.8)
  sombra-2: 0 2px 4px rgba(0,0,0,.4), 0 24px 44px -18px rgba(0,8,129,.95)
  sombra-3: 0 32px 72px -28px rgba(0,0,0,.9), 0 16px 36px -16px rgba(40,48,190,.5)
  brilho: 0 10px 24px -10px rgba(70,80,238,.8)
  halo: 0 0 0 4px rgba(128,136,255,.22)

typography:
  display:
    fontFamily: Inter, system-ui, -apple-system, Segoe UI, sans-serif
    fontSize: clamp(36px, 1.6rem + 2.4vw, 56px)
    fontWeight: 700
    lineHeight: 1.02
    letterSpacing: -0.03em
  valor:
    fontFamily: Inter
    fontSize: clamp(32px, 1.25rem + 2.4vw, 48px)
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: -0.02em
    fontVariantNumeric: tabular-nums
  secao:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: -0.02em
  subtitulo:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: 600
  corpo-lg:
    fontFamily: Inter
    fontSize: 17px
    fontWeight: 400
    lineHeight: 1.65
  corpo:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
  rotulo:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: 500
  apoio:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 400
  botao:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: 600
    lineHeight: 1.2

rounded:
  badge: 6px
  controle: 8px
  midia: 10px
  cartao: 16px

spacing:
  s-1: 4px
  s-2: 8px
  s-3: 12px
  s-4: 16px
  s-5: 24px
  s-6: 32px
  s-7: 48px
  s-8: 64px
  s-9: 112px

components:
  nav-bar:
    backgroundColor: rgba(9, 11, 38, 0.86) com desfoque do que passa por baixo
    textColor: "{colors.text}"
    height: 64px (56px no celular)
    position: sticky
  nav-item-ativo:
    background: "{gradients.accent}"
    textColor: "{colors.on-accent}"
    shadow: "{shadows.brilho}"
    rounded: "{rounded.controle}"
  botao-primario:
    background: "{gradients.accent}"
    hoverBackground: "{gradients.accent-hover}"
    textColor: "{colors.on-accent}"
    shadow: "{shadows.brilho}"
    typography: "{typography.botao}"
    rounded: "{rounded.controle}"
    height: 48px (56px no painel de lance)
  botao-secundario:
    backgroundColor: "{colors.surface-2}"
    hoverBackground: "{colors.surface-3}"
    borderColor: azul claro a 40% (no hover, "{colors.text-link}")
    textColor: "{colors.text}"
    rounded: "{rounded.controle}"
  botao-terciario:
    backgroundColor: transparent
    hoverBackground: azul claro a 15%
    textColor: "{colors.text}"
  botao-icone:
    backgroundColor: "{colors.surface-2}"
    size: 44px
  chip-filtro:
    backgroundColor: "{colors.surface}"
    activeBackground: "{gradients.accent}"
    activeText: "{colors.on-accent}"
    height: 44px
  cartao-leilao:
    background: "{gradients.cartao}"
    border: 1px em azul claro a 16%
    shadow: "{shadows.sombra-1}" (no hover, "{shadows.sombra-2}" e 4px para cima)
    valor: "{colors.ouro}"
    rounded: "{rounded.cartao}"
    padding: "{spacing.s-3}"
  painel-de-lance:
    background: "{gradients.cartao}" com um filete de 3px em "{gradients.ouro}" no alto
    shadow: "{shadows.sombra-2}"
    valor: "{colors.ouro}"
    rounded: "{rounded.cartao}"
    padding: "{spacing.s-6}"
    divider: "{colors.border}"
  campo:
    backgroundColor: "{colors.campo}"
    borderColor: "{colors.border-input}"
    errorBorder: 2px "{colors.erro}"
    focusRing: 2px "{colors.text-link}" + "{shadows.halo}"
    rounded: "{rounded.controle}"
    height: 48px (56px no valor do lance)
  badge-status:
    aberto: fundo "{colors.sucesso}" a 12%, ponto "{colors.sucesso}" pulsando
    encerrado: fundo "{colors.surface-2}", anel vazado em "{colors.text-muted}"
    rounded: "{rounded.badge}"
  tabela:
    zebra: azul claro a 8%
    destaque: azul claro a 15% + barra de 3px em "{colors.ouro}" + negrito
  abas:
    ativa: texto "{colors.text}" + sublinhado de 3px em "{gradients.marca}"
    baseline: "{colors.border}"
  dialogo:
    background: "{gradients.cartao}"
    shadow: "{shadows.sombra-3}"
    backdrop: rgba(4, 5, 20, 0.86) com desfoque
  rodape:
    backgroundColor: rgba(9, 11, 38, 0.86)
    textColor: "{colors.text-muted}"
---

# Leilão TCG · sistema de design (v4)

## Visão geral

Tema escuro em azul e dourado. A paleta é a harmonia complementar que o dono do projeto montou no Adobe
Color, com cinco cores: o azul profundo `#000881`, o marinho `#111442` e o azul claro `#8088FF`, de um lado
do círculo; o dourado `#D7B948` e o dourado escuro `#826700`, do outro. O marinho é a superfície dos cards,
e o fundo da página é um tom mais escuro dele. O azul profundo é a base dos botões e dos itens ativos, com um
tom mais vivo no alto do degradê. O azul claro é a cor de links, do foco e dos contornos. O **dourado** marca
o que é dinheiro (lance atual, saldo, preço de mercado, maior lance), e o dourado escuro entra com ele no
filete que emoldura esses valores. Verde e vermelho existem apenas para dizer sucesso, erro e perigo.

A carta continua sendo a protagonista, e as fotos seguem como as cores mais fortes da página. As
superfícies têm um degradê leve, um contorno fino e sombra; os cards sobem no hover; o botão primário tem
brilho próprio; e o alto da página recebe uma luz azul de fundo.

A tipografia (Inter, servida localmente), a escala de espaçamento e a estrutura das páginas continuam as
mesmas. A v3 (a mesma estrutura sobre o azul `#0038D7`, com violeta nos degradês) foi substituída pelos
tokens abaixo.

## Cores

| Token | Cor | Uso |
|---|---|---|
| `--bg` | `#090B26` | fundo da página (um tom mais escuro do marinho), com uma luz azul no alto |
| `--surface` | `#111442` (da paleta) | base dos cards, do painel de lance, dos formulários e do diálogo |
| `--surface-2` | `#1A1E5C` | botão secundário, avisos, badge de leilão encerrado |
| `--surface-3` | `#242A78` | hover do botão secundário e do botão de ícone, barra de rolagem |
| `--campo` | `#0B0D30` | fundo de campos e da busca do topo: mais escuro que o card, como um rebaixo |
| `--border` | `#2B3080` | divisórias decorativas (painel de lance, base das abas, menu aberto) |
| `--accent` | `#000881` (da paleta) | o azul profundo: base do degradê do botão primário, do item ativo e do chip ativo |
| `--accent-claro` | `#4650EE` | alto do degradê do botão primário; início do degradê da marca |
| `--accent-hover` | `#1017A8` | base do degradê no hover; botão em envio |
| `--text` | `#F4F5FF` | texto principal |
| `--text-muted` | `#ADB2DC` | texto secundário, rótulos, datas |
| `--text-link` | `#8088FF` (da paleta) | links, ícones azuis, anel de foco, miniatura escolhida, fim do degradê da marca |
| `--border-input` | `#858BC9` | borda de campos |
| `--ouro` | `#D7B948` (da paleta) | valores em dinheiro em destaque, etiqueta e barra do maior lance, entrega pendente |
| `--ouro-escuro` | `#826700` (da paleta) | início do degradê dourado (filete do painel de lance e do saldo); nunca em texto |
| `--sucesso` | `#4ADE9F` | leilão ativo, lance registrado, "Você lidera" |
| `--erro` | `#FF8A94` | borda de campo com erro, ícone de erro, resumo de erros |
| `--perigo` / `--perigo-claro` | `#B3202F` / `#D63646` | degradê do botão que cancela ou apaga, sempre como fundo com texto branco |

`--on-accent` (`#FFFFFF`) é o texto branco sobre o degradê azul. Os contornos e véus translúcidos
(`--fio`, `--fio-forte`, `--veu`, `--veu-forte`) são o `--text-link` a 16%, 40%, 8% e 15%: por serem
translúcidos, funcionam sobre qualquer superfície.

### Regra de contraste

`--accent`, `--accent-hover`, `--border` e `--ouro-escuro` ficam abaixo de 4,5:1 sobre o fundo escuro. Por
isso nunca aparecem em texto nem em ícone; o azul de texto é sempre `--text-link` e o dourado de texto,
`--ouro`. Contrastes medidos (WCAG 2.x), no pior caso entre `--bg`, `--surface`, o alto do degradê dos
cards, `--surface-2` e `--campo`:

| Par | Contraste (pior caso) | Mínimo |
|---|---|---|
| `--text` sobre as superfícies | 14,0:1 (17,8 sobre `--bg`) | 4,5:1 |
| `--text-muted` sobre as superfícies | 7,4:1 (9,4 sobre `--bg`) | 4,5:1 |
| `--text-link` sobre as superfícies | 5,0:1 (6,3 sobre `--bg`) | 4,5:1 |
| `--ouro` sobre as superfícies | 7,9:1 | 4,5:1 |
| `--sucesso` sobre as superfícies | 8,8:1 | 4,5:1 |
| `--erro` sobre as superfícies | 6,7:1 | 4,5:1 |
| branco sobre o degradê do botão (`#4650EE` → `#000881`) | 5,8 a 15,5:1 | 4,5:1 |
| branco sobre o degradê do hover (`#5560F5` → `#1017A8`) | 4,8 a 12,3:1 | 4,5:1 |
| branco sobre o degradê de perigo (`#D63646` → `#B3202F`) | 4,7 a 6,6:1 | 4,5:1 |
| `--border-input` sobre `--campo` / `--surface` / `--surface-2` | 5,9 / 5,4 / 4,7:1 | 3:1 (borda de campo) |
| `--text` / `--text-muted` / `--text-link` sobre a luz do alto da página | 13,5 / 7,1 / 4,8:1 | 4,5:1 |
| `--text` sobre a caixa de sucesso e sobre o resumo de erros | 11,4 / 15,6:1 | 4,5:1 |
| `--accent` / `--border` / `--ouro-escuro` sobre `--bg` | 1,2 / 1,7 / 3,6:1 | — (só fundo, divisória ou degradê) |

`--surface-3` só aparece como fundo de hover, com `--text` (11,5:1): o `--text-link` sobre ela teria 4,1:1
e por isso não é usado ali.

### Erro, sucesso e perigo

A cor reforça o estado, mas nunca é o único sinal: todo erro e todo sucesso têm ícone e texto.
- **Erro:** ícone de alerta em `--erro` + texto em `--text` (600), campo com borda de 2 px em `--erro` e
  `aria-invalid`. O resumo de erros tem fundo avermelhado e barra lateral em `--erro`.
- **Sucesso:** check em `--sucesso` + texto em `--text`, numa caixa com fundo e contorno esverdeados.
- **Ativo:** badge esverdeado com um ponto em `--sucesso` que pulsa devagar.
- **Encerrado:** badge em `--surface-2` e o ponto vira um anel vazado em `--text-muted`, sem pulsar.
- **Perigo:** o botão que cancela ou apaga (cancelar leilão, excluir do site, remover cadastro) é vermelho,
  e o texto dele diz o que acontece. O vermelho do botão é mais escuro que `--erro`, que é cor de texto.

## Profundidade

| Token | Uso |
|---|---|
| `--grad-cartao` | fundo de cards, painel, formulários e diálogo: de `#181C56` no alto a `--surface` |
| `--grad-accent` / `--grad-accent-hover` | botão primário, item ativo do menu, chip ativo |
| `--grad-marca` | azul vivo → azul claro: sublinhado da aba ativa |
| `--grad-ouro` | dourado escuro → dourado: filete no alto do painel de lance e do saldo |
| `--grad-perigo` | botão de cancelar e de excluir |
| `--sombra-1` | cards parados, botão secundário |
| `--sombra-2` | card no hover, painel de lance |
| `--sombra-3` | foto principal da galeria, diálogo |
| `--sombra-cartao` | `--sombra-1` + contorno de 1 px (`--fio`) + um fio de luz no alto do card |
| `--brilho` / `--brilho-forte` | sombra azul do botão primário e do item ativo (mais forte no hover) |
| `--halo` | anel de 4 px em volta do campo em foco, além do contorno de foco |

Os contornos de 1 px são feitos com `box-shadow` interno, não com `border`: assim nenhuma medida da
página mudou em relação à v2.

## Tipografia

Inter (variável, 400–900), uma família só. Cinco tamanhos fazem o trabalho visível:

| Papel | Tamanho | Peso | Uso |
|---|---|---|---|
| Display | 36–56 px (fluido) | 700, tracking −0,03em | `h1` (nome da carta, título da página) |
| Valor | 32–48 px (fluido) | 700, `tabular-nums` | saldo e valor a pagar (em `--ouro`); no painel do anúncio, o lance atual vai de 28 a 40 px |
| Seção | 28 px | 600 | `h2` de seção ("Outros leilões de Pokémon") |
| Corpo | 16–17 px | 400 | texto corrido; a descrição do anúncio tem 16 px (`max-width: 68ch`) |
| Apoio | 13–15 px | 400–600 | rótulos, datas, ajuda, chips |

Valores, datas e contagens usam `font-variant-numeric: tabular-nums`. Títulos usam `text-wrap: balance`.
Tudo em caixa de frase: nada de caixa alta espaçada nem Title Case. O nome da marca, no topo, não é texto:
é o letreiro da própria arte (ver Componentes). Os títulos são em cor sólida.

## Espaçamento e grade

- Base de 4 px: 4, 8, 12, 16, 24, 32, 48, 64 e 112 px.
- Container de até 1240 px, com margem lateral fluida de 16 a 40 px.
- Entre seções da página do leilão, 112 px no desktop e 64 px no celular. É sempre maior que qualquer espaço interno.
- Página do leilão: galeria (miniaturas de 72 px + foto de até 352 px) à esquerda e coluna de lance de até
  600 px à direita.

## Formas

| Token | Valor | Uso |
|---|---|---|
| `badge` | 6 px | badge de status |
| `controle` | 8 px | botões, campos, chips, itens do menu, linhas de tabela |
| `midia` | 10 px | fotos nos cards e miniaturas |
| `cartao` | 16 px | cards, painel de lance, diálogo, formulários |

Os raios são escalonados: mais fechados nos controles e mais abertos nos contêineres. Não há pílulas.

## Componentes

- **Marca:** o símbolo da CardHammer (a carta e o martelo de leiloeiro) seguido do nome. O nome é a imagem
  do letreiro original, com a mesma letra inclinada da arte: "CARD" recolorido para o azul do site e
  "HAMMER" em `--ouro`, com 160 px de largura (136 px no celular) e o texto alternativo "CardHammer". A arte original,
  em laranja e dourado sobre cinza, foi recolorida para a paleta: o fundo saiu, o laranja do rastro e da
  explosão virou o azul da marca, o amarelo foi para `--ouro` e o aço do martelo ficou neutro. No topo o
  símbolo tem 54 px e gira de leve no hover; na aba do navegador ele vai sobre um quadrado azul-marinho de
  cantos arredondados, para aparecer bem em tema claro e escuro. Os arquivos ficam em
  `app/static/img/marca/`.
- **Menu superior** (fixo, translúcido, com desfoque do conteúdo que passa por baixo e uma sombra): marca à
  esquerda, busca no meio e, à direita, **Entrar** + **Criar conta** (com contorno) ou **Minha Conta**. O
  item ativo tem o degradê azul com brilho. No celular, recolhe num botão "Menu" com `aria-expanded`, e a
  lista aberta tem fundo opaco.
- **Botão primário:** degradê `--grad-accent`, texto branco, brilho azul embaixo, 48 px (56 px no painel).
  No hover clareia, o brilho cresce e o botão sobe 1 px; pressionado, desce 1 px.
- **Botão secundário:** `--surface-2` com contorno translúcido; no hover, `--surface-3` e contorno em
  `--text-link`.
- **Botão de perigo:** igual ao primário, com o degradê `--perigo-claro` → `--perigo` e brilho vermelho.
  É o botão de cancelar o leilão e de excluí-lo do site, na abertura e na confirmação, e o de remover um
  cadastro na administração.
- **Chips de filtro:** `--surface` com contorno; o ativo usa o mesmo tratamento do item ativo do menu.
- **Card de leilão:** degradê do card, contorno fino e sombra; foto 63:88 com sombra própria, nome,
  edição, lance atual em `--ouro` e tempo restante. No hover sobe 4 px, o contorno clareia e a sombra fica
  azulada. O card inteiro é clicável pelo link do nome.
- **Cards dos jogos** (página inicial, sem rótulo acima deles): a capa com um véu azul-marinho de baixo para cima e, sobre ele, a
  logo oficial do jogo (42 px de altura, 32 px no celular, com uma sombra para destacar da capa) acima do
  total de leilões. As logos mantêm as cores originais: são as marcas dos jogos, não parte da paleta. No
  hover a capa aproxima e o card sobe.
- **Painel de lance:** degradê do card com um filete dourado (`--grad-ouro`) no alto e a sombra mais forte da
  página. Blocos separados por `--border`: lance atual (valor grande em `--ouro`, com um brilho leve),
  regras, cronômetro e número de lances, e o formulário.
- **Campo de valor e campos de formulário:** `--campo`, borda `--border-input`. No foco, borda e contorno
  em `--text-link` e um halo de 4 px.
- **Badge de status:** ver "Erro e sucesso".
- **Tabela de lances:** linhas alternadas com um véu azul; o maior lance tem negrito, véu mais forte, barra
  de 3 px em `--ouro` e a etiqueta "Maior lance" em `--ouro`. O lance que acaba de chegar pisca em azul.
- **Painel de filtros** (página de cada jogo e busca de Criar leilão): um card ao lado da lista, com um
  grupo de caixas de seleção por característica das cartas. A opção marcada ganha o véu azul mais forte. Na
  página do jogo, cada opção traz o total de leilões numa pastilha, que fica em `--accent` quando marcada.
  O grupo com muitas opções rola dentro dele mesmo (até seis linhas à vista). O título "Filtros" recolhe o
  painel, que no celular fica antes da lista e começa recolhido.
- **Criar leilão:** só o título, sem texto de apoio abaixo dele; 48 px entre o título, os jogos, o campo do
  nome e as cartas.
- **Abas:** texto `--text-muted`; a ativa fica em `--text` com sublinhado de 3 px no degradê da marca,
  sobre uma linha-base em `--border`.
- **Lista de definição** (Detalhes, Perfil): linhas alternadas com o véu azul, rótulo à esquerda e valor à direita.
- **Galeria:** a foto principal tem a sombra mais funda (`--sombra-3`); a miniatura escolhida tem contorno
  em `--text-link`; o botão "Ampliar" é translúcido com desfoque e fica azul no hover.
- **Diálogo da foto:** degradê do card, contorno, `--sombra-3` e o fundo da página escurecido e desfocado.
- **Rodapé:** faixa translúcida escura com um fio no alto, texto `--text-muted`.

## Estados

| Estado | Tratamento |
|---|---|
| Hover | botão primário mais claro e com mais brilho; cards sobem e ganham sombra azulada; itens do menu e botões terciários recebem o véu azul |
| Foco | anel de 2 px em `--text-link`, afastado 2 px (`:focus-visible`; `:focus-within` no campo e no card); campos ganham também o halo |
| Pressed | `translateY(1px)` |
| Enviando | botão com `aria-disabled`, sem brilho, e texto "Enviando…" |
| Lance novo na tabela | realce azul que some em 1,6 s (só `opacity`) |

`prefers-reduced-motion` desliga transições e animações: o ponto do status não pulsa e os cards não sobem.

## Responsivo

| Faixa | Mudanças |
|---|---|
| > 1080 px | galeria (440 px) e coluna de lance (600 px) lado a lado; grade de 5 cards |
| ≤ 1080 px | galeria com até 400 px |
| ≤ 900 px | título, galeria e painel empilhados; painel com até 640 px |
| ≤ 767 px | menu recolhido no botão "Menu"; título antes da galeria (foto de 220 px); campo, mensagens e botão empilhados; grade de 2 cards |

Alvos de toque com pelo menos 44 × 44 px e campo de valor com 22 px de fonte (o iOS não aplica zoom).

## Faça

- Use o azul da marca como fundo (em degradê), com texto branco: botão primário, item ativo, chip ativo.
- Para azul em texto, link ou ícone, use `--text-link`.
- Reserve `--ouro` para dinheiro e para o que pede a atenção do lojista; um dourado por bloco basta.
- Dê às superfícies o trio degradê + contorno fino + sombra (`--grad-cartao` e `--sombra-cartao`).
- Mostre erro e sucesso com ícone e texto, além da cor.

## Não faça

- Não escreva texto nem desenhe ícone em `--accent`, `--accent-hover` ou `--border`.
- Não use `--ouro-escuro` sozinho nem em texto: ele só existe dentro do degradê dourado.
- Não use verde e vermelho como decoração: são só para sucesso, erro e, no botão de perigo, para a ação
  que cancela ou apaga.
- Não troque os contornos de `box-shadow` por `border`: isso muda as medidas dos componentes.
- Não use pílulas nem caixa alta espaçada.
