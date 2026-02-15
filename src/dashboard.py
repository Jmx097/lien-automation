#!/usr/bin/env python3
"""
Lien Extraction Dashboard - Web Interface
Run: python3 dashboard.py
Then open: http://localhost:5000
"""

from flask import Flask, render_template, jsonify, request
import json
import os
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

# Paths
BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "config"
LOGS_DIR = BASE_DIR / "logs"
DOWNLOADS_DIR = BASE_DIR / "downloads"

@app.route("/")
def index():
    """Main dashboard page"""
    return render_template("dashboard.html")

@app.route("/api/sites")
def get_sites():
    """Get all site configurations"""
    try:
        with open(CONFIG_DIR / "sites.json") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/sites/<site_id>")
def get_site(site_id):
    """Get specific site configuration"""
    try:
        with open(CONFIG_DIR / "sites.json") as f:
            data = json.load(f)
        for site in data.get("sites", []):
            if str(site.get("id")) == site_id:
                return jsonify(site)
        return jsonify({"error": "Site not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/logs")
def get_logs():
    """Get recent log entries"""
    logs = []
    try:
        if LOGS_DIR.exists():
            log_files = sorted(LOGS_DIR.glob("*.log"), reverse=True)[:5]
            for log_file in log_files:
                with open(log_file) as f:
                    content = f.read()
                    logs.append({
                        "filename": log_file.name,
                        "content": content[-5000:] if len(content) > 5000 else content  # Last 5000 chars
                    })
    except Exception as e:
        logs = [{"filename": "error", "content": str(e)}]
    return jsonify(logs)

@app.route("/api/status")
def get_status():
    """Get system status"""
    status = {
        "timestamp": datetime.now().isoformat(),
        "sites_configured": 0,
        "sites_enabled": 0,
        "downloads_count": 0,
        "logs_count": 0,
        "config_valid": False
    }
    
    try:
        # Check sites
        with open(CONFIG_DIR / "sites.json") as f:
            data = json.load(f)
            sites = data.get("sites", [])
            status["sites_configured"] = len(sites)
            status["sites_enabled"] = sum(1 for s in sites if s.get("enabled"))
    except:
        pass
    
    # Check downloads
    if DOWNLOADS_DIR.exists():
        status["downloads_count"] = len(list(DOWNLOADS_DIR.glob("*.pdf")))
    
    # Check logs
    if LOGS_DIR.exists():
        status["logs_count"] = len(list(LOGS_DIR.glob("*.log")))
    
    status["config_valid"] = status["sites_configured"] > 0
    
    return jsonify(status)

@app.route("/api/test/<site_id>", methods=["POST"])
def test_site(site_id):
    """Run a test extraction for a site"""
    # This would trigger the actual extraction
    # For now, return a mock response
    return jsonify({
        "status": "test_triggered",
        "site_id": site_id,
        "message": "Test run started - check logs for results",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == "__main__":
    print("="*60)
    print("  Lien Extraction Dashboard")
    print("="*60)
    print("\nStarting server...")
    print("Open your browser to: http://localhost:5000")
    print("\nPress Ctrl+C to stop\n")
    
    # Create templates directory
    templates_dir = BASE_DIR / "templates"
    templates_dir.mkdir(exist_ok=True)
    
    # Create the HTML template
    dashboard_html = templates_dir / "dashboard.html"
    if not dashboard_html.exists():
        dashboard_html.write_text("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Federal Tax Lien Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            text-align: center;
        }
        .header h1 { font-size: 2rem; margin-bottom: 0.5rem; }
        .header p { opacity: 0.9; }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }
        .status-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }
        .card:hover { transform: translateY(-2px); }
        .card h3 {
            font-size: 0.875rem;
            text-transform: uppercase;
            color: #666;
            margin-bottom: 0.5rem;
        }
        .card .value {
            font-size: 2rem;
            font-weight: bold;
            color: #333;
        }
        .card .status {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
            margin-top: 0.5rem;
        }
        .status.ok { background: #d4edda; color: #155724; }
        .status.warning { background: #fff3cd; color: #856404; }
        .status.error { background: #f8d7da; color: #721c24; }
        
        .sites-section {
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .sites-section h2 {
            margin-bottom: 1rem;
            color: #333;
        }
        .site-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem;
            border-bottom: 1px solid #eee;
        }
        .site-item:last-child { border-bottom: none; }
        .site-info h4 { margin-bottom: 0.25rem; }
        .site-info p { font-size: 0.875rem; color: #666; }
        .site-actions {
            display: flex;
            gap: 0.5rem;
        }
        .btn {
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.875rem;
            transition: background 0.2s;
        }
        .btn-primary {
            background: #667eea;
            color: white;
        }
        .btn-primary:hover { background: #5568d3; }
        .btn-secondary {
            background: #e9ecef;
            color: #333;
        }
        .btn-secondary:hover { background: #dee2e6; }
        
        .logs-section {
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .logs-section h2 { margin-bottom: 1rem; }
        .log-entry {
            background: #f8f9fa;
            border-radius: 6px;
            padding: 1rem;
            margin-bottom: 0.5rem;
            font-family: 'Courier New', monospace;
            font-size: 0.875rem;
            overflow-x: auto;
        }
        .refresh-btn {
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            padding: 1rem 2rem;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 50px;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            font-size: 1rem;
        }
        .refresh-btn:hover { background: #5568d3; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏛️ Federal Tax Lien Automation</h1>
        <p>Monitor and manage county recorder extractions</p>
    </div>
    
    <div class="container">
        <div class="status-cards" id="status-cards">
            <div class="card">
                <h3>Sites Configured</h3>
                <div class="value" id="sites-count">-</div>
                <span class="status ok" id="sites-status">Loading...</span>
            </div>
            <div class="card">
                <h3>Downloads</h3>
                <div class="value" id="downloads-count">-</div>
                <span class="status ok">PDFs collected</span>
            </div>
            <div class="card">
                <h3>Log Files</h3>
                <div class="value" id="logs-count">-</div>
                <span class="status ok">Available</span>
            </div>
            <div class="card">
                <h3>System Status</h3>
                <div class="value" id="system-status">-</div>
                <span class="status ok" id="system-message">Loading...</span>
            </div>
        </div>
        
        <div class="sites-section">
            <h2>📍 Configured Sites</h2>
            <div id="sites-list">
                <p>Loading sites...</p>
            </div>
        </div>
        
        <div class="logs-section">
            <h2>📝 Recent Logs</h2>
            <div id="logs-list">
                <p>No logs available yet</p>
            </div>
        </div>
    </div>
    
    <button class="refresh-btn" onclick="loadAll()">🔄 Refresh</button>
    
    <script>
        async function loadStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                document.getElementById('sites-count').textContent = data.sites_configured;
                document.getElementById('downloads-count').textContent = data.downloads_count;
                document.getElementById('logs-count').textContent = data.logs_count;
                document.getElementById('system-status').textContent = data.config_valid ? 'OK' : 'Error';
                
                const sitesStatus = document.getElementById('sites-status');
                sitesStatus.textContent = data.sites_enabled + ' enabled';
                
                const systemMsg = document.getElementById('system-message');
                systemMsg.textContent = data.config_valid ? 'Ready' : 'Config Error';
                systemMsg.className = 'status ' + (data.config_valid ? 'ok' : 'error');
            } catch (e) {
                console.error('Failed to load status:', e);
            }
        }
        
        async function loadSites() {
            try {
                const response = await fetch('/api/sites');
                const data = await response.json();
                const sitesList = document.getElementById('sites-list');
                
                if (data.sites && data.sites.length > 0) {
                    sitesList.innerHTML = data.sites.map(site => `
                        <div class="site-item">
                            <div class="site-info">
                                <h4>${site.name}</h4>
                                <p>ID: ${site.id} | State: ${site.state} | ${site.enabled ? '✅ Enabled' : '❌ Disabled'}</p>
                            </div>
                            <div class="site-actions">
                                <button class="btn btn-primary" onclick="testSite('${site.id}')">Test</button>
                                <a href="${site.base_url}" target="_blank" class="btn btn-secondary">Visit</a>
                            </div>
                        </div>
                    `).join('');
                } else {
                    sitesList.innerHTML = '<p>No sites configured</p>';
                }
            } catch (e) {
                console.error('Failed to load sites:', e);
                document.getElementById('sites-list').innerHTML = '<p>Error loading sites</p>';
            }
        }
        
        async function loadLogs() {
            try {
                const response = await fetch('/api/logs');
                const logs = await response.json();
                const logsList = document.getElementById('logs-list');
                
                if (logs && logs.length > 0) {
                    logsList.innerHTML = logs.map(log => `
                        <div class="log-entry">
                            <strong>${log.filename}</strong><br>
                            <pre>${log.content}</pre>
                        </div>
                    `).join('');
                } else {
                    logsList.innerHTML = '<p>No logs available</p>';
                }
            } catch (e) {
                console.error('Failed to load logs:', e);
            }
        }
        
        async function testSite(siteId) {
            try {
                const response = await fetch(`/api/test/${siteId}`, { method: 'POST' });
                const result = await response.json();
                alert(`Test triggered for site ${siteId}!\\n\\n${result.message}`);
            } catch (e) {
                alert('Failed to trigger test: ' + e.message);
            }
        }
        
        function loadAll() {
            loadStatus();
            loadSites();
            loadLogs();
        }
        
        // Load on page load
        loadAll();
        
        // Auto-refresh every 30 seconds
        setInterval(loadAll, 30000);
    </script>
</body>
</html>""")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
