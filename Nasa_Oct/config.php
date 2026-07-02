<?php
// config.php - الإعدادات الأساسية فقط
define('APP_NAME', 'NASA Weather');
define('APP_VERSION', '1.0');
date_default_timezone_set('Africa/Cairo');
error_reporting(E_ALL);
ini_set('display_errors', 1);

// إعدادات الجلسة الآمنة
function setupSession() {
    if (session_status() === PHP_SESSION_NONE) {
        ini_set('session.cookie_httponly', 1);
        ini_set('session.use_only_cookies', 1);
        session_start();
    }
}
?>