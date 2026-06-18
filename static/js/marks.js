/**
 * marks.js — My Marks page logic.
 *
 * Section 7.2:
 *   • Renders one card per enrolled subject.
 *   • Each card has ISA / CP / LB / LD / SEA1 inputs with credit-based
 *     maximums enforced as the HTML 'max' attribute (UI-layer constraint).
 *   • CCA total and "secured so far" update live on every input event —
 *     no save button required for the calculation display.
 *   • Marks are persisted to the server with a short debounce so that
 *     every keystroke doesn't fire a network request.
 *   • A live result banner shows SEA2 needed for A+ (color-coded, Section 3.5).
 *   • Secondary pills show requirements for A, B+, and Pass.
 *   • A PYQPortal link is placed on each card (Section 7.2).
 */

const PYQPORTAL_BASE = 'https://pyqportal.app';
const DEBOUNCE_MS    = 800;   // Wait this long after the last keystroke before saving.

const saveTimers = {};

(async function initMarks() {
  const list = document.getElementById('marks-list');
  if (!list) return;

  const data = await api('/api/subjects');
  if (!data || data.subjects.length === 0) {
    list.innerHTML = renderEmptyState();
    return;
  }

  list.innerHTML = data.subjects.map(subject => buildCard(subject)).join('');

  // Attach input listeners to every card.
  data.subjects.forEach(subject => attachListeners(subject));
})();


/* ── Card builder ────────────────────────────────────────────────────────── */

function buildCard(subject) {
  const marks  = subject.marks  || {};
  const struct = subject.structure;
  const id     = subject.subject_id;

  // The five input fields in display order.
  const fields = [
    { key: 'isa',  label: 'ISA',  max: struct.isa  },
    { key: 'cp',   label: 'CP',   max: struct.cp   },
    { key: 'lb',   label: 'LB',   max: struct.lb   },
    { key: 'ld',   label: 'LD',   max: struct.ld   },
    { key: 'sea1', label: 'SEA1', max: struct.sea1 },
  ];

  const inputsHtml = fields.map(f => `
    <div class="mark-input-group">
      <label class="mark-input-label" for="input-${f.key}-${id}">
        ${f.label} <span class="mark-input-max">/ ${f.max}</span>
      </label>
      <input
        class="mark-input"
        type="number"
        id="input-${f.key}-${id}"
        data-subject="${id}"
        data-field="${f.key}"
        min="0"
        max="${f.max}"
        step="0.5"
        value="${marks[f.key] != null ? marks[f.key] : ''}"
        placeholder="—"
        aria-label="${f.label} mark for ${subject.subject_name}"
      >
    </div>
  `).join('');

  // Initial secured total.
  const secured = ['isa','cp','lb','ld','sea1']
    .reduce((sum, k) => sum + (marks[k] || 0), 0);

  // CCA sub-total.
  const cca = (marks.isa || 0) + (marks.cp || 0) + (marks.lb || 0) + (marks.ld || 0);

  return `
    <div class="marks-card" id="marks-card-${id}">

      <div class="marks-card-header">
        <div class="marks-card-title">${escHtml(subject.subject_name)}</div>
        <span class="credit-badge">${subject.credit} credits · Total ${struct.total}</span>
      </div>

      <div class="marks-card-body">

        <!-- Input grid -->
        <div class="mark-inputs-grid" id="inputs-grid-${id}">${inputsHtml}</div>

        <!-- CCA sub-total (ISA+CP+LB+LD) -->
        <div class="mark-secured-row" id="cca-row-${id}">
          <span class="mark-secured-label">CCA Total (ISA+CP+LB+LD) / ${struct.cca}</span>
          <span class="mark-secured-value" id="cca-total-${id}">${cca}</span>
        </div>

        <!-- Full secured total (CCA + SEA1) -->
        <div class="mark-secured-row" id="secured-row-${id}" style="margin-top:0; border-top:none;">
          <span class="mark-secured-label">Secured So Far / ${struct.total}</span>
          <span class="mark-secured-value" id="secured-total-${id}">${secured}</span>
        </div>

        <!-- A+ result banner (Section 7.2 — live, color-coded) -->
        <div id="banner-${id}" class="grade-banner status-grey" style="margin-top:var(--space-5);">
          <div>
            <div class="grade-banner-main" id="banner-main-${id}">Enter marks to see your A+ target</div>
            <div class="grade-banner-sub" id="banner-sub-${id}">—</div>
          </div>
        </div>

        <!-- Secondary grade pills: A, B+, Pass -->
        <div class="grade-pills" id="pills-${id}" style="margin-top:var(--space-3);"></div>

        <!-- PYQPortal link (Section 7.2 — "what do I need" → "let me practise" in one click) -->
        <a href="${PYQPORTAL_BASE}" target="_blank" rel="noopener"
           class="pyq-link" id="pyq-link-${id}">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          Find past papers on PYQPortal ↗
        </a>

      </div><!-- /marks-card-body -->
    </div><!-- /marks-card -->
  `;
}


/* ── Input listeners ─────────────────────────────────────────────────────── */

function attachListeners(subject) {
  const id     = subject.subject_id;
  const struct = subject.structure;
  const fields = ['isa', 'cp', 'lb', 'ld', 'sea1'];

  fields.forEach(field => {
    const input = document.getElementById(`input-${field}-${id}`);
    if (!input) return;

    input.addEventListener('input', () => {
      // Clamp to maximum at the UI layer (Section 8.2 constraint).
      const max = parseFloat(input.max);
      const val = parseFloat(input.value);
      if (!isNaN(val) && val > max) {
        input.value = max;
        input.classList.add('is-invalid');
        setTimeout(() => input.classList.remove('is-invalid'), 600);
      }

      // Recompute totals and grade requirements immediately (no round-trip needed).
      updateCardDisplay(id, struct);

      // Persist to server with a debounce.
      scheduleSave(id);
    });
  });
}


