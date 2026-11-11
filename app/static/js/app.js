(function () {
  "use strict";

  var brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  var numero = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function reais(centavos) { return brl.format(centavos / 100); }

  function definirTexto(seletor, texto) {
    document.querySelectorAll(seletor).forEach(function (el) {
      if (el.textContent !== texto) el.textContent = texto;
    });
  }

  function iniciarMenu() {
    var nav = document.querySelector(".nav");
    var botao = document.querySelector(".botao-menu");
    var lista = document.getElementById("menu-principal");
    if (!nav || !botao || !lista) return;
    var celular = window.matchMedia("(max-width: 767px)");
    botao.hidden = false;

    function aberto() { return nav.classList.contains("nav--aberta"); }

    function abrir() {
      nav.classList.add("nav--aberta");
      botao.setAttribute("aria-expanded", "true");
      var atual = lista.querySelector("[aria-current]") || lista.querySelector("a");
      if (atual) atual.focus();
    }

    function fechar(devolverFoco) {
      if (!aberto()) return;
      nav.classList.remove("nav--aberta");
      botao.setAttribute("aria-expanded", "false");
      if (devolverFoco) botao.focus();
    }

    botao.addEventListener("click", function () {
      if (aberto()) fechar(false); else abrir();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && aberto()) { e.preventDefault(); fechar(true); }
    });
    document.addEventListener("click", function (e) {
      if (aberto() && !nav.contains(e.target)) fechar(false);
    });
    nav.addEventListener("focusout", function (e) {
      if (aberto() && celular.matches && e.relatedTarget && !nav.contains(e.relatedTarget)) fechar(false);
    });
    celular.addEventListener("change", function (e) { if (!e.matches) fechar(false); });
  }

  var desvio = Date.parse(document.body.dataset.agora) - Date.now();
  if (isNaN(desvio)) desvio = 0;

  function agora() { return Date.now() + desvio; }

  function formatarRestante(ms) {
    var s = Math.max(0, Math.floor(ms / 1000));
    var d = Math.floor(s / 86400);
    var h = Math.floor((s % 86400) / 3600);
    var m = Math.floor((s % 3600) / 60);
    var seg = s % 60;
    if (d > 0) return d + " d " + h + " h " + m + " min";
    if (h > 0) return h + " h " + String(m).padStart(2, "0") + " min";
    return m + " min " + String(seg).padStart(2, "0") + " s";
  }

  function atualizarContagens() {
    document.querySelectorAll("[data-contagem]").forEach(function (el) {
      var restante = Date.parse(el.dataset.alvo) - agora();
      var texto = formatarRestante(restante);
      if (el.textContent !== texto) el.textContent = texto;
      if (restante <= 0 && el.dataset.aoZerar && !el.dataset.zerado) {
        el.dataset.zerado = "1";
        window.setTimeout(function () { window.location.reload(); }, 1500);
      }
    });
  }

  function iniciarContagens() {
    if (!document.querySelector("[data-contagem]")) return;
    atualizarContagens();
    window.setInterval(atualizarContagens, 1000);
  }

  function iniciarAbas() {
    var raiz = document.querySelector("[data-abas]");
    if (!raiz) return;
    var lista = raiz.querySelector("[data-abas-lista]");
    var botoes = Array.prototype.slice.call(lista.querySelectorAll("[data-aba]"));
    var paineis = botoes.map(function (b) { return document.getElementById(b.dataset.aba); });

    lista.hidden = false;
    lista.setAttribute("role", "tablist");
    lista.setAttribute("aria-labelledby", "titulo-abas");
    raiz.classList.add("abas--ativas");
    botoes.forEach(function (botao, i) {
      botao.id = "aba-" + paineis[i].id;
      botao.setAttribute("role", "tab");
      botao.setAttribute("aria-controls", paineis[i].id);
      paineis[i].setAttribute("role", "tabpanel");
      paineis[i].setAttribute("aria-labelledby", botao.id);
      paineis[i].tabIndex = 0;
      var titulo = paineis[i].querySelector(".painel-aba__titulo");
      if (titulo) titulo.classList.add("vh");
    });

    function selecionar(indice, focar, registrar) {
      botoes.forEach(function (botao, i) {
        var ativa = i === indice;
        botao.setAttribute("aria-selected", String(ativa));
        botao.tabIndex = ativa ? 0 : -1;
        paineis[i].hidden = !ativa;
      });
      if (focar) botoes[indice].focus();
      if (registrar) history.replaceState(null, "", indice === 0 ? location.pathname + location.search : "#" + paineis[indice].id);
    }

    lista.addEventListener("click", function (e) {
      var botao = e.target.closest("[data-aba]");
      if (botao) selecionar(botoes.indexOf(botao), false, true);
    });
    lista.addEventListener("keydown", function (e) {
      var atual = botoes.indexOf(document.activeElement);
      if (atual < 0) return;
      var destino = { ArrowRight: atual + 1, ArrowLeft: atual - 1, Home: 0, End: botoes.length - 1 }[e.key];
      if (destino === undefined) return;
      e.preventDefault();
      selecionar((destino + botoes.length) % botoes.length, true, true);
    });
    var inicial = paineis.findIndex(function (painel) { return "#" + painel.id === location.hash; });
    selecionar(Math.max(inicial, 0), false, false);
  }

  function iniciarGaleria() {
    var galeria = document.querySelector("[data-galeria]");
    if (!galeria) return;
    var fotos = Array.prototype.map.call(
      galeria.querySelector("[data-fotos]").content.querySelectorAll("[data-url]"),
      function (el) { return { url: el.dataset.url, descricao: el.dataset.descricao }; }
    );
    var principal = galeria.querySelector("[data-foto-principal]");
    var link = galeria.querySelector("[data-ampliar]");
    var miniaturas = Array.prototype.slice.call(galeria.querySelectorAll(".miniatura"));
    var dialogo = document.querySelector("[data-ampliacao]");
    var atual = 0;
    var atualizarDialogo = function () {};

    function mostrar(indice) {
      atual = (indice + fotos.length) % fotos.length;
      principal.src = fotos[atual].url;
      principal.alt = fotos[atual].descricao;
      link.href = fotos[atual].url;
      miniaturas.forEach(function (m, i) { m.setAttribute("aria-pressed", String(i === atual)); });
      atualizarDialogo();
    }

    miniaturas.forEach(function (miniatura, i) {
      miniatura.addEventListener("click", function () { mostrar(i); });
    });

    if (!dialogo || typeof dialogo.showModal !== "function") return;
    var imagem = dialogo.querySelector("[data-ampliacao-foto]");
    var titulo = dialogo.querySelector("[data-ampliacao-titulo]");
    var legenda = dialogo.querySelector("[data-ampliacao-legenda]");
    var nome = titulo.textContent;

    atualizarDialogo = function () {
      imagem.src = fotos[atual].url;
      imagem.alt = fotos[atual].descricao;
      titulo.textContent = fotos.length > 1 ? nome + " · foto " + (atual + 1) + " de " + fotos.length : nome;
      if (legenda) legenda.textContent = fotos[atual].descricao.split(": ").pop() + " · use as setas para trocar de foto";
    };

    link.setAttribute("role", "button");
    link.setAttribute("aria-haspopup", "dialog");
    function ampliar(e) {
      e.preventDefault();
      atualizarDialogo();
      dialogo.showModal();
    }
    link.addEventListener("click", ampliar);
    link.addEventListener("keydown", function (e) { if (e.key === " ") ampliar(e); });
    dialogo.querySelector("[data-fechar]").addEventListener("click", function () { dialogo.close(); });
    var anterior = dialogo.querySelector("[data-anterior]");
    var proxima = dialogo.querySelector("[data-proxima]");
    if (anterior) anterior.addEventListener("click", function () { mostrar(atual - 1); });
    if (proxima) proxima.addEventListener("click", function () { mostrar(atual + 1); });
    dialogo.addEventListener("keydown", function (e) {
      if (fotos.length < 2) return;
      if (e.key === "ArrowLeft") { e.preventDefault(); mostrar(atual - 1); }
      if (e.key === "ArrowRight") { e.preventDefault(); mostrar(atual + 1); }
    });
    dialogo.addEventListener("click", function (e) { if (e.target === dialogo) dialogo.close(); });
  }

  function iniciarLeilao() {
    var leilao = document.querySelector("[data-leilao]");
    if (!leilao) return;
    var painel = leilao.querySelector("[data-painel]");
    var anuncio = painel.querySelector("[data-anuncio]");
    var form = painel.querySelector("[data-form-lance]");
    var linhas = document.querySelector("[data-linhas-lances]");
    var campo = form && form.elements.valor;
    var valorConhecido = Number(painel.querySelector("[data-valor]").dataset.centavos);
    var minimoNoCampo = campo ? campo.value : null;
    var aberto = leilao.dataset.aberto === "true";

    function anunciar(texto) {
      anuncio.textContent = "";
      window.setTimeout(function () { anuncio.textContent = texto; }, 50);
    }

    function destacarMaior() {
      var linha = linhas && linhas.querySelector("tr.maior");
      if (linha) linha.classList.add("novo");
    }

    function aplicar(dados) {
      var e = dados.estado;
      if (!e) return;
      definirTexto("[data-rotulo-valor]", e.rotulo_valor);
      definirTexto("[data-valor]", reais(e.valor_centavos));
      definirTexto("[data-total-lances]", String(e.total_lances));
      definirTexto("[data-minimo]", reais(e.minimo_centavos));
      definirTexto("[data-regra-inicial]", e.tem_lances ? "Lance inicial " + reais(e.lance_inicial_centavos) : "Nenhum lance ainda");
      definirTexto("[data-minimo-regra]", e.tem_lances ? "(maior lance + incremento mínimo)" : "(o lance inicial)");
      definirTexto("[data-situacao]", e.situacao);
      definirTexto("[data-fim-quando]", e.fim_quando);
      var contagem = painel.querySelector("[data-contagem]");
      if (contagem && contagem.dataset.alvo !== e.fim_iso) {
        contagem.dataset.alvo = e.fim_iso;
        delete contagem.dataset.zerado;
        atualizarContagens();
      }
      if (linhas && typeof dados.tabela === "string") linhas.innerHTML = dados.tabela;
      if (campo && campo.value === minimoNoCampo) {
        minimoNoCampo = numero.format(e.minimo_centavos / 100);
        campo.value = minimoNoCampo;
      }
    }

    if (form) {
      var erro = form.querySelector("#erro-lance");
      var textoDoErro = erro.querySelector("[data-erro]");
      var ajuda = form.querySelector("#ajuda-lance");
      var ok = form.querySelector("[data-ok]");
      var textoDoOk = ok.querySelector("[data-ok-texto]");
      var enviar = form.querySelector("[data-enviar]");
      var caixa = form.querySelector(".campo-valor");

      var mostrarErro = function (texto) {
        textoDoErro.textContent = texto;
        erro.hidden = false;
        erro.setAttribute("role", "alert");
        ajuda.hidden = true;
        ok.hidden = true;
        campo.setAttribute("aria-invalid", "true");
        campo.setAttribute("aria-describedby", "erro-lance");
        caixa.classList.add("campo-valor--erro");
        campo.focus();
      };

      var limparErro = function () {
        erro.hidden = true;
        erro.removeAttribute("role");
        textoDoErro.textContent = "";
        ajuda.hidden = false;
        campo.removeAttribute("aria-invalid");
        campo.setAttribute("aria-describedby", "ajuda-lance");
        caixa.classList.remove("campo-valor--erro");
      };

      campo.addEventListener("input", function () {
        if (!erro.hidden) limparErro();
        ok.hidden = true;
      });

      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        if (enviar.getAttribute("aria-disabled") === "true") return;
        limparErro();
        ok.hidden = true;
        enviar.setAttribute("aria-disabled", "true");
        enviar.textContent = "Enviando…";

        fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          headers: { Accept: "application/json" },
          credentials: "same-origin"
        })
          .then(function (resposta) {
            return resposta.json().then(function (dados) {
              return { status: resposta.status, ok: resposta.ok, dados: dados };
            });
          })
          .then(function (r) {
            if (r.status === 401 && r.dados.entrar) { window.location.assign(r.dados.entrar); return; }
            if (r.ok) {
              minimoNoCampo = campo.value;
              aplicar(r.dados);
              valorConhecido = r.dados.estado.valor_centavos;
              textoDoOk.textContent = r.dados.mensagem;
              ok.hidden = false;
              anunciar(r.dados.mensagem);
              destacarMaior();
            } else {
              aplicar(r.dados);
              mostrarErro(r.dados.mensagem || "Não foi possível registrar o lance.");
            }
          })
          .catch(function () {
            mostrarErro("Não foi possível enviar o lance. Verifique sua conexão e tente de novo.");
          })
          .finally(function () {
            enviar.removeAttribute("aria-disabled");
            enviar.textContent = "Dar lance";
          });
      });
    }

    var url = leilao.dataset.estadoUrl;
    window.setInterval(function () {
      if (document.hidden) return;
      fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (dados) {
          if (!dados || !dados.estado) return;
          // O leilão começou ou terminou: o painel muda inteiro, então a página é recarregada.
          if (dados.estado.aberto !== aberto) { window.location.reload(); return; }
          aplicar(dados);
          if (dados.estado.valor_centavos !== valorConhecido) {
            valorConhecido = dados.estado.valor_centavos;
            if (!dados.estado.voce_lidera) anunciar("Novo lance atual: " + reais(valorConhecido) + ".");
            destacarMaior();
          }
        })
        .catch(function () {});
    }, 5000);
  }

  // Criar leilão: o filtro troca as cartas enquanto o vendedor digita. Sem JavaScript, o formulário recarrega a página.
  function iniciarFiltroDeCartas() {
    var form = document.querySelector("[data-filtro-cartas]");
    var resultados = document.querySelector("[data-resultados]");
    if (!form || !resultados || typeof DOMParser !== "function" || typeof AbortController !== "function") return;
    var campo = form.elements.q;
    var status = form.querySelector("[data-filtro-status]");
    var minimo = campo.minLength > 0 ? campo.minLength : 1;
    var pedido = campo.value.trim();
    var espera = null;
    var controle = null;

    function filtrar() {
      window.clearTimeout(espera);
      var texto = campo.value.trim().replace(/\s+/g, " ");
      if (texto === pedido || (texto && texto.length < minimo)) return;
      pedido = texto;
      var url = new URL(form.action, window.location.href);
      url.searchParams.set("jogo", form.elements.jogo.value);
      if (texto) url.searchParams.set("q", texto);
      if (controle) controle.abort();
      var meu = controle = new AbortController();
      resultados.setAttribute("aria-busy", "true");

      fetch(url, { headers: { Accept: "text/html" }, credentials: "same-origin", signal: meu.signal })
        .then(function (resposta) { return resposta.text(); })
        .then(function (html) {
          var novos = new DOMParser().parseFromString(html, "text/html").querySelector("[data-resultados]");
          // Sem a região de resultados a resposta é outra página (a sessão expirou): o navegador vai até ela.
          if (!novos) { window.location.assign(url); return; }
          resultados.innerHTML = novos.innerHTML;
          history.replaceState(null, "", url);
          var resumo = resultados.querySelector("[data-resumo]");
          if (status && resumo) status.textContent = resumo.textContent.trim();
        })
        .catch(function (erro) {
          if (erro.name !== "AbortError") window.location.assign(url);
        })
        .finally(function () {
          if (controle !== meu) return;
          controle = null;
          resultados.removeAttribute("aria-busy");
        });
    }

    campo.addEventListener("input", function () {
      window.clearTimeout(espera);
      espera = window.setTimeout(filtrar, 350);
    });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      filtrar();
    });
  }

  function iniciarAvisoAoSair() {
    var form = document.querySelector("[data-avisar-ao-sair]");
    if (!form) return;
    var alterado = false;
    form.addEventListener("input", function () { alterado = true; });
    form.addEventListener("submit", function () { alterado = false; });
    window.addEventListener("beforeunload", function (e) {
      if (!alterado) return;
      e.preventDefault();
      e.returnValue = "";
    });
  }

  iniciarMenu();
  iniciarFiltroDeCartas();
  iniciarAvisoAoSair();
  iniciarContagens();
  iniciarAbas();
  iniciarGaleria();
  iniciarLeilao();
})();
