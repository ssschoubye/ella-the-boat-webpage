// Full-screen picture viewer for a filarkiv folder. Reads each picture from
// the data-* attributes on the grid's .js-lightbox-trigger buttons.
(function () {
    var box = document.getElementById("lightbox");
    if (!box) return;

    var triggers = Array.prototype.slice.call(document.querySelectorAll(".js-lightbox-trigger"));
    var figure = box.querySelector(".lightbox__figure");
    var image = box.querySelector(".lightbox__image");
    var title = box.querySelector(".lightbox__title");
    var counter = box.querySelector(".lightbox__counter");
    var download = box.querySelector('[data-field="download"]');
    var edit = box.querySelector('[data-field="edit"]');
    var description = box.querySelector(".lightbox__description");
    var current = 0;
    var lastFocused = null;
    var touchStartX = null;

    function show(index) {
        current = (index + triggers.length) % triggers.length;
        var data = triggers[current].dataset;
        image.src = data.full;
        image.alt = data.title;
        title.textContent = data.title;
        description.textContent = data.description || "";
        description.hidden = !data.description;
        counter.textContent = (current + 1) + " / " + triggers.length;
        download.href = data.download;
        edit.href = data.edit;
        box.classList.toggle("lightbox--single", triggers.length < 2);
    }

    function open(index) {
        lastFocused = document.activeElement;
        show(index);
        box.hidden = false;
        document.body.classList.add("lightbox-open");
        figure.focus();
        document.addEventListener("keydown", onKeydown);
    }

    function close() {
        if (box.hidden) return;
        box.hidden = true;
        image.removeAttribute("src");
        document.body.classList.remove("lightbox-open");
        document.removeEventListener("keydown", onKeydown);
        if (lastFocused && typeof lastFocused.focus === "function") {
            lastFocused.focus();
        }
    }

    function onKeydown(event) {
        if (event.key === "Escape") close();
        else if (event.key === "ArrowLeft") show(current - 1);
        else if (event.key === "ArrowRight") show(current + 1);
    }

    triggers.forEach(function (trigger, index) {
        trigger.addEventListener("click", function () { open(index); });
    });

    box.addEventListener("click", function (event) {
        var step = event.target.closest("[data-step]");
        if (step) {
            show(current + Number(step.dataset.step));
        } else if (event.target.closest("[data-close]")) {
            close();
        }
    });

    box.addEventListener("touchstart", function (event) {
        touchStartX = event.touches.length === 1 ? event.touches[0].clientX : null;
    }, { passive: true });

    box.addEventListener("touchend", function (event) {
        if (touchStartX === null) return;
        var dx = event.changedTouches[0].clientX - touchStartX;
        touchStartX = null;
        if (Math.abs(dx) > 50) show(current + (dx < 0 ? 1 : -1));
    });
})();
