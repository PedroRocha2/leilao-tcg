---
version: 2
name: Leilao-TCG-tema-escuro
description: Tema escuro quase monocromático do Leilão TCG — fundo preto, superfícies azul-acinzentadas e um único azul de destaque usado só como fundo de botão primário e de item ativo. A tipografia (Inter) e a escala de espaçamento vêm da v1; as cores da v1 (Wise) foram substituídas por completo.

colors:
  bg: "#000000"
  surface: "#252B3D"
  surface-2: "#292C33"
  border: "#2D3F70"
  accent: "#0038D7"
  accent-hover: "#2143A3"
  on-accent: "#FFFFFF"
  text: "#F2F4F8"
  text-muted: "#A3ADC2"
  text-link: "#7A9BFF"
  border-input: "#8C96AD"

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
  badge: 4px
  controle: 6px
  midia: 8px
  cartao: 12px

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
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    height: 64px (56px no celular)
    position: sticky
  nav-item-ativo:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.controle}"
  botao-primario:
    backgroundColor: "{colors.accent}"
    hoverBackground: "{colors.accent-hover}"
    textColor: "{colors.on-accent}"
    typography: "{typography.botao}"
    rounded: "{rounded.controle}"
    height: 48px (56px no painel de lance)
  botao-secundario:
    backgroundColor: "{colors.surface}"
    borderColor: "{colors.border-input}"
    textColor: "{colors.text}"
    rounded: "{rounded.controle}"
  botao-terciario:
    backgroundColor: transparent
    hoverBackground: "{colors.surface-2}"
    textColor: "{colors.text}"
  botao-icone:
    backgroundColor: "{colors.surface-2}"
    borderColor: "{colors.border-input}"
    size: 44px
  chip-filtro:
    backgroundColor: "{colors.surface}"
    activeBackground: "{colors.accent}"
    activeText: "{colors.on-accent}"
    height: 44px
  cartao-leilao:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.cartao}"
    padding: "{spacing.s-3}"
  painel-de-lance:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.cartao}"
    padding: "{spacing.s-6}"
    divider: "{colors.border}"
  campo:
    backgroundColor: "{colors.surface-2}"
    borderColor: "{colors.border-input}"
    errorBorder: 2px "{colors.text}"
    focusRing: 2px "{colors.text-link}"
    rounded: "{rounded.controle}"
    height: 48px (56px no valor do lance)
  badge-status:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.text}"
    dot: "{colors.text-link}"
    rounded: "{rounded.badge}"
  tabela:
    zebra: "{colors.surface-2}"
    destaque: barra de 3px em "{colors.text-link}" + negrito
  abas:
    ativa: texto "{colors.text}" + sublinhado de 2px em "{colors.text}"
    baseline: "{colors.border}"
  dialogo:
    backgroundColor: "{colors.surface}"
    backdrop: rgba(0, 0, 0, 0.86)
  rodape:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-muted}"
---

# Leilão TCG · sistema de design (v2)

## Visão geral

Tema escuro quase monocromático: fundo preto, superfícies em azul-acinzentado e um único azul de
destaque. A carta é a protagonista. As fotos são as únicas cores fortes da página, e a interface se
mantém em preto, cinza-azulado e branco. Há bastante respiro, uma cor de destaque só, nenhum gradiente
e nenhuma sombra em elementos parados.

A tipografia (Inter, servida localmente) e a escala de espaçamento continuam as da v1. As cores da v1
(Wise: verde-limão sobre sálvia claro) foram substituídas pelos tokens abaixo.

## Cores

| Token | Cor | Uso |
|---|---|---|
| `--bg` | `#000000` | fundo da página |
| `--surface` | `#252B3D` | cards, painel de lance, menu, rodapé, diálogo |
| `--surface-2` | `#292C33` | campos, linhas alternadas de tabela e de lista de definição, badge de status |
| `--border` | `#2D3F70` | divisórias decorativas (painel de lance, base das abas, menu aberto) |
| `--accent` | `#0038D7` | botão primário, item ativo do menu e chip ativo, sempre como fundo com texto branco |
| `--accent-hover` | `#2143A3` | hover e pressed do botão primário |
| `--text` | `#F2F4F8` | texto principal; borda de campo com erro |
| `--text-muted` | `#A3ADC2` | texto secundário, rótulos, datas |
| `--text-link` | `#7A9BFF` | links, ícones azuis, anel de foco, marca do maior lance |
| `--border-input` | `#8C96AD` | borda de campos e contorno de botões secundários |

