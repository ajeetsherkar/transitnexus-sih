const API = "";
const TOKEN_KEY = "tn_read";
const POLL_MS = 3000;
const REQUEST_TIMEOUT_MS = 4000;

const accessOverlay = document.getElementById("access-overlay");
const accessForm = document.getElementById("access-form");
const accessCode = document.getElementById("access-code");
const accessError = document.getElementById("access-error");

const connectionStatus = document.getElementById("connection-status");
const lastUpdated = document.getElementById("last-updated");
const alertsList = document.getElementById("alerts-list");
const toast = document.getElementById("toast");

const kpiOnline = document.getElementById("kpi-online");
const kpiOffline = document.getElementById("kpi-offline");
const kpiOpenIncidents = document.getElementById("kpi-open-incidents");
const kpiReportsToday = document.getElementById("kpi-reports-today");

const filterType = document.getElementById("filter-type");
const filterStatus = document.getElementById("filter-status");
const filterWindow = document.getElementById("filter-window");

const incidentDrawer = document.getElementById("incident-drawer");
const drawerClose = document.getElementById("drawer-close");
const drawerTitle = document.getElementById("drawer-title");
const drawerError = document.getElementById("drawer-error");
const drawerStatus = document.getElementById("drawer-status");
const drawerConfidence = document.getElementById("drawer-confidence");
const drawerReports = document.getElementById("drawer-reports");
const drawerBuses = document.getElementById("drawer-buses");
const drawerFirstSeen = document.getElementById("drawer-first-seen");
const drawerVerified = document.getElementById("drawer-verified");
const drawerLastSeen = document.getElementById("drawer-last-seen");
const drawerContributors = document.getElementById("drawer-contributors");
const drawerEvidence = document.getElementById("drawer-evidence");
const drawerResolve = document.getElementById("drawer-resolve");

const busMarkers = new Map();
const incidentMarkers = new Map();

let map = null;
let pollTimer = null;
let refreshBusy = false;
let toastTimer = null;
let selectedIncidentId = null;
let selectedIncident = null;
let evidenceObjectUrl = null;

function buildIncidentQuery() {
    const params = new URLSearchParams();

    if (filterType.value) {
        params.set("type", filterType.value);
    }

    if (filterStatus.value) {
        params.set("status", filterStatus.value);
    }

    if (filterWindow.value === "hour") {
        params.set("since", new Date(Date.now() - 60 * 60 * 1000).toISOString());
    } else if (filterWindow.value === "today") {
        const now = new Date();
        const startOfDay = new Date(Date.UTC(
            now.getUTCFullYear(),
            now.getUTCMonth(),
            now.getUTCDate()
        ));
        params.set("since", startOfDay.toISOString());
    }

    const query = params.toString();
    return query ? `/v1/incidents?${query}` : "/v1/incidents";
}

function getToken() {
    return sessionStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
    sessionStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
    sessionStorage.removeItem(TOKEN_KEY);
}

function setConnection(state, text) {
    connectionStatus.className = `status ${state || ""}`.trim();
    connectionStatus.textContent = text;
}

function showToast(message) {
    toast.textContent = message;
    toast.hidden = false;

    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        toast.hidden = true;
    }, 3500);
}

function showAccess(message = "") {
    accessError.textContent = message;
    accessOverlay.classList.remove("hidden");
    accessCode.focus();
}

function hideAccess() {
    accessOverlay.classList.add("hidden");
    accessError.textContent = "";
}

async function getJSON(path) {
    const token = getToken();

    if (!token) {
        throw new Error("AUTH_REQUIRED");
    }

    const controller = new AbortController();
    const timeout = setTimeout(
        () => controller.abort(),
        REQUEST_TIMEOUT_MS
    );

    try {
        const response = await fetch(`${API}${path}`, {
            method: "GET",
            headers: {
                "X-Read-Token": token,
                "Accept": "application/json",
            },
            cache: "no-store",
            signal: controller.signal,
        });

        if (response.status === 401) {
            clearToken();
            showAccess("Access code is invalid or expired.");
            throw new Error("AUTH_REQUIRED");
        }

        if (!response.ok) {
            throw new Error(`HTTP_${response.status}`);
        }

        return await response.json();
    } finally {
        clearTimeout(timeout);
    }
}

