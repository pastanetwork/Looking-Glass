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
    dns: "fa-magnifying-glass",
    speedtest: "fa-gauge-high",
};

var LG_DNS_ALL_SET = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "CAA", "HTTPS", "SRV", "NAPTR", "DS", "DNSKEY", "TLSA", "SSHFP"];
var LG_DNS_RECORD_TYPES = ["ALL", "A", "AAAA", "HTTPS", "CNAME", "MX", "NS", "SOA", "TXT", "CAA", "SRV", "NAPTR", "DS", "DNSKEY", "TLSA", "SSHFP"];

function formatTtl(seconds) {
    if (seconds < 60) { return seconds + " s"; }
    if (seconds < 3600) { return Math.round(seconds / 60) + " min"; }
    return Math.round(seconds / 3600) + " h";
}

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

var LG_DNSSEC_ALGO = {
    "1": "RSAMD5", "3": "DSA", "5": "RSASHA1", "6": "DSA-NSEC3-SHA1",
    "7": "RSASHA1-NSEC3-SHA1", "8": "RSASHA256", "10": "RSASHA512", "12": "ECC-GOST",
    "13": "ECDSAP256SHA256", "14": "ECDSAP384SHA384", "15": "ED25519", "16": "ED448",
};
var LG_DS_DIGEST = { "1": "SHA-1", "2": "SHA-256", "3": "GOST", "4": "SHA-384" };
var LG_SSHFP_ALGO = { "1": "RSA", "2": "DSA", "3": "ECDSA", "4": "Ed25519", "6": "Ed448" };
var LG_SSHFP_FP = { "1": "SHA-1", "2": "SHA-256" };

function lgNamed(map, n) {
    return map[n] ? (n + " — " + map[n]) : n;
}

