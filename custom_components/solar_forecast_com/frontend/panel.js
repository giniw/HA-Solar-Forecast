/**********************************************************************
 * solar-forecast-panel.js
 *
 * Home Assistant custom panel for solar-forecast.com
 *
 * Uses:
 *   GET /api/solar_forecast/entries
 *   GET /api/solar_forecast/{entry_id}
 *
 * Layout mirrors the website /index dashboard:
 *   • Plant selector (multi config entry)
 *   • Summary cards
 *   • Main forecast charts (Forecast / Clear Sky / Generation) by day
 *   • Per-array DC output charts by day
 *   • Array-wise pie + next-3-days bar
 *   • Refresh every 5 minutes
 *********************************************************************/

const SERIES_COLORS = {
    Forecast: "#b06b77",
    "Clear Sky": "#9fc1d6",
    Generation: "#30ab2b",
    Personalised: "#7b68ee",
};

const PANEL_LINE_COLORS = [
    "#b06b77",
    "#30ab2b",
    "#9fc1d6",
    "#f0a030",
    "#7b68ee",
    "#20b2aa",
    "#ff7f50",
    "#e91e8c",
];

const DAY_LABELS = ["Today", "Tomorrow", "Day after"];

let chartPromise = null;

function loadChartJS() {
    if (window.Chart) {
        return Promise.resolve();
    }
    if (chartPromise) {
        return chartPromise;
    }

    chartPromise = new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "/solar_forecast/chart.umd.min.js";
        script.onload = () => resolve();
        script.onerror = (err) => {
            console.error("Unable to load Chart.js");
            reject(err);
        };
        document.head.appendChild(script);
    });

    return chartPromise;
}

class SolarForecastPanel extends HTMLElement {
    constructor() {
        super();
        this._hass = null;
        this._charts = [];
        this._lastData = "";
        this._connected = false;
        this._timer = null;
        this._entries = [];
        this._selectedEntry = null;
        this._mainDay = 0;
        this._arrayDay = 0;
        this._dayBuckets = null;
        this._arrayMeta = [];
        this._api = null;
        this._resizeObserver = null;
        this._onResize = null;
        this._resizeRaf = null;
        this._haNarrow = false;
        this._mediaQuery = null;
        this._onMediaChange = null;
        this._panel = null;
    }