function escapeHTML(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatType(type) {
    return String(type || "incident")
        .replaceAll("_", " ")
        .replace(/\b\w/g, (char) => char.toUpperCase());
}

function normalizeStatus(status) {
    return String(status || "DETECTED").toUpperCase();
}

function statusClass(status) {
    const normalized = normalizeStatus(status);

    if (normalized === "VERIFIED") {
        return "verified";
    }

    if (normalized === "RESOLVED") {
        return "resolved";
    }

    return "detected";
}

function sourceBadge(source) {
    const normalized = String(source || "UNKNOWN").toUpperCase();

    if (normalized.includes("REPLAY")) {
        return "REPLAY";
    }

    if (
        normalized.includes("SIM") ||
        normalized.includes("SYNTH")
    ) {
        return "SIMULATED";
    }

    return "LIVE";
}

function timeAgo(timestamp) {
    if (!timestamp) {
        return "time unknown";
    }

    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
        return "time unknown";
    }

    const seconds = Math.max(
        0,
        Math.floor((Date.now() - date.getTime()) / 1000)
    );

    if (seconds < 10) {
        return "just now";
    }

    if (seconds < 60) {
        return `${seconds}s ago`;
    }

    const minutes = Math.floor(seconds / 60);

    if (minutes < 60) {
        return `${minutes}m ago`;
    }

    const hours = Math.floor(minutes / 60);

    if (hours < 24) {
        return `${hours}h ago`;
    }

    const days = Math.floor(hours / 24);
    return `${days}d ago`;
}

function busIcon(bus) {
    const online = Boolean(bus.online);
    const position = bus.latest_position || {};
    const heading = Number(position.heading);

    const safeHeading = Number.isFinite(heading)
        ? heading
        : 0;

    const source = sourceBadge(bus.source);

    return L.divIcon({
        className: "",
        iconSize: [54, 48],
        iconAnchor: [27, 24],
        popupAnchor: [0, -22],
        html: `
            <div class="bus-marker ${online ? "" : "offline"}">
                <div
                    class="bus-arrow-wrap"
                    style="transform: rotate(${safeHeading}deg)"
                >
                    <div class="bus-arrow"></div>
                </div>
                <div class="bus-badge">
                    ${escapeHTML(bus.bus_id)}
                </div>
                <div class="bus-source">
                    ${escapeHTML(source)}
                </div>
            </div>
        `,
    });
}

function busPopup(bus) {
    const position = bus.latest_position;

    if (!position) {
        return `
            <strong>${escapeHTML(bus.bus_id)}</strong><br>
            Status: Offline<br>
            No recent GPS position
        `;
    }

    const accuracy = Number(position.accuracy_m);
    const speed = Number(position.speed_kmh);
    const heading = Number(position.heading);

    return `
        <strong>${escapeHTML(bus.bus_id)}</strong><br>
        Status: ${bus.online ? "Online" : "Offline"}<br>
        Source: ${escapeHTML(sourceBadge(bus.source))}<br>
        Route: ${escapeHTML(bus.route_id || "—")}<br>
        Speed: ${Number.isFinite(speed) ? speed.toFixed(1) : "—"} km/h<br>
        Heading: ${Number.isFinite(heading) ? heading.toFixed(0) : "—"}°<br>
        GPS accuracy: ${Number.isFinite(accuracy) ? accuracy.toFixed(1) : "—"} m<br>
        Heartbeat: ${timeAgo(position.ts)}
    `;
}

function incidentIcon(incident) {
    const status = statusClass(incident.status);

    return L.divIcon({
        className: "",
        iconSize: [16, 16],
        iconAnchor: [8, 8],
        html: `<div class="incident-marker ${status}"></div>`,
    });
}

function incidentPopup(incident) {
    const status = normalizeStatus(incident.status);

    return `
        <strong>${escapeHTML(formatType(incident.type))}</strong><br>
        Status: ${escapeHTML(status)}<br>
        Buses: ${escapeHTML(incident.bus_count ?? "—")}<br>
        Reports: ${escapeHTML(incident.report_count ?? "—")}<br>
        Confidence: ${
            Number.isFinite(Number(incident.confidence))
                ? `${(Number(incident.confidence) * 100).toFixed(0)}%`
                : "—"
        }<br>
        Last seen: ${escapeHTML(timeAgo(incident.last_seen))}
    `;
}

