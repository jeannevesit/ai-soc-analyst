import os
import secrets
import string
import sqlite3
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from cryptography.fernet import Fernet

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pam-simulator")

DB_FILE = "data/pam.db"
KEY_FILE = "data/secret.key"

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

# 1. Initialize Encryption Key (AES Fernet)
if not os.path.exists(KEY_FILE):
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
        f.write(key)
    logger.info("Generated new secret key for credential vault.")
else:
    with open(KEY_FILE, "rb") as f:
        key = f.read()

cipher = Fernet(key)

def encrypt_password(plain_password: str) -> str:
    return cipher.encrypt(plain_password.encode()).decode()

def decrypt_password(encrypted_password: str) -> str:
    return cipher.decrypt(encrypted_password.encode()).decode()

def generate_random_password(length=16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))

# 2. Database Initialization
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Assets Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            username TEXT,
            encrypted_password TEXT,
            status TEXT, -- LOCKED, CHECKED_OUT, JIT_REQUIRED
            requires_jit INTEGER -- 1 for True, 0 for False
        )
    """)
    
    # JIT Requests Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER,
            requestor TEXT,
            reason TEXT,
            duration_minutes INTEGER,
            status TEXT, -- PENDING, APPROVED, ACTIVE, EXPIRED, DENIED
            expires_at TEXT,
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
    """)
    
    # Audit Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            username TEXT,
            event_type TEXT, -- CHECKOUT, CHECKIN, JIT_REQUEST, APPROVAL, ROTATION, EXPIRED
            asset_name TEXT,
            details TEXT
        )
    """)
    
    # Seed default assets if table is empty
    cursor.execute("SELECT COUNT(*) FROM assets")
    if cursor.fetchone()[0] == 0:
        default_assets = [
            ("SQL Production Database", "sa_prod", generate_random_password(), "LOCKED", 0),
            ("Linux Web Server Root", "root", generate_random_password(), "LOCKED", 0),
            ("Windows Domain Controller Admin", "ad_admin", generate_random_password(), "LOCKED", 1),
            ("AWS Root Console", "aws_admin", generate_random_password(), "LOCKED", 1)
        ]
        for name, user, pwd, status, req_jit in default_assets:
            cursor.execute(
                "INSERT INTO assets (name, username, encrypted_password, status, requires_jit) VALUES (?, ?, ?, ?, ?)",
                (name, user, encrypt_password(pwd), status, req_jit)
            )
        
        # Log database seeding
        cursor.execute(
            "INSERT INTO audit_logs (timestamp, username, event_type, asset_name, details) VALUES (?, ?, ?, ?, ?)",
            (datetime.utcnow().isoformat(), "SYSTEM", "ROTATION", "ALL", "Initial seed vault populated with encrypted credentials.")
        )
        conn.commit()
        logger.info("Seeded default assets database.")
    
    conn.close()

init_db()

# 3. Background JIT Expiration Daemon
def check_expired_sessions():
    """Background loop that checks for expired JIT access grants, rotates passwords, and audits."""
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()
            
            # Find ACTIVE requests that have expired
            cursor.execute("""
                SELECT r.id, r.asset_id, r.requestor, a.name, a.username 
                FROM requests r 
                JOIN assets a ON r.asset_id = a.id 
                WHERE r.status = 'ACTIVE' AND r.expires_at <= ?
            """, (now,))
            
            expired = cursor.fetchall()
            
            for req in expired:
                req_id = req["id"]
                asset_id = req["asset_id"]
                asset_name = req["name"]
                username = req["username"]
                requestor = req["requestor"]
                
                # 1. Update request status to EXPIRED
                cursor.execute("UPDATE requests SET status = 'EXPIRED' WHERE id = ?", (req_id,))
                
                # 2. Lock the asset back down
                cursor.execute("UPDATE assets SET status = 'LOCKED' WHERE id = ?", (asset_id,))
                
                # 3. Rotate the password immediately
                new_pwd = generate_random_password()
                cursor.execute("UPDATE assets SET encrypted_password = ? WHERE id = ?", (encrypt_password(new_pwd), asset_id))
                
                # 4. Write audit logs
                cursor.execute(
                    "INSERT INTO audit_logs (timestamp, username, event_type, asset_name, details) VALUES (?, ?, ?, ?, ?)",
                    (datetime.utcnow().isoformat(), "SYSTEM", "EXPIRED", asset_name, f"JIT session expired for {requestor}. Access revoked.")
                )
                cursor.execute(
                    "INSERT INTO audit_logs (timestamp, username, event_type, asset_name, details) VALUES (?, ?, ?, ?, ?)",
                    (datetime.utcnow().isoformat(), "SYSTEM", "ROTATION", asset_name, f"Credential auto-rotated on session expiry.")
                )
                
                logger.info(f"Revoked JIT access and rotated credential for {asset_name}.")
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error in JIT expiration daemon: {str(e)}")
        
        time.sleep(5)

daemon_thread = threading.Thread(target=check_expired_sessions, daemon=True)
daemon_thread.start()

# 4. FastAPI Setup
app = FastAPI(title="NevesSec PAM / Privileged Access Simulator")

# Serve static files and templates
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Pydantic Schemas
class JITRequestModel(BaseModel):
    asset_id: int
    requestor: str
    reason: str
    duration_minutes: int

# API Endpoints
@app.get("/", response_class=HTMLResponse)
def get_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/assets")
def get_assets():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, username, status, requires_jit FROM assets")
    assets = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return assets

@app.post("/api/assets/checkout/{asset_id}")
def checkout_asset(asset_id: int, requestor: str = "jean.neves"):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
    asset = cursor.fetchone()
    
    if not asset:
        conn.close()
        raise HTTPException(status_code=404, detail="Asset not found")
        
    if asset["requires_jit"] == 1:
        conn.close()
        raise HTTPException(status_code=400, detail="Checkout blocked. This asset requires JIT elevation.")
        
    if asset["status"] == "CHECKED_OUT":
        conn.close()
        raise HTTPException(status_code=400, detail="Asset is already checked out by another user.")
        
    # Check out the asset
    cursor.execute("UPDATE assets SET status = 'CHECKED_OUT' WHERE id = ?", (asset_id,))
    cursor.execute(
        "INSERT INTO audit_logs (timestamp, username, event_type, asset_name, details) VALUES (?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), requestor, "CHECKOUT", asset["name"], f"Standard checkout. Temporary credential revealed.")
    )
    conn.commit()
    
    decrypted_password = decrypt_password(asset["encrypted_password"])
    conn.close()
    
    return {
        "status": "success",
        "asset_name": asset["name"],
        "username": asset["username"],
        "password": decrypted_password
    }

@app.post("/api/assets/checkin/{asset_id}")
def checkin_asset(asset_id: int, requestor: str = "jean.neves"):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
    asset = cursor.fetchone()
    
    if not asset:
        conn.close()
        raise HTTPException(status_code=404, detail="Asset not found")
        
    if asset["status"] == "LOCKED":
        conn.close()
        raise HTTPException(status_code=400, detail="Asset is already locked.")
        
    # Check in asset and auto-rotate password
    new_pwd = generate_random_password()
    cursor.execute("UPDATE assets SET status = 'LOCKED', encrypted_password = ? WHERE id = ?", (encrypt_password(new_pwd), asset_id))
    
    cursor.execute(
        "INSERT INTO audit_logs (timestamp, username, event_type, asset_name, details) VALUES (?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), requestor, "CHECKIN", asset["name"], "Asset checked in. Credential invalidated.")
    )
    cursor.execute(
        "INSERT INTO audit_logs (timestamp, username, event_type, asset_name, details) VALUES (?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), "SYSTEM", "ROTATION", asset["name"], "Credential auto-rotated on check-in.")
    )
    
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Asset checked in and password rotated."}

@app.post("/api/jit/request")
def request_jit_access(payload: JITRequestModel):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM assets WHERE id = ?", (payload.asset_id,))
    asset = cursor.fetchone()
    
    if not asset:
        conn.close()
        raise HTTPException(status_code=404, detail="Asset not found")
        
    if asset["status"] == "CHECKED_OUT":
        conn.close()
        raise HTTPException(status_code=400, detail="Asset is currently in use.")
        
    cursor.execute(
        "INSERT INTO requests (asset_id, requestor, reason, duration_minutes, status, expires_at) VALUES (?, ?, ?, ?, ?, NULL)",
        (payload.asset_id, payload.requestor, payload.reason, payload.duration_minutes, "PENDING")
    )
    
    cursor.execute(
        "INSERT INTO audit_logs (timestamp, username, event_type, asset_name, details) VALUES (?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), payload.requestor, "JIT_REQUEST", asset["name"], f"JIT request submitted for {payload.duration_minutes}m. Reason: {payload.reason}")
    )
    
    conn.commit()
    conn.close()
    return {"status": "success", "message": "JIT request submitted successfully."}

@app.get("/api/jit/requests")
def get_jit_requests():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.id, r.requestor, r.reason, r.duration_minutes, r.status, r.expires_at, a.name as asset_name, a.id as asset_id
        FROM requests r
        JOIN assets a ON r.asset_id = a.id
        ORDER BY r.id DESC
    """)
    requests_list = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return requests_list

