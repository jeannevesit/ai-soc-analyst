import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getFirestore, collection, query, orderBy, limit, onSnapshot } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js";

// Helper for UTC Clock
function updateClock() {
  const clock = document.getElementById("utc-clock");
  if (clock) {
    const now = new Date();
    clock.textContent = now.toISOString().replace("T", " ").substring(0, 19) + " UTC";
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

if (isPlaceholder) {
  // Show Setup Instructions in place of loader if not configured
  loader.innerHTML = `
    <div style="text-align: left; max-width: 500px; margin: 0 auto; background: rgba(255, 59, 48, 0.1); border: 1px solid rgba(255, 59, 48, 0.2); padding: 1.5rem; border-radius: 8px;">
      <h3 style="color: #ff3b30; margin-bottom: 0.5rem;"><i class="fa-solid fa-triangle-exclamation"></i> Firebase Configuration Required</h3>
      <p style="font-size: 0.9rem; margin-bottom: 1rem;">To listen to the Firestore live feed, you need to create a file named <code>firebase-config.js</code> in the dashboard folder containing your Firebase Web App credentials.</p>
      <pre style="background: rgba(0,0,0,0.4); padding: 1rem; border-radius: 4px; font-family: monospace; font-size: 0.75rem; color: #5ac8fa; overflow-x: auto;">
window.firebaseConfig = {
  apiKey: "AIzaSy...",
  authDomain: "your-gcp-project.firebaseapp.com",
  projectId: "your-gcp-project",
  storageBucket: "your-gcp-project.appspot.com",
  messagingSenderId: "123456789",
  appId: "1:1234:web:abcd"
};
      </pre>
    </div>
  `;
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
function renderAlertRow(id, incident) {
  const row = document.createElement("div");
  row.className = "alert-row";
  row.dataset.id = id;
  
  const severity = incident.ai_analysis?.severity || "LOW";
  const severityClass = severity.toLowerCase();
  
  // Format Timestamp
  let formattedTime = "00:00:00";
  try {
    const rawTime = incident.timestamp;
    if (rawTime) {
      const dt = new Date(rawTime);
      formattedTime = dt.toISOString().replace("T", " ").substring(11, 19);
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
  alertsContainer.appendChild(row);
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