    connectedCallback() {
        this._connected = true;
        if (!this.shadowRoot) {
            this.attachShadow({ mode: "open" });
        }

        this.shadowRoot.innerHTML = `
<style>
:host {
  display: block;
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  overflow-x: hidden;
  padding: 0;
  background: var(--primary-background-color);
  color: var(--primary-text-color);
  font-family: var(--paper-font-body1_-_font-family, Roboto, Noto, sans-serif);
}
*, *::before, *::after { box-sizing: border-box; }

/* Match HA / HACS: panel owns the top app bar + hamburger on narrow */
.top-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  height: var(--header-height, 56px);
  min-height: var(--header-height, 56px);
  padding: 0 12px 0 4px;
  padding-top: env(safe-area-inset-top, 0px);
  background-color: var(--app-header-background-color, var(--primary-color));
  color: var(--app-header-text-color, var(--text-primary-color, #fff));
  border-bottom: var(--app-header-border-bottom, none);
  position: sticky;
  top: 0;
  z-index: 4;
}
.menu-btn {
  display: none;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  margin: 0;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: inherit;
  cursor: pointer;
  flex-shrink: 0;
  -webkit-tap-highlight-color: transparent;
}
.menu-btn.visible {
  display: inline-flex;
}
.menu-btn:hover,
.menu-btn:focus-visible {
  background: rgba(255, 255, 255, 0.12);
  outline: none;
}
.menu-btn svg {
  width: 24px;
  height: 24px;
  fill: currentColor;
}
/* Visibility is controlled in JS (.visible) so desktop window resize
   works even when HA has not yet flipped the narrow property. */
.top-bar-title {
  font-size: 20px;
  font-weight: 400;
  line-height: 1.2;
  margin: 0;
  padding-inline-start: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.content {
  padding: 16px;
  max-width: 100%;
  min-width: 0;
}

.plant-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  max-width: 100%;
}
.plant-bar label {
  font-size: 14px;
  color: var(--secondary-text-color);
}
.plant-bar select {
  min-width: 0;
  width: min(100%, 280px);
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--divider-color);
  background: var(--card-background-color);
  color: var(--primary-text-color);
}
.summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
  max-width: 100%;
}
.metric {
  background: var(--card-background-color);
  border-radius: 12px;
  padding: 16px;
  box-shadow: var(--ha-card-box-shadow);
  min-width: 0;
}
.metric-title {
  font-size: 13px;
  color: var(--secondary-text-color);
}
.metric-value {
  font-size: 30px;
  font-weight: 700;
  margin-top: 8px;
  overflow-wrap: anywhere;
}
.metric-unit {
  font-size: 12px;
  color: var(--secondary-text-color);
}
.charts-row,
.lower-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
  max-width: 100%;
  min-width: 0;
}
/* Prefer panel width over viewport so HA sidebar does not break layout */
:host(.narrow) .charts-row,
:host(.narrow) .lower-row,
:host(.ha-narrow) .charts-row,
:host(.ha-narrow) .lower-row {
  grid-template-columns: 1fr;
}
@media (max-width: 900px) {
  .charts-row,
  .lower-row {
    grid-template-columns: 1fr;
  }
}
.panel-card {
  background: var(--card-background-color);
  border-radius: 12px;
  padding: 14px 16px 18px;
  box-shadow: var(--ha-card-box-shadow);
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 4px 0;
}
.section-sub {
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 10px 0;
  min-height: 1.2em;
  overflow-wrap: anywhere;
}
.tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.tab {
  border: 1px solid var(--divider-color);
  background: transparent;
  color: var(--primary-text-color);
  border-radius: 8px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 13px;
}
.tab.active {
  background: var(--primary-color);
  color: var(--text-primary-color, #fff);
  border-color: var(--primary-color);
}
.chart-container {
  position: relative;
  width: 100%;
  height: 320px;
  min-width: 0;
  overflow: hidden;
}
.chart-container.short {
  height: 280px;
}
.chart-container canvas {
  display: block;
  width: 100% !important;
  height: 100% !important;
  max-width: 100%;
}
.status {
  padding: 24px;
  color: var(--secondary-text-color);
}
</style>

<header class="top-bar" part="top-bar">
  <button type="button" class="menu-btn" id="menu-btn" title="Sidebar" aria-label="Open sidebar">
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z"></path>
    </svg>
  </button>
  <h1 class="top-bar-title">Solar Forecast</h1>
</header>

<div class="content">
<div class="plant-bar">
  <label for="plant-select">Plant</label>
  <select id="plant-select"></select>
</div>

<div id="summary" class="summary"></div>

<div class="charts-row">
  <div class="panel-card">
    <div class="tabs" id="main-tabs"></div>
    <p class="section-title" id="main-heading">Expected Generation</p>
    <p class="section-sub" id="main-sub"></p>
    <div class="chart-container"><canvas id="main-chart"></canvas></div>
  </div>
  <div class="panel-card">
    <div class="tabs" id="array-tabs"></div>
    <p class="section-title">Array DC output</p>
    <p class="section-sub">&nbsp;</p>
    <div class="chart-container"><canvas id="array-chart"></canvas></div>
  </div>
</div>

<div class="lower-row">
  <div class="panel-card">
    <p class="section-title">Today's Array-wise Total Production</p>
    <p class="section-sub">&nbsp;</p>
    <div class="chart-container short"><canvas id="pie-chart"></canvas></div>
  </div>
  <div class="panel-card">
    <p class="section-title">Total Production Next 3 Days</p>
    <p class="section-sub">&nbsp;</p>
    <div class="chart-container short"><canvas id="bar-chart"></canvas></div>
  </div>
</div>

<div id="status" class="status" style="display:none"></div>
</div>
`;

        this._buildTabs();
        this._setupMenuButton();
        this._setupResizeHandling();
        if (this._hass) {
            this._initialize();
        }
    }

