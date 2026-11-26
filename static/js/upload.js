(function () {
  'use strict';

  var MAX_BYTES = 5 * 1024 * 1024;
  var TYPES = ['image/jpeg', 'image/png'];

  var zone = document.getElementById('dropzone');
  var input = document.getElementById('pickup-proof');
  var label = document.getElementById('file-label');
  var preview = document.getElementById('proof-preview');
  var button = document.getElementById('upload-btn');
  var defaultLabel = label.textContent;

  function reject(message) {
    input.value = '';
    label.textContent = message;
    label.classList.add('text-bad');
    preview.classList.add('hidden');
    button.disabled = true;
  }

  function handle(file) {
    label.classList.remove('text-bad');
    if (!file) {
      label.textContent = defaultLabel;
      button.disabled = true;
      return;
    }
    if (TYPES.indexOf(file.type) === -1) return reject('Only JPG and PNG photos are accepted.');
    if (file.size > MAX_BYTES) return reject('That photo is over 5 MB. Choose a smaller one.');

    label.textContent = file.name + ' · ' + (file.size / 1024 / 1024).toFixed(1) + ' MB';
    preview.src = URL.createObjectURL(file);
    preview.classList.remove('hidden');
    button.disabled = false;
  }

  input.addEventListener('change', function () { handle(input.files[0]); });

  ['dragenter', 'dragover'].forEach(function (name) {
    zone.addEventListener(name, function (e) {
      e.preventDefault();
      zone.classList.add('is-over');
    });
  });
  ['dragleave', 'drop'].forEach(function (name) {
    zone.addEventListener(name, function (e) {
      e.preventDefault();
      zone.classList.remove('is-over');
    });
  });
  zone.addEventListener('drop', function (e) {
    if (e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      handle(input.files[0]);
    }
  });

  document.getElementById('upload-form').addEventListener('submit', function () {
    button.textContent = 'Uploading...';
  });
})();
