// The Search page (doctors). The results change as the doctor types: two or more characters ask /search/results/ and the answer
// (the count and the list, or "No patient found") replaces what is under the box. The round x clears the box and puts the cursor
// back in it. Without this file the page still works: Enter searches and the page reloads with the results.
(function () {
  var input = document.getElementById('search-input');
  var clear = document.getElementById('search-clear');
  var results = document.getElementById('search-results');
  if (!input || !clear || !results || !window.fetch) { return; }

  var url = input.getAttribute('data-results-url');
  var timer = null;
  var latest = 0;          // each question gets a number, so a slow old answer cannot replace a newer one

  function trim(text) { return text.replace(/^\s+|\s+$/g, ''); }

  function look() {
    var text = trim(input.value);
    clear.hidden = input.value === '';
    if (text.length < 2) {
      latest = latest + 1;
      results.innerHTML = '';
      return;
    }
    var ticket = ++latest;
    window.fetch(url + '?q=' + encodeURIComponent(text), { credentials: 'same-origin' })
      .then(function (response) { return response.ok ? response.text() : null; })
      .then(function (html) { if (html !== null && ticket === latest) { results.innerHTML = html; } })
      .then(null, function () { /* a network hiccup: the next keystroke asks again */ });
  }

  input.addEventListener('input', function () {
    if (timer) { window.clearTimeout(timer); }
    timer = window.setTimeout(look, 150);
  });
  clear.addEventListener('click', function () {
    input.value = '';
    look();
    input.focus();
  });
})();
