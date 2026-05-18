var LG_TOOL_COLORS = ["#f0a030", "#e87530", "#c98f3a", "#d4a24a"];

var LG_STATUS_COLORS = {
    ok: "#34d399",
    running: "#f0a030",
    timeout: "#e87530",
    error: "#ef5350",
    rejected: "#ef5350",
    killed: "#9ca3af",
};

var LG_STATUS_DOTS = {
    ok: "bg-emerald-500",
    running: "bg-gold",
    timeout: "bg-orange",
    error: "bg-red-500",
    rejected: "bg-red-500",
    killed: "bg-gray-400",
};

function lgShortDate(iso) {
    var d = new Date(iso + "T00:00:00");
    if (isNaN(d.getTime())) { return iso; }
    return d.toLocaleDateString(undefined, { day: "2-digit", month: "2-digit" });
}

function statsPage() {
    return {
        loaded: false,
        error: false,
        total: 0,
        last24h: 0,
        avgDuration: null,
        successRate: 0,
        byTool: {},
        byStatus: {},
        activity: [],
        recent: [],
        speedtest: { count: 0, count_24h: 0, total_bytes: 0, avg_mbps: 0, interrupt_rate: 0 },
        _charts: [],

        load: async function () {
            var result = await makeGetRequest("/api/v1/stats");
            if (result.code !== 200 || !result.response || !result.response.data) {
                this.error = true;
                this.loaded = true;
                return;
            }
            var d = result.response.data;
            this.total = d.total || 0;
            this.last24h = d.last_24h || 0;
            this.avgDuration = (d.avg_duration_ms != null) ? d.avg_duration_ms : null;
            this.successRate = d.success_rate || 0;
            this.byTool = d.by_tool || {};
            this.byStatus = d.by_status || {};
            this.activity = d.activity || [];
            this.recent = d.recent || [];
            this.speedtest = d.speedtest || this.speedtest;
            this.loaded = true;
            if (this.total > 0) {
                this.$nextTick(this._renderCharts.bind(this));
            }
        },

        toolLabel: function (k) {
            return window.t("tool_" + k);
        },

        statusLabel: function (k) {
            return window.t("status_" + k);
        },

        statusDot: function (k) {
            return LG_STATUS_DOTS[k] || "bg-gray-400";
        },

        fmtTime: function (s) {
            if (!s) { return "-"; }
            var d = new Date(s.replace(" ", "T") + "Z");
            return isNaN(d.getTime()) ? s : d.toLocaleString();
        },

        _renderCharts: function () {
            var dark = document.documentElement.dataset.theme === "dark";
            this._area("lg-chart-activity", this.activity, dark);
            var toolColors = Object.keys(this.byTool).map(function (k, i) {
                return LG_TOOL_COLORS[i % LG_TOOL_COLORS.length];
            });
            var statusColors = Object.keys(this.byStatus).map(function (k) {
                return LG_STATUS_COLORS[k] || "#9ca3af";
            });
            this._donut("lg-chart-tool", this.byTool, this.toolLabel.bind(this), toolColors, dark);
            this._donut("lg-chart-status", this.byStatus, this.statusLabel.bind(this), statusColors, dark);
        },

        _area: function (elId, activity, dark) {
            var el = document.getElementById(elId);
            if (!el || !window.ApexCharts || activity.length === 0) { return; }
            var chart = new ApexCharts(el, {
                chart: {
                    type: "area",
                    height: 260,
                    fontFamily: '"Outfit", system-ui, sans-serif',
                    foreColor: dark ? "#a09890" : "#3a3a45",
                    toolbar: { show: false },
                    animations: { enabled: false },
                },
                series: [{
                    name: window.t("stats_activity"),
                    data: activity.map(function (a) { return a.count; }),
                }],
                xaxis: {
                    categories: activity.map(function (a) { return lgShortDate(a.date); }),
                    axisBorder: { show: false },
                    axisTicks: { show: false },
                    labels: { rotate: 0, hideOverlappingLabels: true, style: { fontSize: "11px" } },
                },
                yaxis: { min: 0, forceNiceScale: true, labels: { style: { fontSize: "11px" } } },
                colors: ["#f0a030"],
                fill: { type: "gradient", gradient: { shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0.03 } },
                stroke: { curve: "smooth", width: 2.5 },
                dataLabels: { enabled: false },
                grid: { borderColor: dark ? "#2c2c3a" : "#e2e2e8", strokeDashArray: 4 },
                tooltip: { theme: dark ? "dark" : "light" },
                states: {
                    hover: { filter: { type: "none" } },
                    active: { filter: { type: "none" } },
                },
            });
            chart.render();
            this._charts.push(chart);
        },

        _donut: function (elId, data, labelFn, colors, dark) {
            var el = document.getElementById(elId);
            var keys = Object.keys(data);
            if (!el || !window.ApexCharts || keys.length === 0) { return; }
            var chart = new ApexCharts(el, {
                chart: {
                    type: "donut",
                    height: 300,
                    fontFamily: '"Outfit", system-ui, sans-serif',
                    foreColor: dark ? "#a09890" : "#3a3a45",
                    animations: { enabled: false },
                },
                series: keys.map(function (k) { return data[k]; }),
                labels: keys.map(labelFn),
                colors: colors,
                stroke: { width: 2, colors: [dark ? "#1e1e28" : "#f0f0f3"] },
                legend: { position: "bottom", fontSize: "13px", markers: { radius: 4 } },
                dataLabels: { style: { fontSize: "12px", fontWeight: 600 }, dropShadow: { enabled: false } },
                plotOptions: {
                    pie: {
                        donut: {
                            size: "64%",
                            labels: {
                                show: true,
                                total: { show: true, label: "", fontSize: "26px", fontWeight: 600 },
                            },
                        },
                    },
                },
                tooltip: { theme: dark ? "dark" : "light" },
                states: {
                    hover: { filter: { type: "none" } },
                    active: { filter: { type: "none" } },
                },
            });
            chart.render();
            this._charts.push(chart);
        },
    };
}
