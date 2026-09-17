(function () {
    var modal = document.getElementById("event-modal");
    if (!modal) return;

    var dialog = modal.querySelector(".event-modal__dialog");
    var lastFocused = null;

    function setField(name, value, opts) {
        opts = opts || {};
        var el = modal.querySelector('[data-field="' + name + '"]');
        if (!el) return;
        if (opts.href) {
            el.setAttribute("href", value || "#");
            return;
        }
        if (opts.hideIfEmpty && !value) {
            el.hidden = true;
            return;
        }
        el.hidden = false;
        el.textContent = value || "";
    }

    function openModal(trigger) {
        var data = trigger.dataset;
        setField("title", data.title);
        setField("booker", data.booker);
        setField("start", data.start);
        setField("end", data.end);
        setField("notes", data.notes, { hideIfEmpty: true });
        setField("edit-href", data.editUrl, { href: true });

        lastFocused = document.activeElement;
        modal.hidden = false;
        document.body.classList.add("event-modal-open");
        dialog.focus();
        document.addEventListener("keydown", onKeydown);
    }

    function closeModal() {
        if (modal.hidden) return;
        modal.hidden = true;
        document.body.classList.remove("event-modal-open");
        document.removeEventListener("keydown", onKeydown);
        if (lastFocused && typeof lastFocused.focus === "function") {
            lastFocused.focus();
        }
    }

    function onKeydown(event) {
        if (event.key === "Escape") closeModal();
    }

    document.addEventListener("click", function (event) {
        var trigger = event.target.closest(".js-event-trigger");
        if (trigger) {
            openModal(trigger);
            return;
        }
        if (event.target.closest("[data-close]")) {
            closeModal();
        }
    });
})();
