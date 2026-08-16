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
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-confirm-message]").forEach(function (button) {
      button.addEventListener("click", function (event) {
        if (button.hasAttribute("hx-confirm")) return;
        if (!window.confirm(button.dataset.confirmMessage || "Confirmar ação?")) event.preventDefault();
      });
    });
  });

  // Custom properties dos gráficos do dashboard.
  //
  // Os valores vêm do servidor em `data-css-var` / `data-css-value` em vez de
  // um atributo `style=` porque a Content-Security-Policy é `style-src 'self'`
  // sem exceção. A alternativa seria abrir `style-src-attr 'unsafe-inline'`,
  // que o Firefox não implementa — lá a política cairia de volta para
  // `style-src` e as barras ficariam sem altura.
  //
  // Roda no carregamento e depois de cada troca do HTMX, porque o conteúdo do
  // dashboard é substituído por fragmento.
  (function () {
    "use strict";
    function applyTo(element) {
      var name = element.dataset.cssVar;
      var value = element.dataset.cssValue;
      if (name && value !== undefined) element.style.setProperty(name, value);
    }
    function applyChartVariables(scope) {
      var root = scope || document;
      // O proprio alvo da troca pode carregar o atributo; `querySelectorAll` so
      // enxerga descendentes.
      if (root.dataset && root.dataset.cssVar) applyTo(root);
      root.querySelectorAll("[data-css-var]").forEach(applyTo);
    }
    document.addEventListener("DOMContentLoaded", function () {
      applyChartVariables(document);
    });
    document.body.addEventListener("htmx:afterSwap", function (event) {
      applyChartVariables(event.target);
    });
  }());
