// Sheets: the "Show my QR code", "Review request" and "Edit my information" pop-ups, and the phone tabs on My Record.
// - Any element with data-sheet="some-id" opens the <dialog id="some-id">. Anything with data-close closes the sheet it is in.
//   Clicking the dimmed area around a sheet closes it too (Esc works by itself).
// - A page can open a sheet on arrival: /dashboard/?sheet=qr opens #qr-sheet, and /record/#edit opens #edit-sheet.
// - My Record has Notes / Medical / Info tabs on a phone: buttons with data-pane-tab show the cards with that data-pane.
(function () {
  function closest(element, selector) {
    while (element && element.nodeType === 1) {
      if (element.matches && element.matches(selector)) { return element; }
      element = element.parentNode;
    }
    return null;
  }

  function openSheet(id) {
    var dialog = document.getElementById(id);
    if (dialog && dialog.showModal && !dialog.open) {
      dialog.setAttribute('tabindex', '-1');
      dialog.showModal();
      if (dialog.focus) { dialog.focus(); }       // focus the sheet, so no button shows a focus ring until the keyboard is used
      var opened = document.createEvent('Event');
      opened.initEvent('sheetopen', false, false);
      dialog.dispatchEvent(opened);               // lets a sheet with its own work (the QR code) start it
    }
    return dialog;
  }

  document.addEventListener('click', function (event) {
    var opener = closest(event.target, '[data-sheet]');
    if (opener) {
      if (openSheet(opener.getAttribute('data-sheet'))) { event.preventDefault(); }
      return;
    }
    var closer = closest(event.target, '[data-close]');
    if (closer) {
      var inside = closest(closer, 'dialog');
      if (inside) { inside.close(); }
      return;
    }
    var target = event.target;
    if (target && target.tagName === 'DIALOG' && /\bsheet\b/.test(target.className)) { target.close(); }   // the dimmed area
  });

  // ---- open a sheet when the page arrives ----
  var place = window.location;
  if (place) {
    var wanted = /[?&]sheet=([a-z0-9-]+)/.exec(place.search || '');
    if (wanted) { openSheet(document.getElementById(wanted[1]) ? wanted[1] : wanted[1] + '-sheet'); }   // ?sheet=qr or ?sheet=review-3
    if (place.hash === '#edit') { openSheet('edit-sheet'); }
  }

  // ---- phone tabs on My Record ----
  var tabs = document.querySelectorAll('[data-pane-tab]');
  var panes = document.querySelectorAll('[data-pane]');
  if (tabs.length) {
    var show = function (name) {
      for (var i = 0; i < panes.length; i++) {
        var on = panes[i].getAttribute('data-pane') === name;
        panes[i].className = panes[i].className.replace(/\s*\bon\b/g, '') + (on ? ' on' : '');
      }
      for (var j = 0; j < tabs.length; j++) {
        var current = tabs[j].getAttribute('data-pane-tab') === name;
        tabs[j].className = tabs[j].className.replace(/\s*\bon\b/g, '') + (current ? ' on' : '');
      }
    };
    for (var k = 0; k < tabs.length; k++) {
      tabs[k].addEventListener('click', function () { show(this.getAttribute('data-pane-tab')); });
    }
    show('notes');
  }
})();
