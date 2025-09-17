/*! -----------------------------------------------------------------------------------

    Template Name: Riho Admin
    Template URI: https://admin.pixelstrap.net/riho/template/
    Description: This is Admin theme
    Author: Pixelstrap
    Author URI: https://themeforest.net/user/pixelstrap

-----------------------------------------------------------------------------------

        01. password show hide
        02. Background Image js
        03. sidebar filter
        04. Language js
        05. Translate js

 --------------------------------------------------------------------------------- */

(function ($) {
  "use strict";
  $(document).on("click", function (e) {
    var outside_space = $(".outside");
    if (
      !outside_space.is(e.target) &&
      outside_space.has(e.target).length === 0
    ) {
      $(".menu-to-be-close").removeClass("d-block");
      $(".menu-to-be-close").css("display", "none");
    }
  });

  $(".prooduct-details-box .close").on("click", function (e) {
    var tets = $(this).parent().parent().parent().parent().addClass("d-none");
    console.log(tets);
  });

  if ($(".page-wrapper").hasClass("horizontal-wrapper")) {
    $(".sidebar-list").hover(
      function () {
        $(this).addClass("hoverd");
      },
      function () {
        $(this).removeClass("hoverd");
      }
    );
    $(window).on("scroll", function () {
      if ($(this).scrollTop() < 600) {
        $(".sidebar-list").removeClass("hoverd");
      }
    });
  }

  /*----------------------------------------
     password show hide
     ----------------------------------------*/
  $(".show-hide").show();
  $(".show-hide span").addClass("show");

  $(".show-hide span").click(function () {
    if ($(this).hasClass("show")) {
      $('input[name="login[password]"]').attr("type", "text");
      $(this).removeClass("show");
    } else {
      $('input[name="login[password]"]').attr("type", "password");
      $(this).addClass("show");
    }
  });
  $('form button[type="submit"]').on("click", function () {
    $(".show-hide span").addClass("show");
    $(".show-hide")
      .parent()
      .find('input[name="login[password]"]')
      .attr("type", "password");
  });

  /*=====================
      02. Background Image js
      ==========================*/
  $(".bg-center").parent().addClass("b-center");
  $(".bg-img-cover").parent().addClass("bg-size");
  $(".bg-img-cover").each(function () {
    var el = $(this),
      src = el.attr("src"),
      parent = el.parent();
    parent.css({
      "background-image": "url(" + src + ")",
      "background-size": "cover",
      "background-position": "center",
      display: "block",
    });
    el.hide();
  });

  $(".mega-menu-container").css("display", "none");
  $(".header-search").click(function () {
    $(".search-full").addClass("open");
  });
  $(".close-search").click(function () {
    $(".search-full").removeClass("open");
    $("body").removeClass("offcanvas");
  });
  $(".mobile-toggle").click(function () {
    $(".nav-menus").toggleClass("open");
  });
  $(".mobile-toggle-left").click(function () {
    $(".left-header").toggleClass("open");
  });
  $(".bookmark-search").click(function () {
    $(".form-control-search").toggleClass("open");
  });
  $(".filter-toggle").click(function () {
    $(".product-sidebar").toggleClass("open");
  });
  $(".toggle-data").click(function () {
    $(".product-wrapper").toggleClass("sidebaron");
  });
  $(".form-control-search input").keyup(function (e) {
    if (e.target.value) {
      $(".page-wrapper").addClass("offcanvas-bookmark");
    } else {
      $(".page-wrapper").removeClass("offcanvas-bookmark");
    }
  });
  $(".search-full input").keyup(function (e) {
    console.log(e.target.value);
    if (e.target.value) {
      $("body").addClass("offcanvas");
    } else {
      $("body").removeClass("offcanvas");
    }
  });

  $("body").keydown(function (e) {
    if (e.keyCode == 27) {
      $(".search-full input").val("");
      $(".form-control-search input").val("");
      $(".page-wrapper").removeClass("offcanvas-bookmark");
      $(".search-full").removeClass("open");
      $(".search-form .form-control-search").removeClass("open");
      $("body").removeClass("offcanvas");
    }
  });
  $(".mode").on("click", function () {
    const bodyModeDark = $("body").hasClass("dark-only");

    if (!bodyModeDark) {
      $(".mode").addClass("active");
      localStorage.setItem("mode", "dark-only");
      $("body").addClass("dark-only");
      $("body").removeClass("light");
    }
    if (bodyModeDark) {
      $(".mode").removeClass("active");
      localStorage.setItem("mode", "light");
      $("body").removeClass("dark-only");
      $("body").addClass("light");
    }
  }); 
  $(".mode").addClass(
    localStorage.getItem("mode") === "dark-only" ? "active" : " "
  );

  // sidebar filter
  $(".md-sidebar .md-sidebar-toggle ").on("click", function (e) {
    $(".md-sidebar .md-sidebar-aside ").toggleClass("open");
  });

  $(".loader-wrapper").fadeOut("slow", function () {
    $(this).remove();
  });

  $(window).on("scroll", function () {
    if ($(this).scrollTop() > 600) {
      $(".tap-top").fadeIn();
    } else {
      $(".tap-top").fadeOut();
    }
  });

  $(".tap-top").click(function () {
    $("html, body").animate(
      {
        scrollTop: 0,
      },
      600
    );
    return false;
  });
  (function ($, window, document, undefined) {
    "use strict";
    var $ripple = $(".js-ripple");
    $ripple.on("click.ui.ripple", function (e) {
      var $this = $(this);
      var $offset = $this.parent().offset();
      var $circle = $this.find(".c-ripple__circle");
      var x = e.pageX - $offset.left;
      var y = e.pageY - $offset.top;
      $circle.css({ top: y + "px", left: x + "px" });
      $this.addClass("is-active");
    });
    $ripple.on(
      "animationend webkitAnimationEnd oanimationend MSAnimationEnd",
      function (e) {
        $(this).removeClass("is-active");
      }
    );
  })(jQuery, window, document);

  // ----- Custom App Enhancements (notifications + global search) -----
  function renderNotifications(data){
    try{
      // Update the main notification badge
      var badge = document.querySelector('.notification-box .badge');
      if(!badge){
        var container = document.querySelector('.notification-box');
        if(container){
          badge = document.createElement('span');
          badge.className = 'badge rounded-pill badge-secondary';
          badge.style.display = 'none';
          badge.textContent = '0';
          container.appendChild(badge);
        }
      }
      if(badge) { 
        const total = (data.counts && (data.counts.today_visitors + data.counts.low_stock + data.counts.overdue_orders)) || 0;
        if (total > 0) {
          badge.textContent = total;
          badge.style.display = 'inline-block';
        } else {
          badge.style.display = 'none';
        }
      }
      
      // Update the individual notification badges in the dropdown
      const todayBadge = document.querySelector('.notification-dropdown .list-group-item:nth-child(1) .badge');
      const lowStockBadge = document.querySelector('.notification-dropdown .list-group-item:nth-child(2) .badge');
      const overdueBadge = document.querySelector('.notification-dropdown .list-group-item:nth-child(3) .badge');
      
      if (todayBadge && data.counts) {
        todayBadge.textContent = data.counts.today_visitors || 0;
        todayBadge.style.display = data.counts.today_visitors > 0 ? 'inline-flex' : 'none';
      }
      if (lowStockBadge && data.counts) {
        lowStockBadge.textContent = data.counts.low_stock || 0;
        lowStockBadge.style.display = data.counts.low_stock > 0 ? 'inline-flex' : 'none';
      }
      if (overdueBadge && data.counts) {
        overdueBadge.textContent = data.counts.overdue_orders || 0;
        overdueBadge.style.display = data.counts.overdue_orders > 0 ? 'inline-flex' : 'none';
      }

      // Update the notification dropdown content
      var bar = document.querySelector('.notification-dropdown .notitications-bar');
      if(!bar) return;
      
      function fmtTime(iso){ try{ var d=new Date(iso); return d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});}catch(e){return ''} }
      function minutesToPretty(m){ if(m==null) return ''; if(m<60) return m+"m"; var h=Math.floor(m/60); var r=m%60; return h+"h"+(r?" "+r+"m":""); }
      
      var t = (data.items && data.items.today_visitors) || [], 
          l = (data.items && data.items.low_stock) || [], 
          o = (data.items && data.items.overdue_orders) || [];
          
      function custUrl(id){ return ("/customers/"+id+"/"); }
      function orderUrl(id){ return ("/orders/"+id+"/"); }
      
      var html = ''+
        '<div class="mb-2 d-flex justify-content-between"><span class="f-w-600">Today\'s Visitors</span><span class="badge bg-primary">'+ ((data.counts && data.counts.today_visitors)||0) +'</span></div>'+
        '<ul class="list-unstyled mb-3">'+ (t.length > 0 ? t.map(function(x){ return '<li class="mb-1"><a class="f-light f-w-500" href="'+ custUrl(x.id) +'">'+ x.name +'</a> <span class="f-12 text-muted">'+ fmtTime(x.time) +'</span></li>'; }).join('') : '<li class="text-muted f-12">No recent visitors</li>') +'</ul>'+
        '<div class="mb-2 d-flex justify-content-between"><span class="f-w-600">Low Stock</span><span class="badge bg-warning text-dark">'+ ((data.counts && data.counts.low_stock)||0) +'</span></div>'+
        '<ul class="list-unstyled mb-3">'+ (l.length > 0 ? l.map(function(x){ return '<li class="mb-1"><span class="f-light f-w-500">'+ x.name +' ('+ (x.brand||'Unbranded') +')</span> <span class="badge bg-light text-dark">'+ x.quantity +'</span></li>'; }).join('') : '<li class="text-muted f-12">No low stock items</li>') +'</ul>'+
        '<div class="mb-2 d-flex justify-content-between"><span class="f-w-600">Overdue Orders</span><span class="badge bg-danger">'+ ((data.counts && data.counts.overdue_orders)||0) +'</span></div>'+
        '<ul class="list-unstyled mb-0">'+ (o.length > 0 ? o.map(function(x){ return '<li class="mb-1"><a class="f-light f-w-500" href="'+ orderUrl(x.id) +'">'+ x.order_number +'</a> <span class="f-12 text-muted">'+ x.customer +' • '+ x.status.replace('_',' ') +' • '+ minutesToPretty(x.age_minutes) +'</span></li>'; }).join('') : '<li class="text-muted f-12">No overdue orders</li>') +'</ul>';
      bar.innerHTML = html;
    }catch(e){}
  }
  function loadNotifications(){
    console.log('Loading notifications...');
    fetch('/api/notifications/summary/')
      .then(function(response) {
        if (!response.ok) {
          throw new Error('Network response was not ok: ' + response.status);
        }
        return response.json();
      })
      .then(function(data) { 
        console.log('Received notification data:', data);
        if (data && data.success) { 
          renderNotifications(data); 
        } else {
          console.error('Invalid notification data format:', data);
        }
      })
      .catch(function(error) {
        console.error('Error loading notifications:', error);
        // Show error in UI
        const badge = document.querySelector('.notification-box .badge');
        if (badge) {
          badge.textContent = '!';
          badge.style.display = 'inline-block';
          badge.style.backgroundColor = '#dc3545';
        }
      });
  }
  document.addEventListener('DOMContentLoaded', function(){
    loadNotifications();
    setInterval(loadNotifications, 60000);
  });

  // Global header search (customers)
  (function(){
    var timer=null; var box=null; var inputDesktop=document.querySelector('.nav-menus .search-form input[type=search]'); var inputMobile=document.querySelector('#searchInput input[type=search]');
    function ensureBox(){ if(box) return box; box=document.createElement('div'); box.id='global-search-results'; box.style.position='absolute'; box.style.top='56px'; box.style.right='16px'; box.style.zIndex='1050'; box.style.minWidth='280px'; box.className='card shadow'; document.body.appendChild(box); return box; }
    function hideBox(){ if(box){ box.style.display='none'; }}
    function showResults(items){ var el=ensureBox(); var html='<div class="card-body p-0"><div class="list-group list-group-flush">';
      if(!items.length){ html += '<div class="list-group-item text-muted">No results</div>'; }
      items.forEach(function(c){ html += '<a class="list-group-item list-group-item-action d-flex justify-content-between align-items-center" href="/customers/'+ c.id +'/">'+
        '<span>'+ (c.name||'') +' <small class="text-muted">'+ (c.code||'') +'</small></span>'+
        '<small class="badge bg-light text-dark text-capitalize">'+ (c.type||'personal') +'</small>'+
      '</a>'; });
      html += '</div></div>'; el.innerHTML = html; el.style.display='block'; }
    function goSearch(q){ if(!q || q.length<2){ hideBox(); return; }
      fetch('/customers/search/?q='+encodeURIComponent(q)).then(function(r){return r.json()}).then(function(j){ showResults((j && j.results)||[]); }).catch(function(){ hideBox(); });
    }
    function onInput(ev){ var q=ev.target.value.trim(); clearTimeout(timer); timer=setTimeout(function(){ goSearch(q); }, 250); }
    if(inputDesktop){ inputDesktop.addEventListener('input', onInput); inputDesktop.setAttribute('placeholder','Search customers by name, phone, email, code'); }
    if(inputMobile){ inputMobile.addEventListener('input', onInput); inputMobile.setAttribute('placeholder','Search customers'); }
    document.addEventListener('click', function(e){ if(box && !box.contains(e.target) && (!inputDesktop || e.target!==inputDesktop)){ hideBox(); }});
  })();

  // Centered Action Popup
  function ensureActionPopup(){
    var overlay = document.getElementById('actionPopup');
    if(overlay) return overlay;
    overlay = document.createElement('div');
    overlay.className='action-popup-overlay'; overlay.id='actionPopup'; overlay.setAttribute('role','dialog'); overlay.setAttribute('aria-live','polite'); overlay.setAttribute('aria-atomic','true');
    overlay.innerHTML = '<div class="action-popup-card action-popup-enter">\
      <div class="action-popup-icon" id="actionPopupIcon"></div>\
      <div class="action-popup-title" id="actionPopupTitle"></div>\
      <p class="action-popup-message" id="actionPopupMessage"></p>\
    </div>';
    document.body.appendChild(overlay);
    return overlay;
  }
  function showActionPopup(type, title, message){
    try{
      var overlay=ensureActionPopup();
      var icon=overlay.querySelector('#actionPopupIcon');
      var ttl=overlay.querySelector('#actionPopupTitle');
      var msg=overlay.querySelector('#actionPopupMessage');
      icon.className='action-popup-icon '+(type==='success'?'success':'error');
      icon.innerHTML = type==='success' ? '<i class="fa fa-check"></i>' : '<i class="fa fa-times"></i>';
      ttl.textContent = title || (type==='success' ? 'Success' : 'Something went wrong');
      msg.textContent = message || '';
      overlay.style.display='flex';
      clearTimeout(window.__actionPopupTimer);
      window.__actionPopupTimer=setTimeout(function(){ overlay.style.display='none'; }, 2600);
      overlay.onclick=function(e){ if(e.target===overlay){ overlay.style.display='none'; }}
    }catch(e){}
  }
  window.flash = function(level, message){
    var t = (level||'').indexOf('success')>-1 ? 'success' : 'error';
    showActionPopup(t, t==='success'?'Success':'Failed', message||'');
  };
  document.addEventListener('DOMContentLoaded', function(){
    // Upgrade any bootstrap alert messages to popup
    var alerts = document.querySelectorAll('.alert');
    if(alerts && alerts.length){
      var last = alerts[alerts.length-1];
      var isSuccess = last.className.indexOf('alert-success')>-1;
      var isDanger = last.className.indexOf('alert-danger')>-1 || last.className.indexOf('alert-error')>-1;
      var type = isSuccess ? 'success' : (isDanger ? 'error' : 'success');
      var msg = last.textContent.trim();
      showActionPopup(type, isSuccess?'Success':'Notice', msg);
    }
  });

})(jQuery);
