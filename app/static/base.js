// O indicador de requisição HTMX já tem CSS próprio em components.css
// (span.htmx-indicator / .htmx-request .htmx-indicator) cobrindo o mesmo
// show/hide. O <style> que o HTMX injetaria por padrão é redundante e
// viola `style-src 'self'` (sem nonce) — aparece só como ruído no console,
// sem efeito visível, mas desligar evita o aviso de CSP. Roda antes de
// DOMContentLoaded, quando o HTMX de fato aplica o config (init adiado até lá).
htmx.config.includeIndicatorStyles = false;

(function () {
    "use strict";
    var root = document.documentElement;
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    function describe(theme) {
      btn.setAttribute("aria-label", theme === "dark" ? "Mudar para tema claro" : "Mudar para tema escuro");
    }
    describe(root.dataset.theme || "light");
    btn.addEventListener("click", function () {
      var next = root.dataset.theme === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      document.cookie = "theme=" + next + ";path=/;max-age=" + 60 * 60 * 24 * 365 + ";SameSite=Lax";
      describe(next);
    });
  }());
  (function () {
    "use strict";
    var topbar = document.querySelector(".topbar");
    var btn = document.getElementById("nav-toggle");
    var nav = document.getElementById("primary-nav");
    if (!topbar || !btn || !nav) return;
    topbar.classList.add("nav-ready");

    function setOpen(open) {
      topbar.classList.toggle("nav-open", open);
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      btn.setAttribute("aria-label", open ? "Fechar menu principal" : "Abrir menu principal");
    }

    btn.addEventListener("click", function () {
      setOpen(btn.getAttribute("aria-expanded") !== "true");
    });

    nav.addEventListener("click", function (event) {
      if (event.target.closest("a")) setOpen(false);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") setOpen(false);
    });

    window.matchMedia("(min-width: 851px)").addEventListener("change", function (event) {
      if (event.matches) setOpen(false);
    });
  }());
  (function () {
    "use strict";
    // Grupos do menu (Apostas, Concursos, Conta e administração): o botão abre
    // e fecha o painel de subitens; só um fica aberto por vez.
    var groups = Array.prototype.slice.call(document.querySelectorAll("[data-nav-group]"));
    if (!groups.length) return;

    function toggleOf(group) {
      return group.querySelector(".nav-group-toggle");
    }

    function setOpen(group, open) {
      group.classList.toggle("open", open);
      toggleOf(group).setAttribute("aria-expanded", open ? "true" : "false");
    }

    function closeAll(except) {
      groups.forEach(function (group) {
        if (group !== except) setOpen(group, false);
      });
    }

    groups.forEach(function (group) {
      toggleOf(group).addEventListener("click", function () {
        var open = !group.classList.contains("open");
        closeAll(group);
        setOpen(group, open);
      });
    });

    document.addEventListener("click", function (event) {
      if (!event.target.closest("[data-nav-group]")) closeAll(null);
    });

    // O foco que sai do menu (Tab para o conteúdo) fecha o painel.
    document.addEventListener("focusin", function (event) {
      if (!event.target.closest("[data-nav-group]")) closeAll(null);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      var aberto = groups.filter(function (group) { return group.classList.contains("open"); })[0];
      if (!aberto) return;
      closeAll(null);
      toggleOf(aberto).focus();
    });
  }());
