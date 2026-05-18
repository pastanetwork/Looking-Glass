var LG_ANSI = {
    reset: "\x1b[0m",
    meta: "\x1b[38;2;240;160;48m",
    out: "",
    sys: "\x1b[38;2;120;118;130m",
    err: "\x1b[38;2;239;83;80m",
    end: "\x1b[1;38;2;240;160;48m",
};

var LG_TOOL_ICONS = {
    ping: "fa-tower-broadcast",
    traceroute: "fa-route",
    mtr: "fa-wave-square",
    speedtest: "fa-gauge-high",
};

function parseTracerouteHop(raw) {
    var m = raw.match(/^\s*(\d+)\s+(.*\S)\s*$/);
    if (!m) { return null; }
    var rest = m[2];
    var probes = [];
    var probeRe = /(<\s*1|\d+(?:\.\d+)?)\s*ms|\*/gi;
    var pm;
    while ((pm = probeRe.exec(rest)) !== null) {
        if (pm[0] === "*") {
            probes.push(null);
        } else {
            var tok = pm[1].replace(/\s+/g, "");
            probes.push(tok === "<1" ? 0.5 : parseFloat(tok));
        }
    }
    var ipM = rest.match(/(?:\d{1,3}\.){3}\d{1,3}|(?:[0-9a-fA-F]{1,4}:){2,}[0-9a-fA-F]{0,4}/);
    var host = ipM ? ipM[0] : null;
    var hasReply = probes.some(function (p) { return p !== null; });
    var timeout = !host && !hasReply;
    if (!host && !timeout) { return null; }
    return { n: parseInt(m[1], 10), host: host, probes: probes, loss: null, timeout: timeout };
}

function parseMtrHop(raw) {
    var m = raw.match(/^\s*(\d+)\.\|--\s+(\S+)\s+([\d.]+)%\s+\d+\s+[\d.]+\s+([\d.]+)/);
    if (!m) { return null; }
    var unknown = m[2] === "???";
    return {
        n: parseInt(m[1], 10),
        host: unknown ? null : m[2],
        probes: unknown ? [] : [parseFloat(m[4])],
        loss: parseFloat(m[3]),
        timeout: unknown,
    };
}

function parsePingLatency(raw) {
    var m = raw.match(/(?:temps|time)\s*([<=])\s*([\d.,]+)\s*ms/i);
    if (!m) { return null; }
    var v = parseFloat(m[2].replace(",", "."));
    if (isNaN(v)) { return null; }
    return (m[1] === "<" && v > 0.5) ? 0.5 : v;
}

function parsePingLoss(raw) {
    if (!/perte|loss/i.test(raw)) { return null; }
    var m = raw.match(/([\d.,]+)\s*%/);
    return m ? parseFloat(m[1].replace(",", ".")) : null;
}

