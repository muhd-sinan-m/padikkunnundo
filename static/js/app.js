/**
 * app.js — Shared utilities loaded on every authenticated page.
 *
 * Provides:
 *   api(path, options)   — fetch wrapper that returns parsed JSON or null
 *   escHtml(str)         — safe HTML escaping
 *   formatMark(v, max)   — "8 / 10" display
 *   Notification panel toggle (bell icon)
 *   Mobile sidebar drawer
 *   Mobile bell button sync
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

// ── Subjects cache ────────────────────────────────────────────────────────
const SUBJECTS_CACHE_KEY = 'subjects_cache';

async function getSubjects() {
  const cached = sessionStorage.getItem(SUBJECTS_CACHE_KEY);
  if (cached) return JSON.parse(cached);

  const data = await api('/api/subjects');
  if (data) sessionStorage.setItem(SUBJECTS_CACHE_KEY, JSON.stringify(data));
  return data;
}

function invalidateSubjectsCache() {
  sessionStorage.removeItem(SUBJECTS_CACHE_KEY);
}

const ME_CACHE_KEY = 'me_cache';

async function getMe() {
  const cached = sessionStorage.getItem(ME_CACHE_KEY);
  if (cached) return JSON.parse(cached);
  const data = await api('/api/me');
  if (data) sessionStorage.setItem(ME_CACHE_KEY, JSON.stringify(data));
  return data;
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

function formatDesktopName(name) {
  if (!name) return "";
  if (name.length > 18) {
    const parts = name.trim().split(/\s+/);
    if (parts.length > 1) {
      const firstPart = parts.slice(0, -1).join(" ");
      const lastPart = parts[parts.length - 1];
      return `${escHtml(firstPart)}<br class="desktop-only-br"> ${escHtml(lastPart)}`;
    }
  }
  return escHtml(name);
}

function getGreeting(name) {
  const formattedName = formatDesktopName(name);
  const h = new Date().getHours();
  if (h < 12) return `Good morning, ${formattedName}!`;
  if (h < 17) return `Good afternoon, ${formattedName}!`;
  return `Good evening, ${formattedName}!`;
}

/* ── Notification panel ─────────────────────────────────────────────────── */

(function initNoticePanel() {
  const openBtn = document.getElementById('open-notice-panel');
  const closeBtn = document.getElementById('close-notice-panel');
  const overlay = document.getElementById('notice-overlay');
  const panel = document.getElementById('notice-panel');

  if (!openBtn || !panel) return;   // Not on a page that has the panel.

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
})();

/* ── Mobile sidebar drawer ────────────────────────────────────────────────── */

(function initMobileSidebar() {
  const menuBtn = document.getElementById('mobile-menu-btn');
  const closeBtn = document.getElementById('sidebar-close-btn');
  const overlay = document.getElementById('sidebar-overlay');
  const sidebar = document.querySelector('.sidebar');

  if (!menuBtn || !sidebar) return; // Not on a page with sidebar

  function openSidebar() {
    sidebar.classList.add('open');
    overlay.classList.add('open');
    overlay.setAttribute('aria-hidden', 'false');
    menuBtn.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }

  function closeSidebar() {
    sidebar.classList.remove('open');
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
    menuBtn.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  menuBtn.addEventListener('click', openSidebar);
  closeBtn.addEventListener('click', closeSidebar);
  overlay.addEventListener('click', closeSidebar);

  // Close sidebar when a nav link is clicked
  const navItems = sidebar.querySelectorAll('.sidebar-nav-item');
  navItems.forEach(item => {
    item.addEventListener('click', closeSidebar);
  });

  // Keyboard: Escape closes the sidebar
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && sidebar.classList.contains('open')) closeSidebar();
  });
})();

/* ── Mobile bell button sync ──────────────────────────────────────────────── */

(function initMobileBellButton() {
  const mobileBellBtn = document.getElementById('open-notice-panel-mobile');
  const desktopBellBtn = document.getElementById('open-notice-panel');

  if (!mobileBellBtn || !desktopBellBtn) return;

  // Click on mobile bell triggers the desktop bell button's click
  mobileBellBtn.addEventListener('click', () => {
    desktopBellBtn.click();
  });
})();
