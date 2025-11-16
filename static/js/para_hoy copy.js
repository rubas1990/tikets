// static/js/para_hoy.js
// --------------------------------------------------
// Cliente de la Agenda "Para hoy"
// - Llama a /api/para_hoy?n=...
// - Renderiza cards
// - Auto-refresh cada 60s y botón manual
// --------------------------------------------------

(function () {
  // Obtiene el número de tareas a mostrar desde el input
  function getCount() {
    const el = document.getElementById('ph-count');
    const v = parseInt(el.value || '8', 10);
    return isNaN(v) ? 8 : Math.max(1, v);
  }

  // Pequeño ayudante de formato
  function fmtPct(x) { return Math.round((x || 0) * 100) + '%'; }
  function prioPill(prio) {
    // prio: 1 baja, 2 media, 3 alta (ajusta si usas 1..5)
    if (prio >= 3) return '<span class="ph-pill ph-prio-alta">Prioridad ALTA</span>';
    if (prio === 2) return '<span class="ph-pill ph-prio-media">Prioridad MEDIA</span>';
    return '<span class="ph-pill ph-prio-baja">Prioridad BAJA</span>';
  }
  function daysText(d) { return d === 1 ? 'hace 1 día' : `hace ${d} días`; }
  function fillWidth(avance) { return Math.max(2, Math.round((avance || 0) * 100)); }

  // Renderizar impacto ASCII
  function renderImpact(o) {
    const a = o?.antes_pct ?? 0;
    const d = o?.despues_pct ?? a;
    const bar = (n) => '█'.repeat(Math.max(1, Math.round(n / 3))) + ' ' + n + '%';
    return [
      'Antes  : ' + bar(a),
      'Después: ' + bar(d)
    ].join('\n');
  }

  // Renderizar cards
  function renderList(items) {
    const cont = document.getElementById('ph-list');
    if (!items || !items.length) {
      cont.innerHTML = '<div class="ph-card ph-subtle">Sin recomendaciones por ahora. 🎉</div>';
      document.getElementById('ph-legend').textContent = '—';
      return;
    }

    // Leyenda por día (íconos por prioridad)
    const legend = items.map(it => {
      if (it.prioridad >= 3) return '🔴';
      if (it.prioridad === 2) return '🟠';
      return '🟢';
    }).join(' ');
    document.getElementById('ph-legend').textContent = legend;

    // Construye HTML de tarjetas
    const html = items.map(it => {
      const pill = prioPill(it.prioridad);
      const avance = it.avance || 0;
      const barW = fillWidth(avance);

      return `
        <div class="ph-card">
          <div class="ph-header">
            <div style="font-weight:700">${pill}</div>
            <div class="ph-subtle">Score: ${it.score}</div>
          </div>

          <div style="font-size:15px;margin-bottom:6px;">
            <span style="font-weight:600;">Proyecto:</span> ${it.proyecto}
          </div>
          <div style="font-size:15px;margin-bottom:8px;">
            <span style="font-weight:600;">Tarea:</span> ${it.subtarea}
          </div>

          <div class="ph-grid" style="margin-bottom:8px;">
            <div class="ph-subtle">Último trabajo: ${daysText(it.dias_sin_tocar)}</div>
            <div class="ph-subtle">Tiempo sugerido: ${it.tiempo_sugerido_horas}h</div>
          </div>

          <div class="ph-subtle" style="margin-bottom:6px;">Avance: ${fmtPct(avance)}</div>
          <div class="ph-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100">
            <div class="ph-fill" style="width:${barW}%"></div>
          </div>
<div class="ph-actions" style="margin-top:10px; display:flex; gap:8px; flex-wrap:wrap;">
  <!-- ✅ Ticket: va directo al detalle con ID real -->
  <button onclick="location.href='/tikets/${it.subtask_id}'">🎫 Ticket</button>

  <!-- ✅ Proyecto se queda igual -->
  <button onclick="location.href='/projects/${it.project_id}'">📁 Proyecto</button>
</div>

        </div>
      `;
    }).join('');

    cont.innerHTML = html;
  }

  // Fetch al API
  async function fetchData(n = getCount()) {
    console.log("FETCH with n=", n); // 🧪 Debug
    const resp = await fetch(`/api/para_hoy?n=${n}`, { cache: 'no-store' });
    const data = await resp.json();
    console.log("API response:", data); // 🧪 Debug


    if (data.generated_at) {
      const last = new Date(data.generated_at);
      document.getElementById('ph-last').textContent =
        `Últ. actualización: ${last.toLocaleString()}`;
    }

    if (data.impacto) {
      document.getElementById('ph-impact').textContent =
        renderImpact(data.impacto);
    }

    renderList(data.items);
  }


  document.addEventListener('DOMContentLoaded', () => {

    function applyCount() {
      const n = getCount();
      fetchData(n);
    }

    // Cargar inicial
    applyCount();

    // Botón aplicar ✅ ahora sí usa el input correcto
    document.getElementById('ph-apply').addEventListener('click', applyCount);

    // Botón refresh manual ✅ mantiene el valor
    document.getElementById('ph-refresh').addEventListener('click', applyCount);

    // Auto-refresh suave cada 60s ✅ mantiene el valor elegido
    setInterval(applyCount, 60000);
  });

})();
