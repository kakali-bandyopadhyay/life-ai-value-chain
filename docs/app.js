(function () {
  "use strict";

  var dataElement = document.getElementById("vc-data");
  if (!dataElement || !window.VCRank) return;
  var data = JSON.parse(dataElement.textContent);
  var config = data.scoring_config;
  var casesById = Object.create(null);
  data.use_cases.forEach(function (row) { casesById[row.use_case_id] = row; });
  var defaultWeights = {
    value: config.default_weights.value,
    feasibility: config.default_weights.feasibility,
    data_readiness: config.default_weights.data_readiness,
  };
  var currentAppetite = config.default_max_risk;
  var currentStage = "all";
  var lastValid = window.VCRank.rank(data.use_cases, defaultWeights, currentAppetite, config);
  var selectedId = null;
  var rankById = Object.create(null);
  lastValid.ranked.forEach(function (row) { rankById[row.use_case_id] = row; });
  var detailPanel = document.getElementById("row-detail");
  var rankingBody = document.querySelector(".ranked-table tbody");
  var ineligibleBody = document.querySelector(".ineligible-table tbody");
  var formula = document.getElementById("score-formula");
  var announcer = document.getElementById("ranking-announcement");

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char];
    });
  }

  function appetiteLabel(appetite) {
    return appetite.charAt(0).toUpperCase() + appetite.slice(1);
  }

  function stageLabel(stage) {
    var labels = { distribution: "Distribution", underwriting: "Underwriting", policy_admin: "Policy admin", servicing: "Servicing", claims: "Claims" };
    return labels[stage] || String(stage).replace(/_/g, " ");
  }

  function weightsFromInputs() {
    return {
      value: Number(document.getElementById("weight-value").value),
      feasibility: Number(document.getElementById("weight-feasibility").value),
      data_readiness: Number(document.getElementById("weight-data_readiness").value),
    };
  }

  function formulaText(weights, appetite) {
    var total = weights.value + weights.feasibility + weights.data_readiness;
    return "Appetite: " + appetiteLabel(appetite) + " · Score = 100 × (" + weights.value + "·value + " + weights.feasibility + "·feasibility + " + weights.data_readiness + "·data readiness) ÷ (5 × " + total + ")";
  }

  function updateFormula(weights, appetite) {
    var total = weights.value + weights.feasibility + weights.data_readiness;
    formula.classList.toggle("formula-error", total === 0);
    formula.textContent = total === 0 ? "Set at least one weight above 0" : formulaText(weights, appetite);
  }

  function setRowAccess(row) {
    var id = row.getAttribute("data-use-case-id");
    var item = casesById[id];
    if (!item) return;
    row.tabIndex = 0;
    row.setAttribute("role", "button");
    row.setAttribute("aria-expanded", selectedId === id ? "true" : "false");
    row.setAttribute("aria-label", "Open details for " + id + ", " + item.name);
  }

  function setRowsAccess() {
    document.querySelectorAll(".ranked-table tbody tr[data-use-case-id], .ineligible-table tbody tr[data-use-case-id]").forEach(setRowAccess);
  }

  function detailField(label, value) {
    return '<div class="detail-field"><strong>' + escapeHtml(label) + "</strong>" + escapeHtml(value) + "</div>";
  }

  function clearSelectedRows() {
    document.querySelectorAll("tr.is-selected").forEach(function (row) {
      row.classList.remove("is-selected");
      row.setAttribute("aria-expanded", "false");
    });
  }

  function updateSelectedRow() {
    clearSelectedRows();
    if (!selectedId) return;
    document.querySelectorAll('tr[data-use-case-id="' + selectedId + '"]').forEach(function (row) {
      row.classList.add("is-selected");
      row.setAttribute("aria-expanded", "true");
    });
  }

  function openDetail(id, updateHash) {
    var item = casesById[id];
    if (!item) return;
    selectedId = id;
    var rankedItem = rankById[id];
    var statusText = rankedItem ? "Rank " + rankedItem.rank + " · score " + rankedItem.score.toFixed(1) + (rankedItem.shortlisted ? " · Shortlisted" : " · Eligible") : (lastValid.ineligible.find(function (row) { return row.use_case_id === id; }) || {}).status || "Not eligible";
    var fields = [
      detailField("ID", item.use_case_id),
      detailField("Stage", stageLabel(item.value_chain_stage)),
      detailField("Line", item.line_of_business.replace(/\b\w/g, function (letter) { return letter.toUpperCase(); })),
      '<div class="detail-field"><strong>Internal AI risk tier</strong><span class="chip tier tier-' + escapeHtml(item.risk_tier) + '">' + escapeHtml(appetiteLabel(item.risk_tier)) + "</span></div>",
      detailField("Value", item.value),
      detailField("Feasibility", item.feasibility),
      detailField("Data readiness", item.data_readiness),
      detailField(rankedItem ? "Current ranking" : "Gate status", statusText),
      detailField("Owner role", item.owner_role),
    ].join("");
    var governance = "";
    if (item.worked_governance) {
      var summary = data.controls_summary[id] || { pass: 0, fail: 0, "not tested": 0, exceptions: 0 };
      governance = '<div class="stats">' +
        '<span class="chip stat">Pass: <strong>' + summary.pass + "</strong></span>" +
        '<span class="chip stat">Fail: <strong>' + summary.fail + "</strong></span>" +
        '<span class="chip stat">Not tested: <strong>' + summary["not tested"] + "</strong></span>" +
        '<span class="chip stat">Exceptions: <strong>' + summary.exceptions + "</strong></span></div>" +
        '<p class="detail-governance"><a href="#' + escapeHtml(id) + '">Open worked governance ↓</a></p>';
    } else {
      governance = '<p class="detail-governance">Worked governance pack built for VC-01 and VC-05 only.</p>';
    }
    detailPanel.innerHTML = '<div class="detail-heading"><h3>' + escapeHtml(item.use_case_id + " · " + item.name) + '</h3><button class="detail-close" type="button">Close</button></div>' +
      '<div class="detail-grid">' + fields + '</div><div class="detail-rationales"><p><strong>Value rationale:</strong> ' + escapeHtml(item.value_rationale) + '</p>' +
      '<p><strong>Risk rationale:</strong> ' + escapeHtml(item.risk_rationale) + '</p></div>' + governance;
    detailPanel.hidden = false;
    updateSelectedRow();
    if (updateHash && window.location.hash !== "#detail-" + id) window.location.hash = "detail-" + id;
    detailPanel.focus();
  }

  function closeDetail(updateHash) {
    selectedId = null;
    clearSelectedRows();
    detailPanel.hidden = true;
    detailPanel.innerHTML = "";
    if (updateHash && window.location.hash.indexOf("#detail-") === 0) window.location.hash = "ranking";
  }

  function rankedRowHtml(result) {
    var item = casesById[result.use_case_id];
    var status = result.shortlisted ? "Shortlisted" : "Eligible";
    var statusClass = result.shortlisted ? "shortlisted" : "eligible";
    var caseId = item.worked_governance ? '<a href="#' + escapeHtml(item.use_case_id) + '">' + escapeHtml(item.use_case_id) + "</a>" : escapeHtml(item.use_case_id);
    return '<tr data-use-case-id="' + escapeHtml(item.use_case_id) + '">' +
      '<td class="num">' + result.rank + '</td><td class="id-cell">' + caseId + '</td>' +
      '<td class="wrap">' + escapeHtml(item.name) + '</td><td class="wrap">' + escapeHtml(stageLabel(item.value_chain_stage)) + '</td>' +
      '<td class="wrap">' + escapeHtml(item.line_of_business.replace(/\b\w/g, function (letter) { return letter.toUpperCase(); })) + '</td>' +
      '<td class="num">' + item.value + '</td><td class="num">' + item.feasibility + '</td><td class="num">' + item.data_readiness + '</td>' +
      '<td class="wrap"><span class="chip tier tier-' + escapeHtml(item.risk_tier) + '">' + escapeHtml(appetiteLabel(item.risk_tier)) + '</span></td>' +
      '<td class="num">' + result.score.toFixed(1) + '</td><td class="wrap"><span class="chip status status-' + statusClass + '">' + status + '</span></td></tr>';
  }

  function ineligibleRowHtml(result) {
    var item = casesById[result.use_case_id];
    var reason = result.status.replace(/^Not eligible\s+[–-]\s*/, "");
    return '<tr data-use-case-id="' + escapeHtml(item.use_case_id) + '"><td class="id-cell">' + escapeHtml(item.use_case_id) + '</td>' +
      '<td class="wrap">' + escapeHtml(item.name) + '</td><td class="wrap">' + escapeHtml(stageLabel(item.value_chain_stage)) + '</td>' +
      '<td class="wrap"><span class="chip tier tier-' + escapeHtml(item.risk_tier) + '">' + escapeHtml(appetiteLabel(item.risk_tier)) + '</span></td>' +
      '<td class="wrap"><span class="chip status status-not-eligible" aria-label="' + escapeHtml(result.status) + '">Not eligible</span><small class="result-detail">' + escapeHtml(reason) + '</small></td></tr>';
  }

  function updateMatrix(result, appetite) {
    rankById = Object.create(null);
    result.ranked.forEach(function (row) { rankById[row.use_case_id] = row; });
    var ineligibleIds = Object.create(null);
    result.ineligible.forEach(function (row) { ineligibleIds[row.use_case_id] = true; });
    data.use_cases.forEach(function (item) {
      var circle = document.querySelector('.priority-chart circle[data-id="' + item.use_case_id + '"]');
      if (!circle) return;
      var rankedItem = rankById[item.use_case_id];
      circle.setAttribute("class", ineligibleIds[item.use_case_id] ? "gated-point" : rankedItem.shortlisted ? "shortlisted-point" : "eligible-point");
    });
    var caption = document.getElementById("matrix-appetite");
    if (caption) caption.textContent = "Appetite: " + appetiteLabel(appetite);
    var tierOrder = config.risk_order || ["low", "medium", "high", "unacceptable"];
    var boundary = 140 + (tierOrder.indexOf(appetite) + 1) * 120;
    var heatLine = document.querySelector(".heatmap-chart .appetite-line");
    var heatLabel = document.querySelector(".heatmap-chart .appetite-label");
    if (heatLine) {
      heatLine.setAttribute("x1", String(boundary));
      heatLine.setAttribute("x2", String(boundary));
    }
    if (heatLabel) {
      heatLabel.setAttribute("x", String(boundary + 5));
      heatLabel.textContent = "Appetite: " + appetiteLabel(appetite);
    }
  }

  function updateKpis(result, appetite) {
    var eligibleCount = result.ranked.length;
    var shortlistedCount = result.ranked.filter(function (row) { return row.shortlisted; }).length;
    var eligible = document.querySelector(".kpi-eligible");
    var shortlisted = document.querySelector(".kpi-shortlisted");
    var notEligible = document.querySelector(".kpi-ineligible");
    if (eligible) {
      eligible.querySelector(".kpi-main strong").textContent = String(eligibleCount);
      eligible.querySelector(".kpi-caption").textContent = "at " + appetiteLabel(appetite) + " appetite · internal AI risk tier ≤ " + appetiteLabel(appetite);
    }
    if (shortlisted) shortlisted.querySelector(".kpi-main strong").textContent = String(shortlistedCount);
    if (notEligible) {
      notEligible.querySelector(".kpi-main strong").textContent = String(result.ineligible.length);
      var parts = (config.risk_order || ["low", "medium", "high", "unacceptable"]).map(function (tier) {
        var ids = result.ineligible.filter(function (row) { return casesById[row.use_case_id].risk_tier === tier; }).map(function (row) { return row.use_case_id; }).sort();
        return ids.length ? ids.join(", ") + " " + tier : "";
      }).filter(Boolean);
      notEligible.querySelector(".kpi-caption").textContent = parts.join(" · ");
    }
  }

  function applyStageFilter() {
    document.querySelectorAll(".ranked-table tbody tr[data-use-case-id]").forEach(function (row) {
      var item = casesById[row.getAttribute("data-use-case-id")];
      row.hidden = currentStage !== "all" && item.value_chain_stage !== currentStage;
    });
  }

  function renderValidRanking(result, appetite) {
    lastValid = result;
    rankById = Object.create(null);
    result.ranked.forEach(function (row) { rankById[row.use_case_id] = row; });
    rankingBody.innerHTML = result.ranked.map(rankedRowHtml).join("");
    ineligibleBody.innerHTML = result.ineligible.map(ineligibleRowHtml).join("");
    setRowsAccess();
    updateKpis(result, appetite);
    updateMatrix(result, appetite);
    applyStageFilter();
    if (selectedId) {
      if (casesById[selectedId]) openDetail(selectedId, false);
      else closeDetail(false);
    }
    var count = result.ranked.filter(function (row) { return row.shortlisted; }).length;
    announcer.textContent = result.ranked.length + " eligible, " + count + " shortlisted at " + appetiteLabel(appetite) + " appetite";
  }

  function refreshRanking() {
    var weights = weightsFromInputs();
    var appetiteInput = document.querySelector('input[name="appetite"]:checked');
    currentAppetite = appetiteInput ? appetiteInput.value : config.default_max_risk;
    WEIGHT_CONTROL_KEYS.forEach(function (key) {
      var input = document.getElementById("weight-" + key);
      var output = document.getElementById("weight-" + key + "-output");
      var label = key === "data_readiness" ? "Data readiness" : key.charAt(0).toUpperCase() + key.slice(1);
      output.value = input.value;
      input.setAttribute("aria-valuetext", label + " weight " + input.value);
    });
    updateFormula(weights, currentAppetite);
    if (weights.value + weights.feasibility + weights.data_readiness === 0) return;
    renderValidRanking(window.VCRank.rank(data.use_cases, weights, currentAppetite, config), currentAppetite);
  }

  var WEIGHT_CONTROL_KEYS = ["value", "feasibility", "data_readiness"];
  setRowsAccess();
  WEIGHT_CONTROL_KEYS.forEach(function (key) {
    document.getElementById("weight-" + key).addEventListener("input", refreshRanking);
  });
  document.querySelectorAll('input[name="appetite"]').forEach(function (input) { input.addEventListener("change", refreshRanking); });
  document.querySelector(".stage-filters").addEventListener("click", function (event) {
    var button = event.target.closest("button[data-stage]");
    if (!button) return;
    currentStage = button.getAttribute("data-stage");
    document.querySelectorAll(".stage-chip").forEach(function (chip) {
      chip.setAttribute("aria-pressed", chip === button ? "true" : "false");
    });
    applyStageFilter();
  });
  document.querySelector(".reset-ranking").addEventListener("click", function () {
    WEIGHT_CONTROL_KEYS.forEach(function (key) {
      var input = document.getElementById("weight-" + key);
      input.value = String(defaultWeights[key]);
      document.getElementById("weight-" + key + "-output").value = input.value;
      var label = key === "data_readiness" ? "Data readiness" : key.charAt(0).toUpperCase() + key.slice(1);
      input.setAttribute("aria-valuetext", label + " weight " + input.value);
    });
    document.querySelectorAll('input[name="appetite"]').forEach(function (input) { input.checked = input.value === config.default_max_risk; });
    currentAppetite = config.default_max_risk;
    currentStage = "all";
    document.querySelectorAll(".stage-chip").forEach(function (chip) { chip.setAttribute("aria-pressed", chip.getAttribute("data-stage") === "all" ? "true" : "false"); });
    closeDetail(true);
    updateFormula(defaultWeights, currentAppetite);
    renderValidRanking(window.VCRank.rank(data.use_cases, defaultWeights, currentAppetite, config), currentAppetite);
  });

  function rowFromEvent(target) { return target.closest("tr[data-use-case-id]"); }
  document.addEventListener("click", function (event) {
    if (event.target.closest(".detail-close")) {
      closeDetail(true);
      return;
    }
    var row = rowFromEvent(event.target);
    if (row) {
      event.preventDefault();
      openDetail(row.getAttribute("data-use-case-id"), true);
    }
  });
  document.addEventListener("keydown", function (event) {
    var row = rowFromEvent(event.target);
    if (row && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      openDetail(row.getAttribute("data-use-case-id"), true);
      return;
    }
    if (event.key === "Escape" && selectedId) closeDetail(true);
  });
  window.addEventListener("hashchange", function () {
    var match = window.location.hash.match(/^#detail-(VC-\d+)$/);
    if (match) openDetail(match[1], false);
    else if (selectedId) closeDetail(false);
  });
  var initialDetail = window.location.hash.match(/^#detail-(VC-\d+)$/);
  if (initialDetail) openDetail(initialDetail[1], false);
})();
