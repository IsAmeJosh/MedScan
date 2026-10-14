// Form helpers for every page: character counters, show/hide password, phone and date formatting as you type,
// live messages next to each field, and a submit button that waits until the form is valid.
// The server checks everything again, so if this file fails to load the forms still work.
(function () {
  var F = window.MedScanFormat;
  if (!F) { return; }

  function each(list, action) {
    for (var i = 0; i < list.length; i++) { action(list[i], i); }
  }

  function has(node, name) {
    return (' ' + node.className + ' ').indexOf(' ' + name + ' ') !== -1;
  }

  function fieldBox(input) {
    var box = input.parentNode;
    while (box && !has(box, 'field')) { box = box.parentNode; }
    return box;
  }

  // The line under a field: a message on the left and a counter on the right. Made when first needed.
  function footOf(input) {
    var box = fieldBox(input);
    if (!box) { return null; }
    var foot = box.querySelector('.field-foot');
    if (!foot) {
      foot = document.createElement('div');
      foot.className = 'field-foot';
      foot.innerHTML = '<span class="field-msg"></span><span class="counter"></span>';
      box.appendChild(foot);
    }
    return foot;
  }

  // ---- counters: 7 / 25 ----
  function setupCounter(input) {
    var max = parseInt(input.getAttribute('maxlength'), 10);
    var foot = footOf(input);
    if (!max || !foot) { return; }
    var counter = foot.querySelector('.counter');
    var min = parseInt(input.getAttribute('data-min'), 10) || 0;
    function update() {
      var length = input.value.length;
      counter.innerHTML = length + ' / ' + max;
      counter.className = 'counter' + (length > 0 && length < min ? ' low' : '') + (length >= max * 0.9 ? ' near' : '');
    }
    input.addEventListener('input', update);
    update();
  }

  // ---- show/hide password, and a Caps Lock warning ----
  function setupPassword(input) {
    var wrap = input.parentNode;
    var eye = wrap.querySelector('.pw-eye');
    var caps = wrap.parentNode.querySelector('.caps-note');
    if (eye) {
      eye.addEventListener('click', function () {
        var show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        eye.setAttribute('aria-pressed', show ? 'true' : 'false');
        eye.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
        input.focus();
      });
    }
    if (caps) {
      var check = function (event) {
        if (event.getModifierState) { caps.hidden = !event.getModifierState('CapsLock'); }
      };
      input.addEventListener('keydown', check);
      input.addEventListener('keyup', check);
      input.addEventListener('blur', function () { caps.hidden = true; });
    }
  }

  // ---- phone and date formatting while typing ----
  function setupFormat(input) {
    var format = input.getAttribute('data-format') === 'mobile' ? F.formatMobile : F.formatDate;
    function reformat() {
      var before = input.value;
      var after = format(before);
      if (after === before) { return; }
      var caret = input.selectionStart;
      input.value = after;
      try {
        var place = F.caretAfter(before, caret === null ? before.length : caret, after);
        input.setSelectionRange(place, place);
      } catch (ignored) { /* some inputs cannot place the cursor; the text is still right */ }
    }
    input.addEventListener('input', reformat);
    input.value = format(input.value);   // a value that came back from the server after an error
  }

  // ---- the little calendar button next to a date field ----
  function setupDatePicker(button) {
    var wrap = button.parentNode;
    var typed = wrap.querySelector('[data-format="date"]');
    var calendar = wrap.querySelector('.date-calendar');
    if (!typed || !calendar || typeof calendar.showPicker !== 'function') { button.hidden = true; return; }
    button.addEventListener('click', function () {
      calendar.value = F.typedToIso(typed.value);
      try { calendar.showPicker(); } catch (ignored) { calendar.focus(); }
    });
    calendar.addEventListener('change', function () {
      if (!calendar.value) { return; }
      typed.value = F.isoToTyped(calendar.value);
      var event = document.createEvent('Event');
      event.initEvent('input', true, false);
      typed.dispatchEvent(event);
      typed.focus();
    });
  }

  // ---- messages next to fields, and the submit button ----
  var RULES = {
    name: function (value) { return F.nameProblem(value); },
    password: function (value) { return F.passwordProblem(value); },
    dob: function (value) { return F.dateProblem(value, new Date()); },
    mobile: function (value) { return F.mobileProblem(value); },
    'mobile-required': function (value) { return F.mobileRequiredProblem(value); },
    'login-id': function (value) { return F.requiredProblem(value, 'your ID or mobile number'); },
    'login-password': function (value) { return F.requiredProblem(value, 'your password'); }
  };

  function visible(node) {
    return node.offsetParent !== null || (node.getClientRects && node.getClientRects().length > 0);
  }

  function problemOf(input) {
    var rule = RULES[input.getAttribute('data-validate')];
    return rule ? rule(input.value) : '';
  }

  function showAge(input) {
    var target = document.getElementById(input.getAttribute('data-age-target') || '');
    if (!target) { return; }
    var parts = F.parseDate(input.value);
    target.innerHTML = parts && !F.dateProblem(input.value, new Date())
      ? F.ageOn(parts, new Date()) + ' years old' : '';
  }

  function show(input, force) {
    var foot = footOf(input);
    if (!foot) { return; }
    var message = foot.querySelector('.field-msg');
    var problem = problemOf(input);
    var touched = input.getAttribute('data-touched') === '1' || force;
    var shown = touched && problem !== '';
    message.innerHTML = shown ? problem : (input.getAttribute('data-hint') || '');
    message.className = 'field-msg' + (shown ? ' bad' : '');
    input.setAttribute('aria-invalid', shown ? 'true' : 'false');
  }

  function formIsValid(form) {
    var valid = true;
    each(form.querySelectorAll('[data-validate]'), function (input) {
      if (visible(input) && problemOf(input) !== '') { valid = false; }
    });
    return valid;
  }

  function refresh(form) {
    var button = form.querySelector('[data-submit]');
    var hint = form.querySelector('[data-submit-hint]');
    var ok = formIsValid(form);
    if (button) { button.disabled = !ok; }
    if (hint) { hint.hidden = ok; }
  }

  function setupValidation(form) {
    each(form.querySelectorAll('[data-validate]'), function (input) {
      show(input, false);
      input.addEventListener('blur', function () {
        if (input.getAttribute('data-quiet') === '1') { return; }   // login: say nothing until Log in is pressed
        input.setAttribute('data-touched', '1');
        show(input, false);
        refresh(form);
      });
      input.addEventListener('input', function () {
        show(input, false);
        showAge(input);
        refresh(form);
      });
      showAge(input);
    });
    form.addEventListener('change', function () { refresh(form); });
    form.addEventListener('submit', function (event) {
      if (formIsValid(form)) { return; }
      event.preventDefault();
      each(form.querySelectorAll('[data-validate]'), function (input) {
        input.setAttribute('data-touched', '1');
        show(input, true);
      });
      refresh(form);
    });
    refresh(form);
    window.setTimeout(function () { refresh(form); }, 400);   // browsers fill saved passwords a moment late
  }

  // ---- "Remember my ID on this computer" on the login page (the password is never stored) ----
  function setupRemember(input) {
    var key = input.getAttribute('data-remember');
    var box = document.getElementById(input.getAttribute('data-remember-box') || '');
    if (!key || !box || !input.form) { return; }
    try {
      var saved = window.localStorage.getItem(key);
      if (saved) {
        input.value = saved;
        box.checked = true;
        var password = document.getElementById('password');
        if (password) { password.focus(); }          // the ID is already there: go to the password
      }
    } catch (ignored) { /* the browser does not allow storing: the box just does nothing */ }
    input.form.addEventListener('submit', function () {
      try {
        if (box.checked) { window.localStorage.setItem(key, input.value); } else { window.localStorage.removeItem(key); }
      } catch (ignored) { /* see above */ }
    });
  }

  function start() {
    each(document.querySelectorAll('[data-remember]'), setupRemember);
    each(document.querySelectorAll('[data-format]'), setupFormat);
    each(document.querySelectorAll('[data-counter]'), setupCounter);
    each(document.querySelectorAll('[data-toggle-password]'), setupPassword);
    each(document.querySelectorAll('[data-date-picker]'), setupDatePicker);
    each(document.querySelectorAll('form[data-validate-form]'), setupValidation);
  }

  window.MedScanForms = { refresh: refresh };
  start();
})();
