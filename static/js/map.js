(function () {
  'use strict';

  var DEFAULT_CENTER = [11.706149247057967, 124.42393797354536];
  var stores = JSON.parse(document.getElementById('stores-data').textContent);

  var mapEl = document.getElementById('map');
  var listEl = document.getElementById('store-list');
  var emptyEl = document.getElementById('store-empty');
  var searchEl = document.getElementById('store-search');

  var sheet = document.getElementById('store-sheet');
  var form = document.getElementById('reserve-form');
  var tanksEl = document.getElementById('sheet-tanks');
  var noTanksEl = document.getElementById('sheet-no-tanks');
  var orderEl = document.getElementById('sheet-order');
  var qtyInput = document.getElementById('qty');
  var qtyOut = document.getElementById('qty-out');
  var totalEl = document.getElementById('sheet-total');
  var reserveBtn = document.getElementById('reserve-btn');
  var nameInput = document.getElementById('buyer-name');
  var maxQty = parseInt(qtyInput.dataset.max, 10) || 5;

  var peso = new Intl.NumberFormat('en-PH', { style: 'currency', currency: 'PHP' });
  var markers = {};
  var current = null;
  var selected = null;

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function inStock(store) {
    return store.tanks.filter(function (t) { return t.stock > 0; });
  }

  function cheapest(store) {
    var prices = inStock(store).map(function (t) { return parseFloat(t.price); });
    return prices.length ? Math.min.apply(null, prices) : null;
  }

  // Map

  var map = L.map(mapEl, { center: DEFAULT_CENTER, zoom: 17, maxZoom: 19 });
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);

  function pinIcon(store, active) {
    var count = inStock(store).length;
    var cls = 'map-pin' + (count ? '' : ' is-empty') + (active ? ' is-active' : '');
    return L.divIcon({
      className: '',
      html: '<div class="' + cls + '"><span>' + count + '</span></div>',
      iconSize: [34, 34],
      iconAnchor: [17, 34]
    });
  }

  stores.forEach(function (store) {
    var marker = L.marker([store.lat, store.lng], {
      icon: pinIcon(store, false),
      title: store.name,
      keyboard: true
    }).addTo(map);
    marker.on('click', function () { openStore(store); });
    markers[store.id] = marker;
  });

  if (stores.length > 1) {
    map.fitBounds(L.latLngBounds(stores.map(function (s) { return [s.lat, s.lng]; })), { padding: [40, 40], maxZoom: 17 });
  } else if (stores.length === 1) {
    map.setView([stores[0].lat, stores[0].lng], 17);
  }

  // Store list

  function renderList(query) {
    var q = (query || '').trim().toLowerCase();
    listEl.replaceChildren();
    var shown = 0;
    stores.forEach(function (store) {
      var haystack = [store.name, store.owner, store.description]
        .concat(store.tanks.map(function (t) { return t.type; }))
        .join(' ').toLowerCase();
      if (q && haystack.indexOf(q) === -1) return;
      shown++;

      var button = el('button');
      button.type = 'button';
      button.dataset.id = store.id;
      if (current && current.id === store.id) button.classList.add('is-active');

      var img = el('img', 'avatar');
      img.src = store.photo;
      img.alt = '';
      img.loading = 'lazy';

      var text = el('span', 'grow');
      text.appendChild(el('span', 'name', store.name));
      var available = inStock(store).length;
      text.appendChild(el('span', 'sub', available ? available + ' tank type' + (available > 1 ? 's' : '') + ' in stock' : 'Out of stock'));

      var from = el('span', 'from');
      var low = cheapest(store);
      if (low !== null) {
        from.appendChild(document.createTextNode('from'));
        from.appendChild(el('strong', '', peso.format(low)));
      }

      button.append(img, text, from);
      button.addEventListener('click', function () {
        map.setView([store.lat, store.lng], Math.max(map.getZoom(), 17));
        openStore(store);
      });

      var li = el('li');
      li.appendChild(button);
      listEl.appendChild(li);
    });
    emptyEl.classList.toggle('hidden', shown !== 0);
  }

  searchEl.addEventListener('input', function () { renderList(searchEl.value); });

  // Store sheet

  function setActiveMarker(store) {
    Object.keys(markers).forEach(function (id) {
      var s = stores.find(function (x) { return String(x.id) === id; });
      markers[id].setIcon(pinIcon(s, store && s.id === store.id));
    });
  }

  function updateTotal() {
    var qty = parseInt(qtyInput.value, 10) || 1;
    var max = selected ? Math.min(maxQty, selected.stock) : 1;
    sheet.querySelector('[data-step="-1"]').disabled = qty <= 1;
    sheet.querySelector('[data-step="1"]').disabled = qty >= max;
    totalEl.textContent = peso.format(selected ? parseFloat(selected.price) * qty : 0);
    reserveBtn.disabled = !selected;
  }

  function setQty(value) {
    var max = selected ? Math.min(maxQty, selected.stock) : 1;
    var qty = Math.max(1, Math.min(max, value));
    qtyInput.value = qty;
    qtyOut.textContent = qty;
    updateTotal();
  }

  function selectTank(tank) {
    selected = tank;
    form.action = form.dataset.urlTemplate.replace('/0/', '/' + tank.id + '/');
    setQty(parseInt(qtyInput.value, 10) || 1);
  }

  function openStore(store) {
    current = store;
    selected = null;
    form.removeAttribute('action');

    document.getElementById('sheet-title').textContent = store.name;
    document.getElementById('sheet-owner').textContent = 'Run by ' + store.owner;
    document.getElementById('sheet-desc').textContent = store.description || '';
    var photo = document.getElementById('sheet-photo');
    photo.src = store.photo || mapEl.dataset.defaultPhoto;

    tanksEl.replaceChildren();
    store.tanks.forEach(function (tank) {
      var out = tank.stock <= 0;
      var label = el('label', 'tank-option' + (out ? ' is-out' : ''));

      var radio = el('input');
      radio.type = 'radio';
      radio.name = 'tank';
      radio.value = tank.id;
      radio.disabled = out;
      radio.addEventListener('change', function () { selectTank(tank); });

      var img = el('img', 'thumb');
      img.src = tank.image;
      img.alt = '';

      var info = el('span', 'grow');
      info.appendChild(el('strong', '', tank.type));
      info.appendChild(el('span', 'small muted', out ? ' · Out of stock' : ' · ' + tank.stock + ' left'));

      var price = el('span', 'price', peso.format(parseFloat(tank.price)));
      price.appendChild(el('small', '', 'per tank'));

      label.append(radio, img, info, price);
      tanksEl.appendChild(label);
    });

    var anyStock = inStock(store).length > 0;
    noTanksEl.classList.toggle('hidden', store.tanks.length > 0);
    orderEl.classList.toggle('hidden', !anyStock);

    // Preselect the only option to save a tap
    var available = inStock(store);
    if (available.length === 1) {
      tanksEl.querySelector('input[value="' + available[0].id + '"]').checked = true;
      selectTank(available[0]);
    }

    setQty(1);
    setActiveMarker(store);
    renderList(searchEl.value);
    sheet.showModal();
  }

  sheet.querySelectorAll('[data-step]').forEach(function (button) {
    button.addEventListener('click', function () {
      setQty((parseInt(qtyInput.value, 10) || 1) + parseInt(button.dataset.step, 10));
    });
  });

  sheet.querySelectorAll('[data-close]').forEach(function (button) {
    button.addEventListener('click', function () { sheet.close(); });
  });

  sheet.addEventListener('click', function (event) {
    if (event.target === sheet) sheet.close();
  });

  sheet.addEventListener('close', function () {
    current = null;
    setActiveMarker(null);
    renderList(searchEl.value);
  });

  form.addEventListener('submit', function (event) {
    if (!selected || !form.action) {
      event.preventDefault();
      return;
    }
    if (!nameInput.value.trim()) {
      event.preventDefault();
      nameInput.focus();
      nameInput.reportValidity();
    }
  });

  // Collapsible store list; the choice is remembered on this device
  var shell = document.getElementById('map-shell');
  var closeBtn = document.getElementById('panel-close');
  var openBtn = document.getElementById('panel-open');
  var PANEL_KEY = 'pp-store-panel';

  function setPanel(open, remember) {
    shell.classList.toggle('is-collapsed', !open);
    closeBtn.setAttribute('aria-expanded', String(open));
    openBtn.setAttribute('aria-expanded', String(open));
    map.invalidateSize();
    if (remember) {
      try { localStorage.setItem(PANEL_KEY, open ? 'open' : 'closed'); } catch (e) {}
    }
    (open ? closeBtn : openBtn).focus({ preventScroll: true });
  }

  closeBtn.addEventListener('click', function () { setPanel(false, true); });
  openBtn.addEventListener('click', function () { setPanel(true, true); });

  try {
    if (localStorage.getItem(PANEL_KEY) === 'closed') {
      shell.classList.add('is-collapsed');
      closeBtn.setAttribute('aria-expanded', 'false');
      openBtn.setAttribute('aria-expanded', 'false');
    }
  } catch (e) {}

  renderList('');
  // The panel changes the map's size after first layout on small screens
  setTimeout(function () { map.invalidateSize(); }, 100);
})();
