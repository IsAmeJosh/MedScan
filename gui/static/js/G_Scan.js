// The QR scanner on the doctor's Scan QR page. It reads a patient's code with the laptop camera, or from a photo
// the doctor uploads, using the jsQR library (js/vendor/jsQR.js). It only READS the code: what it read is sent to
// /qr/scan/, and the server decides if it is a MedScan patient code and shows the same result as typing the ID.
(function () {
  var video = document.getElementById('qr-video');
  if (!video || !window.jsQR) { return; }

  var canvas = document.getElementById('qr-canvas');
  var idle = document.getElementById('qr-idle');
  var startButton = document.getElementById('qr-start');
  var stopButton = document.getElementById('qr-stop');
  var fileInput = document.getElementById('qr-file');
  var status = document.getElementById('qr-status');
  var stream = null;     // the camera, while it is on
  var done = false;      // true once a code was found, so it is only sent once

  function say(text) { status.textContent = text; }

  // Look for a QR code in a picture (a camera frame or a photo). Returns the text inside it, or null.
  function readCode(source, width, height) {
    var scale = Math.min(1, 800 / Math.max(width, height));   // big photos are shrunk first: much faster, still readable
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    var context = canvas.getContext('2d');
    context.drawImage(source, 0, 0, canvas.width, canvas.height);
    var pixels = context.getImageData(0, 0, canvas.width, canvas.height);
    var found = window.jsQR(pixels.data, pixels.width, pixels.height);
    return found && found.data ? found.data : null;
  }

  function send(text) {
    done = true;
    stopCamera();
    say('Code found. Opening the patient...');
    window.location.href = '/qr/scan/?code=' + encodeURIComponent(text);
  }

  function stopCamera() {
    if (stream) {
      var tracks = stream.getTracks();
      for (var i = 0; i < tracks.length; i++) { tracks[i].stop(); }
      stream = null;
    }
    video.hidden = true;
    idle.hidden = false;
    startButton.hidden = false;
    stopButton.hidden = true;
  }

  // Check about five frames a second until a code is found or the camera is stopped.
  function scanFrame() {
    if (!stream || done) { return; }
    if (video.readyState >= 2 && video.videoWidth) {
      var text = readCode(video, video.videoWidth, video.videoHeight);
      if (text) { send(text); return; }
    }
    window.setTimeout(scanFrame, 200);
  }

  function startCamera() {
    var media = window.navigator.mediaDevices;
    if (!media || !media.getUserMedia) {
      say('This browser cannot open the camera here. Upload a photo of the code instead.');
      return;
    }
    say('Starting the camera...');
    media.getUserMedia({ video: { facingMode: 'environment' }, audio: false }).then(function (camera) {
      stream = camera;
      video.srcObject = camera;
      video.hidden = false;
      idle.hidden = true;
      startButton.hidden = true;
      stopButton.hidden = false;
      video.play();
      say('Hold the code inside the frame.');
      scanFrame();
    }, function (error) {
      if (error && error.name === 'NotAllowedError') {
        say('The camera was blocked. Allow it in the address bar, or upload a photo of the code.');
      } else {
        say('No camera was found. Upload a photo of the code instead.');
      }
    });
  }

  function readPhoto() {
    var file = fileInput.files && fileInput.files[0];
    if (!file) { return; }
    say('Reading the photo...');
    var picture = new Image();
    picture.onload = function () {
      var text = readCode(picture, picture.naturalWidth, picture.naturalHeight);
      window.URL.revokeObjectURL(picture.src);
      if (text) { send(text); } else { say('No QR code was found in that photo. Try a clearer, closer one.'); }
      fileInput.value = '';
    };
    picture.onerror = function () { say('That file is not a picture.'); fileInput.value = ''; };
    picture.src = window.URL.createObjectURL(file);
  }

  startButton.addEventListener('click', startCamera);
  stopButton.addEventListener('click', function () { stopCamera(); say(''); });
  fileInput.addEventListener('change', readPhoto);
  window.addEventListener('pagehide', stopCamera);   // never leave the camera light on after leaving the page
})();
