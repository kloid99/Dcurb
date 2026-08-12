/**
 * DLFI Feature 1: 하역공간 후보지·운영시간 추천 및 설치 시뮬레이터
 *
 * 팀 통합용 단일 기능 모듈.
 * - 전체 HTML/페이지를 만들지 않는다.
 * - 팀 대시보드의 특정 container에만 렌더링한다.
 * - 데이터는 외부에서 주입한다.
 *
 * 사용 예시:
 *   <div id="feature-loading-space"></div>
 *   <script src="./loading_space_feature_module.js"></script>
 *   <script>
 *     LoadingSpaceFeature.init({
 *       mount: "#feature-loading-space",
 *       data: window.DLFI_SIMULATOR_DATA
 *     });
 *   </script>
 */
(function (global) {
  "use strict";

  const FEATURE_ID = "loading-space-feature";

  const DEFAULT_WEIGHTS = {
    demandAccess: 0.25,
    supply: 0.2,
    riskAccess: 0.15,
    trafficSafety: 0.1,
    pedestrianSafety: 0.1,
    operation: 0.1,
    stability: 0.05,
    confidence: 0.05,
  };

  function clamp(value, min = 0, max = 100) {
    return Math.max(min, Math.min(max, Number(value) || 0));
  }

  function fmt(value, suffix = "") {
    return `${Math.round((Number(value) || 0) * 10) / 10}${suffix}`;
  }

  function normalizeData(data) {
    return {
      dongRisk: Array.isArray(data?.dongRisk) ? data.dongRisk : [],
      candidates: Array.isArray(data?.candidates) ? data.candidates : [],
      timebands: Array.isArray(data?.timebands) ? data.timebands : [],
    };
  }

  function selectedRisk(data, dong) {
    return data.dongRisk.find((row) => row.dong === dong) || data.dongRisk[0] || null;
  }

  function getCandidateDong(candidate) {
    return candidate.dong || candidate.행정동 || candidate.adminDong || "";
  }

  function scoreCandidate(candidate, risk, inputs, weights = DEFAULT_WEIGHTS) {
    const distanceM = Number(candidate.distanceM) || 250;
    const parkingSpaces = Number(candidate.parkingSpaces) || 0;
    const parkingLots = Number(risk.parkingLots) || 0;
    const distanceScore = clamp(100 - distanceM / 8);

    const demandAccess = clamp(
      (Number(risk.deliveryDemand) * 0.55 + Number(risk.loadingShortage) * 0.45) *
        (distanceScore / 100),
    );
    const supply = clamp(parkingSpaces * 2.2 + parkingLots * 2);
    const riskAccess = clamp(
      Number(risk.dlfiScore) * 0.65 + Number(risk.enforcementRepeat) * 0.35 - distanceM / 18,
    );
    const trafficSafety = clamp(
      100 -
        Number(risk.trafficConflict) * 0.65 -
        (inputs.startHour < 10 || inputs.startHour >= 17 ? 16 : 0),
    );
    const pedestrianSafety = clamp(
      100 - Number(risk.pedestrianConflict) * 0.5 - Number(risk.safetyVulnerability) * 0.25,
    );
    const operation = clamp(
      (candidate.publicFacility ? 74 : 48) + (candidate.operationKnown ? 16 : -8),
    );
    const stability = candidate.type === "단속완충" ? 62 : 82;
    const confidence =
      risk.reliabilityGrade === "높음" || risk.allocationConfidence === "높음"
        ? 92
        : risk.reliabilityGrade === "보통" || risk.allocationConfidence === "보통"
          ? 74
          : 58;

    let total =
      demandAccess * weights.demandAccess +
      supply * weights.supply +
      riskAccess * weights.riskAccess +
      trafficSafety * weights.trafficSafety +
      pedestrianSafety * weights.pedestrianSafety +
      operation * weights.operation +
      stability * weights.stability +
      confidence * weights.confidence;

    if (inputs.policyMode === "feasible") {
      total = total * 0.82 + operation * 0.12 + confidence * 0.06;
    }

    return {
      total: clamp(total),
      parts: {
        demandAccess,
        supply,
        riskAccess,
        trafficSafety,
        pedestrianSafety,
        operation,
        stability,
        confidence,
      },
    };
  }

  function recommendTimeband(data, risk, inputs) {
    const selectedSlot = `${String(inputs.startHour).padStart(2, "0")}~${String(inputs.endHour).padStart(2, "0")}`;
    const rows = data.timebands.filter((row) => row.dong === risk.dong);
    const exact = rows.find((row) => row.timeband === selectedSlot);
    const best =
      exact || [...rows].sort((a, b) => Number(b.loadingRecommendationScore) - Number(a.loadingRecommendationScore))[0];

    if (best) {
      const score = clamp(best.loadingRecommendationScore);
      const grade = best.displayGrade || best.loadingZoneGrade || "";
      return {
        slot: exact ? `${selectedSlot}시` : `${best.timeband}시`,
        score,
        label: grade === "추천" || score >= 60 ? "추천" : score >= 25 ? "조건부" : "주의",
        evidence: `혼잡 ${fmt(best.congestion)} · 배송집중 ${fmt(best.deliveryConcentration)}`,
      };
    }

    let score = 55 + Number(risk.loadingShortage) * 0.22 + Number(risk.enforcementRepeat) * 0.15;
    if (inputs.startHour >= 14 && inputs.endHour <= 17) score += 17;
    if (inputs.startHour >= 10 && inputs.endHour <= 12) score += 11;
    if (inputs.startHour >= 7 && inputs.endHour <= 10) score -= 26;
    if (inputs.startHour >= 17 && inputs.endHour <= 20) score -= 24;

    score = clamp(score);
    return {
      slot: `${selectedSlot}시`,
      score,
      label: score >= 76 ? "추천" : score >= 58 ? "조건부" : "주의",
      evidence: "기본 규칙 기반",
    };
  }

  function simulateImpact(risk, candidate, candidateScore, inputs) {
    const hours = Math.max(1, inputs.endHour - inputs.startHour);
    const hourlyCapacity = inputs.bays * (60 / Math.max(5, inputs.serviceMinutes));
    const maxCapacity = hourlyCapacity * hours;
    const effectiveCapacity = maxCapacity * inputs.utilization;
    const estimatedDemand = Math.max(
      10,
      (Number(risk.deliveryDemand) * 0.42 + Number(risk.loadingShortage) * 0.58) * hours * 0.2,
    );
    const absorption = clamp((effectiveCapacity / estimatedDemand) * 100);
    const quality = candidateScore.total / 100;

    const after = {
      loadingShortage: clamp(Number(risk.loadingShortage) - absorption * 0.48 * quality),
      enforcementRepeat: clamp(Number(risk.enforcementRepeat) - absorption * 0.22 * quality),
      trafficConflict: clamp(Number(risk.trafficConflict) - absorption * 0.16 * quality),
      pedestrianConflict: clamp(Number(risk.pedestrianConflict) - absorption * 0.1 * quality),
      deliveryDemand: Number(risk.deliveryDemand) || 0,
      safetyVulnerability: Number(risk.safetyVulnerability) || 0,
    };

    const beforeDlfi =
      Number(risk.deliveryDemand) +
      Number(risk.trafficConflict) +
      Number(risk.pedestrianConflict) +
      Number(risk.enforcementRepeat) +
      Number(risk.safetyVulnerability) +
      Number(risk.loadingShortage);
    const afterDlfi =
      after.deliveryDemand +
      after.trafficConflict +
      after.pedestrianConflict +
      after.enforcementRepeat +
      after.safetyVulnerability +
      after.loadingShortage;

    return {
      effectiveCapacity,
      absorption,
      beforeDlfi,
      afterDlfi,
      delta: afterDlfi - beforeDlfi,
      households: Math.round((Number(risk.deliveryDemand) * 45 + (candidate.serviceRadiusM || 350) * 3.2) * ((candidate.serviceRadiusM || 350) / 500)),
      stores: Math.round((Number(risk.deliveryDemand) * 2.4 + Number(risk.trafficConflict) * 1.1) * ((candidate.serviceRadiusM || 350) / 500)),
      after,
    };
  }

  function getCandidates(data, risk, inputs, typeFilter) {
    return data.candidates
      .filter((candidate) => getCandidateDong(candidate) === risk.dong)
      .filter((candidate) => typeFilter.size === 0 || typeFilter.has(candidate.type))
      .map((candidate) => {
        const score = scoreCandidate(candidate, risk, inputs);
        const impact = simulateImpact(risk, candidate, score, inputs);
        const timeband = recommendTimeband(data, risk, inputs);
        return { ...candidate, score, impact, timeband };
      })
      .sort((a, b) => b.score.total - a.score.total);
  }

  function injectStyle() {
    if (document.getElementById(`${FEATURE_ID}-style`)) return;
    const style = document.createElement("style");
    style.id = `${FEATURE_ID}-style`;
    style.textContent = `
      .lsf{display:grid;grid-template-columns:300px minmax(0,1fr);gap:16px;color:#1d2730;font-family:"Segoe UI","Malgun Gothic",system-ui,sans-serif}
      .lsf *{box-sizing:border-box}
      .lsf-panel,.lsf-card{border:1px solid #d9e0e6;border-radius:8px;background:#fff;box-shadow:0 10px 24px rgba(22,31,43,.07)}
      .lsf-panel{padding:18px}
      .lsf-title{margin:0 0 6px;font-size:20px}
      .lsf-sub{margin:0 0 16px;color:#66727d;font-size:13px;line-height:1.5}
      .lsf-field{display:grid;gap:7px;margin-bottom:13px;font-size:13px;font-weight:700}
      .lsf-field select,.lsf-field input{width:100%;border:1px solid #ccd6df;border-radius:8px;padding:9px 10px;font:inherit}
      .lsf-checks{display:grid;grid-template-columns:1fr 1fr;gap:7px}
      .lsf-checks label{display:flex;gap:6px;align-items:center;border:1px solid #d9e0e6;border-radius:8px;padding:8px;font-size:12px}
      .lsf-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:12px}
      .lsf-metric{padding:14px;border:1px solid #d9e0e6;border-radius:8px;background:#fff}
      .lsf-metric span{display:block;color:#66727d;font-size:12px}
      .lsf-metric strong{display:block;margin-top:6px;font-size:22px}
      .lsf-list{display:grid;gap:10px}
      .lsf-card{padding:14px}
      .lsf-card h4{margin:0 0 5px;font-size:15px}
      .lsf-meta{color:#66727d;font-size:12px;line-height:1.45}
      .lsf-score{float:right;color:#0f766e;font-size:22px;font-weight:900}
      .lsf-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
      .lsf-chip{border-radius:999px;background:#edf2f7;padding:5px 8px;font-size:12px;font-weight:700}
      .lsf-bars{display:grid;gap:10px;margin-top:12px}
      .lsf-bar-head{display:flex;justify-content:space-between;font-size:12px;font-weight:800}
      .lsf-track{height:10px;border-radius:999px;background:#e6edf2;overflow:hidden}
      .lsf-fill{height:100%;border-radius:999px;background:#2563eb}
      .lsf-empty{padding:18px;color:#66727d;text-align:center}
      @media(max-width:900px){.lsf{grid-template-columns:1fr}.lsf-metrics{grid-template-columns:1fr 1fr}}
    `;
    document.head.appendChild(style);
  }

  function render(container, data, state) {
    const risk = selectedRisk(data, state.dong);
    if (!risk) {
      container.innerHTML = `<div class="lsf-empty">하역공간 추천 기능에 필요한 행정동 데이터가 없습니다.</div>`;
      return;
    }

    const typeFilter = new Set(state.types);
    const candidates = getCandidates(data, risk, state.inputs, typeFilter);
    const selected = candidates[0] || null;

    container.innerHTML = `
      <section class="lsf">
        <aside class="lsf-panel">
          <h3 class="lsf-title">하역공간 추천</h3>
          <p class="lsf-sub">DLFI와 탄력주정차·시간대 데이터를 이용해 후보지와 설치 효과를 계산합니다.</p>

          <label class="lsf-field">대상 행정동
            <select data-lsf="dong">
              ${data.dongRisk
                .slice()
                .sort((a, b) => Number(a.rank) - Number(b.rank))
                .map((row) => `<option value="${row.dong}" ${row.dong === risk.dong ? "selected" : ""}>${row.rank || "-"}위 ${row.district || ""} ${row.dong}</option>`)
                .join("")}
            </select>
          </label>

          <div class="lsf-field">후보지 유형
            <div class="lsf-checks">
              ${["기존 탄력주정차", "공영주차장", "공공시설", "단속완충"]
                .map((type) => `<label><input type="checkbox" data-lsf-type="${type}" ${typeFilter.has(type) ? "checked" : ""}> ${type}</label>`)
                .join("")}
            </div>
          </div>

          <label class="lsf-field">하역면 수
            <input data-lsf="bays" type="range" min="1" max="10" value="${state.inputs.bays}">
          </label>

          <label class="lsf-field">운영시간
            <select data-lsf="time">
              ${["07~10", "10~12", "12~14", "14~17", "17~20", "20~23"]
                .map((slot) => `<option value="${slot}" ${slot === `${String(state.inputs.startHour).padStart(2, "0")}~${String(state.inputs.endHour).padStart(2, "0")}` ? "selected" : ""}>${slot}시</option>`)
                .join("")}
            </select>
          </label>

          <label class="lsf-field">정책 우선기준
            <select data-lsf="policyMode">
              <option value="effect" ${state.inputs.policyMode === "effect" ? "selected" : ""}>효과 우선</option>
              <option value="feasible" ${state.inputs.policyMode === "feasible" ? "selected" : ""}>실행 가능성 우선</option>
            </select>
          </label>
        </aside>

        <main>
          <div class="lsf-metrics">
            <div class="lsf-metric"><span>설치 전 DLFI</span><strong>${selected ? fmt(selected.impact.beforeDlfi) : "-"}</strong></div>
            <div class="lsf-metric"><span>설치 후 DLFI</span><strong>${selected ? fmt(selected.impact.afterDlfi) : "-"}</strong></div>
            <div class="lsf-metric"><span>예상 변화</span><strong>${selected ? fmt(selected.impact.delta) : "-"}</strong></div>
            <div class="lsf-metric"><span>유효 처리량</span><strong>${selected ? `${Math.round(selected.impact.effectiveCapacity)}대` : "-"}</strong></div>
          </div>

          <div class="lsf-panel">
            <h3 class="lsf-title">${risk.district || ""} ${risk.dong} 추천 후보지</h3>
            <p class="lsf-sub">${risk.priorityGrade || ""} · ${risk.riskType || risk.mainRiskFactors || "위험유형 정보 없음"} · ${risk.policyText || "정책추천 정보 없음"}</p>
            <div class="lsf-list">
              ${
                candidates.length
                  ? candidates
                      .slice(0, 5)
                      .map(
                        (candidate) => `
                          <article class="lsf-card">
                            <span class="lsf-score">${fmt(candidate.score.total)}</span>
                            <h4>${candidate.name}</h4>
                            <div class="lsf-meta">${candidate.type || "후보"} · ${candidate.roadName || ""} ${candidate.startPoint ? `· ${candidate.startPoint} → ${candidate.endPoint}` : ""}</div>
                            <div class="lsf-chips">
                              <span class="lsf-chip">${candidate.timeband.label} ${candidate.timeband.slot}</span>
                              <span class="lsf-chip">${candidate.timeband.evidence}</span>
                              <span class="lsf-chip">기존 허용 ${candidate.allowedTime || "자료 없음"}</span>
                              <span class="lsf-chip">수혜 ${candidate.impact.households.toLocaleString()}세대</span>
                              <span class="lsf-chip">상점 ${candidate.impact.stores.toLocaleString()}개</span>
                            </div>
                          </article>
                        `,
                      )
                      .join("")
                  : `<div class="lsf-empty">선택 조건에 맞는 후보지가 없습니다.</div>`
              }
            </div>
            ${selected ? renderBars(risk, selected.impact.after) : ""}
          </div>
        </main>
      </section>
    `;

    bindEvents(container, data, state);
  }

  function renderBars(risk, after) {
    const rows = [
      ["하역부족", risk.loadingShortage, after.loadingShortage],
      ["단속반복", risk.enforcementRepeat, after.enforcementRepeat],
      ["교통방해", risk.trafficConflict, after.trafficConflict],
      ["보행충돌", risk.pedestrianConflict, after.pedestrianConflict],
    ];
    return `
      <div class="lsf-bars">
        ${rows
          .map(
            ([label, before, next]) => `
              <div>
                <div class="lsf-bar-head"><span>${label}</span><span>${fmt(before)} → ${fmt(next)}</span></div>
                <div class="lsf-track"><div class="lsf-fill" style="width:${clamp(next)}%"></div></div>
              </div>
            `,
          )
          .join("")}
      </div>
    `;
  }

  function bindEvents(container, data, state) {
    container.querySelector('[data-lsf="dong"]').addEventListener("change", (event) => {
      state.dong = event.target.value;
      render(container, data, state);
    });
    container.querySelector('[data-lsf="bays"]').addEventListener("input", (event) => {
      state.inputs.bays = Number(event.target.value);
      render(container, data, state);
    });
    container.querySelector('[data-lsf="time"]').addEventListener("change", (event) => {
      const [start, end] = event.target.value.split("~").map(Number);
      state.inputs.startHour = start;
      state.inputs.endHour = end;
      render(container, data, state);
    });
    container.querySelector('[data-lsf="policyMode"]').addEventListener("change", (event) => {
      state.inputs.policyMode = event.target.value;
      render(container, data, state);
    });
    container.querySelectorAll("[data-lsf-type]").forEach((input) => {
      input.addEventListener("change", () => {
        state.types = [...container.querySelectorAll("[data-lsf-type]:checked")].map((node) =>
          node.getAttribute("data-lsf-type"),
        );
        render(container, data, state);
      });
    });
  }

  function init(options) {
    const container =
      typeof options?.mount === "string" ? document.querySelector(options.mount) : options?.mount;
    if (!container) {
      throw new Error("LoadingSpaceFeature.init: mount container를 찾을 수 없습니다.");
    }

    injectStyle();

    const data = normalizeData(options.data || global.DLFI_SIMULATOR_DATA || {});
    const firstDong = options.defaultDong || data.dongRisk[0]?.dong || "";
    const state = {
      dong: firstDong,
      types: options.types || ["기존 탄력주정차", "공영주차장", "공공시설", "단속완충"],
      inputs: {
        bays: Number(options.bays) || 3,
        startHour: Number(options.startHour) || 14,
        endHour: Number(options.endHour) || 17,
        serviceMinutes: Number(options.serviceMinutes) || 20,
        utilization: Number(options.utilization) || 0.6,
        policyMode: options.policyMode || "effect",
      },
    };

    render(container, data, state);

    return {
      update(nextOptions = {}) {
        if (nextOptions.data) Object.assign(data, normalizeData(nextOptions.data));
        if (nextOptions.defaultDong) state.dong = nextOptions.defaultDong;
        render(container, data, state);
      },
      calculateForDong(dong, inputs = state.inputs) {
        const risk = selectedRisk(data, dong);
        if (!risk) return [];
        return getCandidates(data, risk, inputs, new Set(state.types));
      },
    };
  }

  global.LoadingSpaceFeature = {
    init,
    scoreCandidate,
    recommendTimeband,
    simulateImpact,
    getCandidates,
  };
})(window);
