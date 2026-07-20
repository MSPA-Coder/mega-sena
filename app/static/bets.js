(() => {
    const form = document.querySelector("[data-generation-form]");
    const previewUrl = form?.dataset.previewUrl || "";
    const filterTargetsUrl = form?.dataset.filterTargetsUrl || "";
    const combinationReportUrl = form?.dataset.combinationUrl || "";
    const filterFieldNames = ["consecutive_count", "even_min", "even_max", "sum_min", "sum_max", "range_min_occupied", "range_max_per_band"];
    const fieldNames = ["amount", ...filterFieldNames];
    if (form) {
      const previewCountField = form.querySelector("[data-filter-preview-count]");
      const previewPercentField = form.querySelector("[data-filter-preview-percent]");
      const targetPercentageField = form.querySelector("[data-filter-target-percentage]");
      const targetButton = form.querySelector("[data-filter-target-button]");
      const targetStatus = form.querySelector("[data-filter-target-status]");
      const csrfField = form.querySelector("[data-csrf-token]");
      const closureNumbersField = form.elements.closure_numbers;
      const amountField = form.elements.amount;
      let previewRequest = 0;
      let previewTimer = null;
      let previewController = null;
      const schedulePreview = () => {
        window.clearTimeout(previewTimer);
        previewTimer = window.setTimeout(updatePreview, 200);
      };
      const applyClosureMode = () => {
        const closureMode = Boolean(closureNumbersField && closureNumbersField.value.trim());
        if (amountField) {
          if (closureMode) {
            if (amountField.value !== "") amountField.dataset.lastValue = amountField.value;
            amountField.value = "";
          } else if (amountField.value === "" && amountField.dataset.lastValue) {
            amountField.value = amountField.dataset.lastValue;
          }
          amountField.readOnly = closureMode;
        }
        for (const name of filterFieldNames) {
          const field = form.elements[name];
          if (!field) continue;
          if (closureMode) field.value = "";
          field.readOnly = closureMode;
        }
        if (targetButton) targetButton.disabled = closureMode;
        if (targetStatus && closureMode) targetStatus.textContent = "";
        return closureMode;
      };
      const normalizeEvenRange = () => {
        const minField = form.elements.even_min;
        const maxField = form.elements.even_max;
        if (!minField || !maxField || minField.value === "" || maxField.value === "") return;
        if (Number(maxField.value) < Number(minField.value)) maxField.value = minField.value;
      };
      const buildGenerationParams = () => {
        const params = new URLSearchParams();
        const quantityField = form.elements.quantity;
        if (quantityField) params.set("quantity", quantityField.value);
        for (const name of fieldNames) {
          const field = form.elements[name];
          if (field) params.set(name, field.value);
        }
        const closureNumbersValue = closureNumbersField?.value;
        if (closureNumbersValue !== undefined) params.set("closure_numbers", closureNumbersValue);
        return params;
      };
      const syncUrl = () => {
        const params = buildGenerationParams();
        const generationId = new URLSearchParams(window.location.search).get("generation_id");
        if (generationId) params.set("generation_id", generationId);
        const query = params.toString();
        window.history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
      };
      const escapeHtml = (value) => String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
      const updateCombinationReport = async (params, requestId, signal) => {
        const report = document.querySelector("[data-combination-report]");
        if (!report) return;
        const formatInt = (value) => Number(value || 0).toLocaleString("pt-BR");
        const formatPercent = (value) => {
          const numeric = Number(value || 0);
          const fixed = numeric.toFixed(8).replace(/0+$/, "").replace(/\.$/, "");
          return fixed.replace(".", ",");
        };
        try {
          const response = await fetch(`${combinationReportUrl}?${params.toString()}`, {headers: {"Accept": "application/json"}, signal});
          if (!response.ok || requestId !== previewRequest) return;
          const data = await response.json();
          const setText = (selector, value) => {
            const node = report.querySelector(selector);
            if (node) node.textContent = value ?? "";
          };
          const selectedAmountValue = Number(data.selected_amount || 0);
          const selectedAmount = Number.isFinite(selectedAmountValue) ? Math.max(1, Math.floor(selectedAmountValue)) : 1;
          const coveredByAmount = data.covered_by_amount ?? 0;
          const chanceWithAmountPercent = data.chance_with_amount_percent ?? 0;
          const chanceWithAmountOneIn = data.chance_with_amount_one_in ?? 0;
          const closureMode = Boolean(data.closure_mode);
          const closureBaseCount = Number(data.closure_base_count || 0);
          setText("[data-combination-total]", data.total_formatted);
          if (closureMode) {
            setText("[data-combination-covered-label]", "Apostas no fechamento");
            setText("[data-combination-covered-detail]", `C(${closureBaseCount}, 6) com ${closureBaseCount} dezenas-base`);
            setText("[data-combination-chance-label]", "Chance no fechamento");
          } else {
            setText("[data-combination-covered-label]", `Cobertas por ${selectedAmount} ${selectedAmount === 1 ? "aposta" : "apostas"}`);
            setText("[data-combination-covered-detail]", `C(${form.elements.quantity?.value || "6"}, 6) x ${selectedAmount}`);
            setText("[data-combination-chance-label]", `Chance com ${selectedAmount} ${selectedAmount === 1 ? "aposta" : "apostas"}`);
          }
          setText("[data-combination-covered]", formatInt(coveredByAmount));
          setText("[data-combination-eliminated]", data.eliminated_formatted);
          setText("[data-combination-remaining]", data.remaining_formatted);
          setText("[data-combination-chance]", `${formatPercent(chanceWithAmountPercent)}%`);
          setText("[data-combination-one-in]", `1 em ${formatInt(chanceWithAmountOneIn)}`);
          const stepsNode = report.querySelector("[data-combination-steps]");
          if (!stepsNode) return;
          if (Array.isArray(data.steps) && data.steps.length) {
            stepsNode.innerHTML = data.steps.map((step) => `
              <p><span>${escapeHtml(step.label)} = ${escapeHtml(step.value)}</span><strong>${escapeHtml(step.eliminated_formatted)}</strong><em>eliminadas</em><strong>${escapeHtml(step.remaining_formatted)}</strong><em>restantes</em></p>
            `).join("");
          } else {
            stepsNode.innerHTML = `<p class="muted">Nenhum filtro aplicado. O universo permanece em ${escapeHtml(data.total_formatted)} combinações.</p>`;
          }
        } catch (_error) {
          if (_error.name === "AbortError") return;
          return;
        }
      };
      const updatePreview = async () => {
        applyClosureMode();
        normalizeEvenRange();
        if (!previewCountField && !previewPercentField) return;
        const requestId = ++previewRequest;
        const params = buildGenerationParams();
        previewController?.abort();
        previewController = new AbortController();
        const {signal} = previewController;
        updateCombinationReport(params, requestId, signal);
        try {
          const response = await fetch(`${previewUrl}?${params.toString()}`, {headers: {"Accept": "application/json"}, signal});
          if (!response.ok) return;
          const data = await response.json();
          if (requestId === previewRequest && previewCountField) previewCountField.value = data.count ?? "";
          if (requestId === previewRequest && previewPercentField) previewPercentField.value = data.percentage_text ?? "";
        } catch (_error) {
          if (_error.name === "AbortError") return;
          if (requestId === previewRequest && previewCountField) previewCountField.value = "";
          if (requestId === previewRequest && previewPercentField) previewPercentField.value = "";
        }
      };
      const applyFilterTargets = async () => {
        if (!targetPercentageField || !targetButton) return;
        if (applyClosureMode()) return;
        const parsedTargetPercentage = Number(targetPercentageField.value);
        const targetPercentage = Number.isFinite(parsedTargetPercentage) ? Math.max(0, Math.min(parsedTargetPercentage, 100)) : 80;
        targetPercentageField.value = targetPercentage;
        targetButton.disabled = true;
        if (targetStatus) targetStatus.textContent = "";
        try {
          const params = new URLSearchParams({target_percentage: String(targetPercentage)});
          const response = await fetch(`${filterTargetsUrl}?${params.toString()}`, {headers: {"Accept": "application/json"}});
          if (!response.ok) return;
          const data = await response.json();
          if (!data.total) {
            if (targetStatus) targetStatus.textContent = "Importe concursos para calcular os parâmetros.";
            return;
          }
          for (const [name, result] of Object.entries(data.parameters || {})) {
            const field = form.elements[name];
            if (field && result && result.value !== null && result.value !== undefined) field.value = result.value;
          }
          syncUrl();
          updatePreview();
          if (targetStatus) targetStatus.textContent = `Parâmetros preenchidos para pelo menos ${targetPercentage.toLocaleString("pt-BR")}% em cada critério isolado.`;
        } catch (_error) {
          if (targetStatus) targetStatus.textContent = "Não foi possível calcular os parâmetros.";
        } finally {
          targetButton.disabled = false;
        }
      };

      applyClosureMode();

      for (const name of fieldNames) {
        const field = form.elements[name];
        if (field) field.addEventListener("input", () => { syncUrl(); schedulePreview(); });
        if (field) field.addEventListener("change", () => { syncUrl(); schedulePreview(); });
      }
      if (closureNumbersField) {
        closureNumbersField.addEventListener("input", () => {
          applyClosureMode();
          syncUrl();
          schedulePreview();
        });
      }
      if (targetButton) targetButton.addEventListener("click", applyFilterTargets);
      form.addEventListener("submit", (event) => {
        const method = (event.submitter?.formMethod || form.method || "get").toLowerCase();
        if (csrfField) csrfField.disabled = method === "get";
        applyClosureMode();
        normalizeEvenRange();
      });
      syncUrl();
      updatePreview();
    }

    for (const button of document.querySelectorAll("[data-generation-toggle]")) {
      button.addEventListener("click", () => {
        const generationId = button.dataset.generationToggle;
        const target = document.querySelector(`[data-generation-bets="${generationId}"]`);
        if (!target) return;
        const willOpen = target.hidden;
        target.hidden = !willOpen;
        button.textContent = willOpen ? "Recolher" : "Ver";
        button.closest(".generation-line")?.classList.toggle("active-generation", willOpen);
      });
    }
  })();

