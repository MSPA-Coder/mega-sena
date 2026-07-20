(function () {
  "use strict";

  var config = document.querySelector("[data-dashboard-config]");
  if (!config) return;
  var API_URL = config.dataset.statsUrl;
  var CONTESTS_URL = config.dataset.contestsUrl;
  var dashboardController = null;

  function pad2(n) { return String(n).padStart(2, "0"); }

  function round1(value) { return Math.round(value * 10) / 10; }

  function pct(part, whole) {
    if (!whole) return 0;
    return round1((part / whole) * 100);
  }

  function numericKeysSorted(obj) {
    return Object.keys(obj).map(Number).sort(function (a, b) { return a - b; });
  }

  // ---------------------------------------------------------------------
  // Card "Concursos" / "Acertadores"
  // ---------------------------------------------------------------------

  function applyTopMetrics(data) {
    setText("dash-total-draws", data.total_draws);
    setText("dash-with-winners", data.mega_sena_games_with_winners);
    setText("dash-with-winners-pct", data.mega_sena_games_with_winners_pct + "%");
    setText("dash-without-winners", data.mega_sena_games_without_winners);
    setText("dash-without-winners-pct", data.mega_sena_games_without_winners_pct + "%");

    setText("dash-winners-mega", data.prize_cards.mega_sena.winners);
    setText("dash-winners-quina", data.prize_cards.quina.winners);
    setText("dash-winners-quadra", data.prize_cards.quadra.winners);
  }

  function setText(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  // ---------------------------------------------------------------------
  // Distribuições (pares, sequência consecutiva, faixas)
  // ---------------------------------------------------------------------

  function buildEvenDistribution(data) {
    return numericKeysSorted(data.even_distribution).map(function (qtd) {
      var total = data.even_distribution[String(qtd)];
      return '<p>' +
        '<a class="history-filter-link" href="' + CONTESTS_URL + '?even_count=' + qtd + '"><b>' + qtd + '</b></a>' +
        '<strong>' + total + '</strong>' +
        '<em>concursos</em>' +
        '<em>' + String(pct(total, data.total_draws)).replace(".", ",") + '%</em>' +
        '</p>';
    }).join("");
  }

  function buildConsecutiveDistribution(data) {
    return numericKeysSorted(data.consecutive_distribution).map(function (qtd) {
      var total = data.consecutive_distribution[String(qtd)];
      return '<p>' +
        '<a class="history-filter-link" href="' + CONTESTS_URL + '?consecutive_count=' + qtd + '"><b>' + qtd + '</b></a>' +
        '<strong>' + total + '</strong>' +
        '<em>concursos</em>' +
        '<em>' + String(pct(total, data.total_draws)).replace(".", ",") + '%</em>' +
        '</p>';
    }).join("");
  }

  function buildRanges(data) {
    var order = ["01-10", "11-20", "21-30", "31-40", "41-50", "51-60"];
    var totalSlots = data.total_draws * 6;
    return order.map(function (faixa) {
      var total = data.ranges[faixa] || 0;
      return '<p><span>' + faixa + '</span><strong>' + total + '</strong><em>' +
        String(pct(total, totalSlots)).replace(".", ",") + '%</em></p>';
    }).join("");
  }

  // ---------------------------------------------------------------------
  // Mais / Menos frequentes
  // ---------------------------------------------------------------------

  function buildFrequencyCards(data) {
    var most = (data.most_frequent || []).map(function (pair) {
      return '<span class="frequency-item"><b class="ball">' + pad2(pair[0]) + '</b><strong>' + pair[1] + 'x</strong></span>';
    }).join("");
    var least = (data.least_frequent || []).map(function (pair) {
      return '<span class="frequency-item"><b class="ball warn">' + pad2(pair[0]) + '</b><strong>' + pair[1] + 'x</strong></span>';
    }).join("");
    return { most: most, least: least };
  }

  // ---------------------------------------------------------------------
  // Gráfico: Frequência X Número Sorteado
  // ---------------------------------------------------------------------

  function buildYAxis(maxValue) {
    return [maxValue, Math.round(maxValue * 0.75), Math.round(maxValue * 0.5), Math.round(maxValue * 0.25), 0]
      .map(function (t) { return "<span>" + t + "</span>"; })
      .join("");
  }

  function buildFrequencyChart(data) {
    var freqValues = Object.keys(data.frequency).map(function (k) { return data.frequency[k]; });
    var maxFreq = freqValues.length ? Math.max.apply(null, freqValues) : 0;
    var ticks = [maxFreq, Math.round(maxFreq * 0.75), Math.round(maxFreq * 0.5), Math.round(maxFreq * 0.25)];
    var gridlines = ticks.map(function (t) {
      return '<span class="frequency-gridline" style="--tick:' + t + ';"></span>';
    }).join("");
    var bars = numericKeysSorted(data.frequency).map(function (n) {
      var c = data.frequency[String(n)];
      var label = pad2(n);
      return '<div class="frequency-bar" title="' + label + ': ' + c + 'x" style="--count:' + c + ';">' +
        '<div class="frequency-bar-track"><span></span></div>' +
        '<small>' + label + '</small></div>';
    }).join("");
    return { html: gridlines + bars, maxFreq: maxFreq };
  }

  // ---------------------------------------------------------------------
  // Gráfico: Frequência x Soma dos Números Sorteados
  // ---------------------------------------------------------------------

  function buildSumHistogram(data) {
    var hist = data.sum_histogram || { bins: [], y_ticks: [0], max_frequency: 0 };
    var yAxisHtml = hist.y_ticks.slice().reverse().map(function (t) {
      return "<span>" + t + "</span>";
    }).join("");

    var gridlines = hist.y_ticks.map(function (t) {
      return '<span class="sum-gridline" style="--tick:' + t + ';"></span>';
    }).join("");
    var bars = hist.bins.map(function (bin) {
      return '<div class="sum-histogram-bar" title="' + bin.start + '-' + bin.end + ': ' + bin.count + ' concursos" style="--count:' + bin.count + ';">' +
        '<span></span><small>' + (bin.x_label || "") + '</small></div>';
    }).join("");

    return {
      yAxisHtml: yAxisHtml,
      chartHtml: gridlines + bars,
      maxFrequency: hist.max_frequency || 1,
    };
  }

  // ---------------------------------------------------------------------
  // Label de período
  // ---------------------------------------------------------------------

  function updatePeriodLabel(data) {
    var el = document.getElementById("freq-period-label");
    if (!el) return;
    var n = data.actual_count || 0;
    el.textContent = data.count ? ("últimos " + n + " concursos") : (n + " concursos");
  }

  // ---------------------------------------------------------------------
  // Aplica os dados recebidos a TODOS os elementos do dashboard
  // ---------------------------------------------------------------------

  function setHtml(id, html) {
    var el = document.getElementById(id);
    if (el) el.innerHTML = html;
  }

  function applyData(data) {
    applyTopMetrics(data);
    updatePeriodLabel(data);

    setHtml("dash-even-distribution", buildEvenDistribution(data));
    setHtml("dash-consecutive-distribution", buildConsecutiveDistribution(data));
    setHtml("dash-ranges-distribution", buildRanges(data));

    var freqCards = buildFrequencyCards(data);
    setHtml("most-frequent-list", freqCards.most);
    setHtml("least-frequent-list", freqCards.least);

    var freqChart = buildFrequencyChart(data);
    var chartEl = document.getElementById("freq-chart");
    if (chartEl) chartEl.style.setProperty("--max-frequency", freqChart.maxFreq || 1);
    setHtml("freq-chart", freqChart.html);
    setHtml("freq-y-axis", buildYAxis(freqChart.maxFreq));

    var sumHistogram = buildSumHistogram(data);
    var sumChartEl = document.getElementById("sum-histogram");
    if (sumChartEl) sumChartEl.style.setProperty("--max-frequency", sumHistogram.maxFrequency);
    setHtml("sum-histogram", sumHistogram.chartHtml);
    setHtml("sum-y-axis", sumHistogram.yAxisHtml);

    setDashboardOpacity("1");
  }

  function setDashboardOpacity(value) {
    ["freq-chart", "sum-histogram"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.style.opacity = value;
    });
  }

  function fetchPeriod(period) {
    var url = API_URL + (period ? "?count=" + period : "");
    setDashboardOpacity("0.35");
    if (dashboardController) dashboardController.abort();
    dashboardController = new AbortController();

    fetch(url, {signal: dashboardController.signal})
      .then(function (r) { return r.json(); })
      .then(applyData)
      .catch(function (error) {
        if (error.name !== "AbortError") setDashboardOpacity("1");
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var buttons = document.querySelectorAll(".period-btn");
    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        buttons.forEach(function (b) {
          b.classList.remove("active");
          b.setAttribute("aria-pressed", "false");
        });
        btn.classList.add("active");
        btn.setAttribute("aria-pressed", "true");
        fetchPeriod(btn.dataset.period);
      });
    });
  });
}());