function lgTokens(value) {
    return value.match(/(?:[^\s"]+|"[^"]*")+/g) || [];
}

function lgUnquote(s) {
    return (s || "").replace(/^"|"$/g, "");
}

function dnsRecordFields(type, value) {
    var p = lgTokens(value);
    if (type === "SOA" && p.length >= 7) {
        return [
            { label: "dns_soa_primary", value: p[0] },
            { label: "dns_soa_contact", value: p[1] },
            { label: "dns_soa_serial", value: p[2] },
            { label: "dns_soa_refresh", value: formatTtl(+p[3]) },
            { label: "dns_soa_retry", value: formatTtl(+p[4]) },
            { label: "dns_soa_expire", value: formatTtl(+p[5]) },
            { label: "dns_soa_minimum", value: formatTtl(+p[6]) },
        ];
    }
    if (type === "SRV" && p.length >= 4) {
        return [
            { label: "dns_f_priority", value: p[0] },
            { label: "dns_f_weight", value: p[1] },
            { label: "dns_f_port", value: p[2] },
            { label: "dns_f_target", value: p[3] },
        ];
    }
    if (type === "CAA" && p.length >= 3) {
        return [
            { label: "dns_f_flags", value: p[0] },
            { label: "dns_f_tag", value: p[1] },
            { label: "dns_f_value", value: lgUnquote(p.slice(2).join(" ")) },
        ];
    }
    if (type === "DS" && p.length >= 4) {
        return [
            { label: "dns_f_keytag", value: p[0] },
            { label: "dns_f_algorithm", value: lgNamed(LG_DNSSEC_ALGO, p[1]) },
            { label: "dns_f_digesttype", value: lgNamed(LG_DS_DIGEST, p[2]) },
            { label: "dns_f_digest", value: p.slice(3).join("") },
        ];
    }
    if (type === "DNSKEY" && p.length >= 4) {
        var role = p[0] === "257" ? " (KSK)" : (p[0] === "256" ? " (ZSK)" : "");
        return [
            { label: "dns_f_flags", value: p[0] + role },
            { label: "dns_f_protocol", value: p[1] },
            { label: "dns_f_algorithm", value: lgNamed(LG_DNSSEC_ALGO, p[2]) },
            { label: "dns_f_key", value: p.slice(3).join("") },
        ];
    }
    if (type === "SSHFP" && p.length >= 3) {
        return [
            { label: "dns_f_algorithm", value: lgNamed(LG_SSHFP_ALGO, p[0]) },
            { label: "dns_f_fptype", value: lgNamed(LG_SSHFP_FP, p[1]) },
            { label: "dns_f_fingerprint", value: p.slice(2).join("") },
        ];
    }
    if (type === "TLSA" && p.length >= 4) {
        return [
            { label: "dns_f_usage", value: p[0] },
            { label: "dns_f_selector", value: p[1] },
            { label: "dns_f_matchingtype", value: p[2] },
            { label: "dns_f_certdata", value: p.slice(3).join("") },
        ];
    }
    if (type === "NAPTR" && p.length >= 6) {
        return [
            { label: "dns_f_order", value: p[0] },
            { label: "dns_f_preference", value: p[1] },
            { label: "dns_f_flags", value: lgUnquote(p[2]) },
            { label: "dns_f_service", value: lgUnquote(p[3]) },
            { label: "dns_f_regexp", value: lgUnquote(p[4]) || "—" },
            { label: "dns_f_replacement", value: p[5] },
        ];
    }
    return null;
}

function parseDnsRecord(raw) {
    var m = raw.match(/^(\S+)\s+(\d+)\s+IN\s+([A-Z0-9]+)\s+(.+?)\s*$/);
    if (!m) { return null; }
    var rec = { name: m[1], ttl: parseInt(m[2], 10), type: m[3], value: m[4] };
    if (rec.type === "MX") {
        var mx = rec.value.match(/^(\d+)\s+(.+)$/);
        if (mx) { rec.mxPrio = mx[1]; rec.mxHost = mx[2]; }
    } else if (rec.type === "HTTPS" || rec.type === "SVCB") {
        var tok = lgTokens(rec.value);
        if (tok.length >= 2) {
            var params = [];
            for (var i = 2; i < tok.length; i++) {
                var eq = tok[i].indexOf("=");
                params.push(eq === -1
                    ? { key: tok[i], value: "" }
                    : { key: tok[i].slice(0, eq), value: lgUnquote(tok[i].slice(eq + 1)) });
            }
            rec.https = { priority: tok[0], target: tok[1], params: params };
        }
    } else {
        var fields = dnsRecordFields(rec.type, rec.value);
        if (fields) { rec.fields = fields; }
    }
    return rec;
}

function parseDnsRecords(buffer) {
    var answers = [];
    var rcode = "";
    buffer.forEach(function (raw) {
        var h = raw.match(/status:\s*([A-Z]+)/);
        if (h) {
            if (rcode !== "NXDOMAIN") { rcode = h[1]; }
            return;
        }
        var rec = parseDnsRecord(raw);
        if (rec) { answers.push(rec); }
    });
    return { answers: answers, rcode: rcode };
}

function buildDnsTraceStep(n, records, server, ms) {
    var deleg = ["NS", "DS", "RRSIG", "NSEC", "NSEC3"];
    var ns = records.filter(function (r) { return r.type === "NS"; });
    var answers = records.filter(function (r) { return deleg.indexOf(r.type) === -1; });
    var zone = ns.length ? ns[0].name : (answers.length ? answers[0].name : "");
    return {
        n: n,
        server: server,
        ms: ms,
        zone: zone,
        nsCount: ns.length,
        delegateTo: ns.length ? ns[0].value : "",
        final: answers.length > 0,
        answers: answers.map(function (r) { return { type: r.type, value: r.value }; }),
    };
}

function parseDnsTrace(buffer) {
    var steps = [];
    var pending = [];
    buffer.forEach(function (raw) {
        var recv = raw.match(/^;;\s*Received\s+\d+\s+bytes\s+from\s+(\S+?)#\d+\(([^)]*)\)\s+in\s+(\d+)/i);
        if (recv) {
            steps.push(buildDnsTraceStep(steps.length + 1, pending, recv[2] || recv[1], parseInt(recv[3], 10)));
            pending = [];
            return;
        }
        var rec = parseDnsRecord(raw);
        if (rec) { pending.push(rec); }
    });
    return steps;
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
        dnsMode: "records",
        dnsRecord: "ALL",
        dnsRecordTypes: LG_DNS_RECORD_TYPES,
        dnsAnswers: [],
        dnsSteps: [],
        dnsRcode: "",
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
        stCliLoading: false,
        stCliCommands: null,
        stCliScripts: null,
        stCliOs: "linux",
        stCliCopied: false,
        stCliShowScript: false,

        init: function () {
            this._initTerminal();
            if (this.turnstileSiteKey) {
                this._renderTurnstile();
            }
            var plat = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "";
            this.stCliOs = /win/i.test(plat) ? "windows" : "linux";
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
            this.$watch("stFile", () => {
                this.stCliCommands = null;
                this.stCliScripts = null;
                this.stCliShowScript = false;
            });
            this.$watch("dnsMode", () => {
                if (this.tool === "dns") {
                    if (this.running) { this.stop(); }
                    this.clear();
                }
            });
        },

        get canRun() {
            return !this.running && this.target.trim().length > 0;
        },

        get hasVisual() {
            return this.tool === "ping" || this.tool === "traceroute"
                || this.tool === "mtr" || this.tool === "dns";
        },

        get dnsGroups() {
            var byType = {};
            this.dnsAnswers.forEach(function (r) {
                (byType[r.type] = byType[r.type] || []).push(r);
            });
            var groups = [];
            LG_DNS_RECORD_TYPES.forEach(function (t) {
                if (t !== "ALL" && byType[t]) {
                    groups.push({ type: t, records: byType[t] });
                    delete byType[t];
                }
            });
            Object.keys(byType).forEach(function (t) {
                groups.push({ type: t, records: byType[t] });
            });
            return groups;
        },

        get dnsEmptyTypes() {
            if (this.dnsMode !== "records" || this.dnsRecord !== "ALL" || this.status !== "ok") {
                return [];
            }
            var present = {};
            this.dnsAnswers.forEach(function (r) { present[r.type] = true; });
            return LG_DNS_ALL_SET.filter(function (t) { return !present[t]; });
        },

        get isSpeedtest() {
            return this.tool === "speedtest";
        },

        get stCliCommand() {
            return (this.stCliCommands && this.stCliCommands[this.stCliOs]) || "";
        },

        get stCliScript() {
            return (this.stCliScripts && this.stCliScripts[this.stCliOs]) || "";
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

            // Ctrl+C (ou Cmd+C) copie le texte sélectionné dans le presse-papiers
            // au lieu d'être absorbé par le terminal. Sans sélection, on laisse passer.
            self._term.attachCustomKeyEventHandler(function (e) {
                if (e.type === "keydown" && (e.ctrlKey || e.metaKey) && e.key === "c"
                        && self._term.hasSelection()) {
                    navigator.clipboard.writeText(self._term.getSelection());
                    return false;
                }
                return true;
            });
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

        _parseDns: function () {
            if (this.dnsMode === "trace") {
                this.dnsSteps = parseDnsTrace(this._buffer);
                this.dnsAnswers = [];
                this.dnsRcode = "";
            } else {
                var res = parseDnsRecords(this._buffer);
                this.dnsAnswers = res.answers;
                this.dnsRcode = res.rcode;
                this.dnsSteps = [];
            }
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
            this.dnsAnswers = [];
            this.dnsSteps = [];
            this.dnsRcode = "";
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

        genCliCommand: async function () {
            if (this.stCliLoading || !this.stFile) { return; }

            var token = "";
            if (this.turnstileSiteKey) {
                token = this._turnstileToken();
                if (!token) {
                    showToast("error", window.t("err_turnstile_missing"));
                    return;
                }
            }

            this.stCliLoading = true;
            this.stCliCommands = null;
            this.stCliScripts = null;
            this.stCliShowScript = false;

            var headers = { "Content-Type": "application/json" };
            if (token) { headers["X-Turnstile-Token"] = token; }

            try {
                var resp = await fetch("/api/v1/speedtest/cli-token", {
                    method: "POST",
                    headers: headers,
                    body: JSON.stringify({ file_id: this.stFile }),
                });
                var data = await resp.json().catch(function () { return {}; });
                if (resp.ok && data.data && data.data.commands) {
                    this.stCliCommands = data.data.commands;
                    this.stCliScripts = data.data.scripts;
                } else {
                    showToast("error", window.t((data && data.detail) || "err_generic"));
                }
            } catch (e) {
                showToast("error", window.t("err_network"));
            } finally {
                this.stCliLoading = false;
                this._resetTurnstile();
            }
        },

        copyCliCommand: function () {
            var self = this;
            if (!this.stCliCommand || !navigator.clipboard) { return; }
            navigator.clipboard.writeText(this.stCliCommand).then(function () {
                self.stCliCopied = true;
                setTimeout(function () { self.stCliCopied = false; }, 1600);
            }).catch(function () { /* presse-papiers indisponible */ });
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
            this.dnsAnswers = [];
            this.dnsSteps = [];
            this.dnsRcode = "";
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
                dns_mode: this.dnsMode,
                dns_record: this.dnsRecord,
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
                } else if (this.tool === "dns") {
                    this._parseDns();
                }
            } else if (event === "end") {
                this.status = payload.status || "error";
                this.durationMs = (payload.duration_ms != null) ? payload.duration_ms : null;
                this.exitCode = (payload.exit_code != null) ? payload.exit_code : null;
                if (this.tool === "traceroute" || this.tool === "mtr") {
                    this.hops = this._parseHops();
                } else if (this.tool === "dns") {
                    this._parseDns();
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
