let currentJob = null;
let activeJobs = [];

// Init on Page Load
document.addEventListener("DOMContentLoaded", () => {
    loadJobs();
    
    // Bind global buttons
    document.getElementById("btn-trigger-scrape").addEventListener("click", triggerScrape);
    document.getElementById("btn-save").addEventListener("click", saveDraft);
    document.getElementById("btn-reject").addEventListener("click", rejectJob);
    document.getElementById("btn-submit").addEventListener("click", approveAndSubmit);
});

// Load Jobs from API
async function loadJobs() {
    try {
        const res = await fetch("/api/jobs");
        const data = await res.json();
        
        // Update stats
        document.getElementById("stat-pending").innerText = data.stats.PENDING_REVIEW;
        document.getElementById("stat-submitted").innerText = data.stats.SUBMITTED;
        document.getElementById("stat-limit").innerText = `${5 - data.stats.SUBMITTED} / 5`;
        
        // Populate queue list
        const queueList = document.getElementById("queue-list");
        queueList.innerHTML = "";
        
        if (data.pending.length === 0) {
            queueList.innerHTML = '<div class="empty-state">No jobs pending review.</div>';
        } else {
            data.pending.forEach(job => {
                const card = document.createElement("div");
                card.className = `job-card ${currentJob && currentJob.id === job.id ? 'active' : ''}`;
                card.innerHTML = `
                    <div class="job-card-header">
                        <h3>${job.title}</h3>
                        <span class="score-badge">${job.match_score}% Match</span>
                    </div>
                    <div class="job-card-company">${job.company}</div>
                    <div class="job-card-meta">
                        <span>Discovered: ${new Date(job.created_at).toLocaleDateString()}</span>
                        <span><i class="fa-solid fa-chevron-right"></i></span>
                    </div>
                `;
                card.addEventListener("click", () => selectJob(job));
                queueList.appendChild(card);
            });
        }
        
        // Populate history rows
        const historyRows = document.getElementById("history-rows");
        historyRows.innerHTML = "";
        
        if (data.submitted.length === 0) {
            historyRows.innerHTML = '<tr><td colspan="5" class="empty-state">No submissions logged today.</td></tr>';
        } else {
            data.submitted.forEach(job => {
                const row = document.createElement("tr");
                row.innerHTML = `
                    <td><strong>${job.title}</strong></td>
                    <td>${job.company}</td>
                    <td><span class="score-badge" style="background: rgba(10, 132, 255, 0.08); border-color: rgba(10, 132, 255, 0.2); color: var(--primary);">${job.match_score}%</span></td>
                    <td>${new Date(job.created_at).toLocaleDateString()}</td>
                    <td><span class="score-badge" style="background: rgba(48, 209, 88, 0.08); border-color: rgba(48, 209, 88, 0.2); color: var(--success);"><i class="fa-solid fa-circle-check"></i> Applied</span></td>
                `;
                historyRows.appendChild(row);
            });
        }
    } catch (err) {
        console.error("Error loading jobs:", err);
    }
}

// Select a Job to Edit
async function selectJob(job) {
    currentJob = job;
    
    // Toggle active class in queue cards
    const cards = document.querySelectorAll(".job-card");
    cards.forEach(card => card.classList.remove("active"));
    event.currentTarget.classList.add("active");
    
    // Hide empty state and show editor
    document.getElementById("editor-empty").style.display = "none";
    document.getElementById("editor-workspace").style.display = "block";
    
    // Set metadata
    document.getElementById("edit-job-title").innerText = job.title;
    document.getElementById("edit-job-company").innerText = job.company;
    document.getElementById("edit-job-score").innerText = `${job.match_score}% Match`;
    document.getElementById("edit-job-url").href = job.url;
    document.getElementById("edit-job-desc").innerText = job.description;
    
    // Load drafts fields
    try {
        const res = await fetch(`/api/jobs/${job.id}/drafts`);
        const drafts = await res.json();
        
        const container = document.getElementById("dynamic-fields-container");
        container.innerHTML = "";
        
        drafts.forEach(field => {
            const fieldGroup = document.createElement("div");
            fieldGroup.className = "field-group";
            fieldGroup.style.marginTop = "1.5rem";
            
            const isTextarea = field.field_key === "cover_letter" || field.field_value.length > 50;
            const inputHtml = isTextarea 
                ? `<textarea class="editor-field-input" id="field-${field.field_key}" rows="6">${field.field_value}</textarea>`
                : `<input type="text" class="editor-field-input" id="field-${field.field_key}" value="${field.field_value}">`;
                
            fieldGroup.innerHTML = `
                <label for="field-${field.field_key}">
                    <i class="fa-solid ${field.field_key === 'cover_letter' ? 'fa-file-lines' : 'fa-circle-question'}"></i> 
                    ${field.field_label}
                </label>
                ${inputHtml}
            `;
            container.appendChild(fieldGroup);
        });
    } catch (err) {
        console.error("Error loading drafts:", err);
    }
}

