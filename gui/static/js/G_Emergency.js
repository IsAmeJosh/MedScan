// The emergency pop-up (doctors). Any link marked data-emergency opens it instead of going to another page:
// the red button in the top bar (asks for the patient), and the button on a search result (knows the patient).
// Without this file the links still go to the Emergency Access page.
(function () {
  var dialog = document.getElementById('emergency-dialog');
  if (!dialog || typeof dialog.showModal !== 'function') { return; }

  var form = document.getElementById('emergency-form');
  var who = document.getElementById('emergency-who');
  var idBox = document.getElementById('emergency-id');
  var label = document.getElementById('emergency-patient');
  var reason = document.getElementById('emergency-reason');
  var cancel = document.getElementById('emergency-cancel');

  function openFor(link) {
    var patientId = link.getAttribute('data-patient-id');
    if (patientId) {                       // we already know who: no need to ask
      form.setAttribute('action', '/patient/' + patientId + '/emergency/');
      who.hidden = true;
      idBox.disabled = true;
      idBox.required = false;
      label.textContent = link.getAttribute('data-patient-name');
      label.hidden = false;
    } else {                               // from the top bar: ask who
      form.setAttribute('action', form.getAttribute('data-default-action'));
      who.hidden = false;
      idBox.disabled = false;
      idBox.required = true;
      label.hidden = true;
    }
    reason.value = '';
    dialog.showModal();
    (patientId ? reason : idBox).focus();
  }

  var links = document.querySelectorAll('[data-emergency]');
  for (var i = 0; i < links.length; i++) {
    (function (link) {
      link.addEventListener('click', function (event) {
        event.preventDefault();
        openFor(link);
      });
    })(links[i]);
  }

  cancel.addEventListener('click', function () { dialog.close(); });
})();
