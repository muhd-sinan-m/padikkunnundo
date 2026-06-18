/**
 * app.js — Shared utilities loaded on every authenticated page.
 *
 * Provides:
 *   api(path, options)   — fetch wrapper that returns parsed JSON or null
 *   escHtml(str)         — safe HTML escaping
 *   formatMark(v, max)   — "8 / 10" display
 *   Notification panel toggle (bell icon + tabs)
 *   Focus Priority loader (called when the Focus tab is opened)
 */

/* ── API wrapper ─────────────────────────────────────────────────────────── */

/**
 * Fetch a JSON endpoint and return the parsed body, or null on failure.
 * All requests are same-origin; the JWT lives in an httpOnly cookie and
 * is sent automatically by the browser.
 */
async function api(path, options = {}) {
  try {
    const res = await fetch(path, {
      ...options,
      credentials: 'same-origin',
    });
    if (res.status === 401) {
      // Session expired — redirect to login.
      window.location.href = '/login';
      return null;
    }
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('API error', path, err);
    return null;
  }
}

/* ── HTML escaping ───────────────────────────────────────────────────────── */

function escHtml(str) {
  const div = document.createElement('div');
  div.textContent = str == null ? '' : String(str);
  return div.innerHTML;
}

/* ── Mark formatting ─────────────────────────────────────────────────────── */

function formatMark(value, max) {
  if (value == null) return `— / ${max}`;
  return `${value} / ${max}`;
}

/* ── Time-of-day greeting ────────────────────────────────────────────────── */

function getGreeting(name) {
  const h = new Date().getHours();
  if (h < 12) return `Good morning, ${name}!`;
  if (h < 17) return `Good afternoon, ${name}!`;
  return `Good evening, ${name}!`;
}

/* ── Notification panel (Section 7.1 / 8.2) ─────────────────────────────── */

(function initNoticePanel() {
  const openBtn   = document.getElementById('open-notice-panel');
  const closeBtn  = document.getElementById('close-notice-panel');
  const overlay   = document.getElementById('notice-overlay');
  const panel     = document.getElementById('notice-panel');

  if (!openBtn || !panel) return;   // Not on a page that has the panel.

  let focusLoaded = false;

  function openPanel() {
    panel.classList.add('open');
    overlay.classList.add('open');
    overlay.setAttribute('aria-hidden', 'false');
    openBtn.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }

  function closePanel() {
    panel.classList.remove('open');
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
    openBtn.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  openBtn.addEventListener('click', openPanel);
  closeBtn.addEventListener('click', closePanel);
  overlay.addEventListener('click', closePanel);

  // Keyboard: Escape closes the panel.
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && panel.classList.contains('open')) closePanel();
  });

  // ── Tabs ──────────────────────────────────────────────────────────────────
  const tabs = panel.querySelectorAll('.panel-tab');
  const panes = panel.querySelectorAll('.panel-pane');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => { t.classList.remove('active'); t.setAttribute('aria-selected', 'false'); });
      panes.forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');

      const targetId = tab.getAttribute('aria-controls');
      document.getElementById(targetId).classList.add('active');

      // Load focus priority on first open of that tab.
      if (targetId === 'pane-focus' && !focusLoaded) {
        focusLoaded = true;
        loadFocusPriority();
      }
    });
  });
})();

/* ── Focus Priority loader (Section 3.5 / 7.4) ──────────────────────────── */

async function loadFocusPriority() {
  const container = document.getElementById('focus-list-container');
  if (!container) return;

  const data = await api('/api/focus');
  if (!data) {
    container.innerHTML = renderFocusEmpty('⚠️', 'Could not load focus data.');
    return;
  }

  const { ranked, no_data } = data;

  if (ranked.length === 0 && no_data.length === 0) {
    container.innerHTML = renderFocusEmpty('📊', 'No subjects enrolled yet.');
    return;
  }

  let html = '';

  if (ranked.length > 0) {
    html += ranked.map((subject, i) => {
      const detail = buildFocusDetail(subject);
      return `
        <div class="focus-item" id="focus-item-${subject.subject_id}">
          <div class="focus-rank">${i + 1}</div>
          <div class="focus-info">
            <div class="focus-name" title="${escHtml(subject.subject_name)}">${escHtml(subject.subject_name)}</div>
            <div class="focus-detail">${detail}</div>
          </div>
          <span class="focus-badge ${subject.css_class}">${escHtml(subject.difficulty_label)}</span>
        </div>
      `;
    }).join('');
  }

  if (no_data.length > 0) {
    if (ranked.length > 0) {
      html += `<p class="text-sm text-muted" style="margin-top:var(--space-4); margin-bottom:var(--space-2);">No marks entered yet:</p>`;
    }
    html += no_data.map(subject => `
      <div class="focus-item" id="focus-item-${subject.subject_id}">
        <div class="focus-rank" style="background:var(--gray-50); color:var(--gray-300);">—</div>
        <div class="focus-info">
          <div class="focus-name">${escHtml(subject.subject_name)}</div>
          <div class="focus-detail">No marks entered</div>
        </div>
        <span class="focus-badge status-grey">No data</span>
      </div>
    `).join('');
  }

  container.innerHTML = html;
}

function buildFocusDetail(subject) {
  if (subject.status === 'secured') return 'A+ already secured';
  if (subject.status === 'not_achievable') return 'A+ not achievable';
  return `Need ${subject.sea2_needed_aplus} / ${subject.sea2_max} in SEA2 for A+`;
}

function renderFocusEmpty(icon, msg) {
  return `
    <div class="empty-state" style="padding:var(--space-8) var(--space-4);">
      <div class="empty-state-icon">${icon}</div>
      <div class="empty-state-desc">${escHtml(msg)}</div>
    </div>
  `;
}