// Gather Edited Fields
function getEditedData() {
    const inputs = document.querySelectorAll(".editor-field-input");
    const data = {};
    inputs.forEach(input => {
        const key = input.id.replace("field-", "");
        data[key] = input.value;
    });
    return data;
}

// Save Draft Values
async function saveDraft() {
    if (!currentJob) return;
    const data = getEditedData();
    
    try {
        const res = await fetch(`/api/jobs/${currentJob.id}/save`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });
        const resData = await res.json();
        if (resData.status === "success") {
            showTerminalLine(`System saved draft changes for ${currentJob.company} locally.`, "t-cyan");
        }
    } catch (err) {
        console.error("Error saving draft:", err);
    }
}

// Reject/Archive Job
async function rejectJob() {
    if (!currentJob) return;
    
    try {
        const res = await fetch(`/api/jobs/${currentJob.id}/reject`, {
            method: "POST"
        });
        const resData = await res.json();
        if (resData.status === "success") {
            showTerminalLine(`Job at ${currentJob.company} marked REJECTED and archived.`, "t-red");
            currentJob = null;
            document.getElementById("editor-workspace").style.display = "none";
            document.getElementById("editor-empty").style.display = "flex";
            loadJobs();
        }
    } catch (err) {
        console.error("Error rejecting job:", err);
    }
}

// Approve and Trigger Playwright Automation
async function approveAndSubmit() {
    if (!currentJob) return;
    const data = getEditedData();
    
    // Set terminal UI state to running
    const statusEl = document.getElementById("terminal-status");
    statusEl.innerText = "RUNNING";
    statusEl.className = "terminal-status running";
    
    const termBody = document.getElementById("terminal-body");
    termBody.innerHTML = `<div class="terminal-line"><span class="t-cyan">job-agent:~$</span> executing browser automation pipeline...</div>`;
    
    try {
        const res = await fetch(`/api/jobs/${currentJob.id}/approve`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });
        const resData = await res.json();
        
        if (resData.status === "success") {
            // Animate logs sequentially to feel authentic
            let delay = 0;
            resData.logs.forEach((logLine, idx) => {
                setTimeout(() => {
                    let colorClass = "t-green";
                    if (logLine.includes("Starting") || logLine.includes("Navigating")) colorClass = "t-cyan";
                    if (logLine.includes("Error") || logLine.includes("failed")) colorClass = "t-red";
                    if (logLine.includes("Applied") || logLine.includes("successfully")) colorClass = "t-green";
                    
                    const line = document.createElement("div");
                    line.className = "terminal-line";
                    line.innerHTML = `<span class="${colorClass}">[playwright]</span> ${logLine}`;
                    termBody.appendChild(line);
                    termBody.scrollTop = termBody.scrollHeight;
                    
                    // On final line, update states
                    if (idx === resData.logs.length - 1) {
                        statusEl.innerText = "DONE";
                        statusEl.className = "terminal-status";
                        currentJob = null;
                        document.getElementById("editor-workspace").style.display = "none";
                        document.getElementById("editor-empty").style.display = "flex";
                        loadJobs();
                    }
                }, delay);
                delay += 800; // 800ms between lines
            });
        }
    } catch (err) {
        console.error("Error approving job:", err);
        statusEl.innerText = "ERROR";
        statusEl.className = "terminal-status";
    }
}

// Trigger Simulated Scraper Ingestion
async function triggerScrape() {
    try {
        const res = await fetch("/api/jobs/trigger-scrape", { method: "POST" });
        const resData = await res.json();
        
        if (resData.status === "success") {
            showTerminalLine(resData.message, "t-green");
            loadJobs();
        } else {
            showTerminalLine(resData.message, "t-yellow");
        }
    } catch (err) {
        console.error("Error triggering scrape:", err);
    }
}

// Helper to write line to console
function showTerminalLine(text, colorClass) {
    const termBody = document.getElementById("terminal-body");
    const line = document.createElement("div");
    line.className = "terminal-line";
    line.innerHTML = `<span class="t-cyan">job-agent:~$</span> <span class="${colorClass}">${text}</span>`;
    termBody.appendChild(line);
    termBody.scrollTop = termBody.scrollHeight;
}
