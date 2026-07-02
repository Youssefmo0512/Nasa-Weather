<?php
require_once 'config.php';
require_once 'nasa_power_service.php';
setupSession();

function sanitizeText(string $value): string {
    return trim(filter_var($value, FILTER_SANITIZE_SPECIAL_CHARS));
}

function riskColor(int $score): array {
    if ($score >= 75) {
        return ['label' => 'High Likelihood', 'color' => '#ef4444', 'soft' => 'rgba(239, 68, 68, 0.1)'];
    }
    if ($score >= 50) {
        return ['label' => 'Elevated Likelihood', 'color' => '#f59e0b', 'soft' => 'rgba(245, 158, 11, 0.1)'];
    }
    if ($score >= 30) {
        return ['label' => 'Moderate Likelihood', 'color' => '#00b4d8', 'soft' => 'rgba(0, 180, 216, 0.1)'];
    }
    return ['label' => 'Lower Likelihood', 'color' => '#10b981', 'soft' => 'rgba(16, 185, 129, 0.1)'];
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $query = [
        'place' => sanitizeText($_POST['place'] ?? ''),
        'targetDate' => sanitizeText($_POST['targetDate'] ?? ''),
        'condition' => sanitizeText($_POST['condition'] ?? ''),
        'lat' => is_numeric($_POST['lat'] ?? null) ? (float) $_POST['lat'] : null,
        'lon' => is_numeric($_POST['lon'] ?? null) ? (float) $_POST['lon'] : null
    ];

    $_SESSION['weather_query'] = $query;
} else {
    $query = $_SESSION['weather_query'] ?? null;
}

if (empty($query['place']) || empty($query['targetDate'])) {
    header('Location: index.php');
    exit;
}

$condition = $query['condition'] ?? '';
$conditionLabel = !empty($condition) ? NasaPowerService::conditionLabel($condition) : 'Weather Condition';

try {
    if ($_SERVER['REQUEST_METHOD'] === 'POST' || empty($_SESSION['weather_report'])) {
        $_SESSION['weather_report'] = NasaPowerService::buildReport($query);
    }
    $report = $_SESSION['weather_report'];
    $errorMessage = null;
} catch (Throwable $exception) {
    $report = null;
    $errorMessage = $exception->getMessage();
}

if ($report !== null) {
    $lat = $report['query']['lat'];
    $lon = $report['query']['lon'];
    $condition = $report['query']['condition'];
    $conditionLabel = NasaPowerService::conditionLabel($condition);
    $score = (int) round($report['result']['probability']);
    $riskBand = riskColor($score);
    $monthLabel = date('F j, Y', strtotime($report['query']['targetDate']) ?: time());
    $downloadPayload = [
        'query' => [
            'place' => $report['query']['place'],
            'target_date' => $report['query']['targetDate'],
            'condition' => $conditionLabel,
            'latitude' => $lat,
            'longitude' => $lon
        ],
        'results' => $report['result'],
        'sources' => $report['sources'],
        'metadata' => [
            'app' => APP_NAME,
            'version' => APP_VERSION,
            'generated_at' => date(DATE_ATOM)
        ]
    ];
} else {
    $downloadPayload = [];
    $score = 0;
    $riskBand = riskColor(0);
    $monthLabel = date('F j, Y', strtotime($query['targetDate']) ?: time());
    $lat = $query['lat'] ?? 26.8206;
    $lon = $query['lon'] ?? 30.8025;
}

