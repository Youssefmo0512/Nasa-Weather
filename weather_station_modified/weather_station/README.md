# 🌤 Weather Station — Headless ML Prediction Service

A professional, modular Python weather forecasting service that integrates online machine learning predictions with a premium PHP Web Dashboard. 

The Python script reads sensor data, performs online predictions, maintains rotating CSV logs, and forwards forecasts to a local web server API.

---

## 🚀 Key Features

* **Dual Storage Pipeline**: Saves every prediction locally to rotating CSV files and pushes records to the web backend's `predictions.json` file.
* **Headless Background Runner**: `prediction_poster.py` runs headlessly in the background, minimizing console noise.
* **Command Line Control**:
  * `--quiet` / `-q` mode: Reduces logs to minimal status updates (start, connect, API send confirmations, errors).
  * `--verbose` / `-v` mode: Displays full debug details for diagnostics.
* **Redesigned Dashboard**: A tabbed White & Blue web interface presenting real-time trends, sensor metrics, history tables, and NASA POWER climate charts.

---

## ⚙️ Installation & Setup

1. **Configure Web Path**:
   Ensure your web server (e.g. Apache via XAMPP) is serving the `Nasa_Oct` directory.
   By default, the Python script targets:
   `http://localhost/Final/Nasa_Oct/api_prediction.php`

   To modify this target, edit `APIConfig.url` in `config/config.py`:
   ```python
   @dataclass
   class APIConfig:
       url: str = "http://localhost/Final/Nasa_Oct/api_prediction.php"
   ```

2. **Verify Python Environment**:
   Make sure you have your dependencies installed:
   ```bash
   pip install -r requirements.txt
   ```

---

## 🏃 Running the Headless Prediction Service

Start the headless background runner script using python:

### 1. Default Mode
Shows clean, minimal technical logs in the console:
```bash
python prediction_poster.py
```

### 2. Quiet Mode
Hides standard info messages; outputting only critical status changes (Script started, API connection test, confirmations of sends, and errors):
```bash
python prediction_poster.py --quiet
```
*or*
```bash
python prediction_poster.py -q
```

### 3. Verbose Mode
Prints detailed logs for debugging model features and serial traffic:
```bash
python prediction_poster.py --verbose
```
*or*
```bash
python prediction_poster.py -v
```

---

## 🖥️ Accessing the Web Dashboard

Open your web browser and navigate to the local project page:
`http://localhost/Final/Nasa_Oct/index.php`

The dashboard will open automatically and poll the API (`api_prediction.php`) every 4 seconds to retrieve new ML predictions, update the graphs, and display incoming logs.

---

## 🔍 Verification Checklist

Ensure your predictions are writing to both target destinations successfully:

1. **Verify CSV Logging**:
   - Check the `data` folder inside `weather_station` for `stream_log.csv` and `history.csv`.
   - Incoming serial streams and training metrics will write directly to these tables.

2. **Verify JSON Storage**:
   - Locate the file `Nasa_Oct/storage/predictions.json`.
   - This file holds the latest 200 prediction records serialized as JSON objects.
   - You can also call the API via GET to inspect the records:
     `http://localhost/Final/Nasa_Oct/api_prediction.php`

3. **Verify Dashboard Visuals**:
   - Check that the dashboard updates dynamically with the premium White & Blue styling.
   - Verify the historical temperatures plot on the Chart.js line graph and updates live.
