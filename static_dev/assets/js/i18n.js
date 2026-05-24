function lgTranslate(lang, key, params) {
    var table = (window.I18N_ALL && window.I18N_ALL[lang]) || {};
    var text = (table[key] != null) ? table[key] : key;
    if (params) {
        Object.keys(params).forEach(function (name) {
            text = text.split("%" + name + "%").join(String(params[name]));
        });
    }
    return text;
}

function applyStaticTranslations(lang) {
    var table = (window.I18N_ALL && window.I18N_ALL[lang]) || {};
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
        var key = el.dataset.i18n;
        if (key in table) {
            el.textContent = table[key];
        }
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
        var key = el.dataset.i18nPlaceholder;
        if (key in table) {
            el.placeholder = table[key];
        }
    });
}

document.addEventListener("alpine:init", function () {
    Alpine.store("i18n", {
        lang: window.LG_LANG || "fr",

        t: function (key, params) {
            return lgTranslate(this.lang, key, params);
        },

        setLang: function (code) {
            if (code === this.lang || !window.I18N_ALL || !window.I18N_ALL[code]) {
                return;
            }
            this.lang = code;
            var secure = (location.protocol === "https:") ? "; secure" : "";
            document.cookie = "lg_lang=" + code + "; path=/; max-age=31536000; samesite=lax" + secure;
            document.documentElement.lang = code;
            applyStaticTranslations(code);
        },
    });
});

window.t = function (key, params) {
    var store = (window.Alpine && Alpine.store("i18n")) || null;
    var lang = store ? store.lang : (window.LG_LANG || "fr");
    return lgTranslate(lang, key, params);
};
