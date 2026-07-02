<?php

final class NasaPowerService
{
    private const POWER_BASE_URL = 'https://power.larc.nasa.gov/api/temporal/daily/point';
    private const NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search';
    private const START_YEAR = 1985;
    private const WINDOW_DAYS = 7;

    public static function buildReport(array $query): array
    {
        $resolved = self::resolveLocation($query);
        $targetDate = $query['targetDate'];

        $raw = self::fetchPowerSeries($resolved['lat'], $resolved['lon']);
        $samples = self::extractWindowSamples($raw, $targetDate);

        if (count($samples) < 5) {
            throw new RuntimeException('Not enough NASA POWER records were returned for this location and seasonal window.');
        }

        $probabilities = self::calculateProbabilities($samples);
        
        $condition = $query['condition'] ?? '';
        if (empty($condition)) {
            $highestCondition = 'very-hot';
            $highestProb = -1;
            foreach ($probabilities as $cond => $prob) {
                if ($prob > $highestProb) {
                    $highestProb = $prob;
                    $highestCondition = $cond;
                }
            }
            $condition = $highestCondition;
        }

        $selectedProbability = (int) round($probabilities[$condition] ?? 0);
        $trend = self::calculateTrend($samples, $condition);
        $summary = self::summarizeSamples($samples);

        return [
            'query' => [
                'place' => $resolved['place'],
                'targetDate' => $targetDate,
                'condition' => $condition,
                'lat' => $resolved['lat'],
                'lon' => $resolved['lon']
            ],
            'result' => [
                'probability' => $selectedProbability,
                'probabilities' => $probabilities,
                'sample_count' => count($samples),
                'year_count' => count(array_unique(array_column($samples, 'year'))),
                'trend_delta' => $trend,
                'summary' => $summary,
                'narrative' => self::buildNarrative($condition, $selectedProbability, $summary, $trend),
                'window_days' => self::WINDOW_DAYS,
                'thresholds' => self::thresholds()
            ],
            'sources' => self::sourceCatalog()
        ];
    }

    public static function conditionLabel(string $condition): string
    {
        return [
            'very-hot' => 'Very Hot',
            'very-cold' => 'Very Cold',
            'very-wet' => 'Very Wet',
            'very-windy' => 'Very Windy',
            'very-uncomfortable' => 'Very Uncomfortable'
        ][$condition] ?? 'Weather Condition';
    }

    public static function thresholds(): array
    {
        return [
            'very-hot' => 'T2M_MAX >= 35 C',
            'very-cold' => 'T2M_MIN <= 5 C',
            'very-wet' => 'PRECTOTCORR >= 5 mm/day',
            'very-windy' => 'WS10M >= 8 m/s',
            'very-uncomfortable' => 'Heat index >= 38 C using T2M_MAX and RH2M'
        ];
    }

    public static function sourceCatalog(): array
    {
        return [
            [
                'name' => 'NASA POWER Daily API',
                'role' => 'Active data source used by the app for daily meteorology time series',
                'url' => 'https://power.larc.nasa.gov/api/pages/?urls.primaryName=Daily+API'
            ],
            [
                'name' => 'NASA POWER Meteorology Overview',
                'role' => 'Methodology reference for MERRA-2-derived meteorological parameters',
                'url' => 'https://power.larc.nasa.gov/docs/methodology/meteorology/'
            ],
            [
                'name' => 'GES DISC OPeNDAP / Hyrax',
                'role' => 'Official NASA remote subsetting and access path for gridded datasets',
                'url' => 'https://opendap.earthdata.nasa.gov/'
            ],
            [
                'name' => 'Giovanni',
                'role' => 'Official NASA visualization and analysis reference for maps and time series',
                'url' => 'https://www.earthdata.nasa.gov/topics/human-dimensions/natural-hazards/data-access-tools'
            ],
            [
                'name' => 'Earthdata Search',
                'role' => 'Official NASA data discovery and filtering portal',
                'url' => 'https://www.earthdata.nasa.gov/learn/articles/ed-search_esds'
            ],
            [
                'name' => 'Worldview',
                'role' => 'Official NASA imagery reference for visual context and comparison',
                'url' => 'https://www.earthdata.nasa.gov/news/feature-articles/data-tool-focus-nasa-worldview'
            ],
            [
                'name' => 'Data Rods for Hydrology',
                'role' => 'Official NASA point time-series reference for hydrologic workflows',
                'url' => 'https://www.earthdata.nasa.gov/news/feature-articles/data-tool-focus-data-rods-hydrology'
            ],
            [
                'name' => 'Earthdata Tutorials',
                'role' => 'Official NASA tutorials and Jupyter-style learning resources',
                'url' => 'https://www.earthdata.nasa.gov/learn/tutorials'
            ]
        ];
    }

