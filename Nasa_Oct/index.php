<?php
require_once 'config.php';
setupSession();

$prefillPlace = htmlspecialchars($_GET['place'] ?? '');
$prefillDate = htmlspecialchars($_GET['targetDate'] ?? '');
$prefillCondition = htmlspecialchars($_GET['condition'] ?? '');
$prefillLat = htmlspecialchars($_GET['lat'] ?? '');
$prefillLon = htmlspecialchars($_GET['lon'] ?? '');
?>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>NASA Weather | Intelligence Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <link rel="stylesheet" href="./assets/css/app.css" />
</head>
<body>
  <div class="app-shell">
    <header class="topbar surface reveal is-visible">
      <div class="brand">
        <div class="brand-badge">NW</div>
        <div class="brand-text">
          <strong>NASA Weather Dashboard</strong>
          <span>AI prediction & NASA climate analytics portal</span>
        </div>
      </div>
      <div class="topbar-actions">
        <div class="mini-chip">Cairo, EG timezone</div>
      </div>
    </header>

    <section class="hero">
      <div class="hero-panel surface reveal is-visible">
        <div class="eyebrow">Advanced Climate Intel</div>
        <h1>NASA Weather Intelligence Portal</h1>
        <p>
          Access live machine learning forecasts and run long-term seasonal analyses using NASA Earth observation datasets.
        </p>
      </div>
    </section>

    <!-- Navigation Tabs -->
    <div class="tabs-nav reveal is-visible">
      <button class="tab-btn is-active" id="tab-ai-btn" onclick="switchTab('ai-dashboard', event)">AI Prediction Dashboard</button>
      <button class="tab-btn" id="tab-nasa-btn" onclick="switchTab('nasa-explorer', event)">NASA/Giovanni Dataset Explorer</button>
    </div>

    <!-- TAB 1: AI Prediction Dashboard -->
    <div id="ai-dashboard" class="tab-content is-active reveal is-visible">
      <!-- Status & Summary Cards -->
      <div class="dashboard-grid">
        <div class="dashboard-card">
          <div class="card-label">Predicted Temp</div>
          <div class="card-value" id="card-predicted-temp">--°C</div>
          <div class="card-subtext">ML model next-step prediction</div>
        </div>
        <div class="dashboard-card">
          <div class="card-label">Current Humidity</div>
          <div class="card-value" id="card-humidity">--%</div>
          <div class="card-subtext">Live streaming sensor reading</div>
        </div>
        <div class="dashboard-card">
          <div class="card-label">Current Pressure</div>
          <div class="card-value" id="card-pressure">-- hPa</div>
          <div class="card-subtext">Live streaming sensor reading</div>
        </div>
        <div class="dashboard-card">
          <div class="card-label">Forecast Condition</div>
          <div class="card-value" id="card-condition">--</div>
          <div class="card-subtext" id="card-confidence">Confidence: --%</div>
        </div>
      </div>

      <div class="dashboard-grid" style="grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));">
        <div class="dashboard-card" style="flex-direction: row; gap: 14px; align-items: center;">
          <div>
            <div class="card-label">Prediction Status</div>
            <div class="card-value" id="card-status" style="font-size: 1.3rem;">Initializing...</div>
          </div>
        </div>
        <div class="dashboard-card" style="flex-direction: row; gap: 14px; align-items: center;">
          <div>
            <div class="card-label">Last Prediction Time</div>
            <div class="card-value" id="card-last-time" style="font-size: 1.2rem;">--:--:--</div>
          </div>
        </div>
        <div class="dashboard-card" style="flex-direction: row; gap: 14px; align-items: center;">
          <div>
            <div class="card-label">Prediction Source</div>
            <div class="card-value" id="card-source" style="font-size: 1.2rem;">AI Prediction / Dataset</div>
          </div>
        </div>
      </div>

      <!-- Chart and Historical Table -->
      <div class="layout-grid" style="grid-template-columns: 1.6fr 0.9fr; margin-top: 24px;">
        <div class="surface panel">
          <h2 style="margin-top: 0;">AI Temperature Trend</h2>
          <p style="color: var(--muted); margin-bottom: 12px;">Real-time comparison of predicted vs actual sensor values.</p>
          <div class="chart-shell">
            <canvas id="predictionChart"></canvas>
          </div>
        </div>

        <div class="surface panel" style="max-height: 480px; display: flex; flex-direction: column;">
          <h2 style="margin-top: 0;">Recent Logs</h2>
          <div class="history-table-wrapper" style="flex: 1; overflow-y: auto; margin-top: 8px;">
            <table class="history-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Actual</th>
                  <th>Predicted</th>
                  <th>Forecast</th>
                </tr>
              </thead>
              <tbody id="history-table-body">
                <tr>
                  <td colspan="4" style="text-align: center; color: var(--muted);">No predictions received yet.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 2: NASA/Giovanni Dataset Explorer -->
    <div id="nasa-explorer" class="tab-content reveal">
      <div class="layout-grid">
        <!-- Form Panel -->
        <div class="surface panel">
          <div class="panel-header">
            <div>
              <h2 style="margin-top: 0;">NASA/Giovanni Seasonal Analysis</h2>
              <p>Query a place and target date to calculate the historical likelihood of extreme weather conditions from 1985 to present.</p>
            </div>
          </div>

          <form method="POST" action="results.php" id="weatherForm" class="field-grid">
            <div class="field">
              <label for="place">Location Name</label>
              <div class="input-with-action">
                <input class="control" type="text" id="place" name="place" placeholder="Cairo, Egypt or 30.0444, 31.2357" value="<?= $prefillPlace ?>" required />
                <button type="button" id="geoButton" class="btn-action" title="Use current location">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="geo-icon"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                </button>
              </div>
              <small>Input a location name or click direct coordinate points on the map.</small>
            </div>

            <div class="field">
              <label for="targetDate">Target Date</label>
              <input class="control" type="date" id="targetDate" name="targetDate" value="<?= $prefillDate ?>" required />
              <small>Allows query of specific days for seasonal trends.</small>
            </div>

            <input type="hidden" id="lat" name="lat" value="<?= $prefillLat ?>" />
            <input type="hidden" id="lon" name="lon" value="<?= $prefillLon ?>" />

            <div class="button-row" style="margin-top: 14px;">
              <button id="submitButton" type="submit" class="btn-main" style="width: 100%;">
                Run likelihood analysis
                <span class="loading-dot"></span>
              </button>
            </div>
          </form>
        </div>

        <!-- Interactive Map Panel -->
        <div class="surface map-card" style="padding: 26px;">
          <div class="panel-header" style="margin-bottom: 12px;">
            <div>
              <h2 style="margin: 0 0 4px 0;">Interactive Query Map</h2>
              <p style="margin: 0; color: var(--muted); font-size: 0.9rem;">Drop a pin to lock coordinates, coordinates will sync automatically.</p>
            </div>
          </div>
          <div class="map-shell">
            <div class="map-overlay">
              <strong>Spatial selection</strong>
              <p>Click anywhere to select coordinates. The form will sync automatically.</p>
            </div>
            <div id="map" aria-label="Interactive map for choosing location"></div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    let map = null;
    let marker = null;

    // Initialize Map Function
    function initMap() {
      if (map) return;
      const mapElement = document.getElementById("map");
      if (!mapElement) return;

      const latInput = document.getElementById("lat");
      const lonInput = document.getElementById("lon");
      const placeInput = document.getElementById("place");

      const initialLat = parseFloat(latInput.value || "30.0444");
      const initialLon = parseFloat(lonInput.value || "31.2357");

      map = L.map("map", { zoomControl: false }).setView([initialLat, initialLon], (latInput.value && lonInput.value) ? 7 : 5);
      L.control.zoom({ position: "bottomright" }).addTo(map);

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
        maxZoom: 18
      }).addTo(map);

      const icon = L.divIcon({
        className: "",
        html: '<div class="map-marker"></div>',
        iconSize: [16, 16],
        iconAnchor: [8, 8]
      });

      const updateMarker = (lat, lon, label) => {
        if (marker) {
          marker.remove();
        }
        marker = L.marker([lat, lon], { icon }).addTo(map);
        marker.bindPopup(label).openPopup();
        
        latInput.value = Number(lat).toFixed(5);
        lonInput.value = Number(lon).toFixed(5);
        placeInput.value = label;
      };

      if (latInput.value && lonInput.value) {
        updateMarker(initialLat, initialLon, placeInput.value || `${initialLat.toFixed(5)}, ${initialLon.toFixed(5)}`);
      }

      map.on("click", (e) => {
        const lat = e.latlng.lat;
        const lon = e.latlng.lng;
        const label = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
        updateMarker(lat, lon, label);
        map.flyTo([lat, lon], Math.max(map.getZoom(), 7), { duration: 0.8 });
      });

      window.globalMapInstance = map;
      window.globalUpdateMarker = updateMarker;
    }

    // Tab switching function
    function switchTab(tabId, event) {
      document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('is-active'));
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('is-active'));
      
      const targetTab = document.getElementById(tabId);
      if (targetTab) {
        targetTab.classList.add('is-active');
      }
      
      if (event) {
        event.currentTarget.classList.add('is-active');
      }

      // Initialize map or invalidate size if switching to nasa-explorer
      if (tabId === 'nasa-explorer') {
        setTimeout(() => {
          initMap();
          if (window.globalMapInstance) {
            window.globalMapInstance.invalidateSize();
          }
        }, 150);
      }
    }

    // Geolocation and chart logic
    document.addEventListener("DOMContentLoaded", () => {
      // Geolocation button
      const geoButton = document.getElementById("geoButton");
      const placeInput = document.getElementById("place");
      const latInput = document.getElementById("lat");
      const lonInput = document.getElementById("lon");

      if (geoButton) {
        geoButton.addEventListener("click", () => {
          if (!navigator.geolocation) {
            alert("Geolocation is not supported by your browser.");
            return;
          }
          geoButton.disabled = true;
          geoButton.style.opacity = "0.5";
          
          navigator.geolocation.getCurrentPosition(
            (pos) => {
              const lat = pos.coords.latitude;
              const lon = pos.coords.longitude;
              const label = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
              if (placeInput) placeInput.value = label;
              if (latInput) latInput.value = lat.toFixed(5);
              if (lonInput) lonInput.value = lon.toFixed(5);
              
              if (typeof window.globalUpdateMarker === "function") {
                window.globalUpdateMarker(lat, lon, label);
              }
              if (window.globalMapInstance) {
                window.globalMapInstance.flyTo([lat, lon], 8);
              }

              geoButton.disabled = false;
              geoButton.style.opacity = "1";
            },
            (err) => {
              alert("Unable to retrieve location: " + err.message);
              geoButton.disabled = false;
              geoButton.style.opacity = "1";
            }
          );
        });
      }

      // Form submit spinner
      const form = document.getElementById("weatherForm");
      const submitBtn = document.getElementById("submitButton");
      if (form && submitBtn) {
        form.addEventListener("submit", () => {
          submitBtn.classList.add("is-loading");
          submitBtn.disabled = true;
        });
      }

      // Chart.js Live AI Dashboard Integration
      let chart = null;
      const ctx = document.getElementById('predictionChart');

      function initChart(labels, actualTemps, predictedTemps) {
        if (chart) {
          chart.destroy();
        }

        if (!ctx) return;

        chart = new Chart(ctx, {
          type: 'line',
          data: {
            labels: labels,
            datasets: [
              {
                label: 'Actual Temp (°C)',
                data: actualTemps,
                borderColor: '#00b4d8',
                backgroundColor: 'rgba(0, 180, 216, 0.1)',
                borderWidth: 2,
                pointRadius: 3,
                tension: 0.25,
                fill: false
              },
              {
                label: 'Predicted Temp (°C)',
                data: predictedTemps,
                borderColor: '#0066cc',
                backgroundColor: 'rgba(0, 102, 204, 0.1)',
                borderWidth: 2,
                pointStyle: 'rectRot',
                pointRadius: 4,
                tension: 0.25,
                borderDash: [5, 5],
                fill: false
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: {
                grid: { display: false },
                ticks: { maxTicksLimit: 12, color: '#607089' }
              },
              y: {
                beginAtZero: false,
                grid: { color: '#eef2f9' },
                ticks: { color: '#607089' }
              }
            },
            plugins: {
              legend: { position: 'top', labels: { boxWidth: 15, font: { weight: 'bold' } } }
            }
          }
        });
      }

      function updatePredictionDashboard() {
        fetch('api_prediction.php')
          .then(res => res.json())
          .then(data => {
            // Update cards
            const latest = data.latest;
            
            // Total predictions count
            document.getElementById('card-status').innerText = data.status || 'Idle';
            document.getElementById('card-status').style.color = (data.status === 'Running') ? 'var(--success)' : 'var(--warning)';
            
            if (latest) {
              const rawInput = latest.raw_input || {};
              const predictedTemp = latest.predicted_temperature !== null ? latest.predicted_temperature.toFixed(2) + ' °C' : '--';
              const curTemp = rawInput.temperature !== null ? rawInput.temperature.toFixed(2) + ' °C' : '--';
              const curHum = rawInput.humidity !== null ? rawInput.humidity.toFixed(1) + '%' : '--';
              const curPres = rawInput.pressure !== null ? rawInput.pressure.toFixed(1) + ' hPa' : '--';
              const cond = latest.weather_condition || '--';
              const conf = latest.confidence !== null ? latest.confidence.toFixed(0) + '%' : '--';
              const source = latest.source || 'AI Prediction / Dataset';

              document.getElementById('card-predicted-temp').innerText = predictedTemp;
              document.getElementById('card-humidity').innerText = curHum;
              document.getElementById('card-pressure').innerText = curPres;
              document.getElementById('card-condition').innerText = cond;
              document.getElementById('card-confidence').innerText = 'Confidence: ' + conf;
              document.getElementById('card-source').innerText = source;
              
              if (latest.created_at) {
                const dateObj = new Date(latest.created_at);
                document.getElementById('card-last-time').innerText = dateObj.toLocaleTimeString('en-US', { hour12: false });
              }
            }

            // Update Logs Table
            const history = data.history || [];
            const tbody = document.getElementById('history-table-body');
            
            if (history.length > 0) {
              tbody.innerHTML = '';
              // Show last 8 in table for space
              const displayHistory = history.slice(0, 8);
              displayHistory.forEach(item => {
                const tr = document.createElement('tr');
                const timeString = item.created_at ? new Date(item.created_at).toLocaleTimeString('en-US', { hour12: false }) : '--';
                const actual = (item.raw_input && item.raw_input.temperature !== null) ? item.raw_input.temperature.toFixed(2) + ' °C' : '--';
                const predicted = item.predicted_temperature !== null ? item.predicted_temperature.toFixed(2) + ' °C' : '--';
                const cond = item.weather_condition ? item.weather_condition : '--';

                tr.innerHTML = `
                  <td>${timeString}</td>
                  <td>${actual}</td>
                  <td><strong style="color: var(--primary);">${predicted}</strong></td>
                  <td><span class="badge badge-blue">${cond}</span></td>
                `;
                tbody.appendChild(tr);
              });
            } else {
              tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--muted);">No predictions received yet.</td></tr>`;
            }

            // Update Temperature Line Chart
            if (history.length > 0) {
              // Extract history in chronological order for plotting
              const plotData = [...history].reverse().slice(-30); // show last 30 samples
              const labels = plotData.map(item => item.created_at ? new Date(item.created_at).toLocaleTimeString('en-US', { hour12: false }) : '');
              const actuals = plotData.map(item => (item.raw_input && item.raw_input.temperature !== null) ? item.raw_input.temperature : null);
              const predicteds = plotData.map(item => item.predicted_temperature);
              
              initChart(labels, actuals, predicteds);
            }
          })
          .catch(err => console.error("Error updating prediction dashboard: ", err));
      }

      // Initial update and schedule interval polling every 4 seconds
      updatePredictionDashboard();
      setInterval(updatePredictionDashboard, 4000);
    });
  </script>
</body>
</html>
