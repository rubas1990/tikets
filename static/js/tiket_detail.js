document.addEventListener("DOMContentLoaded", () => {
    // ======================================================
    // 🔹 Referencias globales
    // ======================================================
    const closeForm = document.getElementById("closeForm");
    const closeBtn = document.getElementById("closeButton");
    const overlay = document.getElementById("closingOverlay");
    const timerContainer = document.querySelector(".timer-container");
    const estadoProyecto = document.querySelector("[data-proyecto-status]");
    const botonTrabajar = document.querySelector("form[action*='subtask_timer_toggle'] button");

    // ======================================================
    // 🔔 Toast Bootstrap
    // ======================================================
    const toastElement = document.getElementById("toastMsg");
    const toastBody = toastElement ? toastElement.querySelector(".toast-body") : null;
    const toast = toastElement ? new bootstrap.Toast(toastElement, { delay: 3500 }) : null;
    const showToast = msg => {
        if (!toastElement || !toastBody) return;
        toastBody.textContent = msg;
        toastElement.classList.remove("bg-success");
        toastElement.classList.add("bg-danger");
        toast.show();
    };

    // ======================================================
    // 🎯 Reloj circular funcional
    // ======================================================
    let timerActivo = false;

    if (timerContainer) {
        const startAttr = timerContainer.getAttribute("data-start");
        const rawFlag = (timerContainer.getAttribute("data-en-trabajo") || "false").toLowerCase().trim();
        const enTrabajo = rawFlag === "true";
        const objetivoMin = Number(timerContainer.getAttribute("data-objetivo") || 0) * 60;

        if (enTrabajo && startAttr) {
            timerActivo = true;
            const startTime = new Date(startAttr);
            const circle = document.querySelector(".progress-ring__circle");
            const text = document.getElementById("circularTimer");

            const radius = 58;
            const circumference = 2 * Math.PI * radius;
            circle.style.strokeDasharray = `${circumference}`;
            circle.style.strokeDashoffset = `${circumference}`;

            timerContainer.classList.add("timer-active");

            function updateClock() {
                const now = new Date();
                const diff = Math.floor((now - startTime) / 1000); // segundos transcurridos
                const mins = String(Math.floor(diff / 60)).padStart(2, "0");
                const secs = String(diff % 60).padStart(2, "0");
                text.textContent = `${mins}:${secs}`;

                const offset = circumference - ((diff % 60) / 60) * circumference;
                circle.style.strokeDashoffset = offset;

                if (diff >= objetivoMin) timerContainer.classList.add("over-goal");
            }

            updateClock();
            setInterval(updateClock, 1000);
        }
    }

    // ======================================================
    // 🧩 Checklist persistente (sidebar izquierdo)
    // ======================================================
    let checklistCompleto = false;
    const checklistSidebar = document.getElementById("checklistSidebar");

    if (checklistSidebar) {
        const checklistContainer = document.getElementById("checklistContainer");
        const checklistItems = checklistContainer ? checklistContainer.querySelectorAll(".checklist-item") : [];
        const alertBox = document.getElementById("checklistAlert");

        if (checklistItems.length > 0) {
            const ticketId = checklistSidebar.dataset.ticketId || window.location.pathname.split("/").pop();
            const storageKey = `checklist_state_${ticketId}`;
            const saved = JSON.parse(localStorage.getItem(storageKey) || "[]");
            checklistItems.forEach((cb, i) => (cb.checked = !!saved[i]));

            function verificarChecklist() {
                const total = checklistItems.length;
                const marcados = [...checklistItems].filter(cb => cb.checked).length;
                checklistCompleto = total > 0 && marcados === total;

                if (alertBox) {
                    if (checklistCompleto) {
                        alertBox.className = "alert alert-success mt-3";
                        alertBox.innerHTML = "✅ Checklist completo.";
                    } else {
                        alertBox.className = "alert alert-warning mt-3";
                        alertBox.innerHTML = `🔒 ${total - marcados} punto(s) pendiente(s).`;
                    }
                }

                localStorage.setItem(storageKey, JSON.stringify([...checklistItems].map(cb => cb.checked)));
            }

            checklistItems.forEach(cb => cb.addEventListener("change", verificarChecklist));
            verificarChecklist();
        }
    }

    // ======================================================
    // ⚙️ Estado del timer
    // ======================================================
    function obtenerEstadoTimer() {
        const raw = (timerContainer?.getAttribute("data-en-trabajo") || "false").toLowerCase().trim();
        const enTrabajoAttr = raw === "true";
        const botonBreak = document.querySelector(".btn-danger.btn-xl.w-100");
        return enTrabajoAttr || !!botonBreak;
    }

    // ======================================================
    // 🧠 Validación de cierre
    // ======================================================
    function verificarCierre() {
        const proyectoActivo = estadoProyecto
            ? estadoProyecto.getAttribute("data-proyecto-status") === "Trabajando"
            : true;

        const timerCorriendo = obtenerEstadoTimer();

        // ✅ Comentario (activo o guardado)
        let comentarioLleno = false;
        const comentariosInput = document.querySelector("textarea[name='comentario']");
        if (comentariosInput && comentariosInput.value.trim().length > 0) {
            comentarioLleno = true;
        } else {
            const comentariosGuardados = document.querySelector(".scrollable-box pre");
            if (comentariosGuardados && comentariosGuardados.textContent.trim().length > 0) {
                comentarioLleno = true;
            }
        }

        // ✅ Checklist
        const checklistContainer = document.getElementById("checklistContainer");
        const items = checklistContainer ? checklistContainer.querySelectorAll(".checklist-item") : [];
        const checklistOK = items.length > 0 && [...items].every(cb => cb.checked);

        const puedeCerrar = !timerCorriendo && checklistOK && comentarioLleno && proyectoActivo;

        if (closeForm) {
            closeForm.style.display = puedeCerrar ? "block" : "none";
            closeForm.style.transition = "all 0.3s ease";
        }
        if (closeBtn) closeBtn.disabled = !puedeCerrar;

        console.log("🧩 Validación cierre →", {
            proyectoActivo,
            checklistOK,
            comentarioLleno,
            timerCorriendo,
            puedeCerrar
        });

        return puedeCerrar;
    }

    // ======================================================
    // 🚫 Interceptar envío
    // ======================================================
    if (closeForm) {
        closeForm.addEventListener("submit", e => {
            const valido = verificarCierre();
            if (!valido) {
                e.preventDefault();
                showToast("⏱️ No puedes cerrar: agrega comentarios, detén el tiempo y completa el checklist.");
                return;
            }
            overlay.style.display = "flex";
            setTimeout(() => closeForm.submit(), 4000);
        });
    }

    // ======================================================
    // ⏯️ Bloquear cuando se presiona “Trabajar” o “Break”
    // ======================================================
    if (botonTrabajar && closeBtn && closeForm) {
        botonTrabajar.addEventListener("click", () => {
            closeBtn.disabled = true;
            closeForm.style.display = "none";
        });
    }

    // ======================================================
    // 🔄 Eventos y validación inicial
    // ======================================================
    document.querySelectorAll(".checklist-item").forEach(cb => cb.addEventListener("change", verificarCierre));
    const comentariosInput = document.querySelector("textarea[name='comentario']");
    if (comentariosInput) comentariosInput.addEventListener("input", verificarCierre);

    setTimeout(verificarCierre, 1000);
});
