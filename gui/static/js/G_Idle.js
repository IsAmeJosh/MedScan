// Logs the user out after a stretch of no activity, with a warning a minute before.
// While the user is active it pings the server now and then, so a long consultation note
// can never be lost to a session that quietly expired while it was being typed.
(function () {
  var body = document.body;
  var minutes = parseInt(body.getAttribute('data-idle-minutes'), 10);
  var dialog = document.getElementById('idle-dialog');
  if (!minutes || !dialog) { return; }

  var LIMIT = minutes * 60000;
  var WARN_AT = Math.max(LIMIT - 60000, LIMIT / 2);   // a minute before the end (half-way if the limit is short)
  var PING_EVERY = Math.min(4 * 60000, LIMIT / 3);
  var lastActivity = new Date().getTime();
  var lastPing = lastActivity;
  var warning = false;

  function csrfToken() {
    var field = document.querySelector('#csrf-holder input[name=csrfmiddlewaretoken]');
    return field ? field.value : '';
  }

  function post(url) {
    return window.fetch(url, { method: 'POST', headers: { 'X-CSRFToken': csrfToken() }, credentials: 'same-origin' });
  }

  function ping() {
    lastPing = new Date().getTime();
    post(body.getAttribute('data-keepalive-url'));
  }

  function activity() {
    if (warning) { return; }   // once the warning shows, only its buttons count
    lastActivity = new Date().getTime();
    if (lastActivity - lastPing > PING_EVERY) { ping(); }
  }

  function logOut() {
    var go = function () { window.location = body.getAttribute('data-login-url') + '?expired=1'; };
    post(body.getAttribute('data-logout-url')).then(go, go);
  }

  function stay() {
    warning = false;
    lastActivity = new Date().getTime();
    ping();
    if (typeof dialog.close === 'function') { dialog.close(); }
  }

  function tick() {
    var idle = new Date().getTime() - lastActivity;
    if (idle >= LIMIT) { logOut(); return; }
    if (idle >= WARN_AT) {
      if (!warning) {
        warning = true;
        if (typeof dialog.showModal === 'function') { dialog.showModal(); }
      }
      document.getElementById('idle-seconds').innerHTML = Math.ceil((LIMIT - idle) / 1000);
    }
  }

  var events = ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart', 'click'];
  for (var i = 0; i < events.length; i++) { document.addEventListener(events[i], activity, true); }
  document.getElementById('idle-stay').addEventListener('click', stay);
  dialog.addEventListener('close', function () { if (warning) { stay(); } });   // Pressing Escape closes the dialog, and that counts as choosing to stay logged in.
  window.setInterval(tick, 1000);
})();
