import os
import sys
import json
import base64
import logging
import requests
import datetime
from fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("SecurityMCPServer")

# Initialize FastMCP
mcp = FastMCP("Security Triage Agent Tools")

# Fetch environment variables
# If running inside docker network, SIEM URL is http://mock-siem:8000
SIEM_URL = os.environ.get("SIEM_URL", "http://localhost:8000")
VIRUSTOTAL_API_KEY = os.environ.get("VIRUSTOTAL_API_KEY", "")
EMAIL_LOG_FILE = os.path.join(os.path.dirname(__file__), "sent_emails.log")

@mcp.tool()
def get_siem_alerts() -> str:
    """Retrieve active open (unresolved) alerts from the SIEM database."""
    url = f"{SIEM_URL}/api/alerts?status=OPEN"
    logger.info(f"Fetching open alerts from {url}")
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            alerts = response.json()
            return json.dumps(alerts, indent=2)
        else:
            return f"Error: SIEM responded with status code {response.status_code} - {response.text}"
    except Exception as e:
        return f"Error connecting to SIEM API: {str(e)}"

@mcp.tool()
def analyze_indicator(indicator: str, indicator_type: str) -> str:
    """
    Perform Threat Intelligence enrichment on a security indicator (IP or URL) using VirusTotal.
    
    Args:
        indicator: The IP address, URL, or domain to scan.
        indicator_type: The type of indicator, must be 'IP', 'URL', or 'Command'.
    """
    logger.info(f"Analyzing {indicator_type} indicator: {indicator}")
    
    if not VIRUSTOTAL_API_KEY:
        return json.dumps({
            "status": "WARN",
            "message": "VirusTotal API Key missing from MCP Server environment. Scanning is disabled.",
            "indicator": indicator,
            "reputation": "UNKNOWN"
        })

    headers = {"x-apikey": VIRUSTOTAL_API_KEY}

    if indicator_type.upper() == "IP":
        url = f"https://www.virustotal.com/api/v3/ip_addresses/{indicator}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json().get("data", {})
                attributes = data.get("attributes", {})
                stats = attributes.get("last_analysis_stats", {})
                
                result = {
                    "provider": "VirusTotal",
                    "indicator": indicator,
                    "malicious_votes": stats.get("malicious", 0),
                    "suspicious_votes": stats.get("suspicious", 0),
                    "reputation_score": attributes.get("reputation", 0),
                    "country": attributes.get("country", "Unknown"),
                    "isp_owner": attributes.get("as_owner", "Unknown"),
                    "asn": attributes.get("asn", "Unknown")
                }
                return json.dumps(result, indent=2)
            else:
                return f"VirusTotal IP Lookup Error: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error connecting to VirusTotal for IP lookup: {str(e)}"

    elif indicator_type.upper() == "URL":
        # VirusTotal v3 requires URLs to be URL-safe base64 encoded without padding
        try:
            b64_url = base64.urlsafe_b64encode(indicator.encode()).decode().strip("=")
            url = f"https://www.virustotal.com/api/v3/urls/{b64_url}"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json().get("data", {})
                attributes = data.get("attributes", {})
                stats = attributes.get("last_analysis_stats", {})
                
                result = {
                    "provider": "VirusTotal",
                    "indicator": indicator,
                    "malicious_votes": stats.get("malicious", 0),
                    "suspicious_votes": stats.get("suspicious", 0),
                    "reputation_score": attributes.get("reputation", 0),
                    "title": attributes.get("title", "Unknown")
                }
                return json.dumps(result, indent=2)
            else:
                return f"VirusTotal URL Lookup Error: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error connecting to VirusTotal for URL lookup: {str(e)}"

    elif indicator_type.upper() == "COMMAND":
        # Rule-based analysis for commands (no VT lookup needed)
        malicious_patterns = ["curl", "wget", "bash", "sh |", "chmod +x", "base64 -d", "powershell", "bypass"]
        matched = [p for p in malicious_patterns if p in indicator.lower()]
        
        result = {
            "provider": "Local Signature Analysis",
            "indicator": indicator,
            "suspicious": len(matched) > 0,
            "detected_signatures": matched,
            "reputation_score": -50 if len(matched) > 0 else 0,
            "verdict": "MALICIOUS (Shell payload download/execution command)" if len(matched) > 0 else "UNKNOWN"
        }
        return json.dumps(result, indent=2)
        
    else:
        return f"Error: Unsupported indicator type '{indicator_type}'. Must be 'IP', 'URL', or 'Command'."

