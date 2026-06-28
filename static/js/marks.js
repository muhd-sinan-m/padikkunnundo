/* ── API wrapper ─────────────────────────────────────────────────────────── */
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
 *     The banner stays in placeholder state until at least one mark is entered.
 *   • Secondary pills show requirements for A and B+ only (no Pass).
 *   • A PYQPortal link is placed on each card (Section 7.2).
 *
 * NOTE: Wrapped in an IIFE so that const/let declarations do not throw
 * on re-execution during client-side navigation (nav.js swaps the
 * #main-content and re-evaluates page scripts).
 */

(function () {
  'use strict';

  const PYQPORTAL_BASE = 'https://pyqportal.app';
  const DEBOUNCE_MS    = 800;

  const saveTimers = {};

  /* ── Initialisation ─────────────────────────────────────────────────────── */
  (async function init() {
    const list = document.getElementById('marks-list');
    if (!list) return;

    const data = await getSubjects();
    if (!data) {
      list.innerHTML = renderErrorState();
      return;
    }

    // Check if user needs to complete onboarding (no semester or no subjects)
    if (data.subjects.length === 0) {
      const meData = await api('/api/me');
      if (meData && (!meData.semester || !meData.is_onboarded)) {
        list.innerHTML = renderOnboardingNeeded();
        return;
      }
      list.innerHTML = renderEmptyState();
      return;
    }

    list.innerHTML = data.subjects.map(function (subject) { return buildCard(subject); }).join('');

    // Attach input listeners and immediately recompute the live results
    // so saved marks show the correct prediction banner on page load.
    data.subjects.forEach(function (subject) {
      attachListeners(subject);
      updateCardDisplay(subject.subject_id, subject.structure);
    });

    // Scroll to specific subject if URL contains hash (e.g., from dashboard "Enter marks" link)
    // Wait for render via multiple rAF frames to ensure the card elements exist in the DOM.
    var subjectHash = window.location.hash;
    if (subjectHash && subjectHash.startsWith('#subject-')) {
      (function scrollToSubject() {
        var subjectId = subjectHash.replace('#subject-', '');
        var findCard = function () {
          var card = document.getElementById('marks-card-' + subjectId);
          if (card) {
            // Smooth scroll to the card, with an 80px offset for the topbar
            var headerOffset = 80;
            var elementPosition = card.getBoundingClientRect().top;
            var offsetPosition = elementPosition + window.pageYOffset - headerOffset;

            window.scrollTo({
              top: offsetPosition,
              behavior: 'smooth'
            });

            // Highlight effect
            card.style.transition = 'box-shadow 0.3s ease';
            card.style.boxShadow = '0 0 0 4px var(--color-primary), 0 0 20px rgba(var(--color-primary-rgb, 128, 0, 0), 0.3)';
            setTimeout(function () {
              card.style.boxShadow = '';
              card.style.transition = '';
            }, 2500);
          } else {
            // Not rendered yet — try again after the next animation frame
            requestAnimationFrame(findCard);
          }
        };
        requestAnimationFrame(findCard);
      })();
    }
  })();


  /* ── Card builder ────────────────────────────────────────────────────────── */

  function buildCard(subject) {
    var marks  = subject.marks  || {};
    var struct = subject.structure;
    var id     = subject.subject_id;

    // The five input fields in display order.
    var fields = [
      { key: 'isa',  label: 'ISA',  max: struct.isa  },
      { key: 'cp',   label: 'CP',   max: struct.cp   },
      { key: 'lb',   label: 'LB',   max: struct.lb   },
      { key: 'ld',   label: 'LD',   max: struct.ld   },
      { key: 'sea1', label: 'SEA1', max: struct.sea1 },
    ];

    var inputsHtml = fields.map(function (f) {
      return '<div class="mark-input-group">'
        + '<label class="mark-input-label" for="input-' + f.key + '-' + id + '">'
        + f.label + ' <span class="mark-input-max">/ ' + f.max + '</span>'
        + '</label>'
        + '<input class="mark-input" type="number" id="input-' + f.key + '-' + id + '"'
        + ' data-subject="' + id + '" data-field="' + f.key + '"'
        + ' min="0" max="' + f.max + '" step="0.5"'
        + ' value="' + (marks[f.key] != null ? marks[f.key] : '') + '"'
        + ' placeholder="—"'
        + ' aria-label="' + f.label + ' mark for ' + subject.subject_name + '">'
        + '</div>';
    }).join('');

    // Initial secured total.
    var secured = ['isa', 'cp', 'lb', 'ld', 'sea1']
      .reduce(function (sum, k) { return sum + (marks[k] || 0); }, 0);

    // CCA sub-total.
    var cca = (marks.isa || 0) + (marks.cp || 0) + (marks.lb || 0) + (marks.ld || 0);

    return '<div class="marks-card" id="marks-card-' + id + '">'

      + '<div class="marks-card-header">'
      + '<div class="marks-card-title">' + escHtml(subject.subject_name) + '</div>'
      + '<span class="credit-badge">' + subject.credit + ' credits · Total ' + struct.total + '</span>'
      + '</div>'

      + '<div class="marks-card-body">'

      + '<div class="mark-inputs-grid" id="inputs-grid-' + id + '">' + inputsHtml + '</div>'

      + '<div class="mark-secured-row" id="cca-row-' + id + '">'
      + '<span class="mark-secured-label">CCA Total (ISA+CP+LB+LD) / ' + struct.cca + '</span>'
      + '<span class="mark-secured-value" id="cca-total-' + id + '">' + cca + '</span>'
      + '</div>'

      + '<div class="mark-secured-row" id="secured-row-' + id + '" style="margin-top:0; border-top:none;">'
      + '<span class="mark-secured-label">Secured So Far / ' + struct.total + '</span>'
      + '<span class="mark-secured-value" id="secured-total-' + id + '">' + secured + '</span>'
      + '</div>'

      // A+ result banner
      + '<div id="banner-' + id + '" class="grade-banner status-grey" style="margin-top:var(--space-5);">'
      + '<div>'
      + '<div class="grade-banner-main" id="banner-main-' + id + '">Enter marks to see your A+ target</div>'
      + '<div class="grade-banner-sub" id="banner-sub-' + id + '">—</div>'
      + '</div>'
      + '</div>'

      // Secondary grade pills: A, B+ (no Pass)
      + '<div class="grade-pills" id="pills-' + id + '" style="margin-top:var(--space-3);"></div>'

      // PYQPortal link
      + '<a href="' + PYQPORTAL_BASE + '" target="_blank" rel="noopener" class="pyq-link" id="pyq-link-' + id + '">'
      + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">'
      + '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
      + '<polyline points="14 2 14 8 20 8"/>'
      + '</svg>'
      + ' Find past papers on PYQPortal ↗'
      + '</a>'

      + '</div>'
      + '</div>';
  }


  /* ── Input listeners ─────────────────────────────────────────────────────── */

  function attachListeners(subject) {
    var id     = subject.subject_id;
    var struct = subject.structure;
    var fields = ['isa', 'cp', 'lb', 'ld', 'sea1'];

    fields.forEach(function (field) {
      var input = document.getElementById('input-' + field + '-' + id);
      if (!input) return;

      input.addEventListener('input', function () {
        // Clamp to maximum at the UI layer
        var max = parseFloat(input.max);
        var val = parseFloat(input.value);
        if (!isNaN(val) && val > max) {
          input.value = max;
          input.classList.add('is-invalid');
          setTimeout(function () { input.classList.remove('is-invalid'); }, 600);
        }

        // Recompute totals and grade requirements immediately
        updateCardDisplay(id, struct);

        // Persist to server with a debounce
        scheduleSave(id);
      });
    });
  }


  /* ── Live display update ─────────────────────────────────────────────────── */

  function updateCardDisplay(subjectId, struct) {
    var id = subjectId;

    // Keep the placeholder visible until the user has typed something
    var hasAnyMarks = ['isa', 'cp', 'lb', 'ld', 'sea1'].some(function (f) {
      var el = document.getElementById('input-' + f + '-' + id);
      return el && el.value !== '';
    });

    function val(f) {
      var el = document.getElementById('input-' + f + '-' + id);
      return el ? (parseFloat(el.value) || 0) : 0;
    }

    var isa  = val('isa');
    var cp   = val('cp');
    var lb   = val('lb');
    var ld   = val('ld');
    var sea1 = val('sea1');

    var cca     = isa + cp + lb + ld;
    var secured = cca + sea1;

    // Update CCA sub-total
    var ccaEl = document.getElementById('cca-total-' + id);
    if (ccaEl) ccaEl.textContent = (+cca.toFixed(2)).toString();

    // Update secured total
    var secEl = document.getElementById('secured-total-' + id);
    if (secEl) secEl.textContent = (+secured.toFixed(2)).toString();

    if (!hasAnyMarks) return;

    var grades = computeGradesClientSide(secured, struct);
    renderGradeResults(id, grades);
  }


  /**
   * Client-side implementation of Section 3.4 (mirrors grading.py).
   */
  function computeGradesClientSide(secured, struct) {
    var total   = struct.total;
    var sea2Max = struct.sea2;

    var thresholds = { 'A+': 0.90, 'A': 0.80, 'B+': 0.70 };
    var order      = ['A+', 'A', 'B+'];

    var result = {};
    order.forEach(function (grade) {
      var target     = total * thresholds[grade];
      var sea2Needed = target - secured;

      var status, cssClass, label;

      if (sea2Needed <= 0) {
        status   = 'secured';
        cssClass = 'status-green';
        label    = 'Ready';
      } else if (sea2Needed > sea2Max) {
        status   = 'not_achievable';
        cssClass = (grade === 'A+') ? 'status-red' : 'status-grey';
        label    = 'Limit reached';
      } else {
        if (grade === 'A+') {
          cssClass = 'status-green';
          label    = 'Good pace';
        } else {
          var pct = sea2Needed / sea2Max;
          if      (pct < 0.40) { cssClass = 'status-green';  label = 'Good pace'; }
          else if (pct < 0.65) { cssClass = 'status-yellow'; label = 'Watch closely'; }
          else if (pct < 0.90) { cssClass = 'status-red';    label = 'High pressure'; }
          else                 { cssClass = 'status-grey';   label = 'Very high effort'; }
        }
        status = 'achievable';
      }

      result[grade] = {
        sea2_needed: Math.max(0, sea2Needed),
        sea2_max: sea2Max,
        status: status,
        css_class: cssClass,
        difficulty_label: label,
      };
    });

    return result;
  }


  function renderGradeResults(subjectId, grades) {
    var id      = subjectId;
    var aplus   = grades['A+'];
    var bannerEl = document.getElementById('banner-' + id);
    var mainEl  = document.getElementById('banner-main-' + id);
    var subEl   = document.getElementById('banner-sub-' + id);
    var pillsEl = document.getElementById('pills-' + id);

    if (!bannerEl) return;

    bannerEl.className = 'grade-banner ' + aplus.css_class;

    if (aplus.status === 'secured') {
      mainEl.textContent = 'A+ is secured 🎉';
      subEl.textContent  = '';
    } else if (aplus.status === 'not_achievable') {
      mainEl.textContent = 'Need ' + (+aplus.sea2_needed.toFixed(1)) + ' in SEA2 for A+, but max is ' + aplus.sea2_max;
      subEl.textContent  = '';
    } else {
      mainEl.textContent = 'Need ' + (+aplus.sea2_needed.toFixed(1)) + ' / ' + aplus.sea2_max + ' in SEA2 for A+';
      subEl.textContent  = '';
    }

    pillsEl.innerHTML = ['A', 'B+'].map(function (grade) {
      var g = grades[grade];
      var text;
      if (g.status === 'secured') {
        text = grade + ': secured';
      } else if (g.status === 'not_achievable') {
        text = grade + ': need ' + (+g.sea2_needed.toFixed(1)) + ' / ' + g.sea2_max;
      } else {
        text = grade + ': need ' + (+g.sea2_needed.toFixed(1)) + ' / ' + g.sea2_max;
      }
      return '<span class="grade-pill ' + g.css_class + '">' + text + '</span>';
    }).join('');
  }


  /* ── Debounced save ──────────────────────────────────────────────────────── */

  function scheduleSave(subjectId) {
    clearTimeout(saveTimers[subjectId]);
    saveTimers[subjectId] = setTimeout(function () { saveMarks(subjectId); }, DEBOUNCE_MS);
  }

  async function saveMarks(subjectId) {
    var id     = subjectId;
    var fields = ['isa', 'cp', 'lb', 'ld', 'sea1'];
    var body   = {};

    fields.forEach(function (f) {
      var el  = document.getElementById('input-' + f + '-' + id);
      var raw = el ? el.value : '';
      body[f] = raw === '' ? null : parseFloat(raw);
    });

    await api('/api/marks/' + id, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    invalidateSubjectsCache();
  }


  function renderEmptyState() {
    return '<div class="empty-state">'
      + '<div class="empty-state-icon">📋</div>'
      + '<div class="empty-state-title">No subjects found</div>'
      + '<div class="empty-state-desc">Complete your <a href="/onboarding" style="color:var(--color-primary);">profile setup</a> to see your subjects.</div>'
      + '</div>';
  }

  function renderOnboardingNeeded() {
    return '<div class="empty-state">'
      + '<div class="empty-state-icon">📝</div>'
      + '<div class="empty-state-title">Complete Your Profile</div>'
      + '<div class="empty-state-desc">Please complete your onboarding to enter marks.</div>'
      + '<a href="/onboarding" class="pyq-link" style="margin-top:var(--space-4); display:inline-block;">Go to Onboarding →</a>'
      + '</div>';
  }

  function renderErrorState() {
    return '<div class="empty-state">'
      + '<div class="empty-state-icon">⚠️</div>'
      + '<div class="empty-state-title">Could not load subjects</div>'
      + '<div class="empty-state-desc">Please refresh the page or try again later.</div>'
      + '</div>';
  }

})();