`--on-accent` (`#FFFFFF`) é o texto branco sobre `--accent` e `--accent-hover`.

### Regra de contraste

`#0038D7`, `#2143A3` e `#2D3F70` ficam abaixo de 3:1 sobre o fundo escuro. Por isso nunca aparecem em
texto nem em ícone; o azul de texto é sempre `--text-link`. Contrastes medidos (WCAG 2.x):

| Par | Contraste | Mínimo |
|---|---|---|
| `--text` sobre `--bg` / `--surface` / `--surface-2` | 19,1 / 12,8 / 12,7 : 1 | 4,5:1 |
| `--text-muted` sobre `--bg` / `--surface` / `--surface-2` | 9,3 / 6,2 / 6,2 : 1 | 4,5:1 |
| `--text-link` sobre `--bg` / `--surface` / `--surface-2` | 8,0 / 5,3 / 5,3 : 1 | 4,5:1 |
| branco sobre `--accent` / `--accent-hover` | 8,2 / 8,8 : 1 | 4,5:1 |
| `--border-input` sobre `--surface-2` / `--surface` | 4,7 / 4,8 : 1 | 3:1 (borda de campo) |
| `--accent` / `--accent-hover` / `--border` sobre `--bg` | 2,6 / 2,4 / 2,1 : 1 | — (só fundo ou divisória) |

### Erro e sucesso sem cores novas

A paleta não tem vermelho nem verde, e a v2 não acrescenta nenhum. O estado é dito pela forma e pelo texto:
- **Erro:** ícone de alerta + texto em `--text` (600), campo com borda de 2 px em `--text` e `aria-invalid`.
  O resumo de erros tem barra lateral em `--text`.
- **Sucesso:** check em `--text-link` + texto em `--text`, numa caixa `--surface-2`.
- **Encerrado:** o ponto do badge vira um anel vazado em `--text-muted`.

## Tipografia

Inter (variável, 400–900), uma família só. Cinco tamanhos fazem o trabalho visível:

| Papel | Tamanho | Peso | Uso |
|---|---|---|---|
| Display | 36–56 px (fluido) | 700, tracking −0,03em | `h1` (nome da carta, título da página) |
| Valor | 32–48 px (fluido) | 700, `tabular-nums` | lance atual, saldo |
| Seção | 28 px | 600 | `h2` de seção ("Outros leilões de Pokémon") |
| Corpo | 16–17 px | 400 | texto corrido, descrição (`max-width: 68ch`) |
| Apoio | 13–15 px | 400–600 | rótulos, datas, ajuda, chips |

Valores, datas e contagens usam `font-variant-numeric: tabular-nums`. Títulos usam `text-wrap: balance`.
Tudo em caixa de frase: nada de caixa alta espaçada nem Title Case.

## Espaçamento e grade

- Base de 4 px: 4, 8, 12, 16, 24, 32, 48, 64 e 112 px.
- Container de até 1240 px, com margem lateral fluida de 16 a 40 px.
- Entre seções da página do leilão, 112 px no desktop e 64 px no celular. É sempre maior que qualquer espaço interno.
- Página do leilão: galeria (miniaturas de 72 px + foto de até 440 px) à esquerda e coluna de lance de até
  600 px à direita.

## Formas

| Token | Valor | Uso |
|---|---|---|
| `badge` | 4 px | badge de status |
| `controle` | 6 px | botões, campos, chips, itens do menu, linhas de tabela |
| `midia` | 8 px | fotos nos cards e miniaturas |
| `cartao` | 12 px | cards, painel de lance, diálogo, formulários |

