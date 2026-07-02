// Auto-fill coordinates when page loads with URL parameters
document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    const lat = urlParams.get('lat');
    const lon = urlParams.get('lon');
    
    if (lat && lon) {
        document.getElementById('lat').value = parseFloat(lat).toFixed(6);
        document.getElementById('lon').value = parseFloat(lon).toFixed(6);
    }
    
    // Form submission handling
    const form = document.getElementById('weatherForm');
    const predictBtn = document.getElementById('predictBtn');
    const btnText = document.getElementById('btnText');
    const loadingSpinner = document.getElementById('loadingSpinner');
    
    if (form) {
        form.addEventListener('submit', function(e) {
            // Basic validation
            const place = document.getElementById('place').value.trim();
            const baseUrl = document.getElementById('baseUrl').value.trim();
            
            if (!place || !baseUrl) {
                e.preventDefault();
                alert('يرجى ملء جميع الحقول المطلوبة');
                return;
            }
            
            // Show loading state
            btnText.textContent = 'جاري المعالجة...';
            loadingSpinner.style.display = 'block';
            predictBtn.disabled = true;
        });
        
        // Auto-submit on place enter key
        document.getElementById('place').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                form.dispatchEvent(new Event('submit'));
            }
        });
    }
});

// Show error messages if any
window.onload = function() {
    // Remove any existing URL parameters after processing
    if (window.location.search) {
        const url = new URL(window.location);
        url.search = '';
        window.history.replaceState({}, '', url);
    }
};