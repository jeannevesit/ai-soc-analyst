// State variables
let devices = [];
let incidents = [];
let actions = [];
let selectedDeviceName = "jean-macbook-pro";
let isRemediating = false;

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
    loadData(true);
    // Poll updates every 4 seconds
    setInterval(() => {
        if (!isRemediating) {
            loadData(false);
        }
    }, 4000);
});

// Load data from FastAPI backend
async function loadData(isInitial = false) {
    try {
        const [devicesRes, incidentsRes, actionsRes] = await Promise.all([
            fetch("/api/devices"),
            fetch("/api/incidents"),
            fetch("/api/actions")
        ]);

        devices = await devicesRes.json();
        incidents = await incidentsRes.json();
        actions = await actionsRes.json();

        renderDevices(isInitial);
        renderIncidents();
        renderActions();
        updateMobileView();
    } catch (error) {
        console.error("Error loading dashboard data:", error);
    }
}

// Render the device registry list
function renderDevices(isInitial) {
    const tbody = document.getElementById("device-table-body");
    tbody.innerHTML = "";

    const simSelect = document.getElementById("sim-device");
    const mobileSelect = document.getElementById("mobile-device-view");
    
    // Save current selections before rebuilding options
    const prevSimVal = simSelect.value;
    const prevMobileVal = mobileSelect.value;
    
    if (isInitial) {
        simSelect.innerHTML = "";
        mobileSelect.innerHTML = "";
    }

    devices.forEach(device => {
        // Table row
        const row = document.createElement("tr");
        const statusBadge = `<span class="badge ${device.compliance_status.toLowerCase()}">${device.compliance_status}</span>`;
        
        let osIcon = '<i class="fa-brands fa-linux"></i>';
        if (device.platform === "macOS") osIcon = '<i class="fa-brands fa-apple"></i>';
        else if (device.platform === "Windows") osIcon = '<i class="fa-brands fa-windows"></i>';
        else if (device.platform === "iOS") osIcon = '<i class="fa-solid fa-mobile-screen-button"></i>';

        row.innerHTML = `
            <td><strong>${device.name}</strong></td>
            <td style="font-size: 1.1rem; color: var(--text-muted);">${osIcon} ${device.platform}</td>
            <td>${device.owner}</td>
            <td style="font-family: var(--font-code); color: var(--text-muted);">${device.ip_address}</td>
            <td>${statusBadge}</td>
        `;
        tbody.appendChild(row);

        // Populate dropdowns once on load
        if (isInitial) {
            const opt1 = document.createElement("option");
            opt1.value = device.name;
            opt1.textContent = device.name;
            simSelect.appendChild(opt1);

            const opt2 = document.createElement("option");
            opt2.value = device.name;
            opt2.textContent = `${device.owner} (${device.name})`;
            mobileSelect.appendChild(opt2);
        }
    });

    if (isInitial) {
        mobileSelect.value = selectedDeviceName;
    } else {
        // Restore values
        if (prevSimVal) simSelect.value = prevSimVal;
        if (prevMobileVal) mobileSelect.value = prevMobileVal;
    }
}

// Render EDR incident queue
function renderIncidents() {
    const list = document.getElementById("incidents-list");
    list.innerHTML = "";

    if (incidents.length === 0) {
        list.innerHTML = '<div class="no-incidents"><i class="fa-solid fa-circle-check" style="font-size: 2rem; color: var(--success); margin-bottom: 0.5rem; display: block;"></i> No active threats. Fleet is secure.</div>';
        return;
    }

    incidents.forEach(incident => {
        const card = document.createElement("div");
        card.className = "incident-card";
        
        const time = new Date(incident.timestamp).toLocaleTimeString();
        const sevClass = incident.severity.toLowerCase();
        
        card.innerHTML = `
            <div class="incident-header">
                <span class="incident-title">${incident.threat_name}</span>
                <span class="incident-sev ${sevClass}">${incident.severity}</span>
            </div>
            <div class="incident-body">${incident.details}</div>
            <div class="incident-footer">
                <span>Asset: <strong>${incident.device_name}</strong> (${incident.device_owner})</span>
                <span style="font-family: var(--font-code); color: var(--cyan);">${time}</span>
            </div>
        `;
        list.appendChild(card);
    });
}

