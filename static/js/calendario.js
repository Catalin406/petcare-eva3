/* ============================================================
   CALENDARIO.JS / CALENDARIO CON FULLCALENDAR
   Pide los bloques del veterinario a la API (fetch asíncrono, con la
   sesión del navegador) y los pinta: libre (verde), ocupado (rojo),
   no atiende (café). El clic en un bloque libre abre el formulario de
   cita ya relleno; el clic en uno ocupado abre el detalle de la cita
   (solo si el usuario tiene permiso: la API ya filtró el detalle).
   ============================================================ */
document.addEventListener("DOMContentLoaded", () => {
    const contenedor = document.getElementById("calendario");
    const selector = document.getElementById("selector-profesional");
    if (!contenedor || !selector || typeof FullCalendar === "undefined") return;

    const puedeAgendar = contenedor.dataset.puedeAgendar === "1";

    const calendario = new FullCalendar.Calendar(contenedor, {
        locale: "es",
        timeZone: "America/Santiago",
        initialView: window.innerWidth < 768 ? "timeGridDay" : "timeGridWeek",
        firstDay: 1,
        allDaySlot: false,
        slotMinTime: "07:00:00",
        slotMaxTime: "21:00:00",
        height: "auto",
        nowIndicator: true,
        headerToolbar: { left: "prev,next today", center: "title", right: "timeGridDay,timeGridWeek,dayGridMonth" },
        buttonText: { today: "Hoy", day: "Día", week: "Semana", month: "Mes" },
        eventTimeFormat: { hour: "2-digit", minute: "2-digit", hour12: false },

        // Los eventos vienen de la API; cada cambio de rango o de veterinario vuelve a pedirlos.
        events: async (info, exito, fallo) => {
            try {
                const parametros = new URLSearchParams({
                    profesional: selector.value,
                    start: info.startStr.slice(0, 10),
                    end: info.endStr.slice(0, 10),
                });
                const respuesta = await fetch(`${contenedor.dataset.urlEventos}?${parametros}`, {
                    credentials: "same-origin",
                    headers: { Accept: "application/json" },
                });
                if (!respuesta.ok) throw new Error("HTTP " + respuesta.status);
                const datos = await respuesta.json();
                exito(
                    datos
                        .filter((e) => e.estado !== "PASADO")
                        .map((e) => ({
                            title: e.title,
                            start: e.start,
                            end: e.end,
                            classNames: ["evento-" + e.tipo],
                            extendedProps: e,
                        }))
                );
            } catch (error) {
                fallo(error);
            }
        },

        eventClick: (info) => {
            const e = info.event.extendedProps;
            if (e.estado === "LIBRE" && puedeAgendar) {
                const destino = new URLSearchParams({ profesional: selector.value, inicio: e.start });
                window.location.href = `${contenedor.dataset.urlNueva}?${destino}`;
            } else if (e.estado === "OCUPADO" && e.cita_id) {
                window.location.href = `${contenedor.dataset.urlCitas}${e.cita_id}/`;
            }
        },
    });

    calendario.render();
    selector.addEventListener("change", () => calendario.refetchEvents());
});
