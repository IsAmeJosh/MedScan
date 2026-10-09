// Shows the patient fields or the doctor fields on the Register page.
(function () {
  var role = document.getElementById('role');
  var patientFields = document.getElementById('patientFields');
  var doctorFields = document.getElementById('doctorFields');
  if (!role) { return; }

  function toggleFields() {
    var isDoctor = role.value === 'Doctor';
    patientFields.style.display = isDoctor ? 'none' : 'block';
    doctorFields.style.display = isDoctor ? 'block' : 'none';
  }

  role.addEventListener('change', toggleFields);
  toggleFields();
})();
