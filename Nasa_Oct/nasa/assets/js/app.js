document.addEventListener('DOMContentLoaded', () => {
  // Initialize Map
  const map = L.map('map', {
    zoomControl: false // Move zoom control if needed to keep UI clean
  }).setView([26.8206, 30.8025], 5);
  
  L.control.zoom({ position: 'bottomright' }).addTo(map);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18,
  }).addTo(map);

  let marker;
  const locationInput = document.getElementById("location");

  // Map Click Event
  map.on('click', function(e) {
      const lat = e.latlng.lat.toFixed(5);
      const lng = e.latlng.lng.toFixed(5);
      
      locationInput.value = `${lat}, ${lng}`;
      
      if (marker) {
          map.removeLayer(marker);
      }
      
      // Custom pulsing marker icon
      const customIcon = L.divIcon({
        className: 'custom-marker',
        html: `<div style="background:var(--primary);width:16px;height:16px;border-radius:50%;box-shadow:var(--glow);border:2px solid white;"></div>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10]
      });

      marker = L.marker([lat, lng], {icon: customIcon}).addTo(map);
      
      // Smooth fly to
      map.flyTo([lat, lng], 8, {
          duration: 1.5
      });
  });

  // Chart Setup
  let chartInstance = null;

  function renderChart(probabilities) {
    const ctx = document.getElementById('probabilityChart').getContext('2d');
    
    if (chartInstance) {
      chartInstance.destroy();
    }

    Chart.defaults.color = '#a0aec0';
    Chart.defaults.font.family = "'Outfit', sans-serif";

    chartInstance = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Probability of Condition', 'Other Scenarios'],
        datasets: [{
          data: [probabilities, 100 - probabilities],
          backgroundColor: [
            '#00f2fe',
            'rgba(255, 255, 255, 0.05)'
          ],
          borderWidth: 0,
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '75%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              padding: 20,
              usePointStyle: true,
              pointStyle: 'circle'
            }
          },
          tooltip: {
            backgroundColor: 'rgba(11, 15, 25, 0.9)',
            titleColor: '#fff',
            bodyColor: '#fff',
            borderColor: 'rgba(0, 242, 254, 0.4)',
            borderWidth: 1,
            padding: 12,
            boxPadding: 6
          }
        }
      }
    });
  }

  // Form Submission
  const form = document.getElementById("weatherForm");
  const btn = document.getElementById("submitBtn");
  const resultsContainer = document.getElementById("resultsArea");

  form.addEventListener("submit", async function(e) {
    e.preventDefault();
    
    const location = document.getElementById("location").value;
    const date = document.getElementById("date").value;
    const condition = document.getElementById("condition").value;

    if (!location || !date || !condition) {
      alert("Please fill in all fields.");
      return;
    }

    // UI Loading state
    btn.classList.add('loading');
    btn.disabled = true;

    try {
      // Simulate API call delay for the "wow" feeling
      await new Promise(r => setTimeout(r, 1500));
      
      // MOCK DATA based on condition (Since we don't have the actual ML API yet)
      const mockProbability = Math.floor(Math.random() * (95 - 30 + 1) + 30);
      
      // Update Results DOM
      document.getElementById('res-location').innerText = location;
      document.getElementById('res-date').innerText = date;
      document.getElementById('res-condition').innerText = document.getElementById("condition").options[document.getElementById("condition").selectedIndex].text;
      
      // Show results
      resultsContainer.style.display = 'block';
      
      // Render beautiful chart
      renderChart(mockProbability);

      // Scroll to results smoothly
      resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'end' });

    } catch (error) {
       console.error("Error fetching data", error);
       alert("An error occurred while analyzing the data.");
    } finally {
       btn.classList.remove('loading');
       btn.disabled = false;
    }
  });

  // Add subtle mouse move parallax to body
  document.addEventListener('mousemove', (e) => {
    const x = e.clientX / window.innerWidth;
    const y = e.clientY / window.innerHeight;
    document.body.style.backgroundPosition = `${x * 20}px ${y * 20}px`;
  });
});