    disconnectedCallback() {
        this._connected = false;
        this._teardownResizeHandling();
        this._destroyCharts();
        if (this._timer) {
            clearTimeout(this._timer);
            this._timer = null;
        }
    }

    set hass(hass) {
        this._hass = hass;
        this._updateMenuVisibility();
        if (!this._connected) {
            return;
        }
        if (!this._timer) {
            this._initialize();
        }
    }

    // Home Assistant sets this when the left drawer is collapsed / mobile.
    set narrow(value) {
        this._haNarrow = Boolean(value);
        this.classList.toggle("ha-narrow", this._haNarrow);
        this._updateMenuVisibility();
        this._scheduleChartResize();
    }

    get narrow() {
        return this._haNarrow;
    }

    set panel(panel) {
        this._panel = panel;
    }

    get panel() {
        return this._panel;
    }

    _setupMenuButton() {
        const menuBtn = this.shadowRoot.querySelector("#menu-btn");
        if (!menuBtn) {
            return;
        }
        menuBtn.addEventListener("click", () => this._toggleSidebar());
        this._updateMenuVisibility();
    }

    _toggleSidebar() {
        // Same contract as ha-menu-button / HACS: tell the HA shell to toggle
        // the main navigation drawer. Must cross shadow DOM boundaries.
        this.dispatchEvent(
            new Event("hass-toggle-menu", {
                bubbles: true,
                composed: true,
            })
        );
    }

    _isViewportNarrow() {
        // Home Assistant uses ~870px for narrow / mobile chrome.
        if (this._mediaQuery) {
            return this._mediaQuery.matches;
        }
        return window.matchMedia("(max-width: 870px)").matches;
    }

    _isPanelNarrow() {
        const width =
            this.clientWidth ||
            (this.getBoundingClientRect && this.getBoundingClientRect().width) ||
            0;
        // Slightly above HA's 870 so the button appears as soon as the
        // content column feels phone-like (e.g. desktop window + docked sidebar).
        return width > 0 && width < 900;
    }

    _shouldShowMenuButton() {
        const docked = this._hass && this._hass.dockedSidebar;
        const alwaysHidden = docked === "always_hidden";
        return Boolean(
            this._haNarrow ||
                alwaysHidden ||
                this._isViewportNarrow() ||
                this._isPanelNarrow()
        );
    }

    _updateMenuVisibility() {
        if (!this.shadowRoot) {
            return;
        }
        const show = this._shouldShowMenuButton();
        const panelNarrow = this._isPanelNarrow() || this._isViewportNarrow();

        this.classList.toggle("show-menu", show);
        this.classList.toggle("ha-narrow", Boolean(this._haNarrow));
        this.classList.toggle("narrow", panelNarrow || Boolean(this._haNarrow));

        const menuBtn = this.shadowRoot.querySelector("#menu-btn");
        if (menuBtn) {
            menuBtn.classList.toggle("visible", show);
            menuBtn.setAttribute("aria-hidden", show ? "false" : "true");
        }
    }

    _setupResizeHandling() {
        this._onResize = () => {
            this._updateNarrowClass();
            this._scheduleChartResize();
        };

        window.addEventListener("resize", this._onResize);

        // Desktop window resize: matchMedia fires even when element RO is flaky.
        this._mediaQuery = window.matchMedia("(max-width: 870px)");
        this._onMediaChange = () => {
            this._updateMenuVisibility();
            this._scheduleChartResize();
        };
        if (this._mediaQuery.addEventListener) {
            this._mediaQuery.addEventListener("change", this._onMediaChange);
        } else if (this._mediaQuery.addListener) {
            this._mediaQuery.addListener(this._onMediaChange);
        }

        if (typeof ResizeObserver !== "undefined") {
            this._resizeObserver = new ResizeObserver(() => this._onResize());
            this._resizeObserver.observe(this);
            this.shadowRoot
                .querySelectorAll(".chart-container")
                .forEach((el) => this._resizeObserver.observe(el));
        }

        this._updateNarrowClass();
    }

