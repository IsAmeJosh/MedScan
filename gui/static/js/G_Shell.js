// The bell and the notification panel.
// - The page asks the server every few seconds whether anything is new, and updates the bell, the counts in
//   the sidebar and the panel. It never reloads the page, so nothing you are typing is lost.
// - "Mark all as read" clears the unread marks. A notification is only a pointer: clicking it opens the page it is about
//   (the Approve and Deny buttons live on Home and Access, not here).
(function () {
  var drawer = document.getElementById('notifications-drawer');
  var backdrop = document.getElementById('drawer-backdrop');
  var openBtn = document.getElementById('open-notifications');
  var closeBtn = document.getElementById('close-notifications');
  var markAll = document.getElementById('mark-all-read');
  var badge = document.getElementById('unread-badge');
  var newPill = document.getElementById('new-count');
  var list = document.getElementById('notification-list');
  if (!drawer || !openBtn) { return; }

  var lastUnread = parseInt(badge ? badge.getAttribute('data-count') : '0', 10) || 0;

  function openPanel() {
    drawer.classList.add('open');
    backdrop.classList.add('show');
    drawer.setAttribute('aria-hidden', 'false');
  }

  function closePanel() {
    drawer.classList.remove('open');
    backdrop.classList.remove('show');
    drawer.setAttribute('aria-hidden', 'true');
  }

  // ---- showing a count in the bell, the panel header and the sidebar ----
  function showUnread(count) {
    if (badge) {
      badge.innerHTML = count;
      badge.setAttribute('data-count', String(count));
      badge.hidden = count === 0;
    }
    if (newPill) { newPill.innerHTML = count + ' new'; newPill.hidden = count === 0; }
    if (markAll) { markAll.hidden = count === 0; }
    lastUnread = count;
  }

  function showSidebarCount(id, count) {
    if (typeof count !== 'number') { return; }
    var shown = [document.getElementById(id)];
    var mirrors = document.querySelectorAll('[data-mirror="' + id + '"]');    // the same count on the phone tabs
    for (var i = 0; i < mirrors.length; i++) { shown.push(mirrors[i]); }
    for (var j = 0; j < shown.length; j++) {
      if (shown[j]) {
        shown[j].innerHTML = count;
        shown[j].hidden = count === 0;
      }
    }
  }

  function toast(text) {
    var box = document.querySelector('.toasts');
    if (!box) { return; }
    var item = document.createElement('div');
    item.className = 'toast success';
    item.setAttribute('role', 'status');
    var message = document.createElement('span');
    message.appendChild(document.createTextNode(text));
    var close = document.createElement('button');
    close.type = 'button';
    close.className = 'toast-x';
    close.setAttribute('aria-label', 'Dismiss');
    close.innerHTML = '&times;';
    close.addEventListener('click', function () { box.removeChild(item); });
    item.appendChild(message);
    item.appendChild(close);
    box.appendChild(item);
  }

  // ---- asking the server what is new ----
  var pollUrl = drawer.getAttribute('data-poll-url');
  var pollMs = (parseInt(drawer.getAttribute('data-poll-seconds'), 10) || 10) * 1000;
  var timer = null;

  function apply(data) {
    if (list && typeof data.html === 'string') { list.innerHTML = data.html; }
    if (data.unread > lastUnread) {
      var more = data.unread - lastUnread;
      toast(more === 1 && data.latest ? data.latest : more + ' new notifications');
    }
    showUnread(data.unread);
    showSidebarCount('count-waiting', data.waiting);
    showSidebarCount('count-ready', data.ready);
  }

  function schedule() {
    if (timer) { window.clearTimeout(timer); }
    timer = window.setTimeout(poll, pollMs);
  }

  function poll() {
    if (document.hidden) { schedule(); return; }          // The tab is hidden, so nobody is looking: wait and try again later.
    window.fetch(pollUrl, { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
      .then(function (response) {
        if (response.status === 403) { return null; }     // The session has ended (403): stop asking.
        return response.json();
      })
      .then(function (data) {
        if (!data) { return; }
        apply(data);
        schedule();
      })
      .then(null, schedule);                              // a network hiccup: try again later
  }

  if (pollUrl && window.fetch) {
    schedule();
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) { poll(); }                   // coming back to the tab: catch up now
    });
  }

  // ---- mark all read ----
  if (markAll) {
    markAll.addEventListener('click', function () {
      var token = document.querySelector('#csrf-holder input[name=csrfmiddlewaretoken]');
      if (!token) { return; }
      window.fetch(drawer.getAttribute('data-read-url'), {
        method: 'POST',
        headers: { 'X-CSRFToken': token.value },
        credentials: 'same-origin'
      }).then(function (response) {
        if (!response.ok) { return; }
        var unread = drawer.querySelectorAll('.unread');
        for (var i = 0; i < unread.length; i++) { unread[i].classList.remove('unread'); }
        var dots = drawer.querySelectorAll('.udot');
        for (var d = dots.length - 1; d >= 0; d--) { dots[d].parentNode.removeChild(dots[d]); }
        showUnread(0);
      });
    });
  }

  openBtn.addEventListener('click', openPanel);
  closeBtn.addEventListener('click', closePanel);
  backdrop.addEventListener('click', closePanel);
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') { closePanel(); }
  });
})();
