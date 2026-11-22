(() => {
  const SVG_NS = "http://www.w3.org/2000/svg";
  const SEQUENTIAL = ["--seq-1", "--seq-2", "--seq-3", "--seq-4", "--seq-5", "--seq-6"];
  const CHART_W = 300;
  const CHART_H = 190;
  const PAD = { top: 10, right: 12, bottom: 24, left: 44 };

  const data = window.FARKLE_DATA;
  const tooltipEl = document.querySelector('[data-field="tooltip"]');

  function fmt(n) {
    return Math.round(n).toLocaleString("en-US");
  }

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function niceMax(value) {
    if (value <= 0) return 100;
    const magnitude = Math.pow(10, Math.floor(Math.log10(value)));
    const steps = [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10];
    for (const step of steps) {
      const candidate = step * magnitude;
      if (candidate >= value) return candidate;
    }
    return 10 * magnitude;
  }

  function renderMethodologyLine() {
    const t = data.generatedAtTrials;
    document.querySelector('[data-field="methodology-line"]').textContent =
      `Thresholds: ${t.optimizeTrials.toLocaleString()} trials/eval x ${t.optimizeRounds} rounds, binary search. ` +
      `Decision grid: ${t.gridTrials.toLocaleString()} trials/point. Strategy comparison: ${t.summaryTrials.toLocaleString()} trials/strategy.`;
  }

  function renderStrategyTiles() {
    const container = document.querySelector('[data-field="strategy-tiles"]');
    const strategies = data.strategyComparison;
    const best = Math.max(...strategies.map((s) => s.meanTurnScore));
    for (const s of strategies) {
      const tile = document.createElement("div");
      tile.className = "stat-tile" + (s.meanTurnScore === best ? " is-best" : "");

      const label = document.createElement("span");
      label.className = "label";
      label.textContent = s.name;

      const value = document.createElement("span");
      value.className = "value";
      value.textContent = fmt(s.meanTurnScore) + " pts/turn";

      const delta = document.createElement("span");
      delta.className = "delta";
      if (s.meanTurnScore === best) {
        delta.textContent = "best of the group";
      } else {
        const pct = ((s.meanTurnScore - best) / best) * 100;
        delta.textContent = `${pct.toFixed(1)}% vs optimal`;
      }

      tile.append(label, value, delta);
      container.appendChild(tile);
    }
  }

  function renderThresholdsTable() {
    const table = document.querySelector('[data-field="thresholds-table"]');
    const caption = document.createElement("caption");
    caption.textContent = "One row per dice-remaining state, 1 (riskiest reroll) through 6 (hot dice).";
    const thead = document.createElement("thead");
    thead.innerHTML =
      "<tr><th>Dice remaining</th><th>Bank at score &ge;</th><th>Bust probability (exact)</th><th>Expected score / roll (exact)</th></tr>";
    const tbody = document.createElement("tbody");

    for (const row of data.exactStats) {
      const d = row.diceRemaining;
      const threshold = data.optimalThresholds[String(d)];
      const tr = document.createElement("tr");
      const tdDice = document.createElement("td");
      tdDice.textContent = d === 6 ? "6 (hot dice)" : String(d);
      const tdThreshold = document.createElement("td");
      tdThreshold.textContent = fmt(threshold);
      const tdBust = document.createElement("td");
      tdBust.textContent = (row.bustProbability * 100).toFixed(2) + "%";
      const tdExp = document.createElement("td");
      tdExp.textContent = row.expectedScorePerRoll.toFixed(1);
      tr.append(tdDice, tdThreshold, tdBust, tdExp);
      tbody.appendChild(tr);
    }

    table.append(caption, thead, tbody);
  }

  function makeSvgEl(tag, attrs) {
    const el = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    return el;
  }

  function buildChart(diceRemaining, points, threshold) {
    const plotW = CHART_W - PAD.left - PAD.right;
    const plotH = CHART_H - PAD.top - PAD.bottom;

    const xMax = Math.max(...points.map((p) => p.turnScore));
    const yMax = niceMax(Math.max(...points.map((p) => Math.max(p.evBank, p.evReroll))) * 1.05);

    const xScale = (x) => PAD.left + (x / xMax) * plotW;
    const yScale = (y) => PAD.top + plotH - (y / yMax) * plotH;

    const svg = makeSvgEl("svg", {
      class: "chart",
      viewBox: `0 0 ${CHART_W} ${CHART_H}`,
      role: "img",
      "aria-label": `Dice remaining ${diceRemaining}: bank versus reroll expected value`,
    });

    // Gridlines (y) + axis labels
    const yTicks = 4;
    for (let i = 0; i <= yTicks; i++) {
      const yVal = (yMax / yTicks) * i;
      const y = yScale(yVal);
      svg.appendChild(makeSvgEl("line", { class: "gridline", x1: PAD.left, x2: CHART_W - PAD.right, y1: y, y2: y }));
      const label = makeSvgEl("text", { class: "axis-label", x: PAD.left - 6, y: y + 3, "text-anchor": "end" });
      label.textContent = fmt(yVal);
      svg.appendChild(label);
    }

    // X axis ticks
    const xTicks = 4;
    for (let i = 0; i <= xTicks; i++) {
      const xVal = (xMax / xTicks) * i;
      const x = xScale(xVal);
      const label = makeSvgEl("text", { class: "axis-label", x, y: CHART_H - 6, "text-anchor": "middle" });
      label.textContent = fmt(xVal);
      svg.appendChild(label);
    }
    svg.appendChild(
      makeSvgEl("line", {
        class: "baseline-axis",
        x1: PAD.left,
        x2: CHART_W - PAD.right,
        y1: PAD.top + plotH,
        y2: PAD.top + plotH,
      }),
    );

    // Threshold marker (only if within the visible domain)
    if (threshold <= xMax) {
      const tx = xScale(threshold);
      svg.appendChild(
        makeSvgEl("line", { class: "threshold-marker", x1: tx, x2: tx, y1: PAD.top, y2: PAD.top + plotH }),
      );
    }

    // Bank line (y = x reference)
    const bankPath = points.map((p) => `${xScale(p.turnScore)},${yScale(Math.min(p.evBank, yMax))}`).join(" L ");
    svg.appendChild(makeSvgEl("path", { class: "line-bank", d: `M ${bankPath}` }));

    // Reroll line
    const seqColor = `var(${SEQUENTIAL[diceRemaining - 1]})`;
    const rerollPath = points.map((p) => `${xScale(p.turnScore)},${yScale(Math.min(p.evReroll, yMax))}`).join(" L ");
    svg.appendChild(makeSvgEl("path", { class: "line-reroll", style: `stroke:${seqColor}`, d: `M ${rerollPath}` }));

    // Hover layer: crosshair + two dots, driven by a transparent hit rect
    const crosshair = makeSvgEl("line", {
      class: "crosshair-line",
      x1: 0,
      x2: 0,
      y1: PAD.top,
      y2: PAD.top + plotH,
      visibility: "hidden",
    });
    const bankDot = makeSvgEl("circle", {
      class: "hover-dot",
      r: 4,
      fill: cssVar("--baseline") || "#c3c2b7",
      stroke: cssVar("--surface-1") || "#fff",
      "stroke-width": 2,
      visibility: "hidden",
    });
    const rerollDot = makeSvgEl("circle", {
      class: "hover-dot",
      r: 4,
      fill: seqColor,
      stroke: cssVar("--surface-1") || "#fff",
      "stroke-width": 2,
      visibility: "hidden",
    });
    svg.append(crosshair, bankDot, rerollDot);

    const hitRect = makeSvgEl("rect", {
      class: "hit-rect",
      x: PAD.left,
      y: PAD.top,
      width: plotW,
      height: plotH,
    });
    svg.appendChild(hitRect);

    function nearestPoint(clientX, svgEl) {
      const rect = svgEl.getBoundingClientRect();
      const localX = ((clientX - rect.left) / rect.width) * CHART_W;
      const dataX = ((localX - PAD.left) / plotW) * xMax;
      let nearest = points[0];
      let bestDist = Infinity;
      for (const p of points) {
        const dist = Math.abs(p.turnScore - dataX);
        if (dist < bestDist) {
          bestDist = dist;
          nearest = p;
        }
      }
      return nearest;
    }

    hitRect.addEventListener("pointermove", (e) => {
      const p = nearestPoint(e.clientX, svg);
      const x = xScale(p.turnScore);
      crosshair.setAttribute("x1", x);
      crosshair.setAttribute("x2", x);
      crosshair.setAttribute("visibility", "visible");
      bankDot.setAttribute("cx", x);
      bankDot.setAttribute("cy", yScale(Math.min(p.evBank, yMax)));
      bankDot.setAttribute("visibility", "visible");
      rerollDot.setAttribute("cx", x);
      rerollDot.setAttribute("cy", yScale(Math.min(p.evReroll, yMax)));
      rerollDot.setAttribute("visibility", "visible");

      tooltipEl.hidden = false;
      tooltipEl.style.left = e.clientX + 14 + "px";
      tooltipEl.style.top = e.clientY + 14 + "px";
      tooltipEl.innerHTML = "";
      const title = document.createElement("div");
      title.className = "tt-title";
      title.textContent = `Turn score ${fmt(p.turnScore)}`;
      const rowBank = document.createElement("div");
      rowBank.className = "tt-row";
      rowBank.innerHTML = `<span class="tt-key" style="color:${cssVar("--baseline")}">Bank</span>`;
      const bankVal = document.createElement("span");
      bankVal.className = "tt-value";
      bankVal.textContent = fmt(p.evBank);
      rowBank.appendChild(bankVal);
      const rowReroll = document.createElement("div");
      rowReroll.className = "tt-row";
      rowReroll.innerHTML = `<span class="tt-key" style="color:${seqColor}">Reroll</span>`;
      const rerollVal = document.createElement("span");
      rerollVal.className = "tt-value";
      rerollVal.textContent = fmt(p.evReroll) + ` (±${Math.round(p.stderr * 2)})`;
      rowReroll.appendChild(rerollVal);
      tooltipEl.append(title, rowBank, rowReroll);
    });

    hitRect.addEventListener("pointerleave", () => {
      crosshair.setAttribute("visibility", "hidden");
      bankDot.setAttribute("visibility", "hidden");
      rerollDot.setAttribute("visibility", "hidden");
      tooltipEl.hidden = true;
    });

    return svg;
  }

  function renderEvCharts() {
    const container = document.querySelector('[data-field="ev-charts"]');
    for (let d = 1; d <= 6; d++) {
      const points = data.decisionGrid.filter((g) => g.diceRemaining === d).sort((a, b) => a.turnScore - b.turnScore);
      const threshold = data.optimalThresholds[String(d)];

      const card = document.createElement("div");
      card.className = "chart-card";

      const titleRow = document.createElement("div");
      titleRow.className = "chart-title";
      const name = document.createElement("span");
      name.className = "name";
      name.textContent = d === 6 ? "6 dice (hot dice)" : `${d} ${d === 1 ? "die" : "dice"} remaining`;
      const badge = document.createElement("span");
      badge.className = "threshold-badge";
      const xMax = Math.max(...points.map((p) => p.turnScore));
      badge.textContent = threshold <= xMax ? `threshold: ${fmt(threshold)}` : `threshold: ${fmt(threshold)} (off-chart)`;
      titleRow.append(name, badge);

      const legend = document.createElement("div");
      legend.className = "chart-legend";
      legend.innerHTML = '<span class="key bank">Bank (= turn score)</span><span class="key" style="color:' +
        `var(${SEQUENTIAL[d - 1]})` + '">Reroll (simulated EV)</span>';

      card.append(titleRow, legend, buildChart(d, points, threshold));
      container.appendChild(card);
    }
  }

  function renderEvTable() {
    const table = document.querySelector('[data-field="ev-table"]');
    const caption = document.createElement("caption");
    caption.textContent = "Full decision-grid data backing the charts above (table view for accessibility / no-JS-chart fallback).";
    const thead = document.createElement("thead");
    thead.innerHTML = "<tr><th>Dice remaining</th><th>Turn score</th><th>EV(bank)</th><th>EV(reroll)</th><th>Std. error</th><th>Reroll better?</th></tr>";
    const tbody = document.createElement("tbody");
    for (const row of data.decisionGrid) {
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td>${row.diceRemaining}</td><td>${fmt(row.turnScore)}</td><td>${fmt(row.evBank)}</td>` +
        `<td>${fmt(row.evReroll)}</td><td>${row.stderr.toFixed(1)}</td><td>${row.rerollBetter ? "Yes" : "No"}</td>`;
      tbody.appendChild(tr);
    }
    table.append(caption, thead, tbody);
  }

  function wireTableToggle() {
    const btn = document.querySelector('[data-field="toggle-ev-table"]');
    const wrap = document.querySelector('[data-field="ev-table-wrap"]');
    btn.addEventListener("click", () => {
      const nowHidden = !wrap.hidden;
      wrap.hidden = nowHidden;
      btn.textContent = nowHidden ? "Show data table" : "Hide data table";
    });
  }

  renderMethodologyLine();
  renderStrategyTiles();
  renderThresholdsTable();
  renderEvCharts();
  renderEvTable();
  wireTableToggle();
})();
