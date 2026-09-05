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

// ── Subjects & Me cache ──────────────────────────────────────────────────
const SUBJECTS_CACHE_KEY = 'subjects_cache';
const ME_CACHE_KEY = 'me_cache';

function invalidateSubjectsCache() {
  sessionStorage.removeItem(SUBJECTS_CACHE_KEY);
  sessionStorage.removeItem(ME_CACHE_KEY);
}

async function getMe() {
  const cached = sessionStorage.getItem(ME_CACHE_KEY);
  if (cached) {
    try {
      return JSON.parse(cached);
    } catch (e) {}
  }
  const data = await api('/api/me');
  if (data) sessionStorage.setItem(ME_CACHE_KEY, JSON.stringify(data));
  return data;
}

async function getSubjects() {
  const cached = sessionStorage.getItem(SUBJECTS_CACHE_KEY);
  if (cached) {
    try {
      return JSON.parse(cached);
    } catch (e) {}
  }

  const data = await api('/api/subjects');
  if (data) {
    sessionStorage.setItem(SUBJECTS_CACHE_KEY, JSON.stringify(data));
  }
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
  let parts = name.trim().split(/\s+/);
  if (parts.length > 1) {
    let i = parts.length - 1;
    while (i >= 0 && parts[i].length <= 1) {
      i--;
    }
    const initialsStart = i + 1;
    if (initialsStart < parts.length) {
      const initials = parts.slice(initialsStart).join("");
      parts = parts.slice(0, initialsStart).concat([initials]);
    }
  }
  const cleanedName = parts.join(" ");

  if (cleanedName.length >= 20) {
    if (parts.length > 1) {
      const firstPart = parts.slice(0, -1).join(" ");
      const lastPart = parts[parts.length - 1];
      return `${escHtml(firstPart)}<br class="desktop-only-br"> ${escHtml(lastPart)}`;
    }
  }
  return escHtml(cleanedName);
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
  const pane = document.getElementById('pane-notices');
  const badge = document.getElementById('bell-badge');

  if (!openBtn || !panel) return;   // Not on a page that has the panel.

  let loaded = false;
  let currentNotifications = [];

  function updateBadge(unreadCount) {
    if (badge) {
      if (unreadCount > 0) {
        badge.textContent = unreadCount > 9 ? '9+' : unreadCount;
        badge.style.display = 'flex';
      } else {
        badge.textContent = '';
        badge.style.display = 'none';
      }
    }
    if (openBtn) {
      if (unreadCount > 0) {
        openBtn.classList.add('has-unread');
      } else {
        openBtn.classList.remove('has-unread');
      }
    }
    const mobileBellBtn = document.getElementById('open-notice-panel-mobile');
    if (mobileBellBtn) {
      if (unreadCount > 0) {
        mobileBellBtn.classList.add('has-unread');
      } else {
        mobileBellBtn.classList.remove('has-unread');
      }
    }
  }

  function renderAnnouncements(data) {
    if (!pane) return;
    const items = Array.isArray(data) ? data : (data && data.notifications ? data.notifications : []);
    currentNotifications = items;
    const unreadCount = (data && typeof data.unread_count === 'number')
      ? data.unread_count
      : items.filter(a => !a.is_read).length;

    updateBadge(unreadCount);

    if (items.length === 0) {
      pane.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📢</div>
          <div class="empty-state-title">No notices yet</div>
          <div class="empty-state-desc">Admin notices will appear here.</div>
        </div>`;
      return;
    }

    const unreadItems = items.filter(a => !a.is_read);
    const readItems = items.filter(a => !!a.is_read);

    function renderCard(a) {
      const date = a.created_at ? new Date(a.created_at).toLocaleDateString('en-IN', {
        day: 'numeric', month: 'short', year: 'numeric'
      }) : '';
      const isRead = !!a.is_read;

      return `
        <div class="notice-item ${isRead ? 'is-read' : 'is-unread'}" id="notice-item-${a.id}">
          <div class="notice-item-top">
            <div class="notice-title-row">
              <span class="notice-item-title">${escHtml(a.title)}</span>
            </div>
            <button class="notice-read-toggle ${isRead ? 'read' : 'unread'}" data-id="${a.id}" data-action="${isRead ? 'unread' : 'read'}" title="${isRead ? 'Mark as unread' : 'Mark as read'}" aria-label="${isRead ? 'Mark as unread' : 'Mark as read'}">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
              <span>${isRead ? 'Read' : 'Mark read'}</span>
            </button>
          </div>
          <div class="notice-item-body">${escHtml(a.body)}</div>
          ${date ? `<div class="notice-item-date">${escHtml(date)}</div>` : ''}
        </div>`;
    }

    let subbarHtml = '';
    if (unreadCount > 0) {
      subbarHtml = `
        <div class="notice-panel-subbar">
          <span class="notice-unread-indicator">
            ${unreadCount} unread ${unreadCount === 1 ? 'notice' : 'notices'}
          </span>
          <button class="notice-mark-all-btn" id="mark-all-notices-read">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
            Mark all read
          </button>
        </div>`;
    }

    let unreadHtml = '';
    if (unreadItems.length > 0) {
      unreadHtml = `<div class="unread-notices-list">${unreadItems.map(renderCard).join('')}</div>`;
    } else if (items.length > 0) {
      unreadHtml = `
        <div class="notices-caught-up">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
          <span>All caught up! No unread notices.</span>
        </div>`;
    }

    let readHtml = '';
    if (readItems.length > 0) {
      const isExpanded = !!window._readNoticesExpanded;
      readHtml = `
        <div class="read-notices-section">
          <button class="read-notices-toggle ${isExpanded ? 'expanded' : ''}" id="toggle-read-notices" aria-expanded="${isExpanded}">
            <div class="read-notices-toggle-left">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
              <span>Read Messages (${readItems.length})</span>
            </div>
            <div class="read-notices-toggle-right">
              <span class="read-toggle-hint">${isExpanded ? 'Hide' : 'View'}</span>
              <svg class="read-notices-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
            </div>
          </button>
          <div class="read-notices-list ${isExpanded ? 'open' : ''}" id="read-notices-list">
            ${readItems.map(renderCard).join('')}
          </div>
        </div>`;
    }

    pane.innerHTML = subbarHtml + unreadHtml + readHtml;

    // Attach listener for toggle read notices
    const toggleReadBtn = document.getElementById('toggle-read-notices');
    if (toggleReadBtn) {
      toggleReadBtn.addEventListener('click', (e) => {
        e.preventDefault();
        window._readNoticesExpanded = !window._readNoticesExpanded;
        const readList = document.getElementById('read-notices-list');
        const hint = toggleReadBtn.querySelector('.read-toggle-hint');
        if (window._readNoticesExpanded) {
          toggleReadBtn.classList.add('expanded');
          toggleReadBtn.setAttribute('aria-expanded', 'true');
          if (readList) readList.classList.add('open');
          if (hint) hint.textContent = 'Hide';
        } else {
          toggleReadBtn.classList.remove('expanded');
          toggleReadBtn.setAttribute('aria-expanded', 'false');
          if (readList) readList.classList.remove('open');
          if (hint) hint.textContent = 'View';
        }
      });
    }

    // Attach listener for mark all as read
    const markAllBtn = document.getElementById('mark-all-notices-read');
    if (markAllBtn) {
      markAllBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        markAllBtn.disabled = true;
        markAllBtn.innerHTML = '<span>Marking...</span>';
        currentNotifications.forEach(n => { n.is_read = true; });
        window._cachedNotifications = { notifications: currentNotifications, unread_count: 0 };
        renderAnnouncements(window._cachedNotifications);
        await api('/api/notifications/mark-all-read', { method: 'POST' });
      });
    }

    // Attach listeners for individual mark read/unread buttons
    pane.querySelectorAll('.notice-read-toggle').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = parseInt(btn.dataset.id, 10);
        const action = btn.dataset.action; // 'read' or 'unread'
        const isNowRead = (action === 'read');

        const target = currentNotifications.find(n => n.id === id);
        if (target) {
          target.is_read = isNowRead;
        }

        const newUnread = currentNotifications.filter(n => !n.is_read).length;
        window._cachedNotifications = { notifications: currentNotifications, unread_count: newUnread };
        renderAnnouncements(window._cachedNotifications);

        await api(`/api/notifications/${id}/${action}`, { method: 'POST' });
      });
    });
  }

  async function loadAnnouncements() {
    if (loaded && window._cachedNotifications) {
      renderAnnouncements(window._cachedNotifications);
      return;
    }
    loaded = true;
    if (pane) {
      pane.innerHTML = `<div style="padding:24px;text-align:center;color:var(--text-secondary);font-size:13px;">Loading notices…</div>`;
    }
    const data = await api('/api/notifications');
    window._cachedNotifications = data || { notifications: [], unread_count: 0 };
    renderAnnouncements(window._cachedNotifications);
  }

  // Pre-fetch on page load so badge shows without opening the panel
  api('/api/notifications').then(data => {
    if (data) {
      window._cachedNotifications = data;
      const items = Array.isArray(data) ? data : (data.notifications || []);
      const unreadCount = (typeof data.unread_count === 'number')
        ? data.unread_count
        : items.filter(a => !a.is_read).length;
      updateBadge(unreadCount);
    }
  });

  function openPanel() {
    panel.classList.add('open');
    overlay.classList.add('open');
    overlay.setAttribute('aria-hidden', 'false');
    openBtn.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
    if (window._cachedNotifications) {
      renderAnnouncements(window._cachedNotifications);
      loaded = true;
    } else {
      loadAnnouncements();
    }
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