@app.post("/api/jit/approve/{request_id}")
def approve_jit_request(request_id: int, approver: str = "security.admin"):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT r.*, a.name, a.encrypted_password FROM requests r JOIN assets a ON r.asset_id = a.id WHERE r.id = ?", (request_id,))
    request_data = cursor.fetchone()
    
    if not request_data:
        conn.close()
        raise HTTPException(status_code=404, detail="Request not found")
        
    if request_data["status"] != "PENDING":
        conn.close()
        raise HTTPException(status_code=400, detail=f"Request is already in state: {request_data['status']}")
        
    # Calculate expiry
    expiry = (datetime.utcnow() + timedelta(minutes=request_data["duration_minutes"])).isoformat()
    
    # 1. Update request status to ACTIVE and set expiry
    cursor.execute("UPDATE requests SET status = 'ACTIVE', expires_at = ? WHERE id = ?", (expiry, request_id))
    
    # 2. Update asset status to CHECKED_OUT
    cursor.execute("UPDATE assets SET status = 'CHECKED_OUT' WHERE id = ?", (request_data["asset_id"],))
    
    # 3. Log approval and activation
    cursor.execute(
        "INSERT INTO audit_logs (timestamp, username, event_type, asset_name, details) VALUES (?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), approver, "APPROVAL", request_data["name"], f"JIT Request #{request_id} approved. Expiry set to {expiry} UTC.")
    )
    
    conn.commit()
    decrypted_password = decrypt_password(request_data["encrypted_password"])
    conn.close()
    
    return {
        "status": "success",
        "message": "JIT request approved and active.",
        "password": decrypted_password,
        "expires_at": expiry
    }

