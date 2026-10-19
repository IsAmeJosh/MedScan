// Start-up check for the scripts that run on the pages: every file must parse, and must start without an error
// on a page that has none of the things it looks for (the login page has no counters, no chips, no panel...).
// Uses Windows Script Host (cscript). Run by tests/test_javascript.py, or by hand:  cscript //nologo tests\js\smoke_test.js
var fso = new ActiveXObject('Scripting.FileSystemObject');
var here = fso.GetParentFolderName(WScript.ScriptFullName);
var folder = fso.GetParentFolderName(fso.GetParentFolderName(here)) + '\\gui\\static\\js\\';
var failures = 0;

function read(name) { return fso.OpenTextFile(folder + name, 1).ReadAll(); }
function nothing() { }

var doc = {
  body: { getAttribute: function () { return null; } },
  querySelector: function () { return null; },
  querySelectorAll: function () { return []; },
  getElementById: function () { return null; },
  addEventListener: nothing,
  createElement: function () { return {}; }
};
var win = { addEventListener: nothing, setTimeout: nothing, setInterval: nothing, fetch: nothing };

var module = { exports: {} };
new Function('module', read('G_Format.js'))(module);
win.MedScanFormat = module.exports;

var files = ['G_Fields.js', 'G_Chips.js', 'G_Dialogs.js', 'G_Sheets.js', 'G_Qr.js', 'G_Idle.js', 'G_Shell.js', 'G_Suggest.js', 'G_Scan.js', 'G_Id.js'];
for (var i = 0; i < files.length; i++) {
  try {
    new Function('window', 'document', read(files[i]))(win, doc);
    WScript.Echo('ok   - ' + files[i] + ' starts on a page with nothing to set up');
  } catch (error) {
    failures = failures + 1;
    WScript.Echo('FAIL - ' + files[i] + ': ' + error.message);
  }
}

if (!win.MedScanForms || typeof win.MedScanForms.refresh !== 'function') {
  failures = failures + 1;
  WScript.Echo('FAIL - G_Fields.js did not offer MedScanForms.refresh');
}

if (failures === 0) {
  WScript.Echo('ALL PASS');
  WScript.Quit(0);
}
WScript.Echo(failures + ' file(s) failed');
WScript.Quit(1);
