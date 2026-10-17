// Formatting and form rules, with no page code in it, so they can be tested on their own.
// The server checks the same rules again: this file only gives quicker feedback while typing.
// Written in plain old-style JavaScript (var, function) so the test runner on Windows can execute it.
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.MedScanFormat = factory();
  }
})(this, function () {
  var MAX_AGE_YEARS = 120;

  function trim(text) {
    return String(text).replace(/^\s+|\s+$/g, '');
  }

  function digitsOf(text) {
    return String(text).replace(/\D/g, '');
  }

  // ---- mobile numbers: always shown as 0917 123 4567 ----
  function formatMobile(text) {
    var digits = digitsOf(text);
    if (digits.substr(0, 2) === '63') {
      digits = '0' + digits.substr(2);        // +63 917 ... and 63917 ... become 0917 ...
    } else if (digits.charAt(0) === '9') {
      digits = '0' + digits;                  // 917 ... becomes 0917 ...
    }
    digits = digits.substr(0, 11);
    var out = digits.substr(0, 4);
    if (digits.length > 4) { out += ' ' + digits.substr(4, 3); }
    if (digits.length > 7) { out += ' ' + digits.substr(7, 4); }
    return out;
  }

  function mobileProblem(text) {
    var digits = digitsOf(formatMobile(text));
    if (digits.length === 0) { return ''; }   // An empty number is fine: the field is optional.
    if (digits.length < 11 || digits.substr(0, 2) !== '09') {
      return 'Enter a mobile number like 0917 123 4567.';
    }
    return '';
  }

  // The same, for a patient's number, which cannot be left empty (it is their way back in if they forget the ID).
  function mobileRequiredProblem(text) {
    if (digitsOf(formatMobile(text)).length === 0) { return 'Enter your mobile number.'; }
    return mobileProblem(text);
  }

  // ---- dates of birth: typed as MM/DD/YYYY ----
  function formatDate(text) {
    var typed = trim(text);
    var iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(typed);
    if (iso) { return iso[2] + '/' + iso[3] + '/' + iso[1]; }   // Handles a date pasted as 2004-04-04 and turns it into 04/04/2004.
    if (/[\/\-. ]/.test(typed)) {
      // typed with separators (4/4/2004, 04-04-2004): keep the groups, and a separator after one digit pads it
      var groups = [];
      var current = '';
      for (var c = 0; c < typed.length; c++) {
        var ch = typed.charAt(c);
        if (/\d/.test(ch)) {
          current += ch;
        } else if (/[\/\-. ]/.test(ch) && current !== '') {
          groups.push(current);
          current = '';
        }
      }
      var trailing = current === '';            // the text ended with a separator
      if (!trailing) { groups.push(current); }
      if (groups.length === 0) { return ''; }
      // Month and day take 2 digits, the year 4. Digits that do not fit move on to the next group, so typing
      // 04/04 and then 2 gives 04/04/2 instead of losing the 2.
      var parts = [];
      var carry = '';
      for (var g = 0; g < 3 && (g < groups.length || carry !== ''); g++) {
        var digits = carry + (g < groups.length ? groups[g] : '');
        var size = g < 2 ? 2 : 4;
        var piece = digits.substr(0, size);
        carry = digits.substr(size);
        if (g < 2 && piece.length === 1 && carry === '' && (g < groups.length - 1 || trailing)) { piece = '0' + piece; }
        parts.push(piece);
      }
      return parts.join('/') + (trailing && parts.length < 3 && carry === '' ? '/' : '');
    }
    var run = digitsOf(typed).substr(0, 8);                      // typed as plain digits: 04042004
    var out = run.substr(0, 2);
    if (run.length > 2) { out += '/' + run.substr(2, 2); }
    if (run.length > 4) { out += '/' + run.substr(4, 4); }
    return out;
  }

  // {year, month, day} for a real calendar date written as MM/DD/YYYY, otherwise null.
  function parseDate(text) {
    var m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(trim(text));
    if (!m) { return null; }
    var year = parseInt(m[3], 10);
    var month = parseInt(m[1], 10);
    var day = parseInt(m[2], 10);
    if (year < 1900 || month < 1 || month > 12 || day < 1) { return null; }
    var check = new Date(year, month - 1, day);
    if (check.getFullYear() !== year || check.getMonth() !== month - 1 || check.getDate() !== day) { return null; }
    return { year: year, month: month, day: day };
  }

  function dateProblem(text, today) {
    var typed = trim(text);
    if (typed === '') { return 'Enter your date of birth.'; }
    if (!/^\d{2}\/\d{2}\/\d{4}$/.test(typed)) { return 'Type the date as MM/DD/YYYY, like 04/04/2004.'; }
    var parts = parseDate(typed);
    if (!parts) { return 'That date does not exist.'; }
    var born = new Date(parts.year, parts.month - 1, parts.day).getTime();
    var now = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
    if (born > now) { return 'Date of birth cannot be in the future.'; }
    if (parts.year < today.getFullYear() - MAX_AGE_YEARS) {
      return 'Date of birth cannot be more than ' + MAX_AGE_YEARS + ' years ago.';
    }
    return '';
  }

  // Age in whole years on `today` for the parts returned by parseDate.
  function ageOn(parts, today) {
    var age = today.getFullYear() - parts.year;
    var month = today.getMonth() + 1;
    if (month < parts.month || (month === parts.month && today.getDate() < parts.day)) { age = age - 1; }
    return age;
  }

  // 2004-04-04 (what the calendar gives) to 04/04/2004. Empty if it is not a date like that.
  function isoToTyped(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trim(iso));
    return m ? m[2] + '/' + m[3] + '/' + m[1] : '';
  }

  // And back: 04/04/2004 to 2004-04-04, for the calendar. Empty if the text is not a real date.
  function typedToIso(text) {
    var parts = parseDate(text);
    if (!parts) { return ''; }
    function two(n) { return (n < 10 ? '0' : '') + n; }
    return parts.year + '-' + two(parts.month) + '-' + two(parts.day);
  }

  // ---- other rules (the same limits as the server) ----
  function nameProblem(text) {
    var name = trim(text);
    if (name === '') { return 'Enter your full name.'; }
    if (name.length > 100) { return 'Name is too long (at most 100 characters).'; }
    return '';
  }

  // A box that must not be left empty (the login page). `what` finishes the sentence: 'your password'.
  function requiredProblem(text, what) {
    return String(text).length === 0 || trim(text) === '' ? 'Please enter ' + what + '.' : '';
  }

  function passwordProblem(text) {
    var length = String(text).length;
    if (length === 0) { return 'Enter a password.'; }
    if (length < 6) { return 'Password needs at least 6 characters.'; }
    if (length > 25) { return 'Password can have at most 25 characters.'; }
    return '';
  }

  // Where the cursor should go after a field's text was reformatted: after the same number of digits.
  function caretAfter(oldText, oldCaret, newText) {
    var oldValue = String(oldText);
    var newValue = String(newText);
    if (oldCaret >= oldValue.length) { return newValue.length; }
    var digitsBefore = digitsOf(oldValue.substr(0, oldCaret)).length;
    if (digitsBefore === 0) { return 0; }
    var seen = 0;
    for (var i = 0; i < newValue.length; i++) {
      if (/\d/.test(newValue.charAt(i))) {
        seen = seen + 1;
        if (seen === digitsBefore) { return i + 1; }
      }
    }
    return newValue.length;
  }

  return {
    trim: trim,
    digitsOf: digitsOf,
    formatMobile: formatMobile,
    mobileProblem: mobileProblem,
    mobileRequiredProblem: mobileRequiredProblem,
    formatDate: formatDate,
    parseDate: parseDate,
    dateProblem: dateProblem,
    ageOn: ageOn,
    isoToTyped: isoToTyped,
    typedToIso: typedToIso,
    nameProblem: nameProblem,
    passwordProblem: passwordProblem,
    requiredProblem: requiredProblem,
    caretAfter: caretAfter
  };
});
