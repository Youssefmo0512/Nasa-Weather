document.addEventListener("DOMContentLoaded", () => {
  const conditionInput = document.getElementById("condition");
  const conditionButtons = document.querySelectorAll("[data-condition]");
  const placeInput = document.getElementById("place");
  const latInput = document.getElementById("lat");
  const lonInput = document.getElementById("lon");
  const mapElement = document.getElementById("map");
  const form = document.getElementById("weatherForm");
  const submitButton = document.getElementById("submitButton");
  const dateInput = document.getElementById("targetDate");

  const setSelectedCondition = (value) => {
    conditionButtons.forEach((button) => {
      button.classList.toggle("is-selected", button.dataset.condition === value);
    });
    if (conditionInput) {
      conditionInput.value = value;
    }
  };

  conditionButtons.forEach((button) => {
    button.addEventListener("click", () => setSelectedCondition(button.dataset.condition));
  });

  if (dateInput && !dateInput.value) {
    const now = new Date();
    now.setDate(now.getDate() + 14);
    dateInput.value = now.toISOString().split("T")[0];
  }

  if (conditionInput?.value) {
    setSelectedCondition(conditionInput.value);
  }

  let globalMap = null;
  let globalUpdateMarker = null;

  if (mapElement && window.L) {
    const initialLat = parseFloat(latInput?.value || "26.8206");
    const initialLon = parseFloat(lonInput?.value || "30.8025");
    const map = L.map("map", { zoomControl: false }).setView([initialLat, initialLon], latInput?.value && lonInput?.value ? 7 : 5);
    L.control.zoom({ position: "bottomright" }).addTo(map);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 18
    }).addTo(map);

    const icon = L.divIcon({
      className: "",
      html: '<div class="map-marker"></div>',
      iconSize: [18, 18],
      iconAnchor: [9, 9]
    });

    let marker = null;

    const updateMarker = (lat, lon, label) => {
      if (marker) {
        marker.remove();
      }

      marker = L.marker([lat, lon], { icon }).addTo(map);
      marker.bindPopup(label).openPopup();
      if (latInput) latInput.value = Number(lat).toFixed(5);
      if (lonInput) lonInput.value = Number(lon).toFixed(5);
      if (placeInput && (!placeInput.value.trim() || placeInput.value.includes(","))) {
        placeInput.value = label;
      }
    };

    globalMap = map;
    globalUpdateMarker = updateMarker;

    if (latInput?.value && lonInput?.value) {
      updateMarker(initialLat, initialLon, placeInput?.value || `${initialLat.toFixed(5)}, ${initialLon.toFixed(5)}`);
    }

    map.on("click", (event) => {
      const lat = event.latlng.lat;
      const lon = event.latlng.lng;
      const label = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
      updateMarker(lat, lon, label);
      map.flyTo([lat, lon], Math.max(map.getZoom(), 7), { duration: 1.2 });
    });
  }

  const geoButton = document.getElementById("geoButton");
  if (geoButton) {
    geoButton.addEventListener("click", () => {
      if (!navigator.geolocation) {
        window.alert("Geolocation is not supported by your browser.");
        return;
      }
      geoButton.disabled = true;
      geoButton.style.opacity = "0.5";
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const lat = position.coords.latitude;
          const lon = position.coords.longitude;
          const label = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
          if (placeInput) placeInput.value = label;
          if (latInput) latInput.value = lat.toFixed(5);
          if (lonInput) lonInput.value = lon.toFixed(5);
          
          if (typeof globalUpdateMarker === "function") {
            globalUpdateMarker(lat, lon, label);
          }
          if (globalMap) {
            globalMap.flyTo([lat, lon], Math.max(globalMap.getZoom(), 8), { duration: 1.2 });
          }

          geoButton.disabled = false;
          geoButton.style.opacity = "1";
        },
        (error) => {
          window.alert("Unable to retrieve your location: " + error.message);
          geoButton.disabled = false;
          geoButton.style.opacity = "1";
        }
      );
    });
  }

  if (form && submitButton) {
    form.addEventListener("submit", (event) => {
      submitButton.classList.add("is-loading");
      submitButton.disabled = true;
    });
  }

  const reveals = document.querySelectorAll(".reveal");
  if (reveals.length && "IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.16 });

    reveals.forEach((element, index) => {
      element.style.transitionDelay = `${Math.min(index * 60, 320)}ms`;
      observer.observe(element);
    });
  } else {
    reveals.forEach((element) => element.classList.add("is-visible"));
  }
});
