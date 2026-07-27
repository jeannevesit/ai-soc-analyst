import os
import sqlite3
import logging
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("endpoint-soar")

DB_FILE = "data/endpoint_soar.db"

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(force: bool = False):
    conn = get_db()
    cursor = conn.cursor()
    
    if force:
        cursor.execute("DROP TABLE IF EXISTS devices")
        cursor.execute("DROP TABLE IF EXISTS incidents")
        cursor.execute("DROP TABLE IF EXISTS actions")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        platform TEXT,
        owner TEXT,
        owner_email TEXT,
        compliance_status TEXT,
        last_checkin TEXT,
        ip_address TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        threat_name TEXT,
        severity TEXT,
        status TEXT,
        details TEXT,
        timestamp TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        device_name TEXT,
        action_type TEXT,
        details TEXT
    )
    """)
    
    # Check if empty, then seed default fleet
    cursor.execute("SELECT COUNT(*) FROM devices")
    if cursor.fetchone()[0] == 0:
        default_devices = [
            ("jean-macbook-pro", "macOS", "Jean Neves", "jean.neves@nevessec.com", "COMPLIANT", "Just now", "192.168.1.15"),
            ("win-finance-03", "Windows", "Finance Dept", "finance.ops@nevessec.com", "COMPLIANT", "5 mins ago", "192.168.3.42"),
            ("srv-prod-sql", "Linux", "Database Admin", "db.admin@nevessec.com", "COMPLIANT", "12 mins ago", "10.0.4.10"),
            ("ceo-ipad-01", "iOS", "CEO Office", "ceo.executive@nevessec.com", "COMPLIANT", "1 hr ago", "10.0.12.5")
        ]
        cursor.executemany("""
        INSERT INTO devices (name, platform, owner, owner_email, compliance_status, last_checkin, ip_address)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, default_devices)
        
        # Log initial bootstrap action
        cursor.execute("""
        INSERT INTO actions (timestamp, device_name, action_type, details)
        VALUES (?, 'ALL', 'SYSTEM', 'ERCO Device Compliance Registry bootstrapped.')
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
        
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")

# Bootstrap on startup
init_db()

app = FastAPI(title="NevesSec ERCO | Endpoint Response & Compliance Orchestrator")

# Mount static and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Pydantic Schemas
class ThreatSimulation(BaseModel):
    device_name: str
    threat_type: str  # malware, credential_dump, compliance_drift

class SelfHealRequest(BaseModel):
    device_name: str

class WazuhAlert(BaseModel):
    agent_name: str
    rule_description: str
    severity: str
    details: str

# API Endpoints
@app.get("/", response_class=HTMLResponse)
def get_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})

@app.get("/api/devices")
def get_devices():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM devices")
    devices = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return devices

@app.get("/api/incidents")
def get_incidents():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT incidents.*, devices.name as device_name, devices.owner as device_owner, devices.owner_email 
    FROM incidents 
    JOIN devices ON incidents.device_id = devices.id
    ORDER BY incidents.id DESC
    """)
    incidents = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return incidents

@app.get("/api/actions")
def get_actions():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM actions ORDER BY id DESC LIMIT 50")
    actions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return actions