@mcp.tool()
def close_siem_alert(alert_id: str, status: str, resolution_notes: str) -> str:
    """
    Close/Resolve a security alert in the SIEM database.
    
    Args:
        alert_id: The ID of the alert to resolve (e.g. '101').
        status: The final status, must be 'RESOLVED' or 'DISMISSED'.
        resolution_notes: A summary explaining why it was resolved and MITRE ATT&CK codes.
    """
    url = f"{SIEM_URL}/api/alerts/{alert_id}/resolve"
    payload = {
        "status": status.upper(),
        "resolution_notes": resolution_notes
    }
    logger.info(f"Sending resolution for alert {alert_id} to {url}")
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return f"Success: Alert {alert_id} closed as {status}."
        else:
            return f"Error: SIEM responded with status code {response.status_code} - {response.text}"
    except Exception as e:
        return f"Error resolving alert {alert_id}: {str(e)}"

@mcp.tool()
def block_attacker_ip(ip_address: str, reason: str) -> str:
    """
    Block a malicious attacker IP address at the firewall (SOAR containment action).
    
    Args:
        ip_address: The external IP address to block.
        reason: The reason for the block rule (e.g. 'SSH brute-force scanning').
    """
    logger.info(f"Containment Action: Request to block IP {ip_address} due to: {reason}")
    blocklist_file = os.path.join(os.path.dirname(__file__), "blocklist.conf")
    
    # Check if IP is already in blocklist
    if os.path.exists(blocklist_file):
        try:
            with open(blocklist_file, "r") as f:
                if ip_address in f.read():
                    return f"Info: IP {ip_address} is already blocked in firewall blocklist."
        except Exception as e:
            logger.error(f"Failed to check blocklist file: {str(e)}")
            
    block_rule = f"{datetime.datetime.utcnow().isoformat()}Z - BLOCK {ip_address} - Reason: {reason}\n"
    
    try:
        with open(blocklist_file, "a") as f:
            f.write(block_rule)
        logger.info(f"IP {ip_address} successfully added to blocklist.conf")
        return f"Success: IP {ip_address} successfully blocked on perimeter firewall. Rule persisted to blocklist.conf."
    except Exception as e:
        return f"Error modifying firewall blocklist: {str(e)}"

@mcp.tool()
def send_security_email(subject: str, content: str) -> str:
    """
    Send an email incident report summary (shift-handover summary) to the security manager.
    
    Args:
        subject: The subject line of the security report.
        content: The text content detailing the incident and AI analyst triage actions.
    """
    logger.info(f"Simulating email dispatch: {subject}")
    
    email_data = f"""
============================================================
DATE: {datetime.datetime.utcnow().isoformat()}Z
SUBJECT: {subject}
------------------------------------------------------------
{content}
============================================================
\n"""

    try:
        with open(EMAIL_LOG_FILE, "a") as f:
            f.write(email_data)
        logger.info(f"Mock email successfully appended to {EMAIL_LOG_FILE}")
        return f"Success: Mock email log written to {EMAIL_LOG_FILE}."
    except Exception as e:
        return f"Error logging mock email: {str(e)}"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Security MCP Server")
    parser.add_argument("--sse", action="store_true", help="Run in Server-Sent Events (SSE) mode")
    parser.add_argument("--host", default="0.0.0.0", help="SSE server host")
    parser.add_argument("--port", type=int, default=8500, help="SSE server port")
    
    args = parser.parse_args()
    
    if args.sse:
        logger.info(f"Starting MCP Server on SSE transport at {args.host}:{args.port}")
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        logger.info("Starting MCP Server on stdio transport")
        mcp.run()
