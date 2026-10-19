// Runs the real gui/static/js/G_Overlays.js with Windows Script Host (cscript) against pretend pop-ups, to check the rules every
// dimmed pop-up follows: pressing outside the box closes it, pressing inside never does, Escape (the browser closes the dialog
// itself) throws the typing away, and the focus goes back to what opened it.
// Run by tests/test_javascript.py, or by hand:  cscript //nologo tests\js\overlay_test.js
var fso = new ActiveXObject('Scripting.FileSystemObject');
var here = fso.GetParentFolderName(WScript.ScriptFullName);
var source = fso.OpenTextFile(fso.GetParentFolderName(fso.GetParentFolderName(here)) + '\\gui\\static\\js\\G_Overlays.js', 1).ReadAll();
var passed = 0;
var failed = 0;

function check(name, ok) {
  if (ok) { passed = passed + 1; } else { failed = failed + 1; WScript.Echo('FAIL - ' + name); }
}

// ---- a pretend page: it keeps the listeners the script registers, so the test can fire events at them
var listeners = {};
var doc = {
  querySelector: function () { return null; },
  querySelectorAll: function () { return []; },
  addEventListener: function (type, handler) { (listeners[type] = listeners[type] || []).push(handler); }
};
var win = { setTimeout: function (action) { action(); return 0; } };       // run "later" work right away
new Function('window', 'document', source)(win, doc);
var overlays = win.MedScanOverlays;

function fire(type, event) {
  var list = listeners[type] || [];
  for (var i = 0; i < list.length; i++) { list[i](event); }
}

// ---- a pretend sheet: 100 to 500 across, 100 to 400 down, with one form
function makeSheet(id, className) {
  var resetCount = 0;
  var form = { reset: function () { resetCount = resetCount + 1; } };
  var sheet = {
    tagName: 'DIALOG', id: id, className: className, open: true, returnValue: '', openedBy: null, nodeType: 1,
    getBoundingClientRect: function () { return { left: 100, right: 500, top: 100, bottom: 400 }; },
    querySelectorAll: function () { return [form]; },
    close: function () { sheet.open = false; fire('close', { target: sheet }); },
    resets: function () { return resetCount; }
  };
  return sheet;
}

function press(sheet, x, y) {                          // a full press: down then click, on the sheet element
  fire('mousedown', { target: sheet, clientX: x, clientY: y });
  fire('click', { target: sheet, clientX: x, clientY: y });
}

// ---- which dialogs are looked after
check('a sheet is an overlay', overlays.isOverlay(makeSheet('qr-sheet', 'sheet center')));
check('a modal is an overlay', overlays.isOverlay(makeSheet('confirm-dialog', 'modal')));
check('the idle warning is left alone', !overlays.isOverlay(makeSheet('idle-dialog', 'modal')));
check('a plain element is not an overlay', !overlays.isOverlay({ tagName: 'DIV', id: 'x', className: 'sheet' }));

// ---- pressing outside closes it and throws the typing away
var edit = makeSheet('edit-basic', 'sheet');
press(edit, 50, 50);
check('a press on the dimmed area closes the sheet', edit.open === false);
check('closing resets the form (nothing is saved, nothing half-typed stays)', edit.resets() === 1);

// ---- pressing inside never closes it
var inside = makeSheet('edit-contact', 'sheet');
press(inside, 300, 250);
check('a press inside the box does not close it', inside.open === true);
check('a press inside does not reset the form', inside.resets() === 0);
press(inside, 100, 100);                              // exactly on the edge: still inside
check('a press on the edge of the box is inside', inside.open === true);

// ---- the padding of a modal is part of the dialog element, so only the measured box counts
var modal = makeSheet('confirm-dialog', 'modal');
press(modal, 105, 105);                               // inside the box, in the padding
check('a press in the padding of a modal does not close it', modal.open === true);
press(modal, 600, 250);
check('a press beside a modal closes it', modal.open === false);

// ---- a text selection that starts inside and ends on the dimmed area is not a close
var drag = makeSheet('edit-emergency', 'sheet');
fire('mousedown', { target: drag, clientX: 300, clientY: 250 });     // started inside the box (the browser reports the sheet)
fire('click', { target: drag, clientX: 50, clientY: 50 });            // let go outside
check('a drag that started inside does not close the sheet', drag.open === true);

// ---- the browser closes a dialog on Escape by itself: the close is what matters
var escaped = makeSheet('review-3', 'sheet review');
escaped.close();
check('any close, such as Escape or Cancel, resets the form', escaped.resets() === 1);

// ---- an answered confirmation keeps its answer
var answered = makeSheet('confirm-dialog', 'modal');
answered.returnValue = 'ok';
answered.close();
check('a confirmation that was answered Yes is not reset', answered.resets() === 0);

// ---- focus goes back to the button that opened the pop-up
var focused = null;
var opener = { tagName: 'BUTTON', nodeType: 1, focus: function () { focused = 'opener'; }, getAttribute: function () { return null; }, parentNode: null };
var shown = makeSheet('edit-weight', 'sheet');
shown.openedBy = opener;
shown.close();
check('the focus goes back to the button that opened the sheet', focused === 'opener');
check('it is forgotten after that', shown.openedBy === null);

if (failed === 0) {
  WScript.Echo('ALL PASS (' + passed + ' checks)');
  WScript.Quit(0);
}
WScript.Echo(failed + ' check(s) failed');
WScript.Quit(1);
