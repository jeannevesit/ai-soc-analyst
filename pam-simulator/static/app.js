// State Management
let assets = [];
let jitRequests = [];
let auditLogs = [];
let revealedPasswords = {}; // assetId -> password string
let activeTimers = {}; // requestId -> intervalRef

// Initial Load
document.addEventListener("DOMContentLoaded", () => {
    fetchData();
    // Poll updates every 3 seconds to capture JIT session expiry
    setInterval(fetchData, 3000);
});

async function fetchData() {
    await Promise.all([
        fetchAssets(),
        fetchJITRequests(),
        fetchAuditLogs()
    ]);
}

// 1. Fetch & Render Assets
async function fetchAssets() {
    try {
        const response = await fetch("/api/assets");
        assets = await response.json();
        renderAssets();
        populateAssetDropdown();
    } catch (e) {
        console.error("Failed to load assets", e);
    }
}

function renderAssets() {
    const grid = document.getElementById("assets-grid");
    grid.innerHTML = "";
    
    assets.forEach(asset => {
        const card = document.createElement("div");
        card.className = "asset-card";
        
        const statusClass = asset.status.toLowerCase();
        let statusText = asset.status;
        if (asset.requires_jit && asset.status === 'LOCKED') {
            statusText = 'JIT REQUIRED';
        }
        
        let actionButtons = "";
        let credentialBox = "";
        
        if (asset.status === "CHECKED_OUT") {
            const pwd = revealedPasswords[asset.id] || "••••••••••••••••";
            credentialBox = `
                <div class="asset-credential-box">
                    <span class="credential-text ${revealedPasswords[asset.id] ? 'revealed' : ''}" id="cred-${asset.id}">${pwd}</span>
                    <button class="btn-reveal" onclick="copyPassword(${asset.id}, '${pwd}')" title="Copy password">
                        <i class="fa-solid fa-copy"></i>
                    </button>
                </div>
            `;
            actionButtons = `
                <button class="btn btn-danger" onclick="checkinAsset(${asset.id})">
                    <i class="fa-solid fa-lock"></i> Check In / Rotate
                </button>
            `;
        } else {
            credentialBox = `
                <div class="asset-credential-box">
                    <span class="credential-text">••••••••••••••••</span>
                    <i class="fa-solid fa-lock-keyhole" style="color: var(--text-muted);"></i>
                </div>
            `;
            
            if (asset.requires_jit) {
                actionButtons = `
                    <button class="btn btn-primary" style="background: var(--warning); color: #000;" onclick="selectJITAsset(${asset.id})">
                        <i class="fa-solid fa-ticket-simple"></i> Request JIT
                    </button>
                `;
            } else {
                actionButtons = `
                    <button class="btn btn-success" onclick="checkoutAsset(${asset.id})">
                        <i class="fa-solid fa-key"></i> Check Out
                    </button>
                `;
            }
        }
        
        // Check if there's an active JIT timer for this asset
        let timerHTML = "";
        const activeJIT = jitRequests.find(r => r.asset_id === asset.id && r.status === "ACTIVE");
        if (activeJIT && activeJIT.expires_at) {
            timerHTML = `<div class="expiry-countdown" id="timer-asset-${asset.id}">
                <i class="fa-solid fa-clock-three"></i> Expiry: <span class="countdown-val">Calculating...</span>
            </div>`;
            startCountdown(activeJIT.id, activeJIT.expires_at, `timer-asset-${asset.id}`);
        }
        
        card.innerHTML = `
            <div class="asset-status-row">
                <div>
                    <h3>${asset.name}</h3>
                    <div style="font-size: 0.75rem; color: var(--text-muted);">Username: ${asset.username}</div>
                </div>
                <span class="asset-badge ${statusClass}">${statusText}</span>
            </div>
            ${credentialBox}
            ${timerHTML}
            <div style="margin-top: auto; padding-top: 0.5rem;">
                ${actionButtons}
            </div>
        `;
        
        grid.appendChild(card);
    });
}

