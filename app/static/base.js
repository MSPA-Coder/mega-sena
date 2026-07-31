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

    if (window.matchMedia) {
      var desktop = window.matchMedia("(min-width: 851px)");
      var closeOnDesktop = function (event) {
        if (event.matches) setOpen(false);
      };
      if (desktop.addEventListener) {
        desktop.addEventListener("change", closeOnDesktop);
      } else if (desktop.addListener) {
        desktop.addListener(closeOnDesktop);
      }
    }
  }());
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-submit-on-change]").forEach(function (field) {
      field.addEventListener("change", function () {
        if (field.form) field.form.submit();
      });
    });
    document.querySelectorAll("[data-confirm-message]").forEach(function (button) {
      button.addEventListener("click", function (event) {
        if (button.hasAttribute("hx-confirm")) return;
        if (!window.confirm(button.dataset.confirmMessage || "Confirmar ação?")) event.preventDefault();
      });
    });
  });