    _teardownResizeHandling() {
        if (this._onResize) {
            window.removeEventListener("resize", this._onResize);
            this._onResize = null;
        }
        if (this._mediaQuery && this._onMediaChange) {
            if (this._mediaQuery.removeEventListener) {
                this._mediaQuery.removeEventListener(
                    "change",
                    this._onMediaChange
                );
            } else if (this._mediaQuery.removeListener) {
                this._mediaQuery.removeListener(this._onMediaChange);
            }
        }
        this._mediaQuery = null;
        this._onMediaChange = null;
        if (this._resizeObserver) {
            this._resizeObserver.disconnect();
            this._resizeObserver = null;
        }
        if (this._resizeRaf) {
            cancelAnimationFrame(this._resizeRaf);
            this._resizeRaf = null;
        }
    }

    _updateNarrowClass() {
        this._updateMenuVisibility();
    }

    _scheduleChartResize() {
        if (this._resizeRaf) {
            cancelAnimationFrame(this._resizeRaf);
        }
        this._resizeRaf = requestAnimationFrame(() => {
            this._resizeRaf = null;
            this._resizeCharts();
        });
    }

    _resizeCharts() {
        this._charts.forEach((chart) => {
            try {
                chart.resize();
            } catch (e) {
                /* ignore */
            }
        });
    }

    async _initialize() {
        await this._loadEntries();
        this._scheduleUpdate();
    }

    async _loadEntries() {
        const entries = await this._hass.callApi("GET", "solar_forecast/entries");
        this._entries = entries || [];

        const select = this.shadowRoot.querySelector("#plant-select");
        select.innerHTML = "";

        if (!this._entries.length) {
            this._selectedEntry = null;
            this._setStatus("No Solar Forecast plants configured.");
            return;
        }

        this._entries.forEach((entry) => {
            const option = document.createElement("option");
            option.value = entry.entry_id;
            option.textContent = entry.title;
            select.appendChild(option);
        });

        if (
            !this._selectedEntry ||
            !this._entries.some((e) => e.entry_id === this._selectedEntry)
        ) {
            this._selectedEntry = this._entries[0].entry_id;
        }

        select.value = this._selectedEntry;
        select.onchange = () => {
            this._selectedEntry = select.value;
            this._lastData = "";
            this._mainDay = 0;
            this._arrayDay = 0;
            this._buildTabs();
            this._update();
        };
    }

    _buildTabs() {
        const mainTabs = this.shadowRoot.querySelector("#main-tabs");
        const arrayTabs = this.shadowRoot.querySelector("#array-tabs");
        mainTabs.innerHTML = "";
        arrayTabs.innerHTML = "";

        DAY_LABELS.forEach((label, idx) => {
            const mainBtn = document.createElement("button");
            mainBtn.className = "tab" + (idx === this._mainDay ? " active" : "");
            mainBtn.textContent = label;
            mainBtn.addEventListener("click", () => {
                this._mainDay = idx;
                this._buildTabs();
                this._redrawMainAndArrays();
            });
            mainTabs.appendChild(mainBtn);

            const arrayBtn = document.createElement("button");
            arrayBtn.className = "tab" + (idx === this._arrayDay ? " active" : "");
            arrayBtn.textContent = label;
            arrayBtn.addEventListener("click", () => {
                this._arrayDay = idx;
                this._buildTabs();
                this._redrawMainAndArrays();
            });
            arrayTabs.appendChild(arrayBtn);
        });
    }

    async _scheduleUpdate() {
        await this._update();
        this._timer = setTimeout(() => this._scheduleUpdate(), 300000);
    }