if ($report !== null && isset($_GET['download']) && $_GET['download'] === 'json') {
    header('Content-Type: application/json');
    header('Content-Disposition: attachment; filename="nasa-weather-result.json"');
    echo json_encode($downloadPayload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
    exit;
}

if ($report !== null && isset($_GET['download']) && $_GET['download'] === 'csv') {
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename="nasa-weather-result.csv"');
    $output = fopen('php://output', 'w');
    fputcsv($output, ['field', 'value']);
    fputcsv($output, ['place', $report['query']['place']]);
    fputcsv($output, ['target_date', $report['query']['targetDate']]);
    fputcsv($output, ['condition', $conditionLabel]);
    fputcsv($output, ['latitude', round((float) $lat, 5)]);
    fputcsv($output, ['longitude', round((float) $lon, 5)]);
    fputcsv($output, ['likelihood_score', $score]);
    fputcsv($output, ['risk_band', $riskBand['label']]);
    fputcsv($output, ['sample_count', $report['result']['sample_count']]);
    fputcsv($output, ['year_count', $report['result']['year_count']]);
    fputcsv($output, ['seasonal_trend_signal', $report['result']['trend_delta']]);
    foreach ($report['result']['probabilities'] as $label => $value) {
        fputcsv($output, [$label, $value]);
    }
    foreach ($report['result']['summary'] as $label => $value) {
        fputcsv($output, [$label, (int) round($value)]);
    }
    fclose($output);
    exit;
}

// Map condition key to emoji
$conditionEmojis = [
    'very-hot' => '🔥',
    'very-cold' => '❄️',
    'very-wet' => '🌧️',
    'very-windy' => '💨',
    'very-uncomfortable' => '⚠️'
];
$currentEmoji = $conditionEmojis[$condition] ?? '🌤️';
?>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>NASA Weather Results | <?= htmlspecialchars($conditionLabel) ?></title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="./assets/css/app.css" />
</head>
<body>
  <div class="app-shell">
    <header class="topbar surface reveal is-visible">
      <div class="brand">
        <div class="brand-badge">NW</div>
        <div class="brand-text">
          <strong>NASA Weather Analysis Report</strong>
          <span>Historical weather likelihood snapshot for outdoor planning</span>
        </div>
      </div>
      <div class="topbar-actions">
        <a class="btn-secondary" href="index.php?place=<?= urlencode($query['place']) ?>&targetDate=<?= urlencode($query['targetDate']) ?>&condition=<?= urlencode($condition) ?>&lat=<?= urlencode((string) $lat) ?>&lon=<?= urlencode((string) $lon) ?>">Edit query</a>
      </div>
    </header>

    <section class="page-hero surface reveal is-visible">
      <div class="eyebrow">Query Complete</div>
      <h1><?= htmlspecialchars($conditionLabel) ?> Risk for <?= htmlspecialchars($report['query']['place'] ?? $query['place']) ?></h1>
      <p>
        Calculated from NASA POWER daily observation series from 1985 to present.
      </p>
    </section>

    <?php if ($errorMessage !== null): ?>
      <section class="panel surface reveal is-visible">
        <div class="section-header">
          <h2>Data Fetch Error</h2>
          <p>We could not complete the NASA data request for this query.</p>
        </div>
        <div class="narrative">
          <p><?= htmlspecialchars($errorMessage) ?></p>
        </div>
      </section>
    <?php else: ?>
    <section class="results-grid">
      <div class="stack">
        <!-- Headline weather condition block (replaces old gauge-card) -->
        <section class="weather-status-card reveal is-visible">
          <div class="weather-status-emoji"><?= $currentEmoji ?></div>
          <div class="weather-status-label"><?= htmlspecialchars($conditionLabel) ?></div>
          <div class="weather-status-likelihood">
            Likelihood: <?= $score ?>%
          </div>
          <div style="margin-top: 14px;">
            <span class="badge" style="background: <?= htmlspecialchars($riskBand['soft']) ?>; color: <?= htmlspecialchars($riskBand['color']) ?>; font-size: 0.95rem; padding: 6px 16px;">
              <?= htmlspecialchars($riskBand['label']) ?>
            </span>
          </div>
          <p style="color: var(--muted); font-size: 0.9rem; margin-top: 16px; margin-bottom: 0;">
            Based on <?= (int) $report['result']['year_count'] ?> years of historical observations
          </p>
        </section>

        <!-- Chart block -->
        <section class="chart-card surface reveal is-visible">
          <div class="panel-header" style="margin-bottom: 8px;">
            <div>
              <h2 style="margin: 0 0 6px 0;">Comparison View</h2>
              <p style="margin: 0; color: var(--muted); font-size: 0.9rem;">Probabilities of other extreme factors around the same date.</p>
            </div>
          </div>
          <div class="chart-shell">
            <canvas id="comparisonChart" aria-label="Comparison chart"></canvas>
          </div>
          <div class="narrative">
            <p>
              <?= htmlspecialchars($report['result']['narrative']) ?>
              The seasonal comparison uses a +/- <?= (int) $report['result']['window_days'] ?> day window around
              <strong><?= htmlspecialchars($monthLabel) ?></strong>.
            </p>
          </div>
        </section>
      </div>

      <div class="stack">
        <!-- Summary block -->
        <section class="summary-card surface reveal is-visible">
          <div class="panel-header" style="margin-bottom: 8px;">
            <div>
              <h2 style="margin: 0 0 6px 0;">Query Summary</h2>
              <p style="margin: 0; color: var(--muted); font-size: 0.9rem;">Calculated coordinates and metrics.</p>
            </div>
          </div>

          <div class="summary-list">
            <div class="summary-item">
              <span>Location</span>
              <strong><?= htmlspecialchars($report['query']['place']) ?></strong>
            </div>
            <div class="summary-item">
              <span>Date</span>
              <strong><?= htmlspecialchars($monthLabel) ?></strong>
            </div>
            <div class="summary-item">
              <span>Condition Type</span>
              <strong><?= htmlspecialchars($conditionLabel) ?></strong>
            </div>
            <div class="summary-item">
              <span>Coordinates</span>
              <strong><?= htmlspecialchars(number_format((float) $lat, 5)) ?>, <?= htmlspecialchars(number_format((float) $lon, 5)) ?></strong>
            </div>
            <div class="summary-item">
              <span>Sample Count</span>
              <strong><?= (int) $report['result']['sample_count'] ?> days</strong>
            </div>
            <div class="summary-item">
              <span>Trend Delta</span>
              <strong style="color: <?= $report['result']['trend_delta'] > 0 ? 'var(--warm)' : ($report['result']['trend_delta'] < 0 ? 'var(--success)' : 'var(--text)') ?>;">
                <?= $report['result']['trend_delta'] >= 0 ? '+' : '' ?><?= htmlspecialchars((string) $report['result']['trend_delta']) ?>%
              </strong>
            </div>
          </div>

          <div class="download-row" style="margin-top: 18px;">
            <a class="download-link" href="results.php?download=json" style="flex: 1;">Download JSON</a>
            <a class="download-link" href="results.php?download=csv" style="flex: 1;">Download CSV</a>
          </div>
        </section>

        <!-- Climate Averages block -->
        <section class="detail-card surface reveal is-visible" style="margin-top: 14px;">
          <div class="panel-header" style="margin-bottom: 8px;">
            <div>
              <h2 style="margin: 0 0 6px 0;">Historical Climate Averages</h2>
              <p style="margin: 0; color: var(--muted); font-size: 0.9rem;">Mean daily parameters computed for this seasonal window.</p>
            </div>
          </div>

          <div class="detail-list">
            <div class="detail-item">
              <span>Average Max Temperature</span>
              <strong><?= htmlspecialchars((string) $report['result']['summary']['avg_tmax']) ?> °C</strong>
            </div>
            <div class="detail-item">
              <span>Average Precipitation</span>
              <strong><?= htmlspecialchars((string) $report['result']['summary']['avg_precip']) ?> mm/day</strong>
            </div>
            <div class="detail-item">
              <span>Average Wind Speed</span>
              <strong><?= htmlspecialchars((string) $report['result']['summary']['avg_wind']) ?> m/s</strong>
            </div>
            <div class="detail-item">
              <span>Average Relative Humidity</span>
              <strong><?= htmlspecialchars((string) $report['result']['summary']['avg_humidity']) ?>%</strong>
            </div>
          </div>
        </section>
      </div>
    </section>
    <?php endif; ?>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
  <script>
    document.addEventListener('DOMContentLoaded', function () {
      const chartCanvas = document.getElementById('comparisonChart');
      if (chartCanvas && window.Chart && <?= $errorMessage === null ? 'true' : 'false' ?>) {
        Chart.defaults.color = '#607089';
        Chart.defaults.font.family = '"Space Grotesk", "Segoe UI", sans-serif';
        new Chart(chartCanvas, {
          type: 'bar',
          data: {
            labels: <?= json_encode(array_map([NasaPowerService::class, 'conditionLabel'], array_keys($report['result']['probabilities'] ?? []))) ?>,
            datasets: [{
              label: 'Risk Likelihood (%)',
              data: <?= json_encode(array_map(static fn($value) => (int) round($value), array_values($report['result']['probabilities'] ?? []))) ?>,
              borderRadius: 8,
              backgroundColor: [
                'rgba(0, 102, 204, 0.85)',
                'rgba(0, 180, 216, 0.85)',
                'rgba(245, 158, 11, 0.85)',
                'rgba(239, 68, 68, 0.85)',
                'rgba(16, 185, 129, 0.85)'
              ]
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: {
                grid: { display: false },
                ticks: { color: '#607089' }
              },
              y: {
                beginAtZero: true,
                suggestedMax: 100,
                grid: { color: '#eef2f9' },
                ticks: { color: '#607089' }
              }
            },
            plugins: {
              legend: { display: false },
              tooltip: {
                backgroundColor: 'rgba(11, 34, 64, 0.95)',
                titleColor: '#ffffff',
                bodyColor: '#ffffff',
                borderColor: '#dbeafe',
                borderWidth: 1
              }
            }
          }
        });
      }

      const reveals = document.querySelectorAll('.reveal');
      if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add('is-visible');
              observer.unobserve(entry.target);
            }
          });
        }, { threshold: 0.16 });

        reveals.forEach((item, index) => {
          item.style.transitionDelay = `${Math.min(index * 70, 350)}ms`;
          observer.observe(item);
        });
      } else {
        reveals.forEach((item) => item.classList.add('is-visible'));
      }
    });
  </script>
</body>
</html>
