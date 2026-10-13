// Small helpers used on every page: "Are you sure?" pop-ups, a submit button that locks after one click,
// a Copy button, a close button for cards and messages, and links that open a closed "details" box.
// Without this file everything still works: forms just submit straight away.
(function () {
  function each(list, action) {
    for (var i = 0; i < list.length; i++) { action(list[i], i); }
  }

  // ---- the "Are you sure?" pop-up. Other scripts use it too: MedScanConfirm.ask(options, onYes) ----
  // options: title, message, button (the text on the yes button), tone ('danger' makes it red)
  function ask(options, onYes) {
    var dialog = document.getElementById('confirm-dialog');
    if (!dialog || typeof dialog.showModal !== 'function') {
      if (window.confirm(options.message)) { onYes(); }
      return;
    }
    document.getElementById('confirm-title').textContent = options.title || 'Are you sure?';
    document.getElementById('confirm-text').textContent = options.message;
    var ok = document.getElementById('confirm-ok');
    ok.textContent = options.button || 'Confirm';
    ok.className = options.tone === 'danger' ? 'danger' : '';
    dialog.returnValue = '';
    dialog.onclose = function () {
      if (dialog.returnValue === 'ok') { onYes(); }
    };
    dialog.showModal();
  }
  window.MedScanConfirm = { ask: ask };

  // ---- confirm before a risky form is sent: <form data-confirm="Revoke access?" data-confirm-button="Revoke"> ----
  function proceed(form) {
    form.setAttribute('data-confirmed', '1');
    if (form.requestSubmit) { form.requestSubmit(); } else { form.submit(); }
  }

  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!form.getAttribute || !form.getAttribute('data-confirm')) { return; }
    if (form.getAttribute('data-confirmed') === '1') { form.removeAttribute('data-confirmed'); return; }
    event.preventDefault();
    event.stopImmediatePropagation();
    ask({
      title: form.getAttribute('data-confirm-title'),
      message: form.getAttribute('data-confirm'),
      button: form.getAttribute('data-confirm-button'),
      tone: form.getAttribute('data-confirm-tone')
    }, function () { proceed(form); });
  }, true);

  // ---- one click is enough: lock the buttons once a form is on its way ----
  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (event.defaultPrevented || !form.method || form.method.toLowerCase() !== 'post') { return; }
    window.setTimeout(function () {
      each(form.querySelectorAll('button'), function (button) {
        if (button.type === 'submit') { button.disabled = true; button.className += ' busy'; }
      });
    }, 0);
  });

  // coming back with the browser's Back button must not leave the buttons locked
  window.addEventListener('pageshow', function (event) {
    if (!event.persisted) { return; }
    each(document.querySelectorAll('button.busy'), function (button) {
      button.disabled = false;
      button.className = button.className.replace(' busy', '');
    });
  });

  // ---- a Copy button: <button data-copy="PT-2026-01002"> ----
  function copyText(text, done) {
    if (window.navigator && window.navigator.clipboard && window.navigator.clipboard.writeText) {
      window.navigator.clipboard.writeText(text).then(done, function () { /* blocked: nothing to do */ });
      return;
    }
    var box = document.createElement('textarea');       // older browsers
    box.value = text;
    document.body.appendChild(box);
    box.select();
    try { if (document.execCommand('copy')) { done(); } } catch (ignored) { /* copy is not allowed here */ }
    document.body.removeChild(box);
  }

  each(document.querySelectorAll('[data-copy]'), function (button) {
    var original = button.innerHTML;
    button.addEventListener('click', function () {
      copyText(button.getAttribute('data-copy'), function () {
        button.innerHTML = 'Copied';
        window.setTimeout(function () { button.innerHTML = original; }, 2000);
      });
    });
  });

  // ---- a close button for a card: <button data-dismiss="#welcome-card"> ----
  // With data-hide-key="name" the card also stays hidden on later visits (remembered in this browser only).
  function remembered(key, value) {
    try {
      if (value) { window.localStorage.setItem(key, '1'); }
      return window.localStorage.getItem(key) === '1';
    } catch (ignored) { return false; }     // storage blocked: the card simply comes back next time
  }

  function removeCard(selector) {
    var card = document.querySelector(selector);
    if (card && card.parentNode) { card.parentNode.removeChild(card); }
  }

  each(document.querySelectorAll('[data-dismiss]'), function (button) {
    var selector = button.getAttribute('data-dismiss');
    var key = button.getAttribute('data-hide-key');
    if (key && remembered(key, false)) { removeCard(selector); return; }
    button.addEventListener('click', function () {
      if (key) { remembered(key, true); }
      removeCard(selector);
    });
  });

  // ---- quick phrases for a note: <button data-phrase="#notes">+ Labs requested</button> adds the words ----
  each(document.querySelectorAll('[data-phrase]'), function (button) {
    button.addEventListener('click', function () {
      var box = document.querySelector(button.getAttribute('data-phrase'));
      if (!box) { return; }
      var text = button.textContent.replace(/^\s*\+\s*/, '').replace(/\s+$/, '');
      var old = box.value.replace(/\s+$/, '');
      box.value = old ? old + (/[.!?]$/.test(old) ? ' ' : '. ') + text + '.' : text + '.';
      box.focus();
      var inputEvent = document.createEvent('Event');       // lets the character counter notice
      inputEvent.initEvent('input', true, true);
      box.dispatchEvent(inputEvent);
    });
  });

  // ---- a link that opens a closed box on the same page: <a href="#edit" data-open="edit"> ----
  each(document.querySelectorAll('[data-open]'), function (link) {
    link.addEventListener('click', function () {
      var box = document.getElementById(link.getAttribute('data-open'));
      if (box) { box.open = true; }
    });
  });

  // ---- messages: the close button (they also fade away by themselves) ----
  each(document.querySelectorAll('.toast .toast-x'), function (button) {
    button.addEventListener('click', function () {
      var toast = button.parentNode;
      toast.parentNode.removeChild(toast);
    });
  });
})();
