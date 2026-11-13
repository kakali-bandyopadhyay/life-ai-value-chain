(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (typeof window !== "undefined") window.VCRank = api;
})(typeof window !== "undefined" ? window : {}, function () {
  "use strict";

  var DEFAULT_CONFIG = {
    risk_order: ["low", "medium", "high", "unacceptable"],
    allowed_max_risk: ["low", "medium", "high"],
    shortlist_size: 5,
  };
  var WEIGHT_KEYS = ["value", "feasibility", "data_readiness"];

  function checkedWeights(weights) {
    var values = Array.isArray(weights)
      ? weights.slice()
      : WEIGHT_KEYS.map(function (key) { return weights && Object.prototype.hasOwnProperty.call(weights, key) ? weights[key] : 0; });
    if (values.length !== 3) throw new Error("Weights must contain value, feasibility, and data_readiness");
    if (values.some(function (weight) { return !Number.isInteger(weight) || weight < 0 || weight > 10; })) {
      throw new Error("Weights must be integers from 0 to 10");
    }
    if (values.reduce(function (sum, weight) { return sum + weight; }, 0) === 0) {
      throw new Error("Set at least one weight above 0");
    }
    return values;
  }

  function checkedAppetite(appetite, cfg) {
    var config = cfg || DEFAULT_CONFIG;
    var allowed = config.allowed_max_risk || DEFAULT_CONFIG.allowed_max_risk;
    var order = config.risk_order || DEFAULT_CONFIG.risk_order;
    if (allowed.indexOf(appetite) === -1) throw new Error("Invalid appetite: " + appetite);
    return { order: order, index: order.indexOf(appetite) };
  }

  function eligible(row, appetite, cfg) {
    var gate = checkedAppetite(appetite, cfg);
    var order = gate.order;
    var tier = row && row.risk_tier;
    var tierIndex = order.indexOf(tier);
    if (tierIndex === -1) throw new Error("Invalid risk_tier: " + tier);
    return tier !== "unacceptable" && tierIndex <= gate.index;
  }

  function score(row, weights) {
    var values = checkedWeights(weights);
    var numerator = values[0] * row.value + values[1] * row.feasibility + values[2] * row.data_readiness;
    var denominator = values[0] + values[1] + values[2];
    // Round the exact rational score to tenths using ties-to-even, as Python round does.
    var scaledNumerator = 200 * numerator;
    var quotient = Math.floor(scaledNumerator / denominator);
    var remainder = scaledNumerator % denominator;
    if (2 * remainder > denominator || (2 * remainder === denominator && quotient % 2 === 1)) quotient += 1;
    return quotient / 10;
  }

  function rank(rows, weights, appetite, cfg) {
    var checked = checkedWeights(weights);
    var gate = checkedAppetite(appetite, cfg);
    var config = cfg || DEFAULT_CONFIG;
    var shortlistSize = Number.isInteger(config.shortlist_size) ? config.shortlist_size : DEFAULT_CONFIG.shortlist_size;
    var ranked = [];
    var ineligibleRows = [];
    rows.forEach(function (row) {
      var tierIndex = gate.order.indexOf(row.risk_tier);
      if (tierIndex === -1) throw new Error("Invalid risk_tier: " + row.risk_tier);
      if (row.risk_tier === "unacceptable") {
        ineligibleRows.push({ use_case_id: row.use_case_id, status: "Not eligible – ruled unacceptable" });
      } else if (tierIndex > gate.index) {
        ineligibleRows.push({ use_case_id: row.use_case_id, status: "Not eligible – internal risk tier above appetite" });
      } else {
        ranked.push({ use_case_id: row.use_case_id, score: score(row, checked), value: row.value, data_readiness: row.data_readiness });
      }
    });
    ranked.sort(function (a, b) {
      return b.score - a.score || b.value - a.value || b.data_readiness - a.data_readiness || (a.use_case_id < b.use_case_id ? -1 : a.use_case_id > b.use_case_id ? 1 : 0);
    });
    ranked = ranked.map(function (row, index) {
      return { rank: index + 1, use_case_id: row.use_case_id, score: row.score, shortlisted: index + 1 <= shortlistSize };
    });
    return { ranked: ranked, ineligible: ineligibleRows };
  }

  return { eligible: eligible, score: score, rank: rank };
});
