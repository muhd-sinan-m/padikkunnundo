/**
 * dashboard.js — Dashboard page logic.
 *
 * Section 7.1:
 *   • Personalized greeting (time-of-day aware).
 *   • Populates the 3 stat cards from /api/subjects response.
 *   • Renders the enrolled-subject grid with credit badge and mark progress.
 */

(async function initDashboard() {
  // ── Greeting (Section 7.1) ───────────────────────────────────────────────
  const greetingEl = document.getElementById('greeting-text');
  if (greetingEl) {
    const meData = await api('/api/me');
    if (meData) {
      greetingEl.textContent = getGreeting(meData.name.split(' ')[0]);
    }
  }

  // ── Subjects + stats ─────────────────────────────────────────────────────
  const data = await api('/api/subjects');
  if (!data) {
    renderError();
    return;
  }

  renderStats(data.stats);
  renderSubjectGrid(data.subjects);
})();


function renderStats(stats) {
  const total    = document.getElementById('stat-total');
  const entered  = document.getElementById('stat-entered');
  const onTrack  = document.getElementById('stat-on-track');

  if (total)   total.textContent   = stats.total_subjects;
  if (entered) entered.textContent = `${stats.marks_entered} / ${stats.total_subjects}`;
  if (onTrack) onTrack.textContent = stats.on_track_for_aplus;
}


function renderSubjectGrid(subjects) {
  const grid = document.getElementById('subjects-grid');
  if (!grid) return;

  if (subjects.length === 0) {
    grid.innerHTML = `
      <div style="grid-column:1/-1;" class="empty-state">
        <div class="empty-state-icon">📋</div>
        <div class="empty-state-title">No subjects found</div>
        <div class="empty-state-desc">Contact your administrator if this is unexpected.</div>
      </div>
    `;
    return;
  }

  grid.innerHTML = subjects.map(subject => {
    const marks   = subject.marks || {};
    const struct  = subject.structure;

    // Count how many of the 5 mark fields have been entered.
    const fields       = ['isa', 'cp', 'lb', 'ld', 'sea1'];
    const enteredCount = fields.filter(f => marks[f] != null).length;
    const progressPct  = Math.round((enteredCount / fields.length) * 100);

    // Compute secured so far for the card footer.
    const secured = fields.reduce((sum, f) => sum + (marks[f] || 0), 0);
    const total   = struct.total;

    return `
      <div class="subject-card" id="subject-card-${subject.subject_id}">
        <div class="subject-card-header">
          <div class="subject-name">${escHtml(subject.subject_name)}</div>
          <span class="credit-badge">${subject.credit} cr</span>
        </div>
        <div class="subject-progress-label">
          ${enteredCount === 0
            ? 'No marks entered yet'
            : `${enteredCount} / 5 components entered · ${secured} / ${total} marks`
          }
        </div>
        <div class="progress-bar-track" role="progressbar"
             aria-valuenow="${progressPct}" aria-valuemin="0" aria-valuemax="100">
          <div class="progress-bar-fill" style="width:${progressPct}%"></div>
        </div>
        <div style="margin-top:var(--space-4);">
          <a href="/marks" class="pyq-link" id="goto-marks-${subject.subject_id}">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
            Enter marks →
          </a>
        </div>
      </div>
    `;
  }).join('');
}


function renderError() {
  const grid = document.getElementById('subjects-grid');
  if (!grid) return;
  grid.innerHTML = `
    <div style="grid-column:1/-1;" class="empty-state">
      <div class="empty-state-icon">⚠️</div>
      <div class="empty-state-title">Could not load subjects</div>
      <div class="empty-state-desc">Please refresh the page.</div>
    </div>
  `;
}