function populateAssetDropdown() {
    const select = document.getElementById("target-asset");
    const currentVal = select.value;
    
    // Only rebuild list if count differs or dropdown is unselected
    const jitAssets = assets.filter(a => a.requires_jit);
    
    // Keep placeholder
    select.innerHTML = '<option value="" disabled selected>Select an asset...</option>';
    jitAssets.forEach(asset => {
        const opt = document.createElement("option");
        opt.value = asset.id;
        opt.textContent = `${asset.name} (${asset.username})`;
        select.appendChild(opt);
    });
    
    if (currentVal) {
        select.value = currentVal;
    }
}

// 2. Fetch JIT Requests & Approvals
async function fetchJITRequests() {
    try {
        const response = await fetch("/api/jit/requests");
        jitRequests = await response.json();
        renderApprovals();
    } catch (e) {
        console.error("Failed to load JIT requests", e);
    }
}

function renderApprovals() {
    const approvalsList = document.getElementById("approvals-list");
    approvalsList.innerHTML = "";
    
    // Show PENDING first, then ACTIVE
    const list = jitRequests.filter(r => r.status === "PENDING" || r.status === "ACTIVE");
    
    if (list.length === 0) {
        approvalsList.innerHTML = '<div class="no-requests">No active or pending JIT requests in queue.</div>';
        return;
    }
    
    list.forEach(req => {
        const card = document.createElement("div");
        card.className = "approval-card";
        
        const isPending = req.status === "PENDING";
        
        let actionHTML = "";
        let timerHTML = "";
        
        if (isPending) {
            actionHTML = `
                <div class="approval-actions">
                    <button class="btn btn-success" onclick="approveJIT(${req.id})">
                        <i class="fa-solid fa-circle-check"></i> Approve & Grant
                    </button>
                    <button class="btn btn-danger" onclick="denyJIT(${req.id})">
                        <i class="fa-solid fa-circle-xmark"></i> Deny
                    </button>
                </div>
            `;
        } else {
            timerHTML = `<div class="expiry-countdown" id="timer-req-${req.id}" style="margin-top: 0.5rem;">
                <i class="fa-solid fa-clock-three"></i> Auto-Revoke Expiry: <span class="countdown-val">Calculating...</span>
            </div>`;
            startCountdown(req.id, req.expires_at, `timer-req-${req.id}`);
        }
        
        card.innerHTML = `
            <div class="approval-header">
                <span class="approval-title">${req.asset_name}</span>
                <span class="asset-badge ${req.status.toLowerCase()}">${req.status}</span>
            </div>
            <div class="approval-details">
                <div>Requester: <strong>${req.requestor}</strong></div>
                <div>Duration: <strong>${req.duration_minutes} minutes</strong></div>
                <div>Reason: <i>"${req.reason}"</i></div>
            </div>
            ${timerHTML}
            ${actionHTML}
        `;
        approvalsList.appendChild(card);
    });
}

// 3. Fetch Audit Logs
async function fetchAuditLogs() {
    try {
        const response = await fetch("/api/audit");
        auditLogs = await response.json();
        renderAuditLogs();
    } catch (e) {
        console.error("Failed to load audit logs", e);
    }
}

function renderAuditLogs() {
    const tbody = document.getElementById("audit-log-body");
    tbody.innerHTML = "";
    
    if (auditLogs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No audit history found.</td></tr>';
        return;
    }
    
    auditLogs.forEach(log => {
        const row = document.createElement("tr");
        const date = new Date(log.timestamp).toLocaleString();
        
        row.innerHTML = `
            <td style="font-family: var(--font-code); color: var(--cyan);">${date}</td>
            <td><strong>${log.username}</strong></td>
            <td><span class="event-badge ${log.event_type.toLowerCase()}">${log.event_type}</span></td>
            <td style="color: #fff;">${log.asset_name}</td>
            <td style="color: var(--text-muted);">${log.details}</td>
        `;
        tbody.appendChild(row);
    });
}

// Action Handlers
async function checkoutAsset(id) {
    try {
        const response = await fetch(`/api/assets/checkout/${id}?requestor=jean.neves`, { method: "POST" });
        const result = await response.json();
        if (response.ok) {
            revealedPasswords[id] = result.password;
            fetchData();
        } else {
            alert("Error: " + result.detail);
        }
    } catch (e) {
        alert("Checkout failed: " + e.message);
    }
}

