<?php
// CORS Headers to allow GitHub Pages and local client-side testing
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Headers: Content-Type, Accept");
header("Access-Control-Allow-Methods: GET, POST, OPTIONS");
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    exit(0);
}

require_once 'config.php';
setupSession();

header('Content-Type: application/json');

$storage_dir = __DIR__ . '/storage';
$file_path = $storage_dir . '/predictions.json';
$max_records = 200;

// Ensure storage directory exists
if (!is_dir($storage_dir)) {
    mkdir($storage_dir, 0777, true);
}

// Function to handle corruption recovery
function loadPredictionsSafely(string $path): array {
    if (!file_exists($path)) {
        return [];
    }

    $handle = fopen($path, 'r');
    if (!$handle) {
        return [];
    }

    flock($handle, LOCK_SH);
    $content = '';
    while (!feof($handle)) {
        $content .= fread($handle, 8192);
    }
    flock($handle, LOCK_UN);
    fclose($handle);

    $content = trim($content);
    if (empty($content)) {
        return [];
    }

    $data = json_decode($content, true);
    if (json_last_error() !== JSON_ERROR_NONE || !is_array($data)) {
        // Corrupted file: back it up and create a clean empty array
        $backup_path = $path . '.corrupt.' . time() . '.bak';
        rename($path, $backup_path);
        return [];
    }

    return $data;
}

// Function to save predictions safely with locking
function savePredictionsSafely(string $path, array $data): bool {
    $content = json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
    
    $handle = fopen($path, 'w');
    if (!$handle) {
        return false;
    }

    flock($handle, LOCK_EX);
    $written = fwrite($handle, $content);
    fflush($handle);
    flock($handle, LOCK_UN);
    fclose($handle);

    return $written !== false;
}

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';

if ($method === 'POST') {
    // Read post body
    $raw_input = file_get_contents('php://input');
    $prediction = json_decode($raw_input, true);

    if (json_last_error() !== JSON_ERROR_NONE || !is_array($prediction)) {
        http_response_code(400);
        echo json_encode(['error' => 'Invalid JSON payload']);
        exit;
    }

    // Basic structure validation
    // Ensure predicted_temperature is checked if present, we do not require it to be strictly non-null
    // but check if present in some format.
    if (!array_key_exists('predicted_temperature', $prediction)) {
        http_response_code(400);
        echo json_encode(['error' => 'Missing predicted_temperature field']);
        exit;
    }

    // Add created_at if missing
    if (empty($prediction['created_at'])) {
        $prediction['created_at'] = date(DATE_ATOM);
    }

    // Set other missing fields to null
    $required_fields = [
        'predicted_temperature',
        'predicted_humidity',
        'predicted_pressure',
        'predicted_dew_point',
        'prediction',
        'weather_condition',
        'risk_level',
        'confidence',
        'source',
        'dataset_row_index',
        'dataset_timestamp',
        'raw_input',
        'model_output'
    ];

    foreach ($required_fields as $field) {
        if (!array_key_exists($field, $prediction)) {
            $prediction[$field] = null;
        }
    }

    // Load current records
    $records = loadPredictionsSafely($file_path);

    // Append new prediction to the end of the history array
    $records[] = $prediction;

    // Limit records count to max_records
    if (count($records) > $max_records) {
        $records = array_slice($records, -$max_records);
    }

    // Save records
    if (savePredictionsSafely($file_path, $records)) {
        echo json_encode(['success' => true, 'record' => $prediction]);
    } else {
        http_response_code(500);
        echo json_encode(['error' => 'Failed to save prediction to storage']);
    }
    exit;
}

// GET Handler
if ($method === 'GET') {
    $records = loadPredictionsSafely($file_path);
    $total_count = count($records);
    $latest = $total_count > 0 ? $records[$total_count - 1] : null;
    $last_update = $latest ? $latest['created_at'] : null;

    // Determine status of the prediction engine
    // If we've received a prediction in the last 60 seconds, it's considered Active, otherwise Idle.
    $status = 'Idle';
    if ($last_update) {
        $last_time = strtotime($last_update);
        if ($last_time !== false && (time() - $last_time) < 60) {
            $status = 'Running';
        }
    }

    echo json_encode([
        'latest' => $latest,
        'history' => array_reverse($records), // Return latest first for easier rendering
        'total_count' => $total_count,
        'last_update' => $last_update,
        'status' => $status
    ]);
    exit;
}
