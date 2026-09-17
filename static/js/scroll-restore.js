(function () {
    var STORAGE_KEY = "ella:scrollY";

    function saveScroll() {
        try {
            sessionStorage.setItem(STORAGE_KEY, String(window.scrollY));
        } catch (e) {}
    }

    document.addEventListener("click", function (event) {
        var link = event.target.closest("a[href]");
        if (!link) return;
        if (link.target && link.target !== "" && link.target !== "_self") return;
        if (link.hasAttribute("download")) return;
        var href = link.getAttribute("href");
        if (!href || href.charAt(0) === "#") return;
        try {
            var url = new URL(link.href, window.location.href);
            if (url.origin !== window.location.origin) return;
        } catch (e) {
            return;
        }
        saveScroll();
    });

    document.addEventListener("submit", saveScroll);

    document.addEventListener("DOMContentLoaded", function () {
        var navEntries = window.performance && performance.getEntriesByType
            ? performance.getEntriesByType("navigation")
            : [];
        var navType = navEntries.length ? navEntries[0].type : null;
        // Back/forward already gets correct native scroll restoration from
        // the browser; only override for a fresh link click or form submit.
        if (navType === "back_forward") return;

        try {
            var saved = sessionStorage.getItem(STORAGE_KEY);
            sessionStorage.removeItem(STORAGE_KEY);
            if (saved !== null) {
                window.scrollTo(0, parseInt(saved, 10) || 0);
            }
        } catch (e) {}
    });
})();
