// The two ID screens.
// - Save-your-ID (after registering): "Continue to MedScan" waits until the box "I saved my MedScan ID" is ticked.
//   Without this file the button is simply a link that always works.
// - Printable ID: the Save as PDF button opens the browser's Print dialog (choose "Save as PDF" there), and a page opened
//   with ?auto=1 opens that dialog by itself.
(function () {
  var saved = document.getElementById('id-saved');
  var next = document.getElementById('id-continue');
  if (saved && next) {
    var update = function () {
      if (saved.checked) {
        next.removeAttribute('aria-disabled');
        next.className = next.className.replace(/\s*waits/, '');
      } else {
        next.setAttribute('aria-disabled', 'true');
        if (!/\bwaits\b/.test(next.className)) { next.className += ' waits'; }
      }
    };
    next.addEventListener('click', function (event) {
      if (!saved.checked) { event.preventDefault(); }
    });
    saved.addEventListener('change', update);
    update();
  }

  var printButton = document.getElementById('id-print');
  if (printButton) {
    printButton.addEventListener('click', function () { window.print(); });
  }
  var sheet = document.querySelector('[data-autoprint]');
  if (sheet && window.print) {
    window.setTimeout(function () { window.print(); }, 400);
  }
})();
