(function () {
  'use strict';

  // Top nav: drop to icon-only buttons only when the labels don't fit
  var topbar = document.querySelector('.topbar');
  var nav = topbar && topbar.querySelector('.nav');
  if (nav) {
    var LEVELS = ['compact-1', 'compact-2', 'compact-3'];
    var fitNav = function () {
      topbar.classList.remove.apply(topbar.classList, LEVELS);
      for (var i = 0; i < LEVELS.length && nav.scrollWidth > nav.clientWidth + 1; i++) {
        topbar.classList.add(LEVELS[i]);
      }
    };
    fitNav();
    if ('ResizeObserver' in window) {
      new ResizeObserver(fitNav).observe(topbar);
    } else {
      window.addEventListener('resize', fitNav);
    }
  }

  // Ask before submitting forms marked data-confirm (or buttons marked data-confirm)
  document.addEventListener('submit', function (event) {
    var form = event.target;
    var submitter = event.submitter;
    var message = (submitter && submitter.dataset.confirm) || form.dataset.confirm;
    if (message && !window.confirm(message)) {
      event.preventDefault();
    }
  });

  // Review forms: rejecting needs a written reason
  document.querySelectorAll('form[data-review-form]').forEach(function (form) {
    var reason = form.querySelector('textarea[name="rejection_reason"]');
    form.addEventListener('submit', function (event) {
      var submitter = event.submitter;
      if (submitter && submitter.hasAttribute('data-needs-reason') && reason && !reason.value.trim()) {
        event.preventDefault();
        reason.focus();
        reason.setCustomValidity('Add a reason before rejecting.');
        reason.reportValidity();
      }
    });
    if (reason) {
      reason.addEventListener('input', function () { reason.setCustomValidity(''); });
    }
  });

  // Client-side list filters: <input data-filter="#list"> filters children with data-search
  document.querySelectorAll('input[data-filter]').forEach(function (input) {
    var list = document.querySelector(input.dataset.filter);
    var empty = document.querySelector('[data-filter-empty="' + input.dataset.filter + '"]');
    if (!list) return;
    var items = list.querySelectorAll('[data-search]');
    input.addEventListener('input', function () {
      var q = input.value.trim().toLowerCase();
      var shown = 0;
      items.forEach(function (item) {
        var match = !q || item.dataset.search.indexOf(q) !== -1;
        item.classList.toggle('hidden', !match);
        if (match) shown++;
      });
      list.classList.toggle('hidden', shown === 0);
      if (empty) empty.classList.toggle('hidden', shown !== 0);
    });
  });

  document.querySelectorAll('[data-print]').forEach(function (button) {
    button.addEventListener('click', function () { window.print(); });
  });

  // Floating messages on the map page fade out on their own
  document.querySelectorAll('[data-autohide]').forEach(function (el) {
    setTimeout(function () { el.remove(); }, 6000);
    el.addEventListener('click', function () { el.remove(); });
  });

  // Prevent double submits
  document.addEventListener('submit', function (event) {
    if (event.defaultPrevented) return;
    var button = event.submitter;
    if (button && button.tagName === 'BUTTON') {
      setTimeout(function () { button.disabled = true; }, 0);
    }
  });
})();
