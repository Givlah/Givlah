// Progressive enhancement only: every form works without this file.
(function () {
  "use strict";

  // A saved explicit choice takes priority; auto follows the device preference.
  var motionMode = "force";
  var motionQuery = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  function validMotion(value) { return ["force", "auto", "reduce"].indexOf(value) !== -1; }
  try {
    var savedMotion = window.localStorage.getItem("givlah-motion");
    if (validMotion(savedMotion)) motionMode = savedMotion;
  } catch (e) { /* The preference also works when storage is unavailable. */ }
  var requestedMotion = new URLSearchParams(window.location.search).get("motion");
  if (validMotion(requestedMotion)) {
    motionMode = requestedMotion;
    try { window.localStorage.setItem("givlah-motion", motionMode); } catch (e) {}
  }
  function applyMotion() {
    document.documentElement.dataset.motion = motionMode === "force" || (motionMode === "auto" && !(motionQuery && motionQuery.matches)) ? "on" : "off";
    document.documentElement.dataset.motionMode = motionMode;
    document.documentElement.dataset.motionPaused = document.hidden ? "true" : "false";
  }
  applyMotion();
  if (motionQuery && motionQuery.addEventListener) motionQuery.addEventListener("change", applyMotion);
  document.addEventListener("visibilitychange", applyMotion);

  if ("serviceWorker" in navigator && window.isSecureContext) {
    window.addEventListener("load", function () { navigator.serviceWorker.register("/sw.js").catch(function () {}); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-motion-setting]").forEach(function (setting) {
      setting.hidden = false;
      var choice = setting.querySelector("[data-motion-choice]");
      choice.value = motionMode;
      choice.addEventListener("change", function () {
        if (!validMotion(choice.value)) return;
        motionMode = choice.value;
        try { window.localStorage.setItem("givlah-motion", motionMode); } catch (e) {}
        applyMotion();
      });
    });
    // Disable submit buttons while a request is pending (the server also rejects duplicates).
    document.querySelectorAll("form[data-pending-form]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        var button = form.querySelector("button[type=submit]");
        if (!button) return;
        window.setTimeout(function () {
          if (event.defaultPrevented) return;
          button.disabled = true;
          if (button.dataset.pendingLabel) button.textContent = button.dataset.pendingLabel;
        }, 0);
      });
    });

    // Re-enable buttons when the page is restored from the back/forward cache.
    window.addEventListener("pageshow", function (event) {
      if (!event.persisted) return;
      document.querySelectorAll("form[data-pending-form] button[type=submit]").forEach(function (b) { b.disabled = false; });
    });

    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (!window.confirm(form.dataset.confirm)) event.preventDefault();
      });
    });

    setupPhotoComposer();
    setupPhotoPreview();
    setupLocation();
    setupHoldProgress();
  });

  function setupHoldProgress() {
    document.querySelectorAll("[data-hold-progress]").forEach(function (bar) {
      var start = Date.parse(bar.dataset.start), end = Date.parse(bar.dataset.until);
      if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return;
      function update() {
        if (document.hidden) return;
        bar.max = end - start;
        bar.value = Math.max(0, Math.min(end - start, end - Date.now()));
        bar.hidden = false;
      }
      var timer = null;
      function pause() { window.clearInterval(timer); timer = null; }
      function resume() { update(); if (timer === null && !document.hidden) timer = window.setInterval(update, 1000); }
      resume();
      document.addEventListener("visibilitychange", function () { if (document.hidden) pause(); else resume(); });
      window.addEventListener("pagehide", pause);
      window.addEventListener("pageshow", resume);
    });
  }

  function setupPhotoPreview() {
    var input = document.querySelector("input[type=file][name=photos]");
    var preview = document.querySelector("[data-photo-preview]");
    if (!input || !preview || !window.URL) return;
    input.addEventListener("change", function () {
      preview.textContent = "";
      Array.prototype.slice.call(input.files, 0, 3).forEach(function (file) {
        var img = document.createElement("img");
        img.alt = "Selected photo preview";
        img.src = URL.createObjectURL(file);
        img.onload = function () { URL.revokeObjectURL(img.src); };
        preview.appendChild(img);
      });
      if (input.files.length > 3) {
        var note = document.createElement("p");
        note.className = "error";
        note.textContent = "Choose at most 3 photos.";
        preview.appendChild(note);
      }
    });
  }

  function setupPhotoComposer() {
    var form = document.querySelector("[data-photo-composer]");
    if (!form || !window.URL || !window.DataTransfer) return;
    var input = form.querySelector("input[type=file][name=photos]");
    // Keep the ordinary upload and complete form if file-list assignment is unsupported.
    try {
      var probe = new DataTransfer();
      Array.from(input.files).forEach(function (file) { probe.items.add(file); });
      input.files = probe.files;
    } catch (e) { return; }

    var step = form.querySelector("[data-photo-step]");
    var details = form.querySelector("[data-item-details]");
    var heading = form.querySelector("[data-composer-heading]");
    var next = form.querySelector("[data-photo-next]");
    var back = form.querySelector("[data-photo-back]");
    var close = form.querySelector("[data-photo-close]");
    var error = form.querySelector("[data-photo-error]");
    var status = form.querySelector("[data-photo-status]");
    var hero = form.querySelector("[data-photo-hero]");
    var thumbs = form.querySelector("[data-photo-thumbnails]");
    var summaryImage = form.querySelector("[data-photo-summary-image]");
    var change = form.querySelector("[data-photo-change]");
    var photos = Array.from(input.files);
    var urls = [], active = 0;

    function showError(message) {
      error.textContent = message;
      error.hidden = !message;
    }
    function showStep(showDetails, focus) {
      step.hidden = showDetails;
      details.hidden = !showDetails;
      back.hidden = !showDetails;
      close.hidden = showDetails;
      next.hidden = showDetails;
      heading.textContent = showDetails ? "Item details" : "Add photos";
      form.dataset.composerStep = showDetails ? "details" : "photos";
      if (focus) {
        heading.tabIndex = -1;
        heading.focus({preventScroll: true});
        window.scrollTo(0, 0);
      }
    }
    function selectPhoto(index) {
      active = index;
      hero.src = urls[index];
      hero.alt = "Selected item photo " + (index + 1) + " of " + photos.length;
      thumbs.querySelectorAll("[data-photo-select]").forEach(function (button, i) {
        button.setAttribute("aria-pressed", i === active ? "true" : "false");
      });
    }
    function render() {
      urls.forEach(function (url) { URL.revokeObjectURL(url); });
      urls = photos.map(function (file) { return URL.createObjectURL(file); });
      var transfer = new DataTransfer();
      photos.forEach(function (file) { transfer.items.add(file); });
      input.files = transfer.files;
      thumbs.replaceChildren();
      photos.forEach(function (file, index) {
        var tile = document.createElement("div");
        var button = document.createElement("button");
        button.type = "button";
        button.dataset.photoSelect = "";
        button.className = "photo-thumbnail";
        button.setAttribute("aria-label", "View photo " + (index + 1));
        var image = document.createElement("img");
        image.alt = "";
        image.src = urls[index];
        button.appendChild(image);
        button.addEventListener("click", function () { selectPhoto(index); });
        var remove = document.createElement("button");
        remove.type = "button";
        remove.className = "photo-remove";
        remove.textContent = "Remove";
        remove.setAttribute("aria-label", "Remove photo " + (index + 1));
        remove.addEventListener("click", function () {
          photos.splice(index, 1);
          showError("");
          render();
          var target = thumbs.querySelector("[data-photo-select]") || form.querySelector("[data-photo-camera]");
          target.focus();
        });
        tile.append(button, remove);
        thumbs.appendChild(tile);
      });
      var hasPhotos = photos.length > 0;
      hero.hidden = !hasPhotos;
      summaryImage.hidden = !hasPhotos;
      form.querySelector("[data-photo-empty]").hidden = hasPhotos;
      form.classList.toggle("has-photos", hasPhotos);
      next.disabled = !hasPhotos;
      if (hasPhotos) {
        selectPhoto(Math.min(active, photos.length - 1));
        summaryImage.src = urls[0];
      } else {
        hero.removeAttribute("src");
        summaryImage.removeAttribute("src");
      }
      var count = photos.length + (photos.length === 1 ? " photo selected" : " photos selected");
      form.querySelector("[data-photo-count]").textContent = hasPhotos ? count : "Add photos before publishing";
      change.textContent = hasPhotos ? "Change photos" : "Add photos again";
      status.textContent = hasPhotos ? count + ". You can add up to 3." : "JPEG, PNG or WebP. Up to 5 MB per photo.";
    }
    function picker(camera) {
      var chooser = document.createElement("input");
      chooser.type = "file";
      chooser.accept = input.accept;
      chooser.multiple = !camera;
      if (camera) chooser.setAttribute("capture", "environment");
      chooser.hidden = true;
      form.appendChild(chooser);
      chooser.addEventListener("change", function () {
        var selected = Array.from(chooser.files);
        chooser.remove();
        if (!selected.length) return;
        if (selected.some(function (file) {
          return !(/image\/(jpeg|png|webp)$/i.test(file.type) || (!file.type && /\.(jpe?g|png|webp)$/i.test(file.name)));
        })) { showError("Choose JPEG, PNG or WebP photos."); return; }
        if (selected.some(function (file) { return file.size > 5 * 1024 * 1024; })) {
          showError("Each photo must be 5 MB or smaller."); return;
        }
        if (photos.length + selected.length > 3) {
          showError("Choose at most 3 photos. Remove a selected photo to make room."); return;
        }
        var sources = form.querySelectorAll("[data-photo-sources] button");
        sources.forEach(function (button) { button.disabled = true; });
        next.disabled = true;
        status.textContent = "Preparing photo previews...";
        Promise.all(selected.map(function (file) {
          return new Promise(function (resolve, reject) {
            var image = new Image(), url = URL.createObjectURL(file);
            image.onload = function () {
              URL.revokeObjectURL(url);
              if (image.naturalWidth * image.naturalHeight > 12000000) reject("Each photo must be 12 megapixels or smaller.");
              else resolve();
            };
            image.onerror = function () { URL.revokeObjectURL(url); reject("That file isn't a readable photo. Choose another."); };
            image.src = url;
          });
        })).then(function () {
          photos = photos.concat(selected);
          showError("");
          render();
          next.focus();
        }).catch(function (message) {
          render();
          showError(message);
        }).finally(function () {
          sources.forEach(function (button) { button.disabled = false; });
        });
      });
      chooser.addEventListener("cancel", function () { chooser.remove(); });
      chooser.click();
    }
    form.querySelector("[data-photo-camera]").addEventListener("click", function () { picker(true); });
    form.querySelector("[data-photo-library]").addEventListener("click", function () { picker(false); });
    next.addEventListener("click", function () {
      if (!photos.length) return;
      // The device/browser Back action returns to photos before leaving the composer.
      try { window.history.pushState({givlahComposer: "details"}, ""); } catch (e) {}
      showStep(true, true);
    });
    function backToPhotos() {
      if (window.history.state && window.history.state.givlahComposer === "details") window.history.back();
      else showStep(false, true);
    }
    back.addEventListener("click", backToPhotos);
    change.addEventListener("click", backToPhotos);
    window.addEventListener("popstate", function (event) {
      showStep(!!(event.state && event.state.givlahComposer === "details" && photos.length), true);
    });
    form.addEventListener("submit", function (event) {
      if (!photos.length || !step.hidden) {
        event.preventDefault();
        showStep(false, true);
        if (!photos.length) showError("Add at least one photo before continuing.");
        else next.focus();
      }
    });
    window.addEventListener("pagehide", function (event) {
      if (!event.persisted) urls.forEach(function (url) { URL.revokeObjectURL(url); });
    });
    form.querySelector("[data-photo-native]").hidden = true;
    form.querySelector("[data-photo-fallback]").hidden = true;
    form.querySelector("[data-photo-sources]").hidden = false;
    form.querySelector("[data-photo-summary]").hidden = false;
    render();
    showStep(form.dataset.formBound === "true", false);
  }

  function setupLocation() {
    var box = document.querySelector("[data-location]");
    if (!box) return;
    var button = box.querySelector("[data-locate]");
    var status = box.querySelector("[data-locate-status]");
    var lat = box.querySelector("input[name=latitude]");
    var lng = box.querySelector("input[name=longitude]");
    var zoneSelect = box.querySelector("select[name=zone]");
    var zones = [];
    try { zones = JSON.parse(box.dataset.zones || "[]"); } catch (e) { zones = []; }

    if (lat.value && lng.value) {
      status.textContent = "Using your saved location. Check the area and pickup details below.";
    }
    if (!("geolocation" in navigator) || !window.isSecureContext) {
      status.textContent = "Location isn't available on this connection. Choose your area and type the pickup details.";
      return;
    }
    button.hidden = false;

    button.addEventListener("click", function () {
      button.disabled = true;
      status.textContent = "Finding your location…";
      navigator.geolocation.getCurrentPosition(function (pos) {
        button.disabled = false;
        lat.value = pos.coords.latitude.toFixed(6);
        lng.value = pos.coords.longitude.toFixed(6);
        var nearest = nearestZone(zones, pos.coords.latitude, pos.coords.longitude);
        if (nearest && zoneSelect) {
          zoneSelect.value = String(nearest.id);
          status.textContent = "Location found near " + nearest.name + ". Check the area is right and add your pickup details.";
        } else {
          status.textContent = "Location found. Choose the right area and add your pickup details.";
        }
        if (zoneSelect) zoneSelect.focus();
      }, function (err) {
        button.disabled = false;
        lat.value = "";
        lng.value = "";
        var reason = err.code === 1 ? "Location permission was denied."
          : err.code === 3 ? "Finding your location took too long."
          : "Your location couldn't be found.";
        status.textContent = reason + " Choose your area and type the pickup details instead.";
      }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
    });
  }

  function nearestZone(zones, latitude, longitude) {
    var best = null, bestDist = Infinity;
    zones.forEach(function (z) {
      var dLat = z.lat - latitude, dLng = (z.lng - longitude) * Math.cos(latitude * Math.PI / 180);
      var d = dLat * dLat + dLng * dLng;
      if (d < bestDist) { bestDist = d; best = z; }
    });
    return best;
  }
})();
