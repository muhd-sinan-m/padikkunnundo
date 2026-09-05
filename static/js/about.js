/**
 * about.js — Interactive developer profile modal
 */

(function () {
  'use strict';

  const developers = {
    sinan: {
      number: "01 / Lead Developer",
      nameHtml: 'Muhammed <span class="premium-name-accent premium-name-accent-blue">Sinan</span>',
      batch: "BCA - A &nbsp;(2024 - 28)",
      role: "Platform Architect & Backend",
      theme: "theme-blue",
      initials: "MS",
      image: "/static/img/sinan.webp",
      linkedin: "https://www.linkedin.com/in/muhammed-sinan-m/",
      sites: [
        { name: "Padikkunnundo", desc: "Main academic platform & student companion" },
        { name: "PYQPortal", desc: "Previous year question paper repository & archive" },
        { name: "DoubtUndo", desc: "AI-powered academic doubt assistance engine" }
      ]
    },
    akshara: {
      number: "02 / Developer",
      nameHtml: 'Akshara <span class="premium-name-accent premium-name-accent-cyan">Suresh</span>',
      batch: "BCA - A &nbsp;(2024 - 28)",
      role: "ML Analytics & Performance",
      theme: "theme-cyan",
      initials: "AS",
      image: "/static/img/akshara.webp",
      linkedin: "https://www.linkedin.com/in/akshara-suresh-40112b325/",
      sites: [
        { name: "Markkundo", desc: "Machine learning mark analytics & prediction portal" }
      ]
    },
    daniel: {
      number: "03 / Developer",
      nameHtml: 'Daniel <span class="premium-name-accent premium-name-accent-orange">George</span>',
      batch: "BCA - A &nbsp;(2024 - 28)",
      role: "Interactive Lab Coding",
      theme: "theme-orange",
      initials: "DG",
      image: "/static/img/daniel.webp",
      linkedin: "https://www.linkedin.com/in/daniel-george-vm/",
      sites: [
        { name: "Codeariyoo", desc: "Interactive programming playground & lab simulator" }
      ]
    },
    jerin: {
      number: "04 / Developer",
      nameHtml: 'Jerin <span class="premium-name-accent premium-name-accent-purple">Mathew</span>',
      batch: "BCA - A &nbsp;(2024 - 28)",
      role: "Quiz Practice Portals",
      theme: "theme-purple",
      initials: "JM",
      image: null,
      linkedin: "https://www.linkedin.com/in/jerinmathew2526/",
      sites: [
        { name: "MCQ Portal", desc: "Dynamic objective quiz engine & instant evaluations" }
      ]
    },
    sebastian: {
      number: "05 / Developer",
      nameHtml: 'Sebastian <span class="premium-name-accent premium-name-accent-pink">George</span>',
      batch: "BCA - A &nbsp;(2025 - 29)",
      role: "Resource Architecture",
      theme: "theme-pink",
      initials: "SG",
      image: "/static/img/sebastian.webp",
      linkedin: "https://www.linkedin.com/in/sebastian-george-p-g-9023b8373/",
      sites: [
        { name: "Passavam", desc: "Essential exam topics, syllabus resources & quick guides" }
      ]
    }
  };

  let activeDevKey = null;

  window.openDevImageLightbox = function (src, theme, name) {
    const lightbox = document.getElementById('dev-img-lightbox');
    const imgEl = document.getElementById('dev-img-lightbox-img');
    const frameEl = document.getElementById('dev-img-lightbox-frame');
    const captionEl = document.getElementById('dev-img-lightbox-caption');

    if (!lightbox || !src) return;

    if (imgEl) imgEl.src = src;
    if (frameEl) frameEl.className = 'dev-img-lightbox-frame ' + (theme || '');
    if (captionEl) captionEl.innerHTML = name || '';

    lightbox.classList.add('open');
    lightbox.setAttribute('aria-hidden', 'false');
  };

  window.closeDevImageLightbox = function () {
    const lightbox = document.getElementById('dev-img-lightbox');
    if (lightbox) {
      lightbox.classList.remove('open');
      lightbox.setAttribute('aria-hidden', 'true');
    }
  };

  window.openAboutDevModal = function (key) {
    const dev = developers[key];
    if (!dev) return;

    activeDevKey = key;
    const overlay = document.getElementById('dev-modal-overlay');
    const avatarWrap = document.getElementById('modal-dev-avatar-wrap');
    const numEl = document.getElementById('modal-dev-num');
    const nameEl = document.getElementById('modal-dev-name');
    const batchEl = document.getElementById('modal-dev-batch');
    const roleEl = document.getElementById('modal-dev-role');
    const sitesListEl = document.getElementById('modal-dev-sites');
    const linkedinEl = document.getElementById('modal-dev-linkedin');

    if (!overlay) return;

    if (avatarWrap) {
      if (dev.image) {
        avatarWrap.className = 'dev-modal-avatar-wrapper has-image ' + dev.theme;
        avatarWrap.innerHTML = `<img src="${dev.image}" alt="Developer" class="dev-modal-avatar-img" />`;
        avatarWrap.setAttribute('title', 'Tap to view full image');
      } else {
        avatarWrap.className = 'dev-modal-avatar-wrapper ' + dev.theme;
        avatarWrap.innerHTML = `<div class="dev-modal-avatar-fallback" id="modal-dev-initials">${dev.initials}</div>`;
        avatarWrap.removeAttribute('title');
      }
    }
    if (numEl) numEl.textContent = dev.number;
    if (nameEl) nameEl.innerHTML = dev.nameHtml;
    if (batchEl) batchEl.innerHTML = dev.batch;
    if (roleEl) roleEl.textContent = dev.role;
    if (linkedinEl) linkedinEl.href = dev.linkedin;

    if (sitesListEl) {
      sitesListEl.innerHTML = dev.sites.map(s => `
        <div class="dev-modal-site-card">
          <div class="dev-modal-site-meta">
            <div class="dev-modal-site-name">${s.name}</div>
            ${s.desc ? `<div class="dev-modal-site-desc">${s.desc}</div>` : ''}
          </div>
        </div>
      `).join('');
    }

    overlay.classList.add('open');
    overlay.setAttribute('aria-hidden', 'false');
  };

  window.closeAboutDevModal = function () {
    window.closeDevImageLightbox();
    const overlay = document.getElementById('dev-modal-overlay');
    if (overlay) {
      overlay.classList.remove('open');
      overlay.setAttribute('aria-hidden', 'true');
    }
  };

  // Global document click listener (event delegation) - works across all navigations
  if (!window._aboutDevModalListenerAttached) {
    window._aboutDevModalListenerAttached = true;

    document.addEventListener('click', function (e) {
      // 1. Check if clicked lightbox close button
      if (e.target.closest('#dev-img-lightbox-close') || e.target.closest('.dev-img-lightbox-close')) {
        e.preventDefault();
        window.closeDevImageLightbox();
        return;
      }

      // 2. Check if clicked lightbox overlay background
      const lightbox = document.getElementById('dev-img-lightbox');
      if (lightbox && e.target === lightbox) {
        e.preventDefault();
        window.closeDevImageLightbox();
        return;
      }

      // 3. Check if clicked avatar inside modal to open lightbox
      const avatarInModal = e.target.closest('#modal-dev-avatar-wrap.has-image');
      if (avatarInModal && activeDevKey) {
        const dev = developers[activeDevKey];
        if (dev && dev.image) {
          e.preventDefault();
          e.stopPropagation();
          const cleanName = dev.nameHtml ? dev.nameHtml.replace(/<[^>]*>?/gm, '') : '';
          window.openDevImageLightbox(dev.image, dev.theme, cleanName);
          return;
        }
      }

      // 4. Check if clicked a LinkedIn button inside card
      if (e.target.closest('.premium-linkedin-btn')) {
        return; // allow normal link click
      }

      // 5. Check if clicked a contributor card
      const card = e.target.closest('.contributor-card[data-dev]');
      if (card) {
        e.preventDefault();
        const key = card.getAttribute('data-dev');
        window.openAboutDevModal(key);
        return;
      }

      // 6. Check if clicked modal close button
      if (e.target.closest('#dev-modal-close') || e.target.closest('.dev-modal-close-btn')) {
        e.preventDefault();
        window.closeAboutDevModal();
        return;
      }

      // 7. Check if clicked modal overlay background
      const overlay = document.getElementById('dev-modal-overlay');
      if (overlay && e.target === overlay) {
        e.preventDefault();
        window.closeAboutDevModal();
        return;
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        const lightbox = document.getElementById('dev-img-lightbox');
        if (lightbox && lightbox.classList.contains('open')) {
          e.preventDefault();
          window.closeDevImageLightbox();
          return;
        }
        const overlay = document.getElementById('dev-modal-overlay');
        if (overlay && overlay.classList.contains('open')) {
          window.closeAboutDevModal();
        }
      }
      if ((e.key === 'Enter' || e.key === ' ') && !e.target.closest('a')) {
        const card = e.target.closest('.contributor-card[data-dev]');
        if (card) {
          e.preventDefault();
          const key = card.getAttribute('data-dev');
          window.openAboutDevModal(key);
        }
      }
    });
  }
})();
