async function makeGetRequest(path, timeout) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, timeout || 10000);
    try {
        var res = await fetch(path, {
            signal: controller.signal,
            headers: { Accept: "application/json" },
        });
        var data = await res.json().catch(function () { return {}; });
        return { response: data, code: res.status };
    } catch (e) {
        return { response: {}, code: 0 };
    } finally {
        clearTimeout(timer);
    }
}