async function checkinAsset(id) {
    try {
        const response = await fetch(`/api/assets/checkin/${id}?requestor=jean.neves`, { method: "POST" });
        const result = await response.json();
        if (response.ok) {
            delete revealedPasswords[id];
            fetchData();
        } else {
            alert("Error: " + result.detail);
        }
    } catch (e) {
        alert("Check-in failed: " + e.message);
    }
}

function selectJITAsset(id) {
    const select = document.getElementById("target-asset");
    select.value = id;
    document.getElementById("jit-form").scrollIntoView({ behavior: "smooth" });
}

async function submitJITRequest(event) {
    event.preventDefault();
    const assetId = document.getElementById("target-asset").value;
    const requestor = document.getElementById("requestor").value.trim();
    const duration = document.getElementById("duration").value;
    const reason = document.getElementById("reason").value.trim();
    
    if (!assetId) {
        alert("Please select a target asset!");
        return;
    }
    
    try {
        const response = await fetch("/api/jit/request", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                asset_id: parseInt(assetId),
                requestor: requestor,
                reason: reason,
                duration_minutes: parseInt(duration)
            })
        });
        
        const result = await response.json();
        if (response.ok) {
            document.getElementById("reason").value = "";
            fetchData();
        } else {
            alert("Error: " + result.detail);
        }
    } catch (e) {
        alert("Request submission failed: " + e.message);
    }
}

async function approveJIT(reqId) {
    try {
        const response = await fetch(`/api/jit/approve/${reqId}?approver=security.admin`, { method: "POST" });
        const result = await response.json();
        if (response.ok) {
            const req = jitRequests.find(r => r.id === reqId);
            if (req) {
                revealedPasswords[req.asset_id] = result.password;
            }
            fetchData();
        } else {
            alert("Approval error: " + result.detail);
        }
    } catch (e) {
        alert("Approval failed: " + e.message);
    }
}

async function denyJIT(reqId) {
    try {
        const response = await fetch(`/api/jit/deny/${reqId}?approver=security.admin`, { method: "POST" });
        if (response.ok) {
            fetchData();
        }
    } catch (e) {
        alert("Deny failed: " + e.message);
    }
}

async function clearAuditLogs() {
    if (confirm("Are you sure you want to clear the audit history logs?")) {
        try {
            await fetch("/api/audit/clear", { method: "POST" });
            fetchData();
        } catch (e) {
            console.error(e);
        }
    }
}

// Utility: Timer countdown scheduler
function startCountdown(requestId, expiresAtStr, elementId) {
    // Prevent creating duplicate interval runs
    if (activeTimers[elementId]) {
        clearInterval(activeTimers[elementId]);
    }
    
    const expiryTime = new Date(expiresAtStr + "Z").getTime(); // Treat as UTC
    
    function updateTimer() {
        const now = new Date().getTime();
        const distance = expiryTime - now;
        
        const el = document.getElementById(elementId);
        if (!el) {
            clearInterval(activeTimers[elementId]);
            delete activeTimers[elementId];
            return;
        }
        
        const displayVal = el.querySelector(".countdown-val");
        
        if (distance < 0) {
            displayVal.textContent = "REVOKING ACCESS...";
            displayVal.style.color = "var(--danger)";
            clearInterval(activeTimers[elementId]);
            delete activeTimers[elementId];
            // Immediately sync data to show rotated/expired state
            setTimeout(fetchData, 1000);
            return;
        }
        
        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((distance % (1000 * 60)) / 1000);
        
        displayVal.textContent = `${minutes}m ${seconds}s`;
    }
    
    updateTimer();
    activeTimers[elementId] = setInterval(updateTimer, 1000);
}

function copyPassword(assetId, password) {
    navigator.clipboard.writeText(password).then(() => {
        const btn = document.querySelector(`.asset-card:has(#cred-${assetId}) .btn-reveal`);
        if (btn) {
            const originalHTML = btn.innerHTML;
            btn.innerHTML = `<i class="fa-solid fa-circle-check" style="color: var(--success);"></i>`;
            setTimeout(() => {
                btn.innerHTML = originalHTML;
            }, 1500);
        }
    }).catch(err => {
        console.error("Failed to copy", err);
    });
}
