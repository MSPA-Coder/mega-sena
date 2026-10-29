(() => {
  // HTMX não troca fragmentos 4xx por padrão. Esta recusa é uma resposta
  // de validação esperada da geração, não uma tela genérica de erro/CSRF.
  document.body.addEventListener("htmx:beforeSwap", (event) => {
    const detail = event.detail;
    if (detail.xhr.status === 400 && detail.target?.id === "generation-result" &&
        detail.xhr.getResponseHeader("X-Bets-Validation") === "1") {
      detail.shouldSwap = true;
      detail.isError = false;
    }
  });
  function setupGenerationToggles(root) {
    root.querySelectorAll("[data-generation-toggle]").forEach((button) => {
      if (button.dataset.bound === "true") return;
      button.dataset.bound = "true";
      button.addEventListener("click", () => {
        const target = document.querySelector(`[data-generation-bets="${button.dataset.generationToggle}"]`);
        if (!target) return;
        const willOpen = target.hidden;
        target.hidden = !willOpen;
        button.textContent = willOpen ? "Recolher" : "Ver";
        button.closest(".generation-line")?.classList.toggle("active-generation", willOpen);
      });
    });
  }

  function setupClosureMode(root) {
    const form = root.querySelector("#generation-form");
    if (!form || form.dataset.closureBound === "true") return;
    form.dataset.closureBound = "true";
    const closure = form.elements.closure_numbers;
    const amount = form.elements.amount;
    const quantity = form.elements.quantity;
    const filters = ["consecutive_count", "even_min", "even_max", "sum_min", "sum_max", "range_min_occupied", "range_max_per_band"];
    const apply = () => {
      const enabled = Boolean(closure?.value.trim());
      if (amount) amount.readOnly = enabled;
      if (quantity) quantity.readOnly = enabled;
      filters.forEach((name) => {
        const field = form.elements[name];
        if (field) field.readOnly = enabled;
      });
    };
    closure?.addEventListener("input", apply);
    apply();
  }

  function setupFormBehavior(root) {
    const form = root.querySelector("#generation-form");
    if (!form || form.dataset.submitBound === "true") return;
    form.dataset.submitBound = "true";
    // Enter num campo gera as apostas. Sem isto o navegador aciona o primeiro
    // botão de envio do formulário, que é "Racional", e a pessoa perde a tela.
    form.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" || event.isComposing) return;
      const target = event.target;
      if (!(target instanceof HTMLInputElement) || ["submit", "button"].includes(target.type)) return;
      event.preventDefault();
      document.getElementById("generate-bets")?.click();
    });
    // "Racional" envia o formulário por GET: o token CSRF não pode ir para a
    // URL (histórico, favoritos, cabeçalho Referer). Desabilitado só durante
    // o envio, que lê os campos logo depois deste evento.
    form.addEventListener("submit", (event) => {
      const csrf = form.elements.csrf_token;
      if (csrf && event.submitter && event.submitter.formMethod === "get") {
        csrf.disabled = true;
        setTimeout(() => { csrf.disabled = false; }, 0);
      }
    });
  }

  function setup(root = document) {
    setupGenerationToggles(root);
    setupClosureMode(root);
    setupFormBehavior(root);
  }

  document.addEventListener("DOMContentLoaded", () => setup());
  document.body.addEventListener("htmx:afterSwap", (event) => setup(event.target));
})();
