const DATA_BASE = "data";

const els = {
  temperature: document.getElementById("current-temperature"),
  humidity: document.getElementById("current-humidity"),
  battery: document.getElementById("current-battery"),
  lastUpdated: document.getElementById("last-updated"),
};

const RANGE_CONFIG = {
  "24h": { hours: 24, unit: "hour", maxPoints: 300 },
  "7d": { hours: 24 * 7, unit: "day", maxPoints: 400 },
  "30d": { hours: 24 * 30, unit: "day", maxPoints: 500 },
};

let chart = null;
let currentRange = "24h";

function formatDateTime(isoString) {
  const date = new Date(isoString);
  return date.toLocaleString("ja-JP", { hour12: false, timeZone: "Asia/Tokyo" });
}

async function fetchJson(path) {
  const res = await fetch(`${path}?_=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`fetch failed: ${path} (${res.status})`);
  }
  return res.json();
}

async function loadCurrent() {
  try {
    const latest = await fetchJson(`${DATA_BASE}/latest.json`);
    els.temperature.textContent = latest.temperature ?? "--";
    els.humidity.textContent = latest.humidity ?? "--";
    els.battery.textContent = latest.battery ?? "--";
    els.lastUpdated.textContent = `最終更新: ${formatDateTime(latest.timestamp)}`;
  } catch (err) {
    els.lastUpdated.textContent = "現在値の取得に失敗しました";
    console.error(err);
  }
}

function monthsBetween(start, end) {
  const months = [];
  const cursor = new Date(start.getFullYear(), start.getMonth(), 1);
  const last = new Date(end.getFullYear(), end.getMonth(), 1);
  while (cursor <= last) {
    months.push(`${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}`);
    cursor.setMonth(cursor.getMonth() + 1);
  }
  return months;
}

async function loadHistory(range) {
  const { hours } = RANGE_CONFIG[range];
  const now = new Date();
  const from = new Date(now.getTime() - hours * 60 * 60 * 1000);
  const months = monthsBetween(from, now);

  const results = await Promise.allSettled(months.map((m) => fetchJson(`${DATA_BASE}/${m}.json`)));
  const records = results
    .filter((r) => r.status === "fulfilled")
    .flatMap((r) => r.value);

  return records
    .filter((r) => new Date(r.timestamp) >= from)
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
}

function downsample(records, maxPoints) {
  if (records.length <= maxPoints) {
    return records;
  }
  const step = Math.ceil(records.length / maxPoints);
  return records.filter((_, i) => i % step === 0);
}

function renderChart(records, unit) {
  const labels = records.map((r) => r.timestamp);
  const temperatureData = records.map((r) => r.temperature);
  const humidityData = records.map((r) => r.humidity);

  const data = {
    labels,
    datasets: [
      {
        label: "気温 (°C)",
        data: temperatureData,
        borderColor: "#e4572e",
        backgroundColor: "rgba(228, 87, 46, 0.1)",
        yAxisID: "yTemp",
        tension: 0.2,
        pointRadius: 0,
      },
      {
        label: "湿度 (%)",
        data: humidityData,
        borderColor: "#2e86ab",
        backgroundColor: "rgba(46, 134, 171, 0.1)",
        yAxisID: "yHumidity",
        tension: 0.2,
        pointRadius: 0,
      },
    ],
  };

  if (chart) {
    chart.data = data;
    chart.update();
    return;
  }

  chart = new Chart(document.getElementById("sensor-chart"), {
    type: "line",
    data,
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          type: "time",
          time: { unit },
        },
        yTemp: {
          type: "linear",
          position: "left",
          title: { display: true, text: "気温 (°C)" },
        },
        yHumidity: {
          type: "linear",
          position: "right",
          title: { display: true, text: "湿度 (%)" },
          grid: { drawOnChartArea: false },
        },
      },
    },
  });
}

async function updateChart(range) {
  currentRange = range;
  const { unit, maxPoints } = RANGE_CONFIG[range];
  const emptyMessage = document.getElementById("chart-empty");
  try {
    const records = downsample(await loadHistory(range), maxPoints);
    if (emptyMessage) {
      emptyMessage.hidden = records.length > 0;
    }
    renderChart(records, unit);
  } catch (err) {
    console.error(err);
    if (emptyMessage) {
      emptyMessage.textContent = "履歴データの取得に失敗しました";
      emptyMessage.hidden = false;
    }
  }
}

document.querySelectorAll(".range-buttons button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".range-buttons button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    updateChart(btn.dataset.range);
  });
});

async function init() {
  await loadCurrent();
  await updateChart(currentRange);
  setInterval(loadCurrent, 60 * 1000);
}

init();
