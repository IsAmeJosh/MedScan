// Runs the real gui/static/js/G_Format.js with Windows Script Host (cscript), which every Windows PC has.
// Run by tests/test_javascript.py, or by hand:  cscript //nologo tests\js\format_test.js
var fso = new ActiveXObject('Scripting.FileSystemObject');
var here = fso.GetParentFolderName(WScript.ScriptFullName);
var source = fso.OpenTextFile(here + '\\..\\..\\gui\\static\\js\\G_Format.js', 1).ReadAll();
var module = { exports: {} };
new Function('module', source)(module);
var F = module.exports;

var failures = 0;
var checks = 0;
function check(actual, expected, label) {
  checks = checks + 1;
  if (actual === expected) { return; }
  failures = failures + 1;
  WScript.Echo('FAIL - ' + label + ': got "' + actual + '", expected "' + expected + '"');
}
function fine(problem, label) { check(problem, '', label); }
function refused(problem, label) { check(problem !== '', true, label); }
var TODAY = new Date(2026, 9, 13); // 13 October 2026
var i;

// ---- mobile numbers: one shape, whatever way they are typed ----
var mobile = [
  ['', ''], ['0', '0'], ['09', '09'], ['0917', '0917'], ['09171', '0917 1'], ['0917123', '0917 123'],
  ['09171234', '0917 123 4'], ['09171234567', '0917 123 4567'], ['0917 123 4567', '0917 123 4567'],
  ['0917-123-4567', '0917 123 4567'], ['(0917) 123 4567', '0917 123 4567'],
  ['+639171234567', '0917 123 4567'], ['+63 917 123 4567', '0917 123 4567'], ['63 917 123 4567', '0917 123 4567'],
  ['639171234567', '0917 123 4567'], ['9171234567', '0917 123 4567'], ['917', '0917'], ['+63', '0'], ['+639', '09'],
  ['091712345678999', '0917 123 4567'], ['abc', ''], ['5551234', '5551 234']
];
for (i = 0; i < mobile.length; i++) { check(F.formatMobile(mobile[i][0]), mobile[i][1], 'formatMobile(' + mobile[i][0] + ')'); }
for (i = 0; i < mobile.length; i++) {
  check(F.formatMobile(F.formatMobile(mobile[i][0])), F.formatMobile(mobile[i][0]), 'formatMobile twice is the same as once: ' + mobile[i][0]);
}
var goodMobile = ['', '   ', '0917 123 4567', '+63 917 123 4567', '639171234567', '9171234567', '09171234567'];
for (i = 0; i < goodMobile.length; i++) { fine(F.mobileProblem(goodMobile[i]), 'mobile ok: "' + goodMobile[i] + '"'); }
var badMobile = ['0', '0917', '0917 123 456', '5551234567', '0817 123 4567', '12345', '+64 917 123 4567'];
for (i = 0; i < badMobile.length; i++) { refused(F.mobileProblem(badMobile[i]), 'mobile refused: ' + badMobile[i]); }

// a patient's number cannot be left empty (it is their way back in if they forget the ID)
check(F.mobileRequiredProblem(''), 'Enter your mobile number.', 'a patient must give a number');
check(F.mobileRequiredProblem('   '), 'Enter your mobile number.', 'blank is not a number');
check(F.mobileRequiredProblem('+'), 'Enter your mobile number.', 'a lone plus sign is not a number');
fine(F.mobileRequiredProblem('0917 123 4567'), 'required mobile ok');
fine(F.mobileRequiredProblem('+63 917 123 4567'), 'required mobile ok with +63');
refused(F.mobileRequiredProblem('0917'), 'required mobile too short');

// the browser keeps the cursor sensible while the text changes shape
check(F.caretAfter('09171', 5, '0917 1'), 6, 'caret stays at the end');
check(F.caretAfter('0917123', 2, '0917 123'), 2, 'caret in the middle stays after the same digit');
check(F.caretAfter('0917123', 5, '0917 123'), 6, 'caret moves past the new space');
check(F.caretAfter('0917123', 0, '0917 123'), 0, 'caret at the start stays');

// ---- dates of birth: MM/DD/YYYY, slashes appear on their own ----
var dates = [
  ['', ''], ['0', '0'], ['04', '04'], ['040', '04/0'], ['0404', '04/04'], ['04042', '04/04/2'], ['04042004', '04/04/2004'],
  ['04/04/2004', '04/04/2004'], ['4/4/2004', '04/04/2004'], ['4/', '04/'], ['4/4/', '04/04/'], ['04-04-2004', '04/04/2004'],
  ['04.04.2004', '04/04/2004'], ['2004-04-04', '04/04/2004'], ['0404200499', '04/04/2004'], ['04/04/200499', '04/04/2004'],
  ['ab12cd', '12'], ['/', ''], ['04/', '04/'], ['04/04', '04/04'],
  // digits typed after a slash must flow on into the next group, not disappear (the bug found by hand-testing)
  ['04/042', '04/04/2'], ['04/0420', '04/04/20'], ['04/04200', '04/04/200'], ['04/042004', '04/04/2004'],
  ['4/042', '04/04/2'], ['0404/', '04/04/'], ['0404/2004', '04/04/2004'], ['04/04/20045', '04/04/2004']
];
for (i = 0; i < dates.length; i++) { check(F.formatDate(dates[i][0]), dates[i][1], 'formatDate(' + dates[i][0] + ')'); }
for (i = 0; i < dates.length; i++) {
  check(F.formatDate(F.formatDate(dates[i][0])), F.formatDate(dates[i][0]), 'formatDate twice is the same as once: ' + dates[i][0]);
}