function lookingGlassPage(options) {
    return {
        nodes: options.nodes || [],
        tools: options.tools || ["ping", "traceroute", "mtr"],
        turnstileSiteKey: options.turnstileSiteKey || "",
        nodeId: (options.nodes && options.nodes[0] && options.nodes[0].id) || "",
        tool: "ping",
        target: "",
        family: "auto",
        running: false,
        ipLoading: false,
        copied: false,
        view: "visual",        // console | visual
        status: "idle",        // idle | running | ok | timeout | error | rejected | killed
        commandLabel: "",
        cmdError: "",
        durationMs: null,
        exitCode: null,
        hops: [],
        resolvedIp: "",
        pings: [],
        pingLoss: null,
        _reader: null,
        _tsWidgetId: undefined,
        _term: null,
        _fit: null,
        _pingChart: null,
        _buffer: [],

        speedtestFiles: options.speedtestFiles || [],
        stFile: (options.speedtestFiles && options.speedtestFiles[0] && options.speedtestFiles[0].id) || "",
        stRunning: false,
        stStatus: "idle",       // idle | running | done | error
        stError: "",
        stSpeed: 0,
        stPeak: 0,
        stAvg: 0,
        stProgress: 0,
        stBytes: 0,
        stDuration: 0,
        _stReader: null,
        _stChart: null,
        _stSamples: [],
        _stStopped: false,

        init: function () {
            this._initTerminal();
            if (this.turnstileSiteKey) {
                this._renderTurnstile();
            }
            this.$watch("tool", (t) => {
                if (t !== "speedtest") { this.view = "visual"; }
                if (this.stRunning && t !== "speedtest") {
                    this.stopSpeedtest();
                }
                // Le résultat ne doit pas suivre d'un outil à l'autre : on
                // arrête une commande en cours et on réinitialise l'affichage.
                if (this.running) { this.stop(); }
                this.clear();
            });
        },

        get canRun() {
            return !this.running && this.target.trim().length > 0;
        },

        get hasVisual() {
            return this.tool === "ping" || this.tool === "traceroute" || this.tool === "mtr";
        },

        get isSpeedtest() {
            return this.tool === "speedtest";
        },

        get pingStats() {
            var p = this.pings;
            if (!p.length) { return { min: 0, avg: 0, max: 0 }; }
            var sum = 0;
            for (var i = 0; i < p.length; i++) { sum += p[i]; }
            return {
                min: Math.round(Math.min.apply(null, p) * 10) / 10,
                avg: Math.round((sum / p.length) * 10) / 10,
                max: Math.round(Math.max.apply(null, p) * 10) / 10,
            };
        },

        toolIcon: function (tool) {
            return LG_TOOL_ICONS[tool] || "fa-terminal";
        },

        toolDesc: function (tool) {
            return window.t("tool_" + tool + "_desc");
        },

        statusLabel: function () {
            return window.t("status_" + this.status);
        },

        setView: function (v) {
            this.view = v;
            if (v === "console" && this._fit) {
                this.$nextTick(() => {
                    try { this._fit.fit(); } catch (e) { /* terminal non prêt */ }
                });
            }
        },

        probeLabel: function (p) {
            if (p === null || p === undefined) { return "✕"; }
            return p < 1 ? "<1" : String(Math.round(p * 10) / 10);
        },

        probeColor: function (p) {
            if (p === null || p === undefined) { return "lg-probe--miss"; }
            if (p < 30) { return "lg-probe--ok"; }
            if (p < 100) { return "lg-probe--mid"; }
            return "lg-probe--slow";
        },

        _initTerminal: function () {
            var self = this;
            var el = document.getElementById("lg-console");
            if (!window.Terminal || !window.FitAddon || !el) {
                setTimeout(function () { self._initTerminal(); }, 60);
                return;
            }
            self._term = new window.Terminal({
                fontFamily: '"CascadiaCode", ui-monospace, monospace',
                fontSize: 13,
                lineHeight: 1.45,
                cursorBlink: true,
                cursorStyle: "bar",
                disableStdin: true,
                scrollback: 5000,
                theme: {
                    background: "#0c0c10",
                    foreground: "#d4d4d8",
                    cursor: "#f0a030",
                    cursorAccent: "#0c0c10",
                    selectionBackground: "rgba(240, 160, 48, 0.25)",
                },
            });
            self._fit = new window.FitAddon.FitAddon();
            self._term.loadAddon(self._fit);
            self._term.open(el);
            self._fit.fit();
            window.addEventListener("resize", function () {
                try { self._fit.fit(); } catch (e) { /* terminal non prêt */ }
            });
            self._printIdle();
        },

        _printIdle: function () {
            if (this._term) {
                this._term.write(LG_ANSI.sys + window.t("console_idle") + LG_ANSI.reset + "\r\n");
            }
        },

        _write: function (kind, text) {
            this._buffer.push(text);
            if (this._term) {
                this._term.write((LG_ANSI[kind] || "") + text + LG_ANSI.reset + "\r\n");
            }
        },

        _parseHops: function () {
            var parse = (this.tool === "mtr") ? parseMtrHop : parseTracerouteHop;
            var target = this.resolvedIp;
            var hops = [];
            this._buffer.forEach(function (raw) {
                var hop = parse(raw);
                if (hop) {
                    hop.isTarget = !!(target && hop.host === target);
                    hops.push(hop);
                }
            });
            return hops;
        },

        clear: function () {
            this.status = "idle";
            this.commandLabel = "";
            this.cmdError = "";
            this.durationMs = null;
            this.exitCode = null;
            this.hops = [];
            this.resolvedIp = "";
            this.pings = [];
            this.pingLoss = null;
            this._buffer = [];
            if (this._term) {
                this._term.reset();
                this._printIdle();
            }
            if (this._pingChart) {
                this._pingChart.updateSeries([{ name: "ms", data: [] }], false);
            }
        },

        copyOutput: function () {
            var self = this;
            var text = this._buffer.join("\n");
            if (!text || !navigator.clipboard) { return; }
            navigator.clipboard.writeText(text).then(function () {
                self.copied = true;
                setTimeout(function () { self.copied = false; }, 1600);
            }).catch(function () { /* presse-papiers indisponible */ });
        },

        useMyIp: async function () {
            if (this.ipLoading) { return; }
            this.ipLoading = true;
            try {
                var res = await makeGetRequest("/api/v1/ip");
                var ip = res.response && res.response.data && res.response.data.ip;
                if (res.code === 200 && ip) {
                    this.target = ip;
                } else {
                    showToast("error", window.t("err_myip"));
                }
            } catch (e) {
                showToast("error", window.t("err_myip"));
            } finally {
                this.ipLoading = false;
            }
        },

        runSpeedtest: async function () {
            if (this.stRunning || !this.stFile) { return; }

            var token = "";
            if (this.turnstileSiteKey) {
                token = this._turnstileToken();
                if (!token) {
                    showToast("error", window.t("err_turnstile_missing"));
                    return;
                }
            }

            this.stRunning = true;
            this.stStatus = "running";
            this.stError = "";
            this.stSpeed = 0;
            this.stPeak = 0;
            this.stAvg = 0;
            this.stProgress = 0;
            this.stBytes = 0;
            this.stDuration = 0;
            this._stSamples = [];
            this._stStopped = false;
            this._initSpeedChart();

            var headers = {};
            if (token) { headers["X-Turnstile-Token"] = token; }

            var resp;
            try {
                resp = await fetch("/api/v1/speedtest/" + encodeURIComponent(this.stFile), { headers: headers });
            } catch (e) {
                this._stFail("err_network");
                return;
            }
            if (!resp.ok || !resp.body) {
                var key = "err_generic";
                try {
                    var j = await resp.json();
                    if (j && j.detail) { key = j.detail; }
                } catch (e) { /* corps non JSON */ }
                this._stFail(key);
                return;
            }

            var total = parseInt(resp.headers.get("Content-Length") || "0", 10);
            var reader = resp.body.getReader();
            this._stReader = reader;
            var t0 = performance.now();
            var lastT = t0;
            var lastBytes = 0;
            var received = 0;
            try {
                while (true) {
                    var chunk = await reader.read();
                    if (chunk.done) { break; }
                    received += chunk.value.length;
                    var now = performance.now();
                    if (now - lastT >= 200) {
                        var mbps = ((received - lastBytes) * 8) / ((now - lastT) / 1000) / 1e6;
                        this.stSpeed = Math.round(mbps);
                        this.stPeak = Math.max(this.stPeak, Math.round(mbps));
                        this.stBytes = received;
                        this.stProgress = total ? Math.min(100, Math.round((received / total) * 100)) : 0;
                        this.stDuration = (now - t0) / 1000;
                        this._pushSpeedSample(mbps);
                        lastT = now;
                        lastBytes = received;
                    }
                }
            } catch (e) {
                // flux interrompu (arrêt manuel ou réseau)
            }

            this.stRunning = false;
            this._stReader = null;
            this._resetTurnstile();
            var elapsed = (performance.now() - t0) / 1000;
            this.stBytes = received;
            this.stDuration = elapsed;
            this.stAvg = elapsed > 0 ? Math.round((received * 8) / elapsed / 1e6) : 0;
            if (this._stStopped) {
                this._stStopped = false;
                this.stStatus = "idle";
                return;
            }
            if (total && received < total) {
                this.stStatus = "error";
                this.stError = "err_network";
                return;
            }
            this.stProgress = 100;
            this.stSpeed = this.stAvg;
            this.stStatus = "done";
        },

        stopSpeedtest: function () {
            this._stStopped = true;
            if (this._stReader) {
                try { this._stReader.cancel(); } catch (e) { /* déjà fermé */ }
            }
        },

        _stFail: function (key) {
            this.stRunning = false;
            this.stStatus = "error";
            this.stError = key;
            this._stReader = null;
            this._resetTurnstile();
            showToast("error", window.t(key));
        },

        _initSpeedChart: function () {
            var el = document.getElementById("lg-speed-chart");
            if (!el || !window.ApexCharts) { return; }
            if (this._stChart) {
                this._stChart.destroy();
                this._stChart = null;
            }
            var dark = document.documentElement.dataset.theme === "dark";
            this._stChart = new window.ApexCharts(el, {
                chart: {
                    type: "area",
                    height: 150,
                    fontFamily: '"Outfit", system-ui, sans-serif',
                    foreColor: dark ? "#a09890" : "#3a3a45",
                    toolbar: { show: false },
                    animations: { enabled: false },
                },
                series: [{ name: "Mbps", data: [] }],
                colors: ["#f0a030"],
                fill: { type: "gradient", gradient: { shadeIntensity: 1, opacityFrom: 0.4, opacityTo: 0.05 } },
                stroke: { curve: "smooth", width: 2.5 },
                dataLabels: { enabled: false },
                xaxis: {
                    type: "numeric",
                    labels: { show: false },
                    axisBorder: { show: false },
                    axisTicks: { show: false },
                },
                yaxis: { min: 0, labels: { style: { fontSize: "11px" } } },
                grid: { borderColor: dark ? "#2c2c3a" : "#e2e2e8", strokeDashArray: 4 },
                tooltip: { enabled: false },
            });
            this._stChart.render();
        },

        _pushSpeedSample: function (mbps) {
            this._stSamples.push(Math.round(mbps));
            if (this._stChart) {
                this._stChart.updateSeries([{ name: "Mbps", data: this._stSamples }], false);
            }
        },

        _initPingChart: function () {
            var el = document.getElementById("lg-ping-chart");
            if (!el || !window.ApexCharts) { return; }
            if (this._pingChart) {
                this._pingChart.destroy();
                this._pingChart = null;
            }
            var dark = document.documentElement.dataset.theme === "dark";
            this._pingChart = new window.ApexCharts(el, {
                chart: {
                    type: "line",
                    height: 220,
                    fontFamily: '"Outfit", system-ui, sans-serif',
                    foreColor: dark ? "#a09890" : "#3a3a45",
                    toolbar: { show: false },
                    animations: { enabled: true },
                },
                series: [{ name: "ms", data: [] }],
                colors: ["#f0a030"],
                stroke: { curve: "smooth", width: 2.5 },
                markers: { size: 3, strokeWidth: 0 },
                dataLabels: { enabled: false },
                xaxis: {
                    type: "numeric",
                    labels: { show: false },
                    axisBorder: { show: false },
                    axisTicks: { show: false },
                },
                yaxis: {
                    min: 0,
                    labels: {
                        style: { fontSize: "11px" },
                        formatter: function (v) { return Math.round(v) + " ms"; },
                    },
                },
                grid: { borderColor: dark ? "#2c2c3a" : "#e2e2e8", strokeDashArray: 4 },
                tooltip: { theme: dark ? "dark" : "light" },
            });
            this._pingChart.render();
        },

        _pushPing: function () {
            if (this._pingChart) {
                this._pingChart.updateSeries([{ name: "ms", data: this.pings }], true);
            }
        },

        run: async function () {
            if (this.running || !this.target.trim()) { return; }

            var token = "";
            if (this.turnstileSiteKey) {
                token = this._turnstileToken();
                if (!token) {
                    showToast("error", window.t("err_turnstile_missing"));
                    return;
                }
            }

            this.status = "running";
            this.commandLabel = "";
            this.cmdError = "";
            this.durationMs = null;
            this.exitCode = null;
            this.hops = [];
            this.resolvedIp = "";
            this.pings = [];
            this.pingLoss = null;
            if (this.tool === "ping") { this._initPingChart(); }
            this.running = true;
            this._buffer = [];
            if (this._term) { this._term.reset(); }
            this._write("sys", window.t("console_connecting"));

            var body = {
                node_id: this.nodeId,
                tool: this.tool,
                target: this.target.trim(),
                family: this.family,
                turnstile_token: token,
            };

            var resp;
            try {
                resp = await fetch("/api/v1/run", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(body),
                });
            } catch (e) {
                this._fail("err_network");
                return;
            }

            if (!resp.ok || !resp.body) {
                var key = "err_generic";
                try {
                    var j = await resp.json();
                    if (j && j.detail) { key = j.detail; }
                } catch (e) { /* corps non JSON */ }
                this._fail(key);
                return;
            }

            if (this._term) { this._term.reset(); }  // retire le message de connexion
            this._buffer = [];
            await this._consume(resp.body);

            this.running = false;
            this._reader = null;
            this._resetTurnstile();
        },

        _consume: async function (stream) {
            this._reader = stream.getReader();
            var decoder = new TextDecoder();
            var buffer = "";
            try {
                while (true) {
                    var chunk = await this._reader.read();
                    if (chunk.done) { break; }
                    buffer += decoder.decode(chunk.value, { stream: true });
                    var idx;
                    while ((idx = buffer.indexOf("\n\n")) !== -1) {
                        this._handleFrame(buffer.slice(0, idx));
                        buffer = buffer.slice(idx + 2);
                    }
                }
            } catch (e) {
                // flux interrompu (arrêt manuel ou réseau), l'état est déjà à jour
            }
        },

        _handleFrame: function (frame) {
            var event = "message";
            var data = "";
            frame.split("\n").forEach(function (line) {
                if (line.indexOf("event:") === 0) {
                    event = line.slice(6).trim();
                } else if (line.indexOf("data:") === 0) {
                    data += line.slice(5).trim();
                }
            });
            if (!data) { return; }
            var payload;
            try { payload = JSON.parse(data); } catch (e) { return; }

            if (event === "meta") {
                this.commandLabel = payload.tool + " " + (payload.target || "");
                this.resolvedIp = payload.ip || "";
                var label = "# " + payload.tool + " " + (payload.target || "");
                if (payload.ip && payload.ip !== payload.target) {
                    label += " (" + payload.ip + ")";
                }
                this._write("meta", label);
            } else if (event === "line") {
                this._write("out", payload.text);
                if (this.tool === "ping") {
                    var lat = parsePingLatency(payload.text);
                    if (lat !== null) {
                        this.pings.push(lat);
                        this._pushPing();
                    }
                    var loss = parsePingLoss(payload.text);
                    if (loss !== null) { this.pingLoss = loss; }
                } else if (this.tool === "traceroute" || this.tool === "mtr") {
                    this.hops = this._parseHops();
                }
            } else if (event === "end") {
                this.status = payload.status || "error";
                this.durationMs = (payload.duration_ms != null) ? payload.duration_ms : null;
                this.exitCode = (payload.exit_code != null) ? payload.exit_code : null;
                if (this.tool === "traceroute" || this.tool === "mtr") {
                    this.hops = this._parseHops();
                }
                var summary = "# " + this.statusLabel();
                if (this.durationMs != null) { summary += " : " + formatDuration(this.durationMs); }
                this._write("end", summary);
            }
        },

        stop: function () {
            if (this._reader) {
                try { this._reader.cancel(); } catch (e) { /* déjà fermé */ }
            }
            this.running = false;
        },

        _fail: function (key) {
            this.running = false;
            this.status = "error";
            this.cmdError = key;
            this._write("err", window.t(key));
            this._resetTurnstile();
        },

        _renderTurnstile: function () {
            var self = this;
            var attempt = function () {
                if (window.turnstile) {
                    var el = document.getElementById("lg-turnstile");
                    if (el && self._tsWidgetId === undefined) {
                        var theme = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
                        self._tsWidgetId = window.turnstile.render(el, {
                            sitekey: self.turnstileSiteKey,
                            theme: theme,
                        });
                    }
                } else {
                    setTimeout(attempt, 200);
                }
            };
            attempt();
        },

        _turnstileToken: function () {
            if (window.turnstile && this._tsWidgetId !== undefined) {
                return window.turnstile.getResponse(this._tsWidgetId) || "";
            }
            return "";
        },

        _resetTurnstile: function () {
            if (window.turnstile && this._tsWidgetId !== undefined) {
                try { window.turnstile.reset(this._tsWidgetId); } catch (e) { /* widget absent */ }
            }
        },
    };
}
