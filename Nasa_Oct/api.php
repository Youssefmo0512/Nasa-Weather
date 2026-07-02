<?php
require_once 'config.php';
setupSession();

class WeatherAPIHandler {
    public static function handlePrediction(): void {
        try {
            $baseUrl = $_POST['baseUrl'] ?? '';
            $place = $_POST['place'] ?? '';
            $targetDate = $_POST['targetDate'] ?? '';
            
            if (empty($baseUrl) || empty($place) || empty($targetDate)) {
                throw new Exception('جميع الحقول مطلوبة');
            }

            // 1. Geocoding
            $geoData = self::geocodePlace($place);
            
            // 2. Call prediction API
            $prediction = self::callPredictionAPI($baseUrl, $geoData['lat'], $geoData['lon'], $targetDate);
            
            // Store result in session
            $_SESSION['weather_result'] = $prediction;
            $_SESSION['last_coords'] = ['lat' => $geoData['lat'], 'lon' => $geoData['lon']];
            
            // Redirect back
            header('Location: index.php?lat=' . $geoData['lat'] . '&lon=' . $geoData['lon']);
            exit;
            
        } catch (Exception $e) {
            $_SESSION['error'] = $e->getMessage();
            header('Location: index.php');
            exit;
        }
    }
    
    private static function geocodePlace($place) {
        $url = 'https://nominatim.openstreetmap.org/search?q=' . urlencode($place) . '&format=json&limit=1';
        
        $context = stream_context_create([
            'http' => [
                'header' => "User-Agent: EgipturaWeather/1.0 (contact: you@example.com)\r\n"
            ]
        ]);
        
        $response = file_get_contents($url, false, $context);
        $data = json_decode($response, true);
        
        if (empty($data)) {
            throw new Exception('لم يتم العثور على نتائج للمكان: ' . $place);
        }
        
        return [
            'lat' => (float)$data[0]['lat'],
            'lon' => (float)$data[0]['lon'],
            'display_name' => $data[0]['display_name'] ?? ''
        ];
    }
    
    private static function callPredictionAPI($baseUrl, $lat, $lon, $targetDate) {
        $url = rtrim($baseUrl, '/') . '/predict';
        
        $payload = [
            "lat" => $lat,
            "lon" => $lon,
            "target_date" => $targetDate,
            "start_year" => 1985,
            "end_year" => 2025,
            "window_days" => 7,
            "thresholds" => [
                "very_hot_c" => 35.0,
                "very_cold_c" => 5.0,
                "wet_mm" => 5.0,
                "windy_ms" => 8.0,
                "hi_uncomfortable_c" => 38.0
            ]
        ];
        
        $ch = curl_init();
        curl_setopt_array($ch, [
            CURLOPT_URL => $url,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => json_encode($payload),
            CURLOPT_HTTPHEADER => [
                'Content-Type: application/json',
                'Accept: application/json'
            ],
            CURLOPT_TIMEOUT => 30
        ]);
        
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        
        if ($httpCode !== 200) {
            throw new Exception('خطأ في API: ' . $httpCode . ' - ' . $response);
        }
        
        return json_decode($response, true);
    }
}

// المعالجة الرئيسية
if (isset($_GET['action']) && $_GET['action'] === 'predict') {
    WeatherAPIHandler::handlePrediction();
} else {
    http_response_code(400);
    echo json_encode(['error' => 'Action not specified']);
}
?>