// Typing one character at a time, the way a person does: each key adds to what the box already shows.
function typeIt(format, keys) {
  var shown = '';
  for (var k = 0; k < keys.length; k++) { shown = format(shown + keys.charAt(k)); }
  return shown;
}
var datesTyped = [
  '04042004', '04/04/2004', '4/4/2004', '04/4/2004', '4/04/2004', '04-04-2004', '04.04.2004', '04 04 2004',
  '0404/2004', '04/042004', '4-4-2004'
];
for (i = 0; i < datesTyped.length; i++) { check(typeIt(F.formatDate, datesTyped[i]), '04/04/2004', 'typing a date: ' + datesTyped[i]); }
check(typeIt(F.formatDate, '12/25/1999'), '12/25/1999', 'typing 12/25/1999');
check(typeIt(F.formatDate, '1/1/2000'), '01/01/2000', 'typing 1/1/2000');
check(typeIt(F.formatDate, '04/04/20045'), '04/04/2004', 'a fifth year digit is ignored');
// the exact steps that failed: 04/04, then keep typing the year
check(typeIt(F.formatDate, '04/04'), '04/04', 'typed 04/04');
check(typeIt(F.formatDate, '04/042'), '04/04/2', 'typed 04/04 then 2');
check(typeIt(F.formatDate, '04/0420'), '04/04/20', 'typed 04/04 then 20');
// deleting works too: Backspace on "04/04/2" gives "04/04/", and once more gives "04/04"
check(F.formatDate('04/04/'), '04/04/', 'delete the 2: the slash stays');
check(F.formatDate('04/04'), '04/04', 'delete the slash: it does not come back');

var mobilesTyped = ['+639171234567', '639171234567', '09171234567', '9171234567', '0917 123 4567', '(0917) 123-4567', '+63 917 123 4567'];
for (i = 0; i < mobilesTyped.length; i++) { check(typeIt(F.formatMobile, mobilesTyped[i]), '0917 123 4567', 'typing a mobile number: ' + mobilesTyped[i]); }

var goodDates = ['04/04/2004', '02/29/2000', '12/31/1999', '10/13/2026', '01/01/1907'];
for (i = 0; i < goodDates.length; i++) { fine(F.dateProblem(goodDates[i], TODAY), 'date ok: ' + goodDates[i]); }
var badDates = ['', '04', '04/04', '04/04/04', '04/04/200', '13/01/2004', '00/10/2004', '02/30/2004', '02/29/2001',
                '04/31/2004', '10/14/2026', '01/01/2027', '12/31/1905', '04/04/1850', 'aa/bb/cccc'];
for (i = 0; i < badDates.length; i++) { refused(F.dateProblem(badDates[i], TODAY), 'date refused: "' + badDates[i] + '"'); }
check(F.dateProblem('10/14/2026', TODAY), 'Date of birth cannot be in the future.', 'tomorrow is in the future');
check(F.dateProblem('12/31/1905', TODAY), 'Date of birth cannot be more than 120 years ago.', 'too old');
check(F.dateProblem('04/04/04', TODAY), 'Type the date as MM/DD/YYYY, like 04/04/2004.', 'a two digit year is refused with the format shown');
check(F.dateProblem('02/30/2004', TODAY), 'That date does not exist.', 'a day that does not exist');

// age, including the birthday itself and the day before it
check(F.ageOn(F.parseDate('10/13/1996'), TODAY), 30, 'birthday today');
check(F.ageOn(F.parseDate('10/14/1996'), TODAY), 29, 'birthday tomorrow');
check(F.ageOn(F.parseDate('10/12/1996'), TODAY), 30, 'birthday yesterday');
check(F.ageOn(F.parseDate('04/04/2004'), TODAY), 22, '04/04/2004');
check(F.ageOn(F.parseDate('02/29/2000'), TODAY), 26, 'leap day birthday');
check(F.ageOn(F.parseDate('10/13/2026'), TODAY), 0, 'born today');

// the calendar button's format and ours
check(F.isoToTyped('2004-04-04'), '04/04/2004', 'calendar value to typed');
check(F.isoToTyped(''), '', 'empty calendar value');
check(F.isoToTyped('garbage'), '', 'garbage calendar value');
check(F.typedToIso('04/04/2004'), '2004-04-04', 'typed to calendar value');
check(F.typedToIso('04/04'), '', 'incomplete typed date has no calendar value');
check(F.typedToIso('02/30/2004'), '', 'impossible date has no calendar value');

// ---- name and password: the same limits as the server ----
fine(F.nameProblem('Juan Dela Cruz'), 'name ok');
refused(F.nameProblem(''), 'empty name');
refused(F.nameProblem('    '), 'blank name');
fine(F.nameProblem(new Array(101).join('a')), 'name of exactly 100 characters');   // 100 a's
refused(F.nameProblem(new Array(103).join('a')), 'name of 102 characters');
check(F.passwordProblem(''), 'Enter a password.', 'no password');
check(F.passwordProblem('12345'), 'Password needs at least 6 characters.', '5 characters');
fine(F.passwordProblem('123456'), '6 characters');
check(F.requiredProblem('', 'your password'), 'Please enter your password.', 'empty login box');
check(F.requiredProblem('   ', 'your ID or mobile number'), 'Please enter your ID or mobile number.', 'spaces only');
fine(F.requiredProblem('1001', 'your ID or mobile number'), 'login ID typed');
fine(F.passwordProblem(new Array(26).join('p')), '25 characters');
check(F.passwordProblem(new Array(28).join('p')), 'Password can have at most 25 characters.', '27 characters');
fine(F.passwordProblem('pass word'), 'spaces are allowed');

if (failures === 0) {
  WScript.Echo('ALL PASS (' + checks + ' checks)');
  WScript.Quit(0);
} else {
  WScript.Echo(failures + ' of ' + checks + ' checks failed');
  WScript.Quit(1);
}
