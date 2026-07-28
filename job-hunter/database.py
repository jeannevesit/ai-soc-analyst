import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "job_hunter.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Create Jobs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            description TEXT,
            match_score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'PENDING_REVIEW',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create Drafts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            field_key TEXT NOT NULL,
            field_label TEXT NOT NULL,
            field_value TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    
    # Check if empty to seed mock data
    cursor.execute("SELECT COUNT(*) FROM jobs")
    if cursor.fetchone()[0] == 0:
        seed_mock_data(conn)
        
    conn.close()

def seed_mock_data(conn):
    cursor = conn.cursor()
    
    # Real, Active Greenhouse Jobs
    jobs = [
        (
            "Security Engineer",
            "Neuralink",
            "https://boards.greenhouse.io/neuralink/jobs/4255745005",
            "Triage and investigate alerts (endpoint, identity, network, cloud). Build and tune detections (SIEM, EDR, SOAR) and develop tools to scale security coverage. Harden systems including SSO/MFA, identity lifecycle, and endpoint management.",
            95,
            "PENDING_REVIEW"
        ),
        (
            "Senior Security Engineer, Enterprise Security",
            "Braze",
            "https://boards.greenhouse.io/braze/jobs/5201198004",
            "Protect employees, assets, and work locations. Lead malware and threat investigations, implement Data Loss Prevention (DLP), secure SaaS integrations, and harden OS configurations.",
            91,
            "PENDING_REVIEW"
        ),
        (
            "Cloud Security Engineer",
            "Braze",
            "https://boards.greenhouse.io/braze/jobs/5072036004",
            "Day-to-day security operations including incident response, operating security tools (EDR, SIEM, vulnerability scanners), managing identity access controls, and driving vulnerability remediation.",
            88,
            "PENDING_REVIEW"
        )
    ]
    
    for job in jobs:
        cursor.execute("""
            INSERT INTO jobs (title, company, url, description, match_score, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, job)
        job_id = cursor.lastrowid
        
        # Add drafts based on the job
        if "Neuralink" in job[1]:
            drafts = [
                ("cover_letter", "Cover Letter", "Dear Neuralink Hiring Team,\n\nI am writing to apply for the Security Engineer role. Combining 5+ years of endpoint security administration (Intune/Jamf Pro) and pursuing an M.S. in Cybersecurity at NYU Tandon, I specialize in building automated SIEM/EDR containment pipelines. I am highly motivated by your mission to secure the next generation of brain-computer interface platforms.\n\nBest regards,\nJean Neves"),
                ("q_alert_triage", "Describe your experience triaging and investigating endpoint/identity alerts", "At BTG Pactual and SPX Capital, I served as the primary escalation point for identity and endpoint incidents. I triaged alerts, tracked indicator configurations, and managed user isolation workflows across global multi-platform environments."),
                ("q_automation", "How have you built tools to scale security coverage?", "I built an API-driven orchestration dashboard (ERCO) that automatically receives EDR webhooks, isolates workstations via MDM APIs (Intune/Jamf), and locks G-Suite SSO sessions, minimizing response latency to under 10 seconds.")
            ]
        elif "Senior Security Engineer" in job[0]:
            drafts = [
                ("cover_letter", "Cover Letter", "Dear Braze Recruitment Team,\n\nI am excited to apply for the Senior Security Engineer, Enterprise Security position. My experience managing patch distribution via PDQ Deploy, enforcing device DLP baselines, and administering Active Directory matches your enterprise security goals.\n\nSincerely,\nJean Neves"),
                ("q_dlp", "What is your approach to implementing Data Loss Prevention (DLP) policies?", "I enforce endpoint DLP policies scoped by user groups and device compliance states. By tying DLP rules with Intune/Entra ID Conditional Access, I ensure that corporate data is restricted on unauthorized or non-compliant workstations.")
            ]
        else:
            drafts = [
                ("cover_letter", "Cover Letter", "Dear Braze Team,\n\nI am applying for the Cloud Security Engineer role. With hands-on experience tuning wazuh agents, deploying OS compliance profiles, and managing privileged access, I am eager to help operate and scale your security tooling.\n\nSincerely,\nJean Neves"),
                ("q_vulnerability", "How do you coordinate vulnerability remediation across a workstation fleet?", "I leverage MDM patching schedules integrated with asset compliance logs. I establish SLA-based compliance baselines in Intune to automatically push critical OS patches, using telemetry dashboards to track remediation rates.")
            ]
            
        for draft in drafts:
            cursor.execute("""
                INSERT INTO drafts (job_id, field_key, field_label, field_value)
                VALUES (?, ?, ?, ?)
            """, (job_id, draft[0], draft[1], draft[2]))
            
    conn.commit()

if __name__ == "__main__":
    init_db()
    print("Database initialized and seeded successfully.")