// Render SOAR orchestration audit timeline
function renderActions() {
    const tbody = document.getElementById("audit-log-body");
    tbody.innerHTML = "";

    if (actions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 2rem;">No audit logs registered.</td></tr>';
        return;
    }

    actions.forEach(action => {
        const row = document.createElement("tr");
        
        let typeIcon = '<i class="fa-solid fa-circle-info"></i>';
        if (action.action_type === "ISOLATE") typeIcon = '<i class="fa-solid fa-ban" style="color: var(--danger);"></i>';
        else if (action.action_type === "SUSPEND_SSO") typeIcon = '<i class="fa-solid fa-user-lock" style="color: var(--warning);"></i>';
        else if (action.action_type === "SELF_HEAL") typeIcon = '<i class="fa-solid fa-notes-medical" style="color: var(--success);"></i>';
        else if (action.action_type === "RESTORE") typeIcon = '<i class="fa-solid fa-wifi" style="color: var(--cyan);"></i>';
        else if (action.action_type === "UNSUSPEND_SSO") typeIcon = '<i class="fa-solid fa-user-check" style="color: var(--cyan);"></i>';

        row.innerHTML = `
            <td class="col-time" style="font-family: var(--font-code); color: var(--cyan);">${action.timestamp}</td>
            <td class="col-target"><strong>${action.device_name}</strong></td>
            <td class="col-action"><span class="event-badge ${action.action_type.toLowerCase()}">${typeIcon} ${action.action_type}</span></td>
            <td class="col-details" style="color: var(--text-muted);">${action.details}</td>
        `;
        tbody.appendChild(row);
    });
}

// Update the mobile mockup content based on device state
function updateMobileView() {
    const activeDevice = devices.find(d => d.name === selectedDeviceName);
    if (!activeDevice) return;

    const defaultState = document.getElementById("mobile-default-state");
    const isolatedState = document.getElementById("mobile-isolated-state");

    // Clear remediation progress if we switch devices
    if (!isRemediating) {
        document.getElementById("remediation-progress-box").style.display = "none";
        document.getElementById("remediate-btn").style.display = "block";
    }

    if (activeDevice.compliance_status === "ISOLATED") {
        defaultState.classList.remove("active");
        isolatedState.classList.add("active");
        
        document.getElementById("mobile-owner-isolated").textContent = `${activeDevice.owner} (${activeDevice.owner_email})`;
        document.getElementById("isolated-dev-name").textContent = activeDevice.name;
    } else {
        isolatedState.classList.remove("active");
        defaultState.classList.add("active");
        
        document.getElementById("mobile-owner").textContent = `${activeDevice.owner} (${activeDevice.owner_email})`;
    }
}

// Trigger simulated EDR webhook alert
async function triggerSimulation() {
    const deviceName = document.getElementById("sim-device").value;
    const threatType = document.getElementById("sim-threat").value;

    try {
        const res = await fetch("/api/incidents/simulate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ device_name: deviceName, threat_type: threatType })
        });
        
        if (res.ok) {
            // Automatically switch the phone preview to the attacked device
            selectedDeviceName = deviceName;
            document.getElementById("mobile-device-view").value = deviceName;
            
            await loadData(false);
        }
    } catch (error) {
        console.error("Simulation trigger failed:", error);
    }
}

// Start simulated employee self-remediation
function startRemediation() {
    if (isRemediating) return;
    
    isRemediating = true;
    const progressBox = document.getElementById("remediation-progress-box");
    const remediateBtn = document.getElementById("remediate-btn");
    const progressBarFill = document.getElementById("remediation-bar");
    const statusText = document.getElementById("remediation-status-text");

    remediateBtn.style.display = "none";
    progressBox.style.display = "block";
    progressBarFill.style.style = "0%";

    const steps = [
        { percentage: 10, label: "Starting deep EDR malware scan..." },
        { percentage: 30, label: "Analyzing active processes & RAM..." },
        { percentage: 50, label: "Quarantining CobaltStrike.Beacon executable..." },
        { percentage: 70, label: "Deleting active registry persistence keys..." },
        { percentage: 90, label: "Verifying local disk encryption & firewall compliance..." },
        { percentage: 100, label: "Remediation verified. Unlocking endpoint network..." }
    ];

    let currentStep = 0;
    const interval = setInterval(async () => {
        if (currentStep < steps.length) {
            const step = steps[currentStep];
            progressBarFill.style.width = `${step.percentage}%`;
            statusText.textContent = step.label;
            currentStep++;
        } else {
            clearInterval(interval);
            
            // Invoke the self-heal REST API
            try {
                const res = await fetch("/api/devices/self-heal", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ device_name: selectedDeviceName })
                });

                if (res.ok) {
                    isRemediating = false;
                    progressBox.style.display = "none";
                    remediateBtn.style.display = "block";
                    await loadData(false);
                }
            } catch (error) {
                console.error("Self heal API failed:", error);
                isRemediating = false;
            }
        }
    }, 850);
}

// Switch phone viewer target
function switchMobileView() {
    selectedDeviceName = document.getElementById("mobile-device-view").value;
    updateMobileView();
}

// Reset Database and logs back to initial state
async function resetDemo() {
    if (confirm("Reset the endpoint compliance registry & logs back to demo state?")) {
        try {
            const res = await fetch("/api/actions/clear", { method: "POST" });
            if (res.ok) {
                selectedDeviceName = "jean-macbook-pro";
                await loadData(true);
            }
        } catch (error) {
            console.error("Reset demo failed:", error);
        }
    }
}
