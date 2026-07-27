import requests
import json
import os
from database import get_db

def scrape_greenhouse_feed(company_board_token):
    """
    Simulates fetching jobs from Greenhouse Board API:
    GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs
    """
    print(f"Polling Greenhouse API for: {company_board_token}...")
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_board_token}/jobs"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json().get("jobs", [])
    except Exception as e:
        print(f"Error fetching greenhouse board: {e}")
    return []

def evaluate_job_match(job_title, job_description):
    """
    Evaluates how closely a job description matches the user profile.
    Normally uses the Gemini LLM model to return a score 0-100.
    """
    # Simple semantic keyword matching for default demonstration
    title_lower = job_title.lower()
    keywords = ["endpoint", "intune", "jamf", "security", "systems", "compliance"]
    score = 50
    for kw in keywords:
        if kw in title_lower:
            score += 8
    return min(score, 98)
