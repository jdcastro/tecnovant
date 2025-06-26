document.addEventListener("DOMContentLoaded", () => {
  const farm = document.getElementById("farm");
  const lot = document.getElementById("lot");
  const analysisList = document.getElementById("analysis-list");
  const objectiveDiv = document.getElementById("objective");
  const balanceDiv = document.getElementById("balance-result");
  const modeRadios = document.querySelectorAll('input[name="mode"]');
  const dualSelectBox = document.getElementById("dual-selection");
  const primarySelect = document.getElementById("analysis-primary");
  const compareSelect = document.getElementById("analysis-compare");
  let cropId = null;
  let currentAnalyses = [];

  function updateModeDisplay() {
    const selectedMode = document.querySelector('input[name="mode"]:checked').value;
    if (selectedMode === "dual") {
      dualSelectBox.classList.remove("hidden");
      objectiveDiv.innerHTML = '<p class="text-gray-500">Modo comparación entre análisis</p>';
    } else {
      dualSelectBox.classList.add("hidden");
    }
    balanceDiv.innerHTML = "";
  }

  modeRadios.forEach(radio => radio.addEventListener("change", updateModeDisplay));

  fetch("/api/farms")
    .then((r) => r.json())
    .then((data) => {
      farm.innerHTML = '<option value="">Seleccione finca</option>' + data.map(f => `<option value="${f.id}">${f.name}</option>`).join('');
    });

  farm.addEventListener("change", () => {
    fetch(`/api/lots?farm_id=${farm.value}`)
      .then((r) => r.json())
      .then((data) => {
        lot.innerHTML = '<option value="">Seleccione lote</option>' + data.map(l => `<option value="${l.id}" data-crop="${l.crop_id}">${l.name}</option>`).join('');
      });
  });

  lot.addEventListener("change", () => {
    const selected = lot.selectedOptions[0];
    cropId = selected.dataset.crop;

    fetch(`/api/analyses?lot_id=${lot.value}`)
      .then((r) => r.json())
      .then((data) => {
        currentAnalyses = data;
        analysisList.innerHTML = data.map(a => `
          <div>
            <input type="radio" name="analysis" value="${a.id}"> ${a.date}
          </div>`).join('');

        const options = '<option value="">Seleccione análisis</option>' +
          data.map(a => `<option value="${a.id}">${a.date}</option>`).join('');
        primarySelect.innerHTML = options;
        compareSelect.innerHTML = options;
      });

    fetch(`/api/objective?crop_id=${cropId}`)
      .then((r) => r.json())
      .then((data) => {
        objectiveDiv.innerHTML = Object.entries(data).map(([k, v]) => `<div>${k}: ${v}</div>`).join('');
      });
  });

  analysisList.addEventListener("change", () => {
    const mode = document.querySelector('input[name="mode"]:checked').value;
    const input = document.querySelector('input[name="analysis"]:checked');
    if (!input || mode !== "optimum") return;

    fetch("/api/calculate_balance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: "optimum",
        crop_id: cropId,
        analysis_id: parseInt(input.value)
      })
    })
      .then(r => r.json())
      .then(data => {
        balanceDiv.innerHTML = Object.entries(data.balance).map(([k, v]) =>
          `<div>${k} diferencia: ${v}</div>`).join('');
      });
  });

  compareSelect.addEventListener("change", () => {
    const mode = document.querySelector('input[name="mode"]:checked').value;
    if (mode !== "dual") return;

    const primaryId = parseInt(primarySelect.value);
    const compareId = parseInt(compareSelect.value);
    if (!primaryId || !compareId) return;

    fetch("/api/calculate_balance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: "dual",
        primary_id: primaryId,
        compare_id: compareId
      })
    })
      .then(r => r.json())
      .then(data => {
        balanceDiv.innerHTML = Object.entries(data.balance).map(([k, v]) =>
          `<div>${k} diferencia: ${v}</div>`).join('');
      });
  });

  primarySelect.addEventListener("change", () => compareSelect.dispatchEvent(new Event("change")));
});