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







  function renderList(items) {
    const cont = document.getElementById('ph-carousel');
    if (!items || !items.length) {
      cont.innerHTML = '<div class="ph-card ph-subtle">Sin recomendaciones por ahora. 🎉</div>';
      return;
    }

    // Construcción visual de tarjetas
    const html = items.map(it => {
      const pill = prioPill(it.prioridad);
      const avance = it.avance || 0;
      const barW = fillWidth(avance);

      return `
      <div class="ph-card">
        <div class="ph-card-header d-flex justify-content-between align-items-center">
          <div>${pill}</div>
          <div class="text-muted small fw-semibold">Score: ${it.score ?? '—'}</div>
        </div>

        <div class="mb-2" style="font-size:15px;">
          <strong>📁 Proyecto:</strong> ${it.proyecto}
        </div>
        <div class="mb-3" style="font-size:15px;">
          <strong>🎯 Tarea:</strong> ${it.subtarea}
        </div>

        <div class="d-flex justify-content-between mb-2 text-muted small">
          <div>🕓 Último trabajo: ${daysText(it.dias_sin_tocar)}</div>
          <div>⏱️ Tiempo sugerido: ${it.tiempo_sugerido_horas}h</div>
        </div>

        <div class="text-muted small mb-1">Avance: ${fmtPct(avance)}</div>
        <div class="ph-bar mb-3">
          <div class="ph-fill" style="width:${barW}%;"></div>
        </div>

        <div class="ph-actions d-flex flex-wrap gap-2 justify-content-center">
          <button class="btn btn-outline-primary btn-sm" 
            onclick="location.href='/tikets/${it.subtask_id}'">🎫 Ticket</button>
          <button class="btn btn-outline-secondary btn-sm" 
            onclick="location.href='/projects/${it.project_id}'">📁 Proyecto</button>
        </div>
      </div>
    `;
    }).join('');

    cont.innerHTML = html;

    // 🧩 Asignar animaciones tipo deck
    const cards = cont.querySelectorAll('.ph-card');
    let current = 0;

    function updateView() {
      cards.forEach((c, i) => {
        c.classList.remove('active', 'prev', 'next', 'behind');
        if (i === current) c.classList.add('active');
        else if (i === (current - 1 + cards.length) % cards.length) c.classList.add('prev');
        else if (i === (current + 1) % cards.length) c.classList.add('next');
        else c.classList.add('behind');
      });
    }

    updateView();

    // 🎯 Soporte para touch y mouse swipe
    let startX = 0;
    let endX = 0;
    let isDragging = false;

    function startDrag(e) {
      isDragging = true;
      startX = e.touches ? e.touches[0].clientX : e.clientX;
    }

    function endDrag(e) {
      if (!isDragging) return;
      isDragging = false;
      endX = e.changedTouches ? e.changedTouches[0].clientX : e.clientX;
      const delta = endX - startX;

      // Desplazamiento significativo (mínimo 50px)
      if (Math.abs(delta) > 50) {
        if (delta < 0) {
          // Deslizó hacia la izquierda → siguiente
          current = (current + 1) % cards.length;
        } else {
          // Deslizó hacia la derecha → anterior
          current = (current - 1 + cards.length) % cards.length;
        }
        updateView();
      }
    }

    cont.addEventListener('mousedown', startDrag);
    cont.addEventListener('touchstart', startDrag);

    cont.addEventListener('mouseup', endDrag);
    cont.addEventListener('touchend', endDrag);
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
