// Turns a comma-separated text field (allergies, surgeries, medications) into chips you add and remove.
// The original field stays on the page, hidden, holding the same comma-separated text, so the form is
// submitted exactly as before. Without this file the plain text field simply keeps working.
(function () {
  function each(list, action) {
    for (var i = 0; i < list.length; i++) { action(list[i], i); }
  }

  function splitList(text) {
    var out = [];
    each(String(text).split(','), function (piece) {
      var item = piece.replace(/^\s+|\s+$/g, '');
      if (item) { out.push(item); }
    });
    return out;
  }

  function setup(original) {
    var items = [];
    var wrap = document.createElement('div');
    wrap.className = 'chips';
    var typed = document.createElement('input');
    typed.type = 'text';
    typed.className = 'chip-input';
    typed.maxLength = 200;
    typed.placeholder = original.getAttribute('placeholder') || 'Type and press Enter';
    typed.setAttribute('aria-label', original.getAttribute('aria-label') || 'Add an item');
    wrap.appendChild(typed);
    original.type = 'hidden';
    if (original.id) {                                  // clicking the label should land in the typing box
      var label = document.querySelector('label[for="' + original.id + '"]');
      typed.id = original.id + '-chips';
      if (label) { label.setAttribute('for', typed.id); }
    }
    original.parentNode.insertBefore(wrap, original.nextSibling);

    function sync() {
      original.value = items.join(', ');
      each(wrap.querySelectorAll('.chip'), function (chip) { wrap.removeChild(chip); });
      each(items, function (item, index) {
        var chip = document.createElement('span');
        chip.className = 'chip';
        chip.appendChild(document.createTextNode(item));
        var remove = document.createElement('button');
        remove.type = 'button';
        remove.setAttribute('aria-label', 'Remove ' + item);
        remove.innerHTML = '&times;';
        remove.addEventListener('click', function () { items.splice(index, 1); sync(); typed.focus(); });
        chip.appendChild(remove);
        wrap.insertBefore(chip, typed);
      });
    }

    function exists(item) {
      for (var i = 0; i < items.length; i++) {
        if (items[i].toLowerCase() === item.toLowerCase()) { return true; }
      }
      return false;
    }

    function add(text) {
      var item = text.replace(/^\s+|\s+$/g, '');
      if (item && !exists(item)) { items.push(item); }
    }

    function commit() {
      if (typed.value) { each(splitList(typed.value), add); typed.value = ''; sync(); }
    }

    typed.addEventListener('input', function () {
      if (typed.value.indexOf(',') === -1) { return; }          // a comma (or a pasted list) finishes the items before it
      var pieces = typed.value.split(',');
      var last = pieces.pop();
      each(pieces, add);
      typed.value = last;
      sync();
    });
    typed.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') { event.preventDefault(); commit(); }
      if (event.key === 'Backspace' && typed.value === '' && items.length) { items.pop(); sync(); }
    });
    typed.addEventListener('blur', commit);
    wrap.addEventListener('click', function (event) { if (event.target === wrap) { typed.focus(); } });
    if (original.form) { original.form.addEventListener('submit', commit, true); }

    each(splitList(original.value), add);
    sync();
  }

  each(document.querySelectorAll('[data-chips]'), setup);
})();
