/**
 * calculator.js — A+ Calculator standalone page (Section 7.3).
 *
 * A focused, distraction-free version of the My Marks grade logic.
 * The student selects a subject, enters their marks, and sees the
 * SEA2 requirement for every grade instantly.
 *
 * Uses the same Section 3.4 formula as marks.js and the server.
 */

(async function initCalculator() {
  const subjectSelect = document.getElementById('calc-subject-select');
  const inputsArea    = document.getElementById('calc-inputs');
  if (!subjectSelect) return;

  // ── Load enrolled subjects into the dropdown ───────────────────────────
  const data = await api('/api/subjects');
  if (!data || data.subjects.length === 0) {
    subjectSelect.innerHTML = '<option value="" disabled selected>No subjects found</option>';
    return;
  }

  data.subjects.forEach(subject => {
    const opt = document.createElement('option');
    opt.value = subject.subject_id;
    opt.textContent = `${subject.subject_name} (${subject.credit} credits)`;
    opt.dataset.struct = JSON.stringify(subject.structure);
    opt.dataset.marks  = JSON.stringify(subject.marks || {});
    subjectSelect.appendChild(opt);
  });

  // ── On subject change, render the input fields ─────────────────────────
  subjectSelect.addEventListener('change', () => {
    const selected = subjectSelect.options[subjectSelect.selectedIndex];
    const struct   = JSON.parse(selected.dataset.struct);
    const marks    = JSON.parse(selected.dataset.marks);
    renderInputs(struct, marks);
    inputsArea.style.display = 'block';
    computeAndRender(struct);
  });
})();


function renderInputs(struct, marks) {
  const grid = document.getElementById('calc-inputs-grid');
  if (!grid) return;

  const fields = [
    { key: 'isa',  label: 'ISA',  max: struct.isa  },
    { key: 'cp',   label: 'CP',   max: struct.cp   },
    { key: 'lb',   label: 'LB',   max: struct.lb   },
    { key: 'ld',   label: 'LD',   max: struct.ld   },
    { key: 'sea1', label: 'SEA1', max: struct.sea1 },
  ];

  grid.innerHTML = fields.map(f => `
    <div class="mark-input-group">
      <label class="mark-input-label" for="calc-input-${f.key}">
        ${f.label} <span class="mark-input-max">/ ${f.max}</span>
      </label>
      <input
        class="mark-input"
        type="number"
        id="calc-input-${f.key}"
        data-field="${f.key}"
        min="0"
        max="${f.max}"
        step="0.5"
        value="${marks[f.key] != null ? marks[f.key] : ''}"
        placeholder="—"
        aria-label="${f.label}"
      >
    </div>
  `).join('');

  // Attach listeners for live update.
  fields.forEach(f => {
    const input = document.getElementById(`calc-input-${f.key}`);
    if (!input) return;
    input.addEventListener('input', () => {
      // Clamp to max.
      const max = parseFloat(input.max);
      if (!isNaN(parseFloat(input.value)) && parseFloat(input.value) > max) {
        input.value = max;
        input.classList.add('is-invalid');
        setTimeout(() => input.classList.remove('is-invalid'), 600);
      }
      computeAndRender(struct);
    });
  });

  // Trigger initial computation with pre-filled values.
  computeAndRender(struct);
}


function computeAndRender(struct) {
  const val = key => {
    const el = document.getElementById(`calc-input-${key}`);
    return el ? (parseFloat(el.value) || 0) : 0;
  };

  const secured = val('isa') + val('cp') + val('lb') + val('ld') + val('sea1');

  const securedEl = document.getElementById('calc-secured');
  if (securedEl) securedEl.textContent = +secured.toFixed(2);

  const grades = computeGradesCalc(secured, struct);
  renderCalcResults(grades);
}


function computeGradesCalc(secured, struct) {
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
      status = 'secured'; cssClass = 'status-green'; label = 'Already secured';
    } else if (sea2Needed > sea2Max) {
      status = 'not_achievable'; cssClass = 'status-grey'; label = 'Not achievable';
    } else {
      const pct = sea2Needed / sea2Max;
      if      (pct < 0.40) { cssClass = 'status-green';  label = 'On track'; }
      else if (pct < 0.65) { cssClass = 'status-yellow'; label = 'Needs attention'; }
      else if (pct < 0.90) { cssClass = 'status-red';    label = 'Critical — focus here'; }
      else                 { cssClass = 'status-grey';   label = 'Not achievable'; }
      status = 'achievable';
    }

    result[grade] = { sea2_needed: Math.max(0, sea2Needed), sea2_max: sea2Max, status, css_class: cssClass, difficulty_label: label };
  });

  return result;
}


function renderCalcResults(grades) {
  const aplus    = grades['A+'];
  const bannerEl = document.getElementById('calc-banner');
  const mainEl   = document.getElementById('calc-banner-main');
  const subEl    = document.getElementById('calc-banner-sub');
  const pillsEl  = document.getElementById('calc-pills');

  if (!bannerEl) return;

  bannerEl.className = `grade-banner ${aplus.css_class}`;
  bannerEl.style.display = '';

  if (aplus.status === 'secured') {
    mainEl.textContent = 'A+ is secured 🎉';
    subEl.textContent  = 'You\'ve already crossed the A+ threshold.';
  } else if (aplus.status === 'not_achievable') {
    mainEl.textContent = 'A+ is not achievable';
    subEl.textContent  = `SEA2 needed exceeds the maximum of ${aplus.sea2_max}.`;
  } else {
    mainEl.textContent = `You need ${+aplus.sea2_needed.toFixed(1)} / ${aplus.sea2_max} in SEA2 for A+`;
    subEl.textContent  = aplus.difficulty_label;
  }

  // Secondary grade pills.
  pillsEl.style.display = '';
  pillsEl.innerHTML = ['A', 'B+', 'Pass'].map(grade => {
    const g = grades[grade];
    let text;
    if (g.status === 'secured')          text = `${grade}: secured`;
    else if (g.status === 'not_achievable') text = `${grade}: not achievable`;
    else                                 text = `${grade}: need ${+g.sea2_needed.toFixed(1)} / ${g.sea2_max}`;
    return `<span class="grade-pill ${g.css_class}">${text}</span>`;
  }).join('');
}
