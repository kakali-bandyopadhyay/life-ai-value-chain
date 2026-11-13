"use strict";

const fs = require("fs");
const path = require("path");
const api = require(path.join(__dirname, "..", "docs", "rank.js"));
const useCases = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", "use_cases.json"), "utf8")).use_cases;
const config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", "scoring_config.json"), "utf8"));
const combos = process.argv.slice(2);

if (combos.length === 0) {
  combos.push("medium:5,3,2", "high:5,3,2", "low:5,3,2", "medium:10,0,0", "medium:0,0,10", "high:1,1,1", "medium:0,0,0");
}

const output = combos.map((spec) => {
  const match = /^(low|medium|high):(\d+),(\d+),(\d+)$/.exec(spec);
  if (!match) throw new Error("Invalid parity case: " + spec);
  const appetite = match[1];
  const weights = { value: Number(match[2]), feasibility: Number(match[3]), data_readiness: Number(match[4]) };
  try {
    return { appetite, weights, result: api.rank(useCases, weights, appetite, config) };
  } catch (error) {
    return { appetite, weights, error: error.message };
  }
});

process.stdout.write(JSON.stringify(output));