function syncMarkers(buses, incidents) {
    const activeBusIds = new Set();

    for (const bus of buses) {
        const id = bus.bus_id;

        if (!bus.latest_position) {
            continue;
        }

        const lat = Number(bus.latest_position.lat);
        const lon = Number(bus.latest_position.lon);

        if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
            continue;
        }

        activeBusIds.add(id);

        let marker = busMarkers.get(id);

        if (!marker) {
            marker = L.marker([lat, lon], {
                icon: busIcon(bus),
                keyboard: false,
            }).addTo(map);

            busMarkers.set(id, marker);
        } else {
            marker.setLatLng([lat, lon]);
            marker.setIcon(busIcon(bus));
        }

        marker.setPopupContent(busPopup(bus));

        if (marker.isPopupOpen()) {
            marker.getPopup().setLatLng(marker.getLatLng());
        }
    }

    for (const [id, marker] of busMarkers) {
        if (!activeBusIds.has(id)) {
            map.removeLayer(marker);
            busMarkers.delete(id);
        }
    }

    const activeIncidentIds = new Set();

    for (const incident of incidents) {
        const id = String(incident.id);
        const lat = Number(incident.lat);
        const lon = Number(incident.lon);

        if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
            continue;
        }

        activeIncidentIds.add(id);

        let marker = incidentMarkers.get(id);

        if (!marker) {
            marker = L.marker([lat, lon], {
                icon: incidentIcon(incident),
                keyboard: false,
            }).addTo(map);

            marker.on("click", () => openIncidentDrawer(id));
            incidentMarkers.set(id, marker);
        } else {
            marker.setLatLng([lat, lon]);
            marker.setIcon(incidentIcon(incident));
        }

        marker.setPopupContent(incidentPopup(incident));

        if (marker.isPopupOpen()) {
            marker.getPopup().setLatLng(marker.getLatLng());
        }
    }

    for (const [id, marker] of incidentMarkers) {
        if (!activeIncidentIds.has(id)) {
            map.removeLayer(marker);
            incidentMarkers.delete(id);
        }
    }
}

function renderKPIs(stats, buses) {
    const online = buses.filter((bus) => bus.online).length;
    const offline = Math.max(0, buses.length - online);

    kpiOnline.textContent = online;
    kpiOffline.textContent = offline;
    kpiOpenIncidents.textContent = stats.open_incidents ?? 0;
    kpiReportsToday.textContent = stats.reports_today ?? 0;
}

function setDrawerText(element, value) {
    element.textContent = value == null || value === "" ? "—" : String(value);
}

function formatTimestamp(timestamp) {
    if (!timestamp) {
        return "—";
    }
    const date = new Date(timestamp);
    return Number.isNaN(date.getTime()) ? String(timestamp) : date.toLocaleString();
}

function verifiedTimestamp(incident) {
    // The backend currently records VERIFIED status but has no verified_at field.
    // Do not infer a verification timestamp from report timestamps.
    return null;
}

async function openIncidentDrawer(incidentId) {
    const token = getToken();
    if (!token) {
        showAccess("Enter the dashboard access code.");
        return;
    }

    selectedIncidentId = String(incidentId);
    drawerError.hidden = true;
    drawerError.textContent = "";
    drawerResolve.disabled = true;
    drawerEvidence.removeAttribute("src");
    drawerEvidence.alt = "Loading incident evidence";

    if (evidenceObjectUrl) {
        URL.revokeObjectURL(evidenceObjectUrl);
        evidenceObjectUrl = null;
    }

    incidentDrawer.classList.add("open");
    incidentDrawer.setAttribute("aria-hidden", "false");

    setDrawerText(drawerTitle, "Loading…");
    setDrawerText(drawerStatus, "Loading…");
    setDrawerText(drawerConfidence, "Loading…");
    setDrawerText(drawerReports, "Loading…");
    setDrawerText(drawerBuses, "Loading…");
    setDrawerText(drawerFirstSeen, "Loading…");
    setDrawerText(drawerVerified, "Loading…");
    setDrawerText(drawerLastSeen, "Loading…");
    drawerContributors.replaceChildren();

    try {
        const incident = await getJSON(`/v1/incidents/${encodeURIComponent(selectedIncidentId)}`);
        selectedIncident = incident;

        setDrawerText(drawerTitle, formatType(incident.type));
        setDrawerText(drawerStatus, normalizeStatus(incident.status));

        const confidence = Number(incident.confidence);
        setDrawerText(
            drawerConfidence,
            Number.isFinite(confidence) ? `${(confidence * 100).toFixed(0)}%` : "—"
        );

        setDrawerText(drawerReports, incident.report_count);
        setDrawerText(drawerBuses, incident.bus_count);
        setDrawerText(drawerFirstSeen, formatTimestamp(incident.first_seen));
        setDrawerText(drawerVerified, formatTimestamp(verifiedTimestamp(incident)));
        setDrawerText(drawerLastSeen, formatTimestamp(incident.last_seen));

        const reports = Array.isArray(incident.reports) ? incident.reports : [];
        const seenBuses = new Set();

        for (const report of reports) {
            if (report.bus_id) {
                seenBuses.add(String(report.bus_id));
            }

            const row = document.createElement("tr");

            const busCell = document.createElement("td");
            busCell.textContent = report.bus_id || "—";

            const confidenceCell = document.createElement("td");
            const reportConfidence = Number(report.confidence);
            confidenceCell.textContent = Number.isFinite(reportConfidence)
                ? `${(reportConfidence * 100).toFixed(0)}%`
                : "—";

            const timeCell = document.createElement("td");
            timeCell.textContent = formatTimestamp(report.ts);

            row.append(busCell, confidenceCell, timeCell);
            drawerContributors.appendChild(row);
        }

        if (!reports.length) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = 3;
            cell.textContent = "No contributing reports.";
            row.appendChild(cell);
            drawerContributors.appendChild(row);
        }

        if (seenBuses.size > 0) {
            setDrawerText(drawerBuses, seenBuses.size);
        }

        drawerResolve.disabled = normalizeStatus(incident.status) === "RESOLVED";

        const evidenceReport = reports.find(
            (report) => report.has_evidence && report.event_id
        );

        if (evidenceReport) {
            showEvidence(evidenceReport.event_id, drawerEvidence).catch(() => {
                drawerEvidence.alt = "No evidence available";
            });
        } else {
            drawerEvidence.alt = "No evidence available";
        }
    } catch (error) {
        if (error && error.status === 401) {
            return;
        }

        drawerError.textContent = "Unable to load incident details.";
        drawerError.hidden = false;
        drawerResolve.disabled = true;
    }
}

