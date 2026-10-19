# Auditoria de interface (v2)

Telas auditadas: lista de leilões, página do leilão, criar conta, entrar e Minha Conta (Perfil,
Carteira e Meus lances). Arquivos: `app/templates/**/*.html`, `app/static/css/app.css` e
`app/static/js/app.js`.

## 1. Web Interface Guidelines (skill `web-design-guidelines`)

Regras obtidas de `vercel-labs/web-interface-guidelines` (command.md) em 14/10/2026. Os achados estão
no formato da skill (`arquivo:linha`), apontando para a linha corrigida.

### Achados e correções

**app/templates/leilao.html**
- [leilao.html:18](../app/templates/leilao.html#L18) — nomes de carta, edição e condição ("Lightning Bolt",
  "Base Set", "Lightly Played") eram traduzidos pelo tradutor automático → `translate="no"`. O mesmo
  vale para [_cartao.html:6](../app/templates/_cartao.html#L6), Meus lances, a trilha e a aba Detalhes
  ([leilao.html:142](../app/templates/leilao.html#L142)).
- [leilao.html:113](../app/templates/leilao.html#L113) — voz passiva ("não podem ser cancelados") → "você não pode cancelá-lo nem reduzi-lo".
- O link "Ampliar" abria um diálogo com JavaScript, ou seja, fazia papel de botão → com JS, ganha
  `role="button"`, `aria-haspopup="dialog"` e responde ao Espaço ([app.js:191](../app/static/js/app.js#L191)).
  Sem JS, continua sendo um link para a foto.
- A aba aberta não ficava no endereço → `#painel-detalhes` e `#painel-descricao` entram na URL; recarregar
  ou compartilhar mantém a aba ([app.js:129](../app/static/js/app.js#L129)).

**app/templates/contas/criar_conta.html**
- [criar_conta.html:40](../app/templates/contas/criar_conta.html#L40) — aspas retas em "Licitante" → “Licitante”.
- [criar_conta.html:23](../app/templates/contas/criar_conta.html#L23) — sair do cadastro com campos
  preenchidos perdia os dados sem aviso → `beforeunload` só quando algum campo foi alterado
  ([app.js:370](../app/static/js/app.js#L370)).

**Mensagens de erro sem próximo passo**
- [leiloes.py:171](../app/dominio/leiloes.py#L171) — recusas por leilão inativo, ainda não iniciado,
  prazo encerrado ou valor zero → cada uma diz o que fazer.
- [contas.py:71](../app/rotas/contas.py#L71) — "E-mail ou senha incorretos." → acrescentado "Confira os dois e tente de novo."

**app/templates/base.html**
- [base.html:67](../app/templates/base.html#L67) — marca no rodapé podia quebrar entre as palavras → `Leilão&nbsp;TCG`.

**app/static/css/app.css**
- [app.css:80](../app/static/css/app.css#L80) — só o `h1` tinha `text-wrap: balance` → vale para `h1`–`h4`.
- [app.css:85](../app/static/css/app.css#L85) — `touch-action: manipulation` só nos botões → links e
  botões em geral (chips, abas, miniaturas, menu).
- [app.css:61](../app/static/css/app.css#L61) — rolagem elástica da página → `overscroll-behavior: none`
  em `@media (pointer: fine)`; telas de toque mantêm o padrão.
- [app.css:559](../app/static/css/app.css#L559) — diálogo da foto sem `overscroll-behavior: contain` → incluído.
- [app.css:511](../app/static/css/app.css#L511) — realce do lance novo animava `background-color` →
  anima só `opacity`, numa camada atrás do texto.
- [app.css:331](../app/static/css/app.css#L331) e [app.css:353](../app/static/css/app.css#L353) —
  miniaturas e botão "Ampliar" sem estado de hover → contorno e fundo mais escuro.
- [app.css:163](../app/static/css/app.css#L163) — o hover do botão de ícone usava `--border`, token
  reservado a divisórias → contorno em `--text`.
- [app.css:222](../app/static/css/app.css#L222) — textos dentro de flex (avisos e erros) sem `min-width: 0` → incluído.
- [app.css:299](../app/static/css/app.css#L299) — nome de carta muito longo na trilha podia estourar → `overflow-wrap: anywhere`.
- [app.css:738](../app/static/css/app.css#L738) — em 360 px, as abas de Minha Conta e o "Sair" não cabiam
  na mesma linha → fonte de 15 px e espaçamento menor.

**Encontrados ao revalidar o RNF01 (seção 3)**
- [app.css:710](../app/static/css/app.css#L710) — no celular, o campo de valor tinha 29 px de altura
  (`flex: 1` em coluna anulava os 56 px), e o motivo da recusa ficava abaixo do botão, longe do campo →
  a área de lance passou a ser um grid: campo, mensagens e botão, nessa ordem.
- [app.css:650](../app/static/css/app.css#L650) — em 768 px as duas colunas espremiam o painel: o lance
  atual quebrava no meio ("R$ 2.35 / 5,00") e o campo mostrava só "R$" → abaixo de 900 px, título,
  galeria e painel ficam empilhados. O valor usa tamanho fluido e não quebra linha
  ([app.css:375](../app/static/css/app.css#L375)).
- [app.js:92](../app/static/js/app.js#L92) — quando a RN02 prorrogava o prazo, o cronômetro só mudava
  no tique seguinte → redesenha na hora.

### Já atendidos desde o início

- Link "Pular para o conteúdo", landmarks (`header`, `nav`, `main`, `footer`) e títulos em ordem (`h1` → `h4`).
- `aria-label` em todo botão só com ícone; SVGs decorativos com `aria-hidden="true"`.
- `label` em todos os campos; `autocomplete`, `type` e `inputmode` corretos (`email`, `tel`, `numeric`,
  `decimal`, `new-password`, `current-password`); `spellcheck="false"` em e-mail, CPF e valor.
- Placeholders com exemplo e terminando em "…" ("(48) 99123-4567…", "000.000.000-00…").
- Erros junto ao campo com `aria-invalid` e `aria-describedby`; resumo de erros com links; foco no
  primeiro campo com erro.
- Resultado do lance anunciado por `aria-live="polite"`; recusa com `role="alert"`; cronômetro com `role="timer"`.
- Botão em "Enviando…" (com `aria-disabled`) durante o envio, e de volta em seguida.
- Abas no padrão ARIA (setas, Home e End); sem JS, as três seções aparecem empilhadas com títulos.
- Diálogo nativo (`<dialog>`): foco preso, Esc fecha e o foco volta ao "Ampliar".
- Menu do celular com `aria-expanded`/`aria-controls`, Esc devolve o foco ao botão e o item ativo tem `aria-current`.
- `:focus-visible` em tudo, com `:focus-within` nos controles compostos (campo de valor, card).
- `scroll-padding-top` para o menu fixo não cobrir o elemento focado.
- `width` e `height` em todas as imagens; `fetchpriority="high"` acima da dobra e `loading="lazy"` abaixo.
- Fonte com `preload` e `font-display: swap`; `color-scheme: dark`.
- `tabular-nums` em valores, datas e contagens; `transition` com propriedades listadas; `prefers-reduced-motion`.
- Filtro por jogo no endereço (`?jogo=pokemon`); navegação sempre por `<a>`.
- Estados vazios: lista filtrada sem leilões, leilão sem lances, Meus lances e extrato vazios.

### Exceções justificadas

- **`outline: none` em `main` ([app.css:116](../app/static/css/app.css#L116)):** o `main` só recebe foco
  programático, pelo link "Pular para o conteúdo". Não é um controle.
- **`theme-color` = `#252B3D` ([base.html:8](../app/templates/base.html#L8)):** é a cor do menu fixo,
  logo abaixo da barra do navegador. Com `#000` apareceria uma emenda entre as duas faixas.
- **Datas formatadas no servidor:** a loja é brasileira, a página é `lang="pt-BR"` e as datas saem no fuso
  America/Sao_Paulo, com `<time datetime>` em ISO para máquinas. O cronômetro mostra uma duração, e
  `Intl.DurationFormat` ainda não tem suporte amplo.
- **Moeda:** no navegador, os valores atualizados sem recarga usam `Intl.NumberFormat("pt-BR", {currency: "BRL"})`.
  O servidor gera exatamente o mesmo texto (teste `test_formata_como_o_intl_number_format_pt_br`), então a
  primeira renderização e as atualizações coincidem.
- **Title Case:** é convenção do inglês. Em português usamos só a primeira letra maiúscula; "Minha Conta"
  segue o nome dado no enunciado.
- **Confirmação antes de ação destrutiva:** dar lance não apaga nada. É irrevogável (RN03), e por isso o
  valor fica visível no campo, o mínimo aparece logo abaixo e o aviso de irrevogabilidade fica embaixo
  do botão. Um modal de confirmação atrasaria lances nos últimos minutos (RN02).
- **`autofocus`:** só aparece quando há erro, para levar ao primeiro campo a corrigir.
- **`alt=""` nas fotos dos cards:** o nome da carta está no título do card, que é o link. Repetir o nome no
  `alt` faria o leitor de tela ler duas vezes.

## 2. Lint da `design-taste-frontend`

```
node scripts/lint.mjs app/templates app/static/css app/static/js
RESULT: 0 FAIL, 2 WARN
```

**Primeira execução: 11 FAIL e 4 WARN.** Como cada um foi tratado:
- **Linhas divisórias (8 FAIL):** a paleta da v2 tem `--border` justamente para divisórias decorativas.
  Ficaram só as do painel de lance e as linhas-base das abas e do menu aberto, marcadas com
  `taste-skill-ignore`. A ficha de detalhes e o perfil trocaram as linhas por linhas alternadas em
  `--surface-2`, como a tabela de lances. O rodapé trocou a linha por uma faixa em `--surface`, que
  repete o menu.
- **Sombras (3 FAIL):** o anel de hover do botão de ícone ficou comentado. O `box-shadow: none` do
  item ativo saiu, e o contorno passou a valer só para `:not([aria-current])`. O ponto vazio do status
  "Encerrado" virou borda.
- **WARN do campo com contorno:** é um campo de formulário com `--border-input`; ficou comentado.
- **WARN do `100vh`:** é o fallback do `100dvh`; ficou comentado.

**Os 2 WARN que restam** são o `padStart` do cronômetro, um caso que a própria regra aceita ("fine for a clock").

O `inspect.mjs` da skill não foi usado, pelos mesmos motivos da v1: ele foi feito para landing pages e
exige animações e fotos por seção. A skill se declara "not for dashboards or app screens". O que vale
para estas telas é a medição do RNF01 abaixo.

## 3. RNF01 revalidado depois do redesign

`pytest tests/test_rnf01_responsivo.py` gera [rnf01/](rnf01/) com as capturas e `medicoes.json`. Em 360,
390 e 768 px:

| Largura | Rolagem horizontal | Campo de valor (largura × altura) | Fonte do campo | Botão "Dar lance" |
|---|---|---|---|---|
| 360 px | não (360 = 360) | 247 × 56 px | 22 px | 288 × 56 px |
| 390 px | não (390 = 390) | 277 × 56 px | 22 px | 318 × 56 px |
| 768 px | não (768 = 768) | 389 × 56 px | 22 px | 134 × 56 px |

Também são medidos:
- cronômetro e lance atual numa linha só;
- miniaturas, abas, chips e itens do menu com pelo menos 44 × 44 px;
- recusa com o motivo junto ao campo e aceite sem recarregar, nas três larguras;
- menu do celular operável pelo teclado.

Para conferir que os critérios novos detectam problemas, o bloco de tablet do CSS foi removido de
propósito. O teste falhou em 768 px ("o campo de valor ficou estreito demais para digitar") e também
em 360 e 390 px (rolagem horizontal). O CSS foi restaurado em seguida.
