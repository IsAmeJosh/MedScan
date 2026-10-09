// Shows the patient or doctor fields on the Register page.
function toggleFields(){
  var isDoctor = document.getElementById('role').value === 'Doctor';
  document.getElementById('patientFields').style.display = isDoctor ? 'none' : 'block';
  document.getElementById('doctorFields').style.display = isDoctor ? 'block' : 'none';
}
