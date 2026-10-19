// Every pop-up that dims the page behind it (the sheets: QR code, review request, edit, emergency; the "Are you sure?" questions,
// including the remove confirmations; and the log-out question) behaves the same way, and this is the one place that says how:
// - Pressing the dimmed area outside the box closes it, exactly like Cancel. Pressing inside the box never does.
// - Escape closes it too.
// - Closing throws away anything half-typed or chosen: every box goes back to what the page started with. Nothing is saved.
// - The page underneath is left as it was, and the focus goes back to the button that opened the pop-up.
// The "Still there?" pop-up is the one exception: it is a timer that must be answered, so it is left alone.
// (The notification panel and the top-bar search have their own dimmed areas and follow the same rules in G_Shell.js and G_Suggest.js.)
(function () {
  var lastTrigger = null;      // the button or link the person last pressed: focus goes back to it when a pop-up closes
  var pressedOutside = null;   // the pop-up a press started outside of (a press that ends elsewhere is a text selection, not a close)

  function each(list, action) {
    for (var i = 0; i < list.length; i++) { action(list[i], i); }
  }

  // A pop-up this script looks after: a <dialog> that is a sheet or a modal, except the idle warning.
  function isOverlay(element) {
    return !!element && element.tagName === 'DIALOG' && element.id !== 'idle-dialog' && /\b(sheet|modal)\b/.test(element.className || '');
  }

  // True when a point is outside the box of the pop-up. The dimmed area counts as the pop-up element itself in the browser, so the
  // box has to be measured: the padding inside a modal is inside the box.
  function outside(dialog, x, y) {
    var box = dialog.getBoundingClientRect();
    return x < box.left || x > box.right || y < box.top || y > box.bottom;
  }

  // Forget what was typed or chosen: every form in the pop-up goes back to its starting values (the chips boxes listen for this too).
  function discard(dialog) {
    each(dialog.querySelectorAll('form'), function (form) { if (form.reset) { form.reset(); } });
  }

  // Everything that follows a close, however it happened (outside press, Escape, Cancel, the round x).
  function afterClose(dialog) {
    if (!isOverlay(dialog)) { return; }
    if (dialog.returnValue !== 'ok') { discard(dialog); }             // "ok" means a confirmation was answered Yes and is on its way
    var trigger = dialog.openedBy;
    dialog.openedBy = null;
    if (trigger && trigger.focus) { window.setTimeout(function () { trigger.focus(); }, 0); }
  }

  function closeIfOutside(event) {
    var dialog = event.target;
    var started = pressedOutside;
    pressedOutside = null;
    if (isOverlay(dialog) && started === dialog && outside(dialog, event.clientX, event.clientY) && dialog.open) { dialog.close(); }
  }

  function remember(event) {
    var target = event.target;
    while (target && target.nodeType === 1) {
      if (/^(A|BUTTON|SUMMARY)$/.test(target.tagName) || (target.getAttribute && target.getAttribute('data-sheet'))) { lastTrigger = target; return; }
      target = target.parentNode;
    }
  }

  document.addEventListener('mousedown', function (event) {
    var dialog = event.target;
    pressedOutside = isOverlay(dialog) && outside(dialog, event.clientX, event.clientY) ? dialog : null;
  }, true);
  document.addEventListener('click', function (event) { remember(event); closeIfOutside(event); }, true);
  document.addEventListener('close', function (event) { afterClose(event.target); }, true);   // "close" does not bubble, but capturing hears it

  // Remember what opened each pop-up, whoever opens it (a data-sheet link, the confirm question, the page on arrival).
  if (window.HTMLDialogElement && window.HTMLDialogElement.prototype.showModal) {
    var showModal = window.HTMLDialogElement.prototype.showModal;
    window.HTMLDialogElement.prototype.showModal = function () {
      this.openedBy = lastTrigger && lastTrigger.focus ? lastTrigger : null;
      return showModal.apply(this, arguments);
    };
  }

  // The log-out question is a page of its own (the Settings page behind a dimmed area), not a <dialog>: pressing outside it
  // or Escape does what its Stay button does.
  var scrim = document.querySelector('.scrim[role=dialog]');
  if (scrim) {
    var stay = scrim.querySelector('.sheet-actions a');
    var stayHere = function () { if (stay) { window.location = stay.getAttribute('href'); } };
    scrim.addEventListener('click', function (event) { if (event.target === scrim) { stayHere(); } });
    document.addEventListener('keydown', function (event) { if (event.key === 'Escape') { stayHere(); } });
  }

  // For the tests, and for any script that needs the same rules.
  window.MedScanOverlays = { isOverlay: isOverlay, outside: outside, afterClose: afterClose, discard: discard };
})();