async function showEvidence(eventId, imgEl) {
    const token = getToken();

    if (!token || !eventId) {
        imgEl.removeAttribute("src");
        imgEl.alt = "No evidence available";
        return;
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    try {
        const response = await fetch(
            `${API}/v1/evidence/${encodeURIComponent(eventId)}.jpg`,
            {
                headers: {
                    "X-Read-Token": token,
                },
                signal: controller.signal,
            }
        );

        if (response.status === 401) {
            clearToken();
            showAccess("Access code expired or invalid.");
            throw new Error("Unauthorized");
        }

        if (!response.ok) {
            imgEl.removeAttribute("src");
            imgEl.alt = "No evidence available";
            return;
        }

        if (evidenceObjectUrl) {
            URL.revokeObjectURL(evidenceObjectUrl);
        }

        evidenceObjectUrl = URL.createObjectURL(await response.blob());
        imgEl.src = evidenceObjectUrl;
        imgEl.alt = "Incident evidence";
    } finally {
        clearTimeout(timeout);
    }
}

function renderAlerts(incidents) {
    if (!incidents.length) {
        alertsList.innerHTML = `
            <div class="empty-state">
                No incidents reported.
            </div>
        `;
        return;
    }

    alertsList.innerHTML = incidents
        .slice(0, 30)
        .map((incident) => {
            const status = statusClass(incident.status);
            const id = String(incident.id);

            return `
                <article
                    class="alert-item"
                    data-incident-id="${escapeHTML(id)}"
                    tabindex="0"
                    role="button"
                >
                    <div class="alert-main">
                        <span class="alert-dot ${status}"></span>
                        <span class="alert-type">
                            ${escapeHTML(formatType(incident.type))}
                        </span>
                    </div>
                    <div class="alert-meta">
                        ${escapeHTML(normalizeStatus(incident.status))}
                        · ${escapeHTML(incident.bus_count ?? 0)} bus${
                            Number(incident.bus_count) === 1 ? "" : "es"
                        }
                        · ${escapeHTML(timeAgo(incident.last_seen))}
                    </div>
                </article>
            `;
        })
        .join("");

    for (const item of alertsList.querySelectorAll(".alert-item")) {
        const openIncident = () => {
            const marker = incidentMarkers.get(
                item.dataset.incidentId
            );

            if (!marker) {
                return;
            }

            map.flyTo(marker.getLatLng(), Math.max(map.getZoom(), 15), {
                duration: 0.7,
            });

            marker.openPopup();
        };

        item.addEventListener("click", openIncident);
        item.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                openIncident();
            }
        });
    }
}

function handleAlertActivation(event) {
    const item = event.target.closest(".alert-item");
    if (!item || !alertsList.contains(item)) {
        return;
    }

    const incidentId = item.dataset.incidentId;
    if (incidentId) {
        openIncidentDrawer(incidentId);
    }
}