    private static function resolveLocation(array $query): array
    {
        $place = trim((string) ($query['place'] ?? ''));
        $lat = $query['lat'] ?? null;
        $lon = $query['lon'] ?? null;

        if (is_numeric($lat) && is_numeric($lon)) {
            return [
                'place' => $place !== '' ? $place : sprintf('%.5f, %.5f', (float) $lat, (float) $lon),
                'lat' => round((float) $lat, 5),
                'lon' => round((float) $lon, 5)
            ];
        }

        if (preg_match('/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/', $place, $matches)) {
            return [
                'place' => $place,
                'lat' => round((float) $matches[1], 5),
                'lon' => round((float) $matches[2], 5)
            ];
        }

        $response = self::httpJson(self::NOMINATIM_URL . '?q=' . rawurlencode($place) . '&format=json&limit=1', [
            'User-Agent: NASA-Weather/1.0'
        ]);

        if (empty($response[0]['lat']) || empty($response[0]['lon'])) {
            throw new RuntimeException('Could not resolve this location to coordinates.');
        }

        return [
            'place' => $response[0]['display_name'] ?? $place,
            'lat' => round((float) $response[0]['lat'], 5),
            'lon' => round((float) $response[0]['lon'], 5)
        ];
    }

    private static function fetchPowerSeries(float $lat, float $lon): array
    {
        $endYear = max(self::START_YEAR, (int) date('Y') - 1);
        $query = http_build_query([
            'parameters' => 'T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,WS10M,RH2M',
            'community' => 'AG',
            'longitude' => $lon,
            'latitude' => $lat,
            'start' => self::START_YEAR . '0101',
            'end' => $endYear . '1231',
            'format' => 'JSON',
            'time-standard' => 'UTC'
        ]);

        $response = self::httpJson(self::POWER_BASE_URL . '?' . $query, [
            'User-Agent: NASA-Weather/1.0'
        ]);

        if (empty($response['properties']['parameter'])) {
            throw new RuntimeException('NASA POWER returned an unexpected response.');
        }

        return $response;
    }

    private static function httpJson(string $url, array $headers = []): array
    {
        if (function_exists('curl_init')) {
            $ch = curl_init($url);
            curl_setopt_array($ch, [
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_HTTPHEADER => $headers,
                CURLOPT_TIMEOUT => 45,
                CURLOPT_SSL_VERIFYPEER => false,
                CURLOPT_SSL_VERIFYHOST => false
            ]);
            $body = curl_exec($ch);
            $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
            curl_close($ch);

            if ($body === false || $code >= 400) {
                throw new RuntimeException('Remote data request failed.');
            }
        } else {
            $context = stream_context_create([
                'http' => [
                    'method' => 'GET',
                    'header' => implode("\r\n", $headers),
                    'timeout' => 45
                ],
                'ssl' => [
                    'verify_peer' => false,
                    'verify_peer_name' => false
                ]
            ]);
            $body = @file_get_contents($url, false, $context);
            if ($body === false) {
                throw new RuntimeException('Remote data request failed.');
            }
        }

        $decoded = json_decode($body, true);
        if (!is_array($decoded)) {
            throw new RuntimeException('Could not decode remote JSON data.');
        }

        return $decoded;
    }

    private static function extractWindowSamples(array $raw, string $targetDate): array
    {
        $parameters = $raw['properties']['parameter'];
        $targetMonthDay = date('m-d', strtotime($targetDate) ?: time());
        $samples = [];

        foreach (($parameters['T2M'] ?? []) as $date => $value) {
            if (!self::isFiniteValue($value)) {
                continue;
            }

            $timestamp = strtotime($date);
            if ($timestamp === false || !self::isWithinSeasonalWindow($targetMonthDay, date('m-d', $timestamp))) {
                continue;
            }

            $tmax = self::normalizeValue($parameters['T2M_MAX'][$date] ?? null);
            $tmin = self::normalizeValue($parameters['T2M_MIN'][$date] ?? null);
            $precip = self::normalizeValue($parameters['PRECTOTCORR'][$date] ?? null);
            $wind = self::normalizeValue($parameters['WS10M'][$date] ?? null);
            $humidity = self::normalizeValue($parameters['RH2M'][$date] ?? null);

            if ($tmax === null || $tmin === null || $precip === null || $wind === null || $humidity === null) {
                continue;
            }

            $samples[] = [
                'date' => $date,
                'year' => (int) date('Y', $timestamp),
                't2m' => self::normalizeValue($value),
                'tmax' => $tmax,
                'tmin' => $tmin,
                'precip' => $precip,
                'wind' => $wind,
                'humidity' => $humidity,
                'heat_index' => self::heatIndexC($tmax, $humidity)
            ];
        }

        return $samples;
    }

    private static function calculateProbabilities(array $samples): array
    {
        $counts = [
            'very-hot' => 0,
            'very-cold' => 0,
            'very-wet' => 0,
            'very-windy' => 0,
            'very-uncomfortable' => 0
        ];

        foreach ($samples as $sample) {
            foreach (array_keys($counts) as $condition) {
                if (self::meetsCondition($sample, $condition)) {
                    $counts[$condition]++;
                }
            }
        }

        $total = max(1, count($samples));
        foreach ($counts as $condition => $count) {
            $counts[$condition] = round(($count / $total) * 100, 1);
        }

        return $counts;
    }

