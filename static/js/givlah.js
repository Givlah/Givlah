// Progressive enhancement only: every form works without this file.
(function () {
  "use strict";

  if ("serviceWorker" in navigator && window.isSecureContext) {
    window.addEventListener("load", function () { navigator.serviceWorker.register("/sw.js").catch(function () {}); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    // Disable submit buttons while a request is pending (the server also rejects duplicates).
    document.querySelectorAll("form[data-pending-form]").forEach(function (form) {
      form.addEventListener("submit", function () {
        var button = form.querySelector("button[type=submit]");
        if (!button) return;
        window.setTimeout(function () {
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

    setupPhotoPreview();
    setupLocation();
  });

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
