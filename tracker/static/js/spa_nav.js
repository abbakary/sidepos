document.addEventListener('DOMContentLoaded', function() {
  const sidebarSelector = '.sidebar-wrapper';
  const contentSelector = '.page-body';

  function isInternalLink(link) {
    try {
      const url = new URL(link, window.location.origin);
      return url.origin === window.location.origin;
    } catch (e) { return false; }
  }

  function findMainContent(doc) {
    return doc.querySelector(contentSelector) || doc.querySelector('main') || doc.body;
  }

  async function fetchAndReplace(url, push=true) {
    try {
      const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      if (!res.ok) { window.location.href = url; return; }
      const html = await res.text();
      const doc = new DOMParser().parseFromString(html, 'text/html');
      const newContent = findMainContent(doc);
      const currentContent = document.querySelector(contentSelector) || document.querySelector('main') || document.body;
      if (newContent && currentContent) {
        currentContent.innerHTML = newContent.innerHTML;
        // Execute scripts in replaced content
        const scripts = currentContent.querySelectorAll('script');
        scripts.forEach(oldScript => {
          const s = document.createElement('script');
          if (oldScript.src) s.src = oldScript.src;
          else s.text = oldScript.textContent;
          if (oldScript.type) s.type = oldScript.type;
          document.body.appendChild(s);
          if (!oldScript.src) setTimeout(() => s.remove(), 0);
        });
      }

      // Update document title
      const newTitle = doc.querySelector('title');
      if (newTitle) document.title = newTitle.textContent;

      if (push) history.pushState({ url: url }, '', url);

      // Update active sidebar link(s)
      updateActiveSidebar(url);

    } catch (e) {
      console.error('SPA navigation error', e);
      window.location.href = url;
    }
  }

  function updateActiveSidebar(url) {
    const u = new URL(url, window.location.origin);
    // remove existing active
    document.querySelectorAll('.sidebar-links li.active').forEach(li => li.classList.remove('active'));
    // find matching link
    const links = document.querySelectorAll(sidebarSelector + ' a');
    let matched = null;
    links.forEach(a => {
      try {
        const href = a.getAttribute('href');
        if (!href) return;
        const linkUrl = new URL(href, window.location.origin);
        if (linkUrl.pathname === u.pathname) matched = a;
      } catch (e) {}
    });
    if (matched) {
      const li = matched.closest('li');
      if (li) li.classList.add('active');
      // ensure only one deep active for submenu
      const parentLi = matched.closest('.sidebar-submenu');
      if (parentLi) {
        const parent = parentLi.closest('li');
        if (parent) parent.classList.add('active');
      }
    }
  }

  // Intercept sidebar clicks
  function bindSidebarLinks() {
    document.querySelectorAll(sidebarSelector + ' a').forEach(a => {
      if (!isInternalLink(a.getAttribute('href'))) return;
      a.addEventListener('click', function(e) {
        // allow anchors and JS handlers (href starting with '#')
        const href = a.getAttribute('href');
        if (!href || href.startsWith('#')) return;
        e.preventDefault();
        // If link would navigate to same page, no-op
        const url = new URL(href, window.location.origin);
        if (url.pathname === window.location.pathname) return;
        fetchAndReplace(url.href, true);
      });
    });
  }

  // handle back/forward
  window.addEventListener('popstate', function(e) {
    const url = (e.state && e.state.url) ? e.state.url : window.location.href;
    fetchAndReplace(url, false);
  });

  // expose for manual rebind after ajax swaps
  window.__spaNav = { bindSidebarLinks, fetchAndReplace, updateActiveSidebar };

  // initial bind
  bindSidebarLinks();
  // set active on load
  updateActiveSidebar(window.location.href);

});
