// The search box in the top bar (doctors): suggestions from your own patients as you type, and the "/" key
// that jumps to the box from anywhere. The page is dimmed while the box is in use. Press Enter on a suggestion to open that
// record, or Enter with nothing chosen to go to the Search page with the text carried over.
// Like every other pop-up with a dim behind it, pressing outside the box or Escape closes it and throws away what was typed.
(function () {
  var input = document.getElementById('top-search-input');
  var box = document.getElementById('suggest');
  if (!input || !box) { return; }

  var url = input.getAttribute('data-suggest-url');
  var timer = null;
  var links = [];
  var active = -1;

  function close() {
    box.hidden = true;
    box.innerHTML = '';
    links = [];
    active = -1;
  }

  // Close the suggestions, forget the typing and give the page back, as Cancel would.
  function cancel() {
    window.clearTimeout(timer);
    input.value = '';
    close();
    dim(false);
    input.blur();
  }

  function highlight(index) {
    for (var i = 0; i < links.length; i++) { links[i].className = i === index ? 'on' : ''; }
    active = index;
  }

  function show(items, text) {
    box.innerHTML = '';
    links = [];
    active = -1;
    if (!items.length) {
      var hint = document.createElement('div');
      hint.className = 'hint';
      hint.appendChild(document.createTextNode(
        text.length > 1 ? 'None of your patients match. Press Enter to search by the whole MedScan ID.' : ''));
      if (text.length > 1) { box.appendChild(hint); }
    }
    for (var i = 0; i < items.length; i++) {
      var link = document.createElement('a');
      link.href = items[i].url;
      var name = document.createElement('b');
      name.appendChild(document.createTextNode(items[i].name));
      var id = document.createElement('span');
      id.appendChild(document.createTextNode(items[i].id));
      link.appendChild(name);
      link.appendChild(id);
      box.appendChild(link);
      links.push(link);
    }
    box.hidden = box.innerHTML === '';
  }

  function ask() {
    var text = input.value.replace(/^\s+|\s+$/g, '');
    if (!text) { close(); return; }
    window.fetch(url + '?q=' + encodeURIComponent(text), { credentials: 'same-origin' })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (input.value.replace(/^\s+|\s+$/g, '') !== text || !data.ok) { return; }   // The person kept typing since this question was asked, so this answer is out of date: ignore it.
        show(data.items, text);
      })
      .then(null, close);
  }

  input.addEventListener('input', function () {
    window.clearTimeout(timer);
    timer = window.setTimeout(ask, 150);
  });

  input.addEventListener('keydown', function (event) {
    if (event.key === 'ArrowDown' && links.length) {
      event.preventDefault();
      highlight(active + 1 >= links.length ? 0 : active + 1);
    } else if (event.key === 'ArrowUp' && links.length) {
      event.preventDefault();
      highlight(active <= 0 ? links.length - 1 : active - 1);
    } else if (event.key === 'Enter' && active >= 0) {
      event.preventDefault();
      window.location = links[active].href;
    } else if (event.key === 'Escape') {
      cancel();
    }
  });

  // While the box is in use the rest of the page is dimmed and blurred (the styles are in G_Style.css, keyed on the
  // class "searching" on the page).
  function dim(on) {
    var body = document.body;
    if (!body) { return; }
    body.className = on ? body.className.replace(/\s*searching/, '') + ' searching' : body.className.replace(/\s*searching/g, '');
  }

  input.addEventListener('focus', function () { dim(true); });

  // Pressing anywhere outside the box (on the dimmed page) closes it. A press on a suggestion is not outside: it opens that record.
  document.addEventListener('mousedown', function (event) {
    var form = input.form || box.parentNode;
    var target = event.target;
    while (target && target !== form) { target = target.parentNode; }
    if (target === form) { return; }
    if (document.body && /\bsearching\b/.test(document.body.className)) { cancel(); }
  }, true);

  // "/" jumps to the search box, unless you are typing somewhere
  document.addEventListener('keydown', function (event) {
    if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) { return; }
    var target = event.target;
    var tag = target && target.tagName ? target.tagName.toUpperCase() : '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (target && target.isContentEditable)) { return; }
    event.preventDefault();
    input.focus();
    input.select();
  });
})();
