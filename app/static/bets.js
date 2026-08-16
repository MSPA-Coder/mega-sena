(() => {
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
    const filters = ["consecutive_count", "even_min", "even_max", "sum_min", "sum_max", "range_min_occupied", "range_max_per_band"];
    const apply = () => {
      const enabled = Boolean(closure?.value.trim());
      if (amount) amount.readOnly = enabled;
      filters.forEach((name) => {
        const field = form.elements[name];
        if (field) field.readOnly = enabled;
      });
    };
    closure?.addEventListener("input", apply);
    apply();
  }

  function setup(root = document) {
    setupGenerationToggles(root);
    setupClosureMode(root);
  }

  document.addEventListener("DOMContentLoaded", () => setup());
  document.body.addEventListener("htmx:afterSwap", (event) => setup(event.target));
})();