    _destroyCharts() {
        this._charts.forEach((chart) => {
            try {
                chart.destroy();
            } catch (e) {
                /* ignore */
            }
        });
        this._charts = [];
    }

    _setStatus(msg) {
        const el = this.shadowRoot.querySelector("#status");
        if (!msg) {
            el.style.display = "none";
            el.textContent = "";
            return;
        }
        el.style.display = "block";
        el.textContent = msg;
    }

    async _update() {
        if (!this._hass) {
            return;
        }
        if (!this._selectedEntry) {
            this._setStatus("No Solar Forecast plants configured.");
            return;
        }

        try {
            await loadChartJS();
            const api = await this._hass.callApi(
                "GET",
                `solar_forecast/${this._selectedEntry}`
            );
            if (!api || api.error) {
                this._setStatus(api?.error || "Unable to retrieve forecast.");
                return;
            }

            this._setStatus("");
            this._renderSummary(api);

            const fingerprint = JSON.stringify({
                entry: this._selectedEntry,
                kWatt: api.kWatt,
                clearsky_kWatt: api.clearsky_kWatt,
                personalised_kWatt: api.personalised_kWatt,
                generation: api.generation,
                arrays: api.arrays,
                ArrayDayTotals: api.ArrayDayTotals,
                Next3Days: api.Next3Days,
            });

            if (fingerprint === this._lastData && this._charts.length > 0) {
                return;
            }

            this._lastData = fingerprint;
            this._api = api;
            this._arrayMeta = api.arrays || [];
            this._dayBuckets = this._buildDayBuckets(api);

            if (!this._dayBuckets.days.length) {
                this._setStatus("No forecast data available");
                this._destroyCharts();
                return;
            }

            this._drawAll();
        } catch (err) {
            console.error(err);
            this._setStatus("Unable to retrieve forecast.");
        }
    }

    _renderSummary(api) {
        const summary = this.shadowRoot.querySelector("#summary");
        summary.innerHTML = "";

        const cards = [
            { title: "Today's Forecast", value: api.TodaysForecast, unit: "kWh" },
            { title: "Tomorrow's Forecast", value: api.TomorrowsForecast, unit: "kWh" },
            { title: "Day After Forecast", value: api.DayAftersForecast, unit: "kWh" },
            { title: "Generation Now", value: api.GenerationNow, unit: "kW" },
            { title: "Total Generation", value: api.TotalGeneration, unit: "kWh" },
        ];

        (api.ArrayDayTotals || []).forEach((item) => {
            cards.push({
                title: `${item.label || ("Array " + item.array)} Today`,
                value: item.today,
                unit: "kWh",
            });
        });

        cards.forEach((card) => {
            const div = document.createElement("div");
            div.className = "metric";
            div.innerHTML = `
                <div class="metric-title">${card.title}</div>
                <div class="metric-value">${Number(card.value ?? 0).toFixed(2)}</div>
                <div class="metric-unit">${card.unit}</div>
            `;
            summary.appendChild(div);
        });
    }

