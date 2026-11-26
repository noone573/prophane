(function () {
  'use strict';

  var DEFAULT_CENTER = [11.706149247057967, 124.42393797354536];

  var pickerEl = document.getElementById('picker');
  var latInput = document.getElementById('id_latitude');
  var lngInput = document.getElementById('id_longitude');
  var coordsEl = document.getElementById('coords');
  var marker = null;

  var map = L.map(pickerEl).setView(DEFAULT_CENTER, 17);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);

  var pin = L.divIcon({
    className: '',
    html: '<div class="map-pin"><span></span></div>',
    iconSize: [34, 34],
    iconAnchor: [17, 34]
  });

  function place(lat, lng) {
    lat = Number(lat.toFixed(6));
    lng = Number(lng.toFixed(6));
    if (marker) {
      marker.setLatLng([lat, lng]);
    } else {
      marker = L.marker([lat, lng], { icon: pin, draggable: true }).addTo(map);
      marker.on('dragend', function () {
        var p = marker.getLatLng();
        place(p.lat, p.lng);
      });
    }
    latInput.value = lat;
    lngInput.value = lng;
    coordsEl.textContent = lat + ', ' + lng + ' (drag the pin to adjust)';
  }

  map.on('click', function (e) { place(e.latlng.lat, e.latlng.lng); });

  var startLat = parseFloat(pickerEl.dataset.lat);
  var startLng = parseFloat(pickerEl.dataset.lng);
  if (!isNaN(startLat) && !isNaN(startLng)) {
    map.setView([startLat, startLng], 17);
    place(startLat, startLng);
  } else if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(function (pos) {
      if (marker) return;
      map.setView([pos.coords.latitude, pos.coords.longitude], 17);
      place(pos.coords.latitude, pos.coords.longitude);
    }, function () {}, { timeout: 8000, maximumAge: 60000 });
  }

  // Show price and stock fields only for the tanks being sold
  var checkboxes = document.querySelectorAll('#tank-choices input[type="checkbox"]');
  function syncTankFields() {
    checkboxes.forEach(function (box) {
      var section = document.querySelector('.tank-fields[data-tank="' + CSS.escape(box.value) + '"]');
      if (section) section.classList.toggle('hidden', !box.checked);
    });
  }
  checkboxes.forEach(function (box) { box.addEventListener('change', syncTankFields); });
  syncTankFields();

  // Photo preview
  var photoInput = document.getElementById('id_owner_photo');
  var preview = document.getElementById('photo-preview');
  photoInput.addEventListener('change', function () {
    var file = photoInput.files[0];
    if (!file) {
      preview.classList.add('hidden');
      return;
    }
    preview.src = URL.createObjectURL(file);
    preview.classList.remove('hidden');
  });

  document.getElementById('store-form').addEventListener('submit', function (event) {
    if (!latInput.value || !lngInput.value) {
      event.preventDefault();
      coordsEl.textContent = 'Click the map to set your store location first.';
      coordsEl.classList.add('text-bad');
      pickerEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
})();
