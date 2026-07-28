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
    
    # Real, Active US Remote Greenhouse Jobs
    jobs = [
        (
            "Staff Security Engineer (Remote - US)",
            "SmarterDx",
            "https://boards.greenhouse.io/smarterdx/jobs/5283525004",
            "SmarterDx is hiring a remote Staff Security Engineer in the US. Focus on AI security (guardrails for agentic tooling and ML workloads), threat detection, and incident response. Build and run detections using Panther and Python.",
            95,
            "PENDING_REVIEW"
        ),
        (
            "Security Engineer (Remote - US)",
            "Chainguard",
            "https://boards.greenhouse.io/chainguard/jobs/5643441003",
            "Chainguard is hiring a remote Security Engineer in the US. Secure Identity and Access Management (IAM), AI infrastructure, and cloud security (GCP/AWS/Azure).",
            91,
            "PENDING_REVIEW"
        ),
        (
            "Software Security Engineer - Corporate Platforms (Remote - US)",
            "Wiz",
            "https://boards.greenhouse.io/wiz/jobs/4272186005",
            "Wiz is hiring a remote Software Security Engineer in the US. Develop enterprise security tools, manage endpoint security configurations, Conditional Access, IAM, detection response, and vulnerability management.",
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
        
        # Add drafts (technical questions only - NO cover letter)
        if "SmarterDx" in job[1]:
            drafts = [
                ("q_ai_security", "Describe your approach to implementing guardrails for AI and agentic tools", "I implement input/output validation, system prompt hardening, and monitor LLM tool calls using real-time policy engines to prevent prompt injection and unauthorized execution of tools."),
                ("q_python", "What is your experience writing detection rules or automation in Python?", "I write Python scripts to parse system logs, query API endpoints of cloud providers, and automate alert response. I also write custom detections for logging platforms using Python syntax.")
            ]
        elif "Chainguard" in job[1]:
            drafts = [
                ("q_cloud", "What is your experience securing GCP, AWS, or Azure environments?", "I configure IAM policies, restrict network access via VPC controls, and monitor logging streams (such as CloudTrail or Stackdriver) to ensure multi-cloud environment integrity."),
                ("q_iam", "Describe your experience managing Identity and Access Management (IAM) permissions", "I enforce least-privilege configurations, audit stale credentials, and manage automated account provisioning integrated with Entra ID and Google Workspace directories.")
            ]
        else:
            drafts = [
                ("q_endpoint", "How do you manage and audit endpoint security configurations at scale?", "I design, deploy, and audit MDM configurations (Microsoft Intune and Jamf Pro) across Windows and macOS fleets, ensuring compliance baselines and patch enforcement."),
                ("q_vuln", "Describe your workflow for vulnerability management and remediation", "I prioritize vulnerabilities based on CVSS scores and actual threat availability, deploy patches automatically via MDM schedules, and monitor success rates via custom telemetry dashboards.")
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