    private static function calculateTrend(array $samples, string $condition): float
    {
        $byYear = [];
        foreach ($samples as $sample) {
            $byYear[$sample['year']][] = self::meetsCondition($sample, $condition) ? 1 : 0;
        }

        ksort($byYear);
        $years = array_keys($byYear);
        if (count($years) < 10) {
            return 0.0;
        }

        $windowSize = min(10, max(3, (int) floor(count($years) / 2)));
        $earlyYears = array_slice($years, 0, $windowSize);
        $recentYears = array_slice($years, -$windowSize);

        $early = self::averageYearGroups($byYear, $earlyYears);
        $recent = self::averageYearGroups($byYear, $recentYears);

        return round($recent - $early, 1);
    }

    private static function averageYearGroups(array $byYear, array $years): float
    {
        $values = [];
        foreach ($years as $year) {
            $bucket = $byYear[$year] ?? [];
            if ($bucket !== []) {
                $values[] = array_sum($bucket) / count($bucket) * 100;
            }
        }

        return $values === [] ? 0.0 : array_sum($values) / count($values);
    }

    private static function summarizeSamples(array $samples): array
    {
        return [
            'avg_tmax' => round(self::average(array_column($samples, 'tmax')), 1),
            'avg_tmin' => round(self::average(array_column($samples, 'tmin')), 1),
            'avg_precip' => round(self::average(array_column($samples, 'precip')), 2),
            'avg_wind' => round(self::average(array_column($samples, 'wind')), 2),
            'avg_humidity' => round(self::average(array_column($samples, 'humidity')), 1),
            'avg_heat_index' => round(self::average(array_column($samples, 'heat_index')), 1)
        ];
    }

    private static function buildNarrative(string $condition, int $probability, array $summary, float $trend): string
    {
        $conditionText = self::conditionLabel($condition);
        $trendText = $trend > 0 ? 'an increasing signal' : ($trend < 0 ? 'a decreasing signal' : 'a fairly stable signal');

        return sprintf(
            '%s conditions show a %.0f%% historical likelihood in the seasonal window around this date. Average max temperature is %.1f C, precipitation averages %.2f mm/day, wind averages %.2f m/s, and the long-term comparison shows %s.',
            $conditionText,
            $probability,
            $summary['avg_tmax'],
            $summary['avg_precip'],
            $summary['avg_wind'],
            $trendText
        );
    }

    private static function meetsCondition(array $sample, string $condition): bool
    {
        return match ($condition) {
            'very-hot' => $sample['tmax'] >= 35.0,
            'very-cold' => $sample['tmin'] <= 5.0,
            'very-wet' => $sample['precip'] >= 5.0,
            'very-windy' => $sample['wind'] >= 8.0,
            'very-uncomfortable' => $sample['heat_index'] >= 38.0,
            default => false,
        };
    }

    private static function heatIndexC(float $tempC, float $humidity): float
    {
        if ($tempC < 27 || $humidity < 40) {
            return $tempC;
        }

        $tempF = ($tempC * 9 / 5) + 32;
        $indexF = -42.379
            + 2.04901523 * $tempF
            + 10.14333127 * $humidity
            - 0.22475541 * $tempF * $humidity
            - 0.00683783 * $tempF * $tempF
            - 0.05481717 * $humidity * $humidity
            + 0.00122874 * $tempF * $tempF * $humidity
            + 0.00085282 * $tempF * $humidity * $humidity
            - 0.00000199 * $tempF * $tempF * $humidity * $humidity;

        return ($indexF - 32) * 5 / 9;
    }

    private static function normalizeValue(mixed $value): ?float
    {
        if (!self::isFiniteValue($value)) {
            return null;
        }

        return (float) $value;
    }

    private static function isFiniteValue(mixed $value): bool
    {
        return is_numeric($value) && (float) $value > -900;
    }

    private static function average(array $values): float
    {
        if ($values === []) {
            return 0.0;
        }

        return array_sum($values) / count($values);
    }

    private static function isWithinSeasonalWindow(string $targetMonthDay, string $candidateMonthDay): bool
    {
        [$targetMonth, $targetDay] = array_map('intval', explode('-', $targetMonthDay));
        [$candidateMonth, $candidateDay] = array_map('intval', explode('-', $candidateMonthDay));

        $baseYear = 2001;
        $target = (int) date('z', strtotime(sprintf('%04d-%02d-%02d', $baseYear, $targetMonth, $targetDay)));
        $candidate = (int) date('z', strtotime(sprintf('%04d-%02d-%02d', $baseYear, $candidateMonth, $candidateDay)));
        $distance = abs($candidate - $target);

        return min($distance, 365 - $distance) <= self::WINDOW_DAYS;
    }
}
