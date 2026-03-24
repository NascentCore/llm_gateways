/**
 * Vertex AI PT vs PayGo calculator — no build step.
 * PT pricing: https://cloud.google.com/vertex-ai/generative-ai/pricing#provisioned-throughput
 */

const PT_TERMS = [
  { id: "week", label: "1 周 ($1,200/GSU/周)", pricePerWeek: 1200 },
  { id: "month", label: "1 月 ($2,700/GSU/月)", pricePerMonth: 2700 },
  { id: "quarter", label: "3 月约 ($2,400/GSU/月)", pricePerMonth: 2400 },
  { id: "year", label: "1 年约 ($2,000/GSU/月)", pricePerMonth: 2000 },
];

const MODEL_PRESETS = {
  "gemini-3.1-flash-image": {
    label: "Gemini 3.1 Flash Image (Nano Banana 2)",
    throughputPerGsu: 2015,
    burndown: { input: 1, outText: 6, outImage: 120 },
    paygoPerM: { input: 0.5, outText: 3, outImage: 60 },
  },
  "gemini-2.5-flash-image": {
    label: "Gemini 2.5 Flash Image",
    throughputPerGsu: 2690,
    burndown: { input: 1, outText: 9, outImage: 100 },
    paygoPerM: { input: 0.3, outText: 2.5, outImage: 30 },
  },
  custom: { label: "Custom（手动填写）", custom: true },
};

function $(id) {
  return document.getElementById(id);
}

