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
    
    # Mock Jobs
    jobs = [
        (
            "Senior Security Endpoint Engineer",
            "Dragos, Inc.",
            "https://boards.greenhouse.io/dragos/jobs/4019283",
            "Own the complete endpoint lifecycle including provisioning, configuration, and decommission using Microsoft Intune and Jamf Pro. Lead endpoint threat containment and optimize EDR/Wazuh alert detection policies.",
            92,
            "PENDING_REVIEW"
        ),
        (
            "Security Endpoint Specialist",
            "CrowdStrike",
            "https://jobs.lever.co/crowdstrike/8a7b6c5d",
            "Support corporate workstation security posture, deploy MDM configuration baselines, tune EDR rules, and administer identity mappings in Entra ID.",
            85,
            "PENDING_REVIEW"
        ),
        (
            "IAM & Systems Engineer",
            "SPX Capital",
            "https://boards.greenhouse.io/spxcapital/jobs/110293",
            "Manage hybrid directory systems, deploy zero-trust access controls, manage Senha Segura PAM instances, and write custom PowerShell automation scripts.",
            89,
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
        if "Dragos" in job[1]:
            drafts = [
                ("cover_letter", "Cover Letter", "Dear Hiring Team at Dragos,\n\nI am writing to express my strong interest in the Senior Security Endpoint Engineer role. With over 5 years of experience managing multi-platform fleets via Microsoft Intune and Jamf Pro, and currently pursuing my M.S. in Cybersecurity at NYU Tandon, I specialize in automating endpoint compliance and containment. I look forward to contributing to Dragos' critical infrastructure security mission.\n\nSincerely,\nJean Neves"),
                ("q_mdm", "Describe your experience with MDM configuration at scale", "At BTG Pactual and SPX Capital, I managed Intune and Jamf MDM configurations for hybrid fleets. I built Autopilot provisioning pipelines, custom compliance baselines, and enforced Conditional Access, reducing provisioning errors and security compliance gaps by over 30%."),
                ("q_edr", "How do you approach EDR threat containment?", "I deploy automated SOAR containment playbooks. If an EDR alert is triggered, my API gateway automatically calls the Intune isolate endpoint and suspends G-Suite SSO access in parallel. I balance this control with user self-remediation options to reduce helpdesk friction.")
            ]
        elif "CrowdStrike" in job[1]:
            drafts = [
                ("cover_letter", "Cover Letter", "Dear CrowdStrike Hiring Team,\n\nI am thrilled to apply for the Security Endpoint Specialist position. My background in tuning wazuh agents, deploying Intune policies, and administering privileged access fits perfectly with CrowdStrike's endpoint protection ecosystem.\n\nSincerely,\nJean Neves"),
                ("q_entra", "What Entra ID / identity policies have you implemented?", "I regularly design and configure Entra ID Conditional Access policies, scoping endpoint DLP rules by user and device posture to enforce strict zero-trust access control across corporate and BYOD fleets.")
            ]
        else:
            drafts = [
                ("cover_letter", "Cover Letter", "Dear SPX Capital Team,\n\nI am writing to apply for the IAM & Systems Engineer position. Having managed Google Workspace, M365, and Senha Segura PAM systems previously, I am excited to help harden your directory architectures and security operations.\n\nSincerely,\nJean Neves"),
                ("q_scripting", "Provide an example of a PowerShell automation script you wrote", "I wrote custom PowerShell monitoring and remediation scripts deployed via Intune to audit and quarantine unauthorized local administrator privileges across our global workstation fleet.")
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
