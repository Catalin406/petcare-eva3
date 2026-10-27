/* ============================================================
   CITA_FORM.JS / HORARIOS LIBRES EN EL FORMULARIO DE CITA
   Al cambiar veterinario o fecha, pide a la API los bloques LIBRES
   de ese día (fetch asíncrono) y rellena el selector de hora. El
   servidor vuelve a validar todo al guardar: esto solo ayuda a elegir.
   ============================================================ */
document.addEventListener("DOMContentLoaded", () => {
    const profesional = document.getElementById("id_profesional");
    const fecha = document.getElementById("id_fecha");
    const hora = document.getElementById("id_hora");
    if (!profesional || !fecha || !hora) return;

    async function cargarHorarios() {
        if (!profesional.value || !fecha.value) return;
        const seleccionada = hora.value;
        hora.innerHTML = "<option value=''>Cargando horarios…</option>";
        try {
            const respuesta = await fetch(
                `/api/profesionales/${profesional.value}/horarios/?fecha=${fecha.value}`,
                { credentials: "same-origin", headers: { Accept: "application/json" } }
            );
            if (!respuesta.ok) throw new Error("HTTP " + respuesta.status);
            const bloques = (await respuesta.json()).filter((b) => b.estado === "LIBRE");
            hora.innerHTML = bloques.length
                ? "<option value=''>Elige un horario…</option>"
                : "<option value=''>Sin horarios libres ese día</option>";
            bloques.forEach((b) => {
                const opcion = new Option(`${b.hora_inicio} – ${b.hora_fin}`, b.hora_inicio);
                opcion.selected = b.hora_inicio === seleccionada;
                hora.add(opcion);
            });
        } catch (error) {
            hora.innerHTML = "<option value=''>No se pudieron cargar los horarios</option>";
        }
    }

    profesional.addEventListener("change", cargarHorarios);
    fecha.addEventListener("change", cargarHorarios);
});