/* ── Live display update ─────────────────────────────────────────────────── */

function updateCardDisplay(subjectId, struct) {
  const id = subjectId;
  const val = f => {
    const el = document.getElementById(`input-${f}-${id}`);
    return el ? (parseFloat(el.value) || 0) : 0;
  };

  const isa  = val('isa');
  const cp   = val('cp');
  const lb   = val('lb');
  const ld   = val('ld');
  const sea1 = val('sea1');

  const cca     = isa + cp + lb + ld;
  const secured = cca + sea1;

  // Update CCA sub-total.
  const ccaEl = document.getElementById(`cca-total-${id}`);
  if (ccaEl) ccaEl.textContent = +cca.toFixed(2);

  // Update secured total.
  const secEl = document.getElementById(`secured-total-${id}`);
  if (secEl) secEl.textContent = +secured.toFixed(2);

  // Compute grade requirements client-side using the same formula as the server
  // (Section 3.4). This gives instant feedback without a network round-trip.
  const grades = computeGradesClientSide(secured, struct);
  renderGradeResults(id, grades);
}


/**
 * Client-side implementation of Section 3.4 (mirrors grading.py).
 * Used for instant feedback; the server also validates and stores.
 */
function computeGradesClientSide(secured, struct) {
  const total   = struct.total;
  const sea2Max = struct.sea2;

  const thresholds = { 'A+': 0.90, 'A': 0.80, 'B+': 0.70, 'Pass': 0.40 };
  const order      = ['A+', 'A', 'B+', 'Pass'];

  const result = {};
  order.forEach(grade => {
    const target     = total * thresholds[grade];
    const sea2Needed = target - secured;

    let status, cssClass, label;

    if (sea2Needed <= 0) {
      status   = 'secured';
      cssClass = 'status-green';
      label    = 'Already secured';
    } else if (sea2Needed > sea2Max) {
      status   = 'not_achievable';
      cssClass = 'status-grey';
      label    = 'Not achievable';
    } else {
      const pct = sea2Needed / sea2Max;
      if (pct < 0.40)      { cssClass = 'status-green';  label = 'On track'; }
      else if (pct < 0.65) { cssClass = 'status-yellow'; label = 'Needs attention'; }
      else if (pct < 0.90) { cssClass = 'status-red';    label = 'Critical — focus here'; }
      else                 { cssClass = 'status-grey';   label = 'Not achievable'; }
      status = 'achievable';
    }

    result[grade] = {
      sea2_needed: Math.max(0, sea2Needed),
      sea2_max: sea2Max,
      status,
      css_class: cssClass,
      difficulty_label: label,
    };
  });

  return result;
}


function renderGradeResults(subjectId, grades) {
  const id = subjectId;
  const aplus    = grades['A+'];
  const bannerEl = document.getElementById(`banner-${id}`);
  const mainEl   = document.getElementById(`banner-main-${id}`);
  const subEl    = document.getElementById(`banner-sub-${id}`);
  const pillsEl  = document.getElementById(`pills-${id}`);

  if (!bannerEl) return;

  // ── A+ banner ─────────────────────────────────────────────────────────────
  bannerEl.className = `grade-banner ${aplus.css_class}`;

  if (aplus.status === 'secured') {
    mainEl.textContent = 'A+ is secured 🎉';
    subEl.textContent  = 'You\'ve already crossed the A+ threshold.';
  } else if (aplus.status === 'not_achievable') {
    mainEl.textContent = 'A+ is not achievable';
    subEl.textContent  = `SEA2 needed exceeds the maximum (${aplus.sea2_max}).`;
  } else {
    mainEl.textContent = `You need ${+aplus.sea2_needed.toFixed(1)} / ${aplus.sea2_max} in SEA2 for A+`;
    subEl.textContent  = aplus.difficulty_label;
  }

  // ── Secondary grade pills (A, B+, Pass) ───────────────────────────────────
  const secondaryGrades = ['A', 'B+', 'Pass'];
  pillsEl.innerHTML = secondaryGrades.map(grade => {
    const g = grades[grade];
    let text;
    if (g.status === 'secured')       text = `${grade}: secured`;
    else if (g.status === 'not_achievable') text = `${grade}: not achievable`;
    else                              text = `${grade}: need ${+g.sea2_needed.toFixed(1)} / ${g.sea2_max}`;
    return `<span class="grade-pill ${g.css_class}">${text}</span>`;
  }).join('');
}


/* ── Debounced save ──────────────────────────────────────────────────────── */

function scheduleSave(subjectId) {
  clearTimeout(saveTimers[subjectId]);
  saveTimers[subjectId] = setTimeout(() => saveMarks(subjectId), DEBOUNCE_MS);
}

async function saveMarks(subjectId) {
  const id     = subjectId;
  const fields = ['isa', 'cp', 'lb', 'ld', 'sea1'];
  const body   = {};

  fields.forEach(f => {
    const el  = document.getElementById(`input-${f}-${id}`);
    const raw = el ? el.value : '';
    body[f]   = raw === '' ? null : parseFloat(raw);
  });

  await api(`/api/marks/${id}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  // We don't update the UI from the server response here because we already
  // updated it client-side on the input event. The server save is for persistence.
}


function renderEmptyState() {
  return `
    <div class="empty-state">
      <div class="empty-state-icon">📋</div>
      <div class="empty-state-title">No subjects found</div>
      <div class="empty-state-desc">
        Complete your <a href="/onboarding" style="color:var(--color-primary);">profile setup</a> to see your subjects.
      </div>
    </div>
  `;
}