function fmtMoney(n) {
  if (!Number.isFinite(n)) return "—";
  return (
    "$" +
    n.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

function getActiveModelSpec() {
  const key = $("model").value;
  if (key === "custom") {
    return {
      throughputPerGsu: Number($("cThroughput").value) || 0,
      burndown: {
        input: Number($("cRin").value) || 0,
        outText: Number($("cRoutText").value) || 0,
        outImage: Number($("cRoutImg").value) || 0,
      },
      paygoPerM: {
        input: Number($("cPayIn").value) || 0,
        outText: Number($("cPayOutT").value) || 0,
        outImage: Number($("cPayOutI").value) || 0,
      },
    };
  }
  const p = MODEL_PRESETS[key];
  return {
    throughputPerGsu: p.throughputPerGsu,
    burndown: { ...p.burndown },
    paygoPerM: { ...p.paygoPerM },
  };
}

function ptCostForWindow(gsu, termId, windowDays) {
  const g = Math.max(0, gsu);
  const d = Math.max(0, windowDays);
  const term = PT_TERMS.find((t) => t.id === termId) || PT_TERMS[1];
  if (term.pricePerWeek != null) {
    return g * term.pricePerWeek * (d / 7);
  }
  return g * term.pricePerMonth * (d / 30);
}

function getUsageInWindow(windowDays) {
  const scale = windowDays / 30;
  const mode = document.querySelector('input[name="usageMode"]:checked').value;

  if (mode === "perRequest") {
    const reqMonth = Math.max(0, Number($("reqPerMonth").value) || 0);
    const avgIn = Math.max(0, Number($("avgIn").value) || 0);
    const avgOt = Math.max(0, Number($("avgOutText").value) || 0);
    const avgOi = Math.max(0, Number($("avgOutImg").value) || 0);
    const reqWin = reqMonth * scale;
    return {
      inputTokens: avgIn * reqWin,
      outTextTokens: avgOt * reqWin,
      outImageTokens: avgOi * reqWin,
      requestsInWindow: reqWin,
    };
  }

  const inM = Math.max(0, Number($("totInM").value) || 0);
  const otM = Math.max(0, Number($("totOutTextM").value) || 0);
  const oiM = Math.max(0, Number($("totOutImgM").value) || 0);
  return {
    inputTokens: inM * 1e6 * scale,
    outTextTokens: otM * 1e6 * scale,
    outImageTokens: oiM * 1e6 * scale,
    requestsInWindow: null,
  };
}

function paygoCost(tokens, paygoPerM) {
  return (
    (tokens.inputTokens / 1e6) * paygoPerM.input +
    (tokens.outTextTokens / 1e6) * paygoPerM.outText +
    (tokens.outImageTokens / 1e6) * paygoPerM.outImage
  );
}

function burndownPerRequest(spec, avgIn, avgOt, avgOi) {
  const b = spec.burndown;
  return avgIn * b.input + avgOt * b.outText + avgOi * b.outImage;
}

function calculate() {
  const spec = getActiveModelSpec();
  const windowDays = Math.max(1, Number($("windowDays").value) || 30);
  const gsu = Number($("gsu").value) || 0;
  const termId = $("term").value;

  const tokens = getUsageInWindow(windowDays);
  const paygo = paygoCost(tokens, spec.paygoPerM);
  const pt = ptCostForWindow(gsu, termId, windowDays);

  const secWindow = windowDays * 86400;
  let avgBurndownPerSec = 0;

  const mode = document.querySelector('input[name="usageMode"]:checked').value;
  if (mode === "perRequest") {
    const avgIn = Math.max(0, Number($("avgIn").value) || 0);
    const avgOt = Math.max(0, Number($("avgOutText").value) || 0);
    const avgOi = Math.max(0, Number($("avgOutImg").value) || 0);
    const bdReq = burndownPerRequest(spec, avgIn, avgOt, avgOi);
    const reqMonth = Math.max(0, Number($("reqPerMonth").value) || 0);
    const totalBd = bdReq * reqMonth * (windowDays / 30);
    avgBurndownPerSec = secWindow > 0 ? totalBd / secWindow : 0;
  } else {
    const b = spec.burndown;
    const scale = windowDays / 30;
    const inM = Math.max(0, Number($("totInM").value) || 0) * scale;
    const otM = Math.max(0, Number($("totOutTextM").value) || 0) * scale;
    const oiM = Math.max(0, Number($("totOutImgM").value) || 0) * scale;
    const totalBd =
      inM * 1e6 * b.input + otM * 1e6 * b.outText + oiM * 1e6 * b.outImage;
    avgBurndownPerSec = secWindow > 0 ? totalBd / secWindow : 0;
  }

  const capacityBd = gsu * spec.throughputPerGsu;
  const utilPct =
    capacityBd > 0 ? Math.min(999, (avgBurndownPerSec / capacityBd) * 100) : 0;

  const inMwin = tokens.inputTokens / 1e6;
  const otMwin = tokens.outTextTokens / 1e6;
  const oiMwin = tokens.outImageTokens / 1e6;

  const b = spec.burndown;
  const bdIn = tokens.inputTokens * b.input;
  const bdOt = tokens.outTextTokens * b.outText;
  const bdOi = tokens.outImageTokens * b.outImage;
  const totalBd = bdIn + bdOt + bdOi;

  let effIn = NaN;
  let effOt = NaN;
  let effOi = NaN;
  if (totalBd > 0 && pt >= 0) {
    if (inMwin > 0) effIn = (pt * (bdIn / totalBd)) / inMwin;
    if (otMwin > 0) effOt = (pt * (bdOt / totalBd)) / otMwin;
    if (oiMwin > 0) effOi = (pt * (bdOi / totalBd)) / oiMwin;
  }

  $("outPt").textContent = fmtMoney(pt);
  $("outPaygo").textContent = fmtMoney(paygo);
  const delta = paygo - pt;
  $("outDelta").textContent = fmtMoney(delta);
  $("outDelta").style.color =
    delta > 0 ? "var(--good)" : delta < 0 ? "var(--bad)" : "inherit";

  $("outTokens").textContent = [
    Math.round(tokens.inputTokens).toLocaleString(),
    Math.round(tokens.outTextTokens).toLocaleString(),
    Math.round(tokens.outImageTokens).toLocaleString(),
  ].join(" / ");

  $("outNeedBd").textContent =
    avgBurndownPerSec.toLocaleString("en-US", { maximumFractionDigits: 1 }) +
    " /s";
  $("outCapBd").textContent =
    capacityBd.toLocaleString("en-US", { maximumFractionDigits: 1 }) + " /s";
  $("outUtil").textContent = utilPct.toFixed(1) + "%";

  const bar = $("utilBar");
  const w = Math.min(100, utilPct);
  bar.style.width = w + "%";
  bar.className = "bar";
  if (utilPct > 100) bar.classList.add("bad");
  else if (utilPct > 85) bar.classList.add("warn");

  const alertEl = $("utilAlert");
  alertEl.innerHTML = "";
  if (capacityBd <= 0) {
    alertEl.innerHTML =
      '<div class="alert warn">GSU 为 0 或未配置 throughput，无法计算容量利用率。</div>';
  } else if (utilPct > 100) {
    alertEl.innerHTML =
      '<div class="alert warn">平均所需 burndown/s 超过已购容量。超额请求通常会走 PayGo（spillover）或受限；本表中的 PayGo 行仍为<strong>全量按量</strong>估算，未与 PT 拆分双计。</div>';
  }

  $("outEffIn").textContent = Number.isFinite(effIn) ? fmtMoney(effIn) : "N/A";
  $("outEffOutT").textContent = Number.isFinite(effOt) ? fmtMoney(effOt) : "N/A";
  $("outEffOutI").textContent = Number.isFinite(effOi) ? fmtMoney(effOi) : "N/A";

  $("results").hidden = false;
}

function init() {
  const modelSel = $("model");
  modelSel.innerHTML = "";
  for (const [k, v] of Object.entries(MODEL_PRESETS)) {
    const opt = document.createElement("option");
    opt.value = k;
    opt.textContent = v.label;
    modelSel.appendChild(opt);
  }

  const termSel = $("term");
  termSel.innerHTML = "";
  for (const t of PT_TERMS) {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = t.label;
    termSel.appendChild(opt);
  }

  function toggleCustom() {
    const custom = $("model").value === "custom";
    $("customFields").classList.toggle("visible", custom);
  }

  function toggleUsageMode() {
    const perReq =
      document.querySelector('input[name="usageMode"]:checked').value ===
      "perRequest";
    $("modePerRequest").style.display = perReq ? "block" : "none";
    $("modeTotals").style.display = perReq ? "none" : "block";
  }

  $("model").addEventListener("change", toggleCustom);
  document.querySelectorAll('input[name="usageMode"]').forEach((r) => {
    r.addEventListener("change", toggleUsageMode);
  });

  $("calcBtn").addEventListener("click", calculate);
  toggleCustom();
  toggleUsageMode();
  calculate();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