async function resolveSelectedIncident() {
    if (!selectedIncidentId) {
        return;
    }

    if (!confirm("Resolve this incident?")) {
        return;
    }

    const adminToken = window.prompt("Enter admin code:");
    if (!adminToken) {
        return;
    }

    drawerResolve.disabled = true;
    drawerError.hidden = true;
    drawerError.textContent = "";

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    try {
        const response = await fetch(
            `${API}/v1/incidents/${encodeURIComponent(selectedIncidentId)}/resolve`,
            {
                method: "POST",
                headers: {
                    "X-Admin-Token": adminToken,
                },
                signal: controller.signal,
            }
        );

        if (response.status === 401) {
            drawerError.textContent = "Invalid admin code.";
            drawerError.hidden = false;
            drawerResolve.disabled = false;
            return;
        }

        if (!response.ok) {
            drawerError.textContent = "Unable to resolve this incident.";
            drawerError.hidden = false;
            drawerResolve.disabled = false;
            return;
        }

        const result = await response.json();

        if (selectedIncident) {
            selectedIncident.status = result.status || "RESOLVED";
        }

        const marker = incidentMarkers.get(String(selectedIncidentId));
        if (marker && selectedIncident) {
            marker.setIcon(incidentIcon(selectedIncident));
            marker.setPopupContent(incidentPopup(selectedIncident));
        }

        drawerStatus.textContent = normalizeStatus(result.status || "RESOLVED");
        drawerResolve.disabled = true;

        showToast("Incident resolved.");
        await refresh();
    } catch (error) {
        if (error && error.name === "AbortError") {
            drawerError.textContent = "Resolve request timed out.";
        } else {
            drawerError.textContent = "Unable to resolve this incident.";
        }
        drawerError.hidden = false;
        drawerResolve.disabled = false;
    } finally {
        clearTimeout(timeout);
    }
}

function closeIncidentDrawer() {
    incidentDrawer.classList.remove("open");
    incidentDrawer.setAttribute("aria-hidden", "true");
    selectedIncidentId = null;
    selectedIncident = null;

    if (evidenceObjectUrl) {
        URL.revokeObjectURL(evidenceObjectUrl);
        evidenceObjectUrl = null;
    }

    drawerEvidence.removeAttribute("src");
    drawerEvidence.alt = "Incident evidence";
}

drawerClose.addEventListener("click", closeIncidentDrawer);
drawerResolve.addEventListener("click", resolveSelectedIncident);

alertsList.addEventListener("click", handleAlertActivation);
alertsList.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        handleAlertActivation(event);
    }
});

function initMap() {
    map = L.map("map", {
        zoomControl: true,
        preferCanvas: true,
    }).setView([19.9975, 73.7898], 13);

    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            maxZoom: 19,
            attribution: "&copy; OpenStreetMap contributors",
        }
    ).addTo(map);

    window.setTimeout(() => map.invalidateSize(), 100);
}

async function refresh() {
    if (refreshBusy) {
        return;
    }

    if (!getToken()) {
        showAccess();
        return;
    }

    refreshBusy = true;
    setConnection("", "Updating...");

    try {
        const [stats, buses, incidents] = await Promise.all([
            getJSON("/v1/stats"),
            getJSON("/v1/buses"),
            getJSON(buildIncidentQuery()),
        ]);

        renderKPIs(stats, buses);
        syncMarkers(buses, incidents);
        renderAlerts(incidents);

        lastUpdated.textContent = new Date().toLocaleTimeString();
        setConnection("connected", "LIVE");
    } catch (error) {
        if (error.message === "AUTH_REQUIRED") {
            setConnection("error", "Access required");
            return;
        }

        if (error.name === "AbortError") {
            setConnection("error", "Request timeout");
        } else {
            setConnection("error", "Backend unavailable");
        }
    } finally {
        refreshBusy = false;
    }
}

function startPolling() {
    clearInterval(pollTimer);

    pollTimer = setInterval(() => {
        refresh();
    }, POLL_MS);
}

accessForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const token = accessCode.value.trim();

    if (!token) {
        accessError.textContent = "Enter the access code.";
        return;
    }

    setToken(token);
    accessError.textContent = "";

    try {
        await refresh();

        if (getToken()) {
            hideAccess();
            accessCode.value = "";
        }
    } catch (error) {
        clearToken();
        accessError.textContent = "Unable to validate the access code.";
    }
});

window.addEventListener("resize", () => {
    if (map) {
        map.invalidateSize();
    }
});

document.addEventListener("DOMContentLoaded", () => {
    initMap();
    startPolling();

    if (getToken()) {
        hideAccess();
        refresh();
    } else {
        showAccess();
    }
});
