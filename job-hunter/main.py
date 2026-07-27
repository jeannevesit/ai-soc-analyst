from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import sqlite3
from database import get_db, init_db

app = FastAPI(title="NevesSec Job Hunter Agent")

# Initialize database schema
init_db()

# Set up templates and static files directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/jobs")
async def get_jobs():
    conn = get_db()
    cursor = conn.cursor()
    
    # Get stats
    cursor.execute("SELECT status, COUNT(*) as count FROM jobs GROUP BY status")
    stats_raw = cursor.fetchall()
    stats = {"PENDING_REVIEW": 0, "SUBMITTED": 0, "REJECTED": 0}
    for row in stats_raw:
        if row["status"] in stats:
            stats[row["status"]] = row["count"]
            
    # Get pending review list
    cursor.execute("""
        SELECT id, title, company, url, description, match_score, created_at 
        FROM jobs 
        WHERE status = 'PENDING_REVIEW' 
        ORDER BY match_score DESC
    """)
    pending = [dict(row) for row in cursor.fetchall()]
    
    # Get submitted history log
    cursor.execute("""
        SELECT id, title, company, url, match_score, created_at 
        FROM jobs 
        WHERE status = 'SUBMITTED' 
        ORDER BY created_at DESC
    """)
    submitted = [dict(row) for row in cursor.fetchall()]

    # Get rejected list
    cursor.execute("""
        SELECT id, title, company, url, match_score, created_at 
        FROM jobs 
        WHERE status = 'REJECTED' 
        ORDER BY created_at DESC
    """)
    rejected = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return {
        "stats": stats,
        "pending": pending,
        "submitted": submitted,
        "rejected": rejected
    }

@app.get("/api/jobs/{job_id}/drafts")
async def get_job_drafts(job_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, field_key, field_label, field_value FROM drafts WHERE job_id = ?", (job_id,))
    drafts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return drafts

@app.post("/api/jobs/{job_id}/save")
async def save_drafts(job_id: int, request: Request):
    data = await request.json()
    conn = get_db()
    cursor = conn.cursor()
    
    for key, value in data.items():
        cursor.execute("UPDATE drafts SET field_value = ? WHERE job_id = ? AND field_key = ?", (value, job_id, key))
        
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Draft changes saved."}

@app.post("/api/jobs/{job_id}/approve")
async def approve_job(job_id: int, request: Request):
    data = await request.json()
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if job exists and status is PENDING_REVIEW
    cursor.execute("SELECT id, title, company, url FROM jobs WHERE id = ? AND status = 'PENDING_REVIEW'", (job_id,))
    job = cursor.fetchone()
    if not job:
        conn.close()
        raise HTTPException(status_code=404, detail="Job not found or already processed.")
        
    # Save edits first
    for key, value in data.items():
        cursor.execute("UPDATE drafts SET field_value = ? WHERE job_id = ? AND field_key = ?", (value, job_id, key))
        
    # Set status to SUBMITTED
    cursor.execute("UPDATE jobs SET status = 'SUBMITTED' WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    
    # Trigger simulated automation logs (Playwright run)
    logs = [
        f"Starting browser automation script for {job['company']}...",
        f"Navigating to job portal URL: {job['url']}",
        "Detecting standard Greenhouse form elements...",
        "Pre-filling personal contact details (Jean Neves)...",
        "Uploading resume: /app/data/Jean_Neves_Resume.pdf (SUCCESS)",
        "Mapping custom application questions to approved drafts..."
    ]
    for key, val in data.items():
        if key != "cover_letter":
            logs.append(f" - Filled: '{key}' -> '{val[:40]}...'")
            
    logs.extend([
        "Simulating realistic human click delays (1200ms)...",
        "Bypassing bot-detection signatures...",
        f"Application successfully submitted to {job['company']}! API logged status 200 OK."
    ])
    
    return {
        "status": "success",
        "message": f"Successfully applied to {job['company']}.",
        "logs": logs
    }

@app.post("/api/jobs/{job_id}/reject")
async def reject_job(job_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE jobs SET status = 'REJECTED' WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Application rejected and archived."}

@app.post("/api/jobs/trigger-scrape")
async def trigger_scrape():
    # Mocking discovery of a new job posting
    conn = get_db()
    cursor = conn.cursor()
    
    # We will check if it already exists to avoid duplicate entries
    new_url = "https://boards.greenhouse.io/sentinelone/jobs/5592812"
    cursor.execute("SELECT id FROM jobs WHERE url = ?", (new_url,))
    if cursor.fetchone():
        conn.close()
        return {"status": "no_new_jobs", "message": "No new jobs discovered at this time."}
        
    cursor.execute("""
        INSERT INTO jobs (title, company, url, description, match_score, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "Endpoint Security & Systems Engineer",
        "SentinelOne",
        new_url,
        "Deploy and monitor endpoint policies. Automate response scripts and patch configuration. Collaborate with IT and Security teams to enforce compliance baselines.",
        94,
        "PENDING_REVIEW"
    ))
    job_id = cursor.lastrowid
    
    drafts = [
        ("cover_letter", "Cover Letter", "Dear SentinelOne Recruitment Team,\n\nI am writing to express my enthusiasm for the Endpoint Security & Systems Engineer opening. My background building automated EDR threat containment pipelines (Wazuh/Playwright/ n8n) and administering Microsoft Intune alignments at BTG Pactual and SPX Capital maps directly to your technical criteria.\n\nBest regards,\nJean Neves"),
        ("q_compliance", "How do you automate compliance verification?", "I deploy automated configuration baselines in Microsoft Intune and enforce them via conditional access. I also write custom PowerShell scripts to audit registry keys and verify endpoint protection agents are active in real-time.")
    ]
    
    for draft in drafts:
        cursor.execute("""
            INSERT INTO drafts (job_id, field_key, field_label, field_value)
            VALUES (?, ?, ?, ?)
        """, (job_id, draft[0], draft[1], draft[2]))
        
    conn.commit()
    conn.close()
    return {"status": "success", "message": "New job discovered: Endpoint Security & Systems Engineer at SentinelOne!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8095, reload=True)