Os raios são escalonados: mais fechados nos controles e mais abertos nos contêineres. Não há pílulas.

## Componentes

- **Menu superior** (`--surface`, fixo): marca à esquerda (leva a Leilões), **Leilões** e, à direita,
  **Entrar** + **Criar conta** (contorno `--border-input`) ou **Minha Conta**. O item ativo tem fundo
  `--accent` com texto branco. No celular, recolhe num botão "Menu" com `aria-expanded`.
- **Botão primário:** fundo `--accent`, texto branco, 48 px (56 px no painel), hover e pressed em `--accent-hover`.
- **Chips de filtro:** `--surface` com contagem em `--text-muted`; o ativo usa o mesmo tratamento do item ativo do menu.
- **Card de leilão:** `--surface`, foto 63:88 com raio de 8 px, nome, edição, lance atual e tempo
  restante. No hover, contorno de 1 px em `--border-input`. O card inteiro é clicável pelo link do nome.
- **Painel de lance:** `--surface`, 32 px de respiro, blocos separados por `--border`: lance atual
  (valor grande), regras (lance inicial e incremento), cronômetro e número de lances, e o formulário.
- **Campo de valor:** `--surface-2`, borda `--border-input`, prefixo "R$", 22 px tabulares e 56 px de
  altura. Já vem preenchido com o lance mínimo.
- **Badge de status:** `--surface-2`, raio de 4 px, ponto em `--text-link` (aberto) ou anel vazado (encerrado).
- **Tabela de lances:** linhas alternadas em `--surface-2`; o maior lance tem negrito, barra de 3 px em
  `--text-link` e a etiqueta "Maior lance".
- **Abas:** texto `--text-muted`; a ativa fica em `--text` com sublinhado de 2 px em `--text`, sobre uma
  linha-base em `--border`.
- **Lista de definição** (Detalhes, Perfil): linhas alternadas em `--surface-2`, rótulo à esquerda e valor à direita.
- **Diálogo da foto:** `--surface`, fundo escurecido a 86%, sombra só aqui (é um elemento sobreposto).
- **Rodapé:** faixa em `--surface`, texto `--text-muted`.

## Estados

| Estado | Tratamento |
|---|---|
| Hover | botão primário em `--accent-hover`; itens e chips em `--surface-2`; cards e miniaturas ganham contorno |
| Foco | anel de 2 px em `--text-link`, afastado 2 px (`:focus-visible`; `:focus-within` no campo e no card) |
| Pressed | `translateY(1px)` |
| Enviando | botão com `aria-disabled` e texto "Enviando…" |
| Lance novo na tabela | realce em `--surface` que some em 1,6 s (só `opacity`) |

`prefers-reduced-motion` desliga transições e animações.

## Responsivo

| Faixa | Mudanças |
|---|---|
| > 1080 px | galeria (520 px) e coluna de lance (600 px) lado a lado; grade de 5 cards |
| ≤ 1080 px | galeria com até 400 px |
| ≤ 900 px | título, galeria e painel empilhados; painel com até 640 px |
| ≤ 767 px | menu recolhido no botão "Menu"; título antes da galeria (foto de 220 px); campo, mensagens e botão empilhados; grade de 2 cards |

Alvos de toque com pelo menos 44 × 44 px e campo de valor com 22 px de fonte (o iOS não aplica zoom).

## Faça

- Use `--accent` só como fundo, com texto branco: botão primário, item ativo, chip ativo.
- Para azul em texto, link ou ícone, use `--text-link`.
- Separe superfícies por degrau de tom (`--bg` → `--surface` → `--surface-2`). Linha só onde a divisória ajuda a ler.
- Mostre erro e sucesso com ícone e texto, além de cor.

## Não faça

- Não escreva texto nem desenhe ícone em `--accent`, `--accent-hover` ou `--border`.
- Não acrescente cores (vermelho, verde, amarelo) nem gradientes.
- Não use sombra em elementos parados; só no menu aberto do celular e no diálogo.
- Não use pílulas nem caixa alta espaçada.
