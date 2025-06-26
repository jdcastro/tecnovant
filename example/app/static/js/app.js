document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("calcBtn").addEventListener("click", () => {
        fetch("/api/calculate_balance", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ objective_id: 1, analysis_ids: [1,2] })
        })
        .then(res => res.json())
        .then(data => {
            const resultsDiv = document.getElementById("results");
            let html = '<table class="table-auto border border-collapse border-gray-400 w-full text-left">';
            html += '<thead><tr><th class="border p-2">Nutriente</th><th class="border p-2">Objetivo</th><th class="border p-2">Actual</th><th class="border p-2">Diferencia</th></tr></thead><tbody>';
            Object.keys(data.objective).forEach(key => {
                html += `<tr><td class="border p-2">${key}</td><td class="border p-2">${data.objective[key]}</td><td class="border p-2">${data.actual[key]}</td><td class="border p-2">${data.difference[key]}</td></tr>`;
            });
            html += "</tbody></table>";
            resultsDiv.innerHTML = html;
        });
    });
});