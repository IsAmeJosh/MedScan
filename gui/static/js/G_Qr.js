// The "Show my QR code" sheet (patients). The code is a one-time secret that works for five minutes, so the sheet asks
// the server for it every time it opens and counts the time down.
// - When the time runs out the sheet shows the "expired" state (the code blurred, with a Make a new code button on it).
//   It does not renew by itself, so nobody is shown a dead code as if it were live.
// - "Make a new code" replaces the code at once (the old one stops working).
// - While the sheet is open it also asks every few seconds, so a code that was used by a doctor's scan is replaced.
(function () {
  var sheet = document.getElementById('qr-sheet');
  if (!sheet || !window.fetch) { return; }
  var picture = document.getElementById('qr-picture');
  var timerText = document.getElementById('qr-timer-text');
  var newButton = document.getElementById('qr-new');
  var title = document.getElementById('qr-title');
  var note = document.getElementById('qr-note');
  var normalTitle = title ? title.textContent : '';
  var normalNote = note ? note.textContent : '';
  var expired = false;      // true once the time ran out and nobody has asked for a new code yet
  var lastPicture = '';
  var codeUrl = sheet.getAttribute('data-code-url');
  var newUrl = sheet.getAttribute('data-new-url');
  var shownId = null;       // which code is on screen
  var left = 0;             // How many seconds the current code still works (counted down on screen).
  var ticker = null;
  var poller = null;
  var busy = false;         // true while a request is on its way, so two never overlap

  function two(number) { return number < 10 ? '0' + number : String(number); }

  function showTime() {
    timerText.innerHTML = left > 0 ? 'Works once &middot; ' + Math.floor(left / 60) + ':' + two(left % 60) + ' left' : 'Expired';
  }

  function show(data) {
    shownId = data.id;
    left = data.seconds;
    expired = false;
    lastPicture = data.svg;
    picture.innerHTML = data.svg;
    sheet.className = sheet.className.replace(/\s*\bexpired\b/g, '');
    if (title) { title.textContent = normalTitle; }
    if (note) { note.textContent = normalNote; }
    showTime();
  }

  // The time ran out: blur the old code and offer a new one.
  function expire() {
    expired = true;
    picture.innerHTML = lastPicture + '<div class="over"><button type="button" class="btn primary" data-qr-new>Make a new code</button></div>';
    sheet.className += ' expired';
    if (title) { title.textContent = 'This code has expired'; }
    if (note) { note.textContent = 'Codes last 5 minutes so nobody can reuse an old one.'; }
    showTime();
  }

  function ask(url, method) {
    if (busy) { return; }
    busy = true;
    var token = document.querySelector('#csrf-holder input[name=csrfmiddlewaretoken]');
    var options = { method: method, credentials: 'same-origin', headers: { 'Accept': 'application/json' } };
    if (method === 'POST' && token) { options.headers['X-CSRFToken'] = token.value; }
    window.fetch(url, options)
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (data) {
        busy = false;
        if (data && data.ok && (method === 'POST' || data.id !== shownId)) { show(data); }
      })
      .then(null, function () { busy = false; });          // a network hiccup: the next tick tries again
  }

  function tick() {
    if (expired) { return; }
    if (left > 0) { left = left - 1; }
    showTime();
    if (left === 0 && shownId !== null) { expire(); }
  }

  function start() {
    ask(codeUrl, 'GET');
    if (!ticker) { ticker = window.setInterval(tick, 1000); }
    if (!poller) { poller = window.setInterval(function () { if (!expired) { ask(codeUrl, 'GET'); } }, 5000); }
  }

  function stop() {
    if (ticker) { window.clearInterval(ticker); ticker = null; }
    if (poller) { window.clearInterval(poller); poller = null; }
  }

  // G_Qr.js is loaded before G_Sheets.js on purpose: a sheet that opens as the page arrives (?sheet=qr) is heard.
  sheet.addEventListener('sheetopen', start);
  sheet.addEventListener('close', stop);
  if (newButton) { newButton.addEventListener('click', function () { ask(newUrl, 'POST'); }); }
  picture.addEventListener('click', function (event) {         // the Make a new code button on the blurred code
    if (event.target && event.target.getAttribute && event.target.getAttribute('data-qr-new') !== null) { ask(newUrl, 'POST'); }
  });
})();