@app.post("/api/jit/deny/{request_id}")
def deny_jit_request(request_id: int, approver: str = "security.admin"):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT r.*, a.name FROM requests r JOIN assets a ON r.asset_id = a.id WHERE r.id = ?", (request_id,))
    request_data = cursor.fetchone()
    
    if not request_data:
        conn.close()
        raise HTTPException(status_code=404, detail="Request not found")
        
    if request_data["status"] != "PENDING":
        conn.close()
        raise HTTPException(status_code=400, detail="Request is not pending.")
        
    cursor.execute("UPDATE requests SET status = 'DENIED' WHERE id = ?", (request_id,))
    cursor.execute(
        "INSERT INTO audit_logs (timestamp, username, event_type, asset_name, details) VALUES (?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), approver, "DENIED", request_data["name"], f"JIT Request #{request_id} denied.")
    )
    
    conn.commit()
    conn.close()
    return {"status": "success", "message": "JIT request denied."}

@app.get("/api/audit")
def get_audit_logs():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 100")
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return logs

@app.post("/api/audit/clear")
def clear_logs():
    """Admin endpoint to clear logs and seed initial reset event."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM audit_logs")
    cursor.execute(
        "INSERT INTO audit_logs (timestamp, username, event_type, asset_name, details) VALUES (?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), "SYSTEM", "ROTATION", "ALL", "Audit trail cleared by administrator. Restarted event logs.")
    )
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Audit logs cleared."}
