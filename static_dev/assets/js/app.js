function toggleTheme() {
    var root = document.documentElement;
    if (root.dataset.theme === "dark") {
        delete root.dataset.theme;
        localStorage.setItem("lg-theme", "light");
    } else {
        root.dataset.theme = "dark";
        localStorage.setItem("lg-theme", "dark");
    }
}

document.addEventListener("alpine:init", function () {
    Alpine.store("toasts", {
        items: [],
        add: function (type, message, duration) {
            var id = Date.now() + Math.random();
            this.items.push({ id: id, type: type, message: message });
            var self = this;
            setTimeout(function () { self.remove(id); }, duration || 5000);
        },
        remove: function (id) {
            this.items = this.items.filter(function (it) { return it.id !== id; });
        },
    });
});

function showToast(type, message, duration) {
    if (window.Alpine && Alpine.store("toasts")) {
        Alpine.store("toasts").add(type, message, duration);
    }
}

function formatDuration(ms) {
    if (ms === null || ms === undefined) { return "—"; }
    if (ms < 1000) { return ms + " ms"; }
    if (ms < 60000) { return (Math.round(ms / 100) / 10) + " s"; }
    var totalSec = Math.round(ms / 1000);
    var min = Math.floor(totalSec / 60);
    var sec = totalSec % 60;
    return min + " min " + (sec < 10 ? "0" : "") + sec + " s";
}

function formatBytes(n) {
    if (!n) { return "0 o"; }
    if (n < 1024) { return n + " o"; }
    if (n < 1048576) { return (Math.round(n / 1024 * 10) / 10) + " Ko"; }
    if (n < 1073741824) { return (Math.round(n / 1048576 * 10) / 10) + " Mo"; }
    return (Math.round(n / 1073741824 * 100) / 100) + " Go";
}