    _buildDayBuckets(api) {
        const seriesMap = {};
        if (api.kWatt) seriesMap.Forecast = api.kWatt;
        if (api.clearsky_kWatt) seriesMap["Clear Sky"] = api.clearsky_kWatt;
        if (api.personalised_kWatt && Object.keys(api.personalised_kWatt).length) {
            seriesMap.Personalised = api.personalised_kWatt;
        }
        if (api.generation) seriesMap.Generation = api.generation;

        const arraySeries = {};
        (api.arrays || []).forEach((item) => {
            const key = item.key || `array_${item.array}_kWatt`;
            if (api[key]) {
                arraySeries[item.label || `Array ${item.array}`] = {
                    series: api[key],
                    color:
                        item.color ||
                        PANEL_LINE_COLORS[(item.array - 1) % PANEL_LINE_COLORS.length],
                    array: item.array,
                };
            }
        });

        if (!Object.keys(arraySeries).length) {
            Object.keys(api).forEach((key) => {
                const match = /^array_(\d+)_kWatt$/.exec(key);
                if (!match || !api[key] || typeof api[key] !== "object") {
                    return;
                }
                const num = Number(match[1]);
                arraySeries[`Array ${num}`] = {
                    series: api[key],
                    color: PANEL_LINE_COLORS[(num - 1) % PANEL_LINE_COLORS.length],
                    array: num,
                };
            });
        }

        const daySet = new Set();

        const toPointsByDay = (series) => {
            const byDay = {};
            Object.entries(series || {}).forEach(([ts, value]) => {
                const d = new Date(ts);
                if (Number.isNaN(d.getTime())) {
                    return;
                }
                const day =
                    d.getFullYear() +
                    "-" +
                    String(d.getMonth() + 1).padStart(2, "0") +
                    "-" +
                    String(d.getDate()).padStart(2, "0");
                daySet.add(day);
                if (!byDay[day]) {
                    byDay[day] = [];
                }
                const y = Number(value);
                byDay[day].push({
                    x: d.getTime(),
                    y: Number.isFinite(y) ? y : null,
                });
            });
            Object.values(byDay).forEach((pts) => pts.sort((a, b) => a.x - b.x));
            return byDay;
        };

        const mainByName = {};
        Object.entries(seriesMap).forEach(([name, series]) => {
            mainByName[name] = toPointsByDay(series);
        });

        const arrayByName = {};
        Object.entries(arraySeries).forEach(([name, info]) => {
            arrayByName[name] = {
                color: info.color,
                byDay: toPointsByDay(info.series),
            };
        });

        const days = Array.from(daySet).sort();
        return { days, mainByName, arrayByName };
    }

    _dayKey(offset) {
        const days = this._dayBuckets?.days || [];
        return days[offset] || null;
    }

