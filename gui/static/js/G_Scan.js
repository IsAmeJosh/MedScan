// The QR scanner on the doctor's Scan QR page. It starts the laptop or phone camera by itself and reads a patient's code
// with the jsQR library (js/vendor/jsQR.js). It only READS the code: what it read is sent to /qr/scan/, and the server
// decides what it means (a live one-time code is the patient's approval; a plain ID only finds the patient).
// There is no photo upload and no typing of IDs here: the scan is the point.
(function () {
  var video = document.getElementById('qr-video');
  if (!video || !window.jsQR) { return; }

  var canvas = document.getElementById('qr-canvas');
  var status = document.getElementById('qr-status');
  var retry = document.getElementById('qr-retry');
  var stream = null;     // the camera, while it is on
  var done = false;      // true once a code was found, so it is only sent once

  function say(text) { status.textContent = text; }

  // Look for a QR code in one camera frame. Returns the text inside it, or null.
  function readCode() {
    var scale = Math.min(1, 800 / Math.max(video.videoWidth, video.videoHeight));   // a smaller picture is much faster to search
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    var context = canvas.getContext('2d');
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    var pixels = context.getImageData(0, 0, canvas.width, canvas.height);
    var found = window.jsQR(pixels.data, pixels.width, pixels.height);
    return found && found.data ? found.data : null;
  }

  function stopCamera() {
    if (stream) {
      var tracks = stream.getTracks();
      for (var i = 0; i < tracks.length; i++) { tracks[i].stop(); }
      stream = null;
    }
  }

  function send(text) {
    done = true;
    stopCamera();
    say('Code found. Opening the patient...');
    window.location.href = '/qr/scan/?code=' + encodeURIComponent(text);
  }

  // Check about five frames a second until a code is found or the camera is stopped.
  function scanFrame() {
    if (!stream || done) { return; }
    if (video.readyState >= 2 && video.videoWidth) {
      var text = readCode();
      if (text) { send(text); return; }
    }
    window.setTimeout(scanFrame, 200);
  }

  function failed(text) {
    say(text);
    retry.hidden = false;
  }

  function startCamera() {
    var media = window.navigator.mediaDevices;
    retry.hidden = true;
    if (!media || !media.getUserMedia) {
      failed('This browser cannot open the camera here. Open MedScan over https or on localhost, in a current browser.');
      return;
    }
    say('Starting the camera...');
    media.getUserMedia({ video: { facingMode: 'environment' }, audio: false }).then(function (camera) {
      stream = camera;
      video.srcObject = camera;
      video.play();
      say("Hold the patient's code inside the frame");
      scanFrame();
    }, function (error) {
      if (error && error.name === 'NotAllowedError') {
        failed('The camera is blocked. Allow it in the address bar, then try again.');
      } else {
        failed('No camera was found on this device.');
      }
    });
  }

  retry.addEventListener('click', startCamera);
  window.addEventListener('pagehide', stopCamera);   // never leave the camera light on after leaving the page
  startCamera();
})();
