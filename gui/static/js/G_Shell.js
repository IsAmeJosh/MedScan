// Notification panel: opens from the sidebar, marks everything as read when opened.
(function () {
  var drawer = document.getElementById('notifications-drawer');
  var backdrop = document.getElementById('drawer-backdrop');
  var openBtn = document.getElementById('open-notifications');
  var closeBtn = document.getElementById('close-notifications');
  var badge = document.getElementById('unread-badge');
  if (!drawer || !openBtn) { return; }

  function markRead() {
    var token = document.querySelector('#csrf-holder input[name=csrfmiddlewaretoken]');
    if (!token || !badge || badge.dataset.count === '0') { return; }
    fetch(drawer.dataset.readUrl, {
      method: 'POST',
      headers: { 'X-CSRFToken': token.value },
      credentials: 'same-origin'
    }).then(function (response) {
      if (response.ok) {
        badge.hidden = true;
        badge.dataset.count = '0';
      }
    });
  }

  function openPanel() {
    drawer.classList.add('open');
    backdrop.classList.add('show');
    drawer.setAttribute('aria-hidden', 'false');
    markRead();
  }

  function closePanel() {
    drawer.classList.remove('open');
    backdrop.classList.remove('show');
    drawer.setAttribute('aria-hidden', 'true');
    drawer.querySelectorAll('.unread').forEach(function (item) {
      item.classList.remove('unread');
    });
  }

  openBtn.addEventListener('click', openPanel);
  closeBtn.addEventListener('click', closePanel);
  backdrop.addEventListener('click', closePanel);
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') { closePanel(); }
  });
})();