    _formatTime(ms) {
        return new Date(ms).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    _lineOptions(yTitle) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            parsing: false,
            interaction: { mode: "nearest", axis: "x", intersect: false },
            plugins: {
                legend: { position: "top" },
                tooltip: {
                    enabled: true,
                    callbacks: {
                        title: (items) =>
                            items.length ? this._formatTime(items[0].parsed.x) : "",
                    },
                },
            },
            scales: {
                x: {
                    type: "linear",
                    title: { display: true, text: "Time" },
                    ticks: { callback: (value) => this._formatTime(value) },
                },
                y: {
                    beginAtZero: true,
                    title: { display: true, text: yTitle },
                },
            },
        };
    }

    _drawAll() {
        this._destroyCharts();
        this._redrawMainAndArrays();
    }

    _redrawMainAndArrays() {
        if (!this._dayBuckets) {
            return;
        }
        this._destroyCharts();
        this._drawMain();
        this._drawArrays();
        this._drawPie();
        this._drawBar();
        this._scheduleChartResize();
    }

    _makeChart(canvas, config) {
        if (!config.options) {
            config.options = {};
        }
        config.options.responsive = true;
        config.options.maintainAspectRatio = false;
        // Chart.js observes the canvas parent; keep that in sync with our containers.
        config.options.resizeDelay = 0;

        const chart = new Chart(canvas.getContext("2d"), config);
        this._charts.push(chart);
        return chart;
    }

    _drawMain() {
        const api = this._api || {};
        const dayKey = this._dayKey(this._mainDay);
        const canvas = this.shadowRoot.querySelector("#main-chart");
        const heading = this.shadowRoot.querySelector("#main-heading");
        const sub = this.shadowRoot.querySelector("#main-sub");

        const totals = [
            api.TodaysForecast,
            api.TomorrowsForecast,
            api.DayAftersForecast,
        ];
        const gen = api.TotalGeneration;

        if (this._mainDay === 0) {
            heading.textContent = "Expected Generation | Generated Today";
            sub.textContent = `${Number(totals[0] ?? 0).toFixed(2)} kWh | ${Number(gen ?? 0).toFixed(2)} kWh`;
        } else {
            heading.textContent = "Expected Generation";
            sub.textContent = `${Number(totals[this._mainDay] ?? 0).toFixed(2)} kWh`;
        }

        if (!dayKey || !this._dayBuckets) {
            return;
        }

        const order = ["Forecast", "Clear Sky", "Generation", "Personalised"];
        const datasets = [];

        order.forEach((name) => {
            const byDay = this._dayBuckets.mainByName[name];
            if (!byDay) {
                return;
            }
            if (name === "Generation" && this._mainDay !== 0) {
                return;
            }
            const fill = name === "Forecast" || name === "Generation";
            datasets.push({
                label: name,
                data: byDay[dayKey] || [],
                borderColor: SERIES_COLORS[name],
                backgroundColor: fill ? SERIES_COLORS[name] + "33" : "transparent",
                fill,
                tension: 0.25,
                borderWidth: 2,
                pointRadius: 0,
                spanGaps: true,
            });
        });

        this._makeChart(canvas, {
            type: "line",
            data: { datasets },
            options: this._lineOptions("Power (kW)"),
        });
    }

    _drawArrays() {
        const dayKey = this._dayKey(this._arrayDay);
        const canvas = this.shadowRoot.querySelector("#array-chart");
        if (!dayKey || !this._dayBuckets) {
            return;
        }

        const datasets = Object.entries(this._dayBuckets.arrayByName).map(
            ([name, info]) => ({
                label: name,
                data: info.byDay[dayKey] || [],
                borderColor: info.color,
                backgroundColor: "transparent",
                fill: false,
                tension: 0.25,
                borderWidth: 2,
                pointRadius: 0,
                spanGaps: true,
            })
        );

        this._makeChart(canvas, {
            type: "line",
            data: { datasets },
            options: this._lineOptions("Power (kW)"),
        });
    }

    _drawPie() {
        const canvas = this.shadowRoot.querySelector("#pie-chart");
        const totals = this._api?.ArrayDayTotals || [];
        const labels = totals.map((t) => t.label || `Array ${t.array}`);
        const values = totals.map((t) => Number(t.today ?? 0));
        const colors = totals.map(
            (t, i) => t.color || PANEL_LINE_COLORS[i % PANEL_LINE_COLORS.length]
        );
        const sum = values.reduce((a, b) => a + b, 0);

        this._makeChart(canvas, {
            type: "doughnut",
            data: {
                labels: sum > 0 ? labels : ["No production data"],
                datasets: [
                    {
                        data: sum > 0 ? values : [1],
                        backgroundColor: sum > 0 ? colors : ["#cccccc"],
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: {
                    legend: { position: "bottom" },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                if (sum <= 0) {
                                    return "No production data";
                                }
                                const v = Number(ctx.raw || 0);
                                const pct = ((v / sum) * 100).toFixed(1);
                                return `${ctx.label}: ${v.toFixed(2)} kWh (${pct}%)`;
                            },
                        },
                    },
                },
            },
        });
    }

    _drawBar() {
        const canvas = this.shadowRoot.querySelector("#bar-chart");
        const values = (
            this._api?.Next3Days || [
                this._api?.TodaysForecast,
                this._api?.TomorrowsForecast,
                this._api?.DayAftersForecast,
            ]
        ).map((v) => Number(v ?? 0));

        this._makeChart(canvas, {
            type: "bar",
            data: {
                labels: DAY_LABELS,
                datasets: [
                    {
                        label: "Energy (kWh)",
                        data: values,
                        backgroundColor: "#4f46e5",
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${Number(ctx.raw || 0).toFixed(2)} kWh`,
                        },
                    },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: "Energy (kWh)" },
                    },
                },
            },
        });
    }

    getCardSize() {
        return 12;
    }
}

if (!customElements.get("solar-forecast-panel")) {
    customElements.define("solar-forecast-panel", SolarForecastPanel);
}