# 1. Threat Simulation Webhook
@app.post("/api/incidents/simulate")
def simulate_threat(req: ThreatSimulation):
    conn = get_db()
    cursor = conn.cursor()
    
    # Get device info
    cursor.execute("SELECT * FROM devices WHERE name = ?", (req.device_name,))
    device = cursor.fetchone()
    if not device:
        conn.close()
        raise HTTPException(status_code=404, detail="Device not found")
    
    device_id = device["id"]
    email = device["owner_email"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Map threat details
    if req.threat_type == "malware":
        threat_name = "Win32/CobaltStrike.Beacon"
        severity = "CRITICAL"
        details = "Unauthorized HTTP beaconing to known C2 IP address detected by EDR agent."
    elif req.threat_type == "credential_dump":
        threat_name = "T1003.001 - LSASS Memory Dump"
        severity = "HIGH"
        details = "LSASS.exe process memory read attempt detected. Potential credential theft."
    elif req.threat_type == "compliance_drift":
        threat_name = "Compliance Drift: Disk Encryption Disabled"
        severity = "MEDIUM"
        details = "BitLocker/FileVault disk encryption status reported as DISABLED."
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid threat type")
    
    # 1. Insert Open Incident
    cursor.execute("""
    INSERT INTO incidents (device_id, threat_name, severity, status, details, timestamp)
    VALUES (?, ?, ?, 'OPEN', ?, ?)
    """, (device_id, threat_name, severity, details, timestamp))
    
    # 2. Trigger Automated Containment Policies if CRITICAL or HIGH
    if severity in ["CRITICAL", "HIGH"]:
        # Isolate via Mock MDM API call simulation
        cursor.execute("UPDATE devices SET compliance_status = 'ISOLATED' WHERE id = ?", (device_id,))
        
        # Log Jamf/Intune Action
        mdm_system = "Jamf Pro" if device["platform"] == "macOS" else "Microsoft Intune"
        cursor.execute("""
        INSERT INTO actions (timestamp, device_name, action_type, details)
        VALUES (?, ?, 'ISOLATE', ?)
        """, (timestamp, req.device_name, f"Device isolated. Applied network quarantine policy via {mdm_system} API."))
        
        # Log Google Workspace/Identity Action (SSO Suspension)
        cursor.execute("""
        INSERT INTO actions (timestamp, device_name, action_type, details)
        VALUES (?, ?, 'SUSPEND_SSO', ?)
        """, (timestamp, req.device_name, f"SSO account session revoked & suspended for {email} via Workspace Directory SDK."))
    else:
        # Non-critical compliance drift: mark non-compliant, do not isolate
        cursor.execute("UPDATE devices SET compliance_status = 'NON_COMPLIANT' WHERE id = ?", (device_id,))
        cursor.execute("""
        INSERT INTO actions (timestamp, device_name, action_type, details)
        VALUES (?, ?, 'POLICY_ALERT', ?)
        """, (timestamp, req.device_name, "Marked Non-Compliant. Triggered email patch notification to user."))

    conn.commit()
    conn.close()
    
    logger.info(f"Simulated threat {threat_name} on {req.device_name}")
    return {"status": "success", "message": "Incident created & policies executed"}

# 2. Employee Self-Remediation & Healing Endpoint
@app.post("/api/devices/self-heal")
def self_heal_device(req: SelfHealRequest):
    conn = get_db()
    cursor = conn.cursor()
    
    # Get device info
    cursor.execute("SELECT * FROM devices WHERE name = ?", (req.device_name,))
    device = cursor.fetchone()
    if not device:
        conn.close()
        raise HTTPException(status_code=404, detail="Device not found")
    
    device_id = device["id"]
    email = device["owner_email"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Update compliance status back to COMPLIANT
    cursor.execute("UPDATE devices SET compliance_status = 'COMPLIANT' WHERE id = ?", (device_id,))
    
    # 2. Resolve the incidents
    cursor.execute("UPDATE incidents SET status = 'RESOLVED' WHERE device_id = ? AND status != 'RESOLVED'", (device_id,))
    
    # 3. Log the restoration actions in the SOAR audit log
    mdm_system = "Jamf Pro" if device["platform"] == "macOS" else "Microsoft Intune"
    cursor.execute("""
    INSERT INTO actions (timestamp, device_name, action_type, details)
    VALUES (?, ?, 'SELF_HEAL', ?)
    """, (timestamp, req.device_name, "Local malware removed & agent health check verified by employee scan."))
    
    cursor.execute("""
    INSERT INTO actions (timestamp, device_name, action_type, details)
    VALUES (?, ?, 'RESTORE', ?)
    """, (timestamp, req.device_name, f"Network containment profile removed. Restored connectivity via {mdm_system} API."))
    
    cursor.execute("""
    INSERT INTO actions (timestamp, device_name, action_type, details)
    VALUES (?, ?, 'UNSUSPEND_SSO', ?)
    """, (timestamp, req.device_name, f"SSO account reactivated & unsuspended for {email} via Workspace Directory SDK."))
    
    conn.commit()
    conn.close()
    
    logger.info(f"Device {req.device_name} self-healed successfully.")
    return {"status": "success", "message": "Device restored & incidents resolved"}

# 3. Reset Demo Endpoint
@app.post("/api/actions/clear")
def clear_logs():
    init_db(force=True)
    return {"status": "success", "message": "Demo database reset to initial seed state"}
