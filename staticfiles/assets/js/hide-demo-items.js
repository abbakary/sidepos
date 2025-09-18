// Demo items removal helper (commented out by default)
// (original commented-out content preserved above)

// SPA nav loader: dynamically load SPA helper to keep sidebar persistent and set active state
(function(){
  try{
    var s = document.createElement('script');
    s.src = '/static/js/spa_nav.js';
    s.onload = function(){ if(window.__spaNav && typeof window.__spaNav.bindSidebarLinks === 'function') window.__spaNav.bindSidebarLinks(); };
    s.onerror = function(){ console.warn('Failed to load SPA nav helper'); };
    document.body.appendChild(s);
  }catch(e){ console.error(e); }
})();
