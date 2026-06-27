/**
 * nav.js — Client-side navigation for padikkunnundo.app
 *
 * Intercepts sidebar link clicks, fetches the page via AJAX,
 * swaps only the #main-content area (sidebar stays intact in the DOM),
 * and re-executes page-specific scripts so every page works correctly.
 *
 * The sidebar is never destroyed, so no flicker on desktop.
 */

(function () {
  'use strict';

  var sidebar = document.querySelector('.sidebar');
  if (!sidebar) return; // not on a page with sidebar

  var navContainer = sidebar.querySelector('.sidebar-nav');
  if (!navContainer) return;

  var isPopState = false;

  // Set initial active nav item based on current URL (replaces server-side active_page logic)
  setActiveNav(window.location.href);

  /* ── Intercept sidebar link clicks ──────────────────────────────────── */
  navContainer.addEventListener('click', function (e) {
    var link = e.target.closest('a');
    if (!link) return;

    // Skip external, anchor-only, and marked links
    if (link.getAttribute('target') === '_blank') return;
    if (link.getAttribute('href') === '#') return;
    if (link.getAttribute('data-turbo') === 'false') return;
    if (link.hostname !== window.location.hostname) return;

    // Same-page — just prevent default, no navigation
    if (link.href === window.location.href) {
      e.preventDefault();
      return;
    }

    e.preventDefault();
    navigateTo(link.href);
  });

  /* ── Core navigation ────────────────────────────────────────────────── */
  async function navigateTo(url) {
    // Immediately update active nav item (instant visual feedback)
    setActiveNav(url);

    try {
      var res = await fetch(url, { credentials: 'same-origin' });

      // 401 — session expired, do a real redirect so login page renders
      if (res.status === 401) {
        window.location.href = '/login';
        return;
      }

      if (!res.ok) throw new Error('HTTP ' + res.status);

      var html = await res.text();
      var doc = new DOMParser().parseFromString(html, 'text/html');

      // Update page title
      var newTitle = doc.querySelector('title');
      if (newTitle) document.title = newTitle.textContent;

      // Extract and swap main content
      var newContent = doc.getElementById('main-content');
      var currentContent = document.getElementById('main-content');

      if (!newContent || !currentContent) {
        // Fallback — full page load
        window.location.href = url;
        return;
      }

      currentContent.innerHTML = newContent.innerHTML;

      // Re-execute <script> tags inside the new content.
      // Scripts inserted via innerHTML do not run automatically,
      // so we create fresh <script> elements for each one.
      // External scripts (src=) must be appended to the document —
      // setting textContent on a src-bearing script does nothing.
// Re-execute page-specific scripts from the fetched document.
      // Search the entire fetched doc (not just #main-content) because
      // {% block scripts %} now lives outside #main-content in base.html.
      // Skip app.js and nav.js — they are already loaded globally.
      doc.querySelectorAll('script[src]').forEach(function (oldScript) {
        if (oldScript.src.includes('app.js') || oldScript.src.includes('nav.js')) return;
        var newScript = document.createElement('script');
        for (var i = 0; i < oldScript.attributes.length; i++) {
          var attr = oldScript.attributes[i];
          newScript.setAttribute(attr.name, attr.value);
        }
        document.body.appendChild(newScript);
      });
      // Update the address bar
      if (!isPopState) {
        window.history.pushState({}, '', url);
      }

      // Scroll to top
      window.scrollTo({ top: 0, behavior: 'auto' });

    } catch (err) {
      console.error('Client nav failed, falling back to full load:', err);
      window.location.href = url;
    } finally {
      isPopState = false;
    }
  }

  /* ── Active nav item ─────────────────────────────────────────────────── */
  function setActiveNav(url) {
    var items = navContainer.querySelectorAll('.sidebar-nav-item');
    for (var i = 0; i < items.length; i++) {
      items[i].classList.toggle('active', items[i].href === url);
    }
  }

  /* ── Handle browser back / forward ───────────────────────────────────── */
  window.addEventListener('popstate', function () {
    isPopState = true;
    navigateTo(window.location.href);
  });

})();
