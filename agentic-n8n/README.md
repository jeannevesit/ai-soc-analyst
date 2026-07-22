# Agentic n8n + MCP SOC Analyst (Local Workflow Setup)

This folder contains **Track B** of the AI SOC Analyst project—a local, agentic orchestration pipeline using **n8n** (workflow builder), the **Model Context Protocol (MCP)**, and **Google Gemini** to autonomously triage and resolve alerts inside an Enterprise SIEM.

---

## 📂 Component Layout

*   `docker-compose.yml`: Spins up n8n, the Mock SIEM API, and the custom MCP Server.
*   `mock-siem/`: FastAPI app representing our threat log database.
*   `mcp-server/`: Python-based MCP server providing incident triage tools.
*   `workflow.json`: Pre-configured n8n workflow export ready for import.

---

## ⚡ Quick Start

### 1. Launch the Docker Containers
In your terminal, navigate to this folder and run:
```bash
docker-compose up --build
```
This spins up three containers:
*   **n8n** at `http://localhost:5678`
*   **Mock SIEM Console** at `http://localhost:8000`
*   **Custom MCP Server** at `http://localhost:8500`

### 2. Configure n8n & Import Workflow
1. Open `http://localhost:5678` in your browser. Set up a free local account.
2. In the n8n sidebar, click **Workflows** -> **Import from File** (top right dropdown).
3. Select the `workflow.json` located in this directory.
4. Double-click the **Google Gemini** node, click the credential dropdown -> *Create New Credential*, and paste your Gemini API key (obtainable from Google AI Studio).
5. (Optional) If you have a VirusTotal API Key, set it in the environment variable `VIRUSTOTAL_API_KEY` in your shell before running `docker-compose up`, or update the `mcp-server` service environment in the compose file.

### 3. Run the Analyst Triage Workflow
1. Visit the Mock SIEM Console at `http://localhost:8000` to view the mock alerts (e.g. employee phishing clicks, SSH brute-forcing).
2. Inside your n8n workspace tab, click **Test Workflow** at the bottom.
3. Watch the nodes light up in green as the AI Agent:
   - Fetches the active alerts.
   - Leverages MCP to check indicators on VirusTotal.
   - Analyzes threat commands.
   - Closes the alerts in the SIEM database with detailed resolution summaries.
   - Logs a mock handover report email to `sent_emails.log`.
4. Refresh your Mock SIEM webpage to see the alerts marked as **RESOLVED** with Gemini's detailed incident investigation comments!
