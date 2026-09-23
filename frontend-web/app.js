const ROUTE_POINTS = [
    [19.884188, 74.479192],
    [19.885733, 74.479345],
    [19.886093, 74.479362],
    [19.886133, 74.479363],
    [19.886581, 74.479384],
    [19.887104, 74.479408],
    [19.887581, 74.479462],
    [19.887983, 74.479609],
    [19.890071, 74.481530],
    [19.890874, 74.482214],
    [19.890944, 74.482274],
    [19.893670, 74.484625],
    [19.894723, 74.485526],
    [19.894929, 74.485980],
    [19.895452, 74.487171],
    [19.897331, 74.491450],
    [19.897712, 74.492315],
    [19.898117, 74.493091],
    [19.898456, 74.493570],
    [19.899359, 74.494319],
    [19.899822, 74.494702],
    [19.900258, 74.495189],
    [19.900307, 74.495244],
    [19.900801, 74.496295],
    [19.901114, 74.496955],
    [19.903253, 74.499152],
    [19.903514, 74.499365],
    [19.903619, 74.499566],
    [19.903813, 74.499786],
    [19.905049, 74.502538],
    [19.904529, 74.502879],
    [19.903694, 74.503182]
];

const API_URL =
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1"
        ? "http://127.0.0.1:8000"
        : "https://transitnexus-v3.onrender.com";

const WS_URL = API_URL.replace(/^http/, "ws") + "/ws/alerts";

// Same simulated route area used by TransitNexus.
const MAP_CENTER = [19.9000, 74.4900];

const map = L.map("map").setView(MAP_CENTER, 14);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors"
}).addTo(map);

// Accurate Kopargaon route
const routeLine = L.polyline(ROUTE_POINTS, {
    weight: 5,
    opacity: 0.8
}).addTo(map);

routeLine.bindTooltip(
    "Kopargaon MSRTC Bus Stand → Kopargaon Railway Station"
);

L.marker(ROUTE_POINTS[0])
    .bindPopup("Route Start<br>Kopargaon MSRTC Bus Stand")
    .addTo(map);

L.marker(ROUTE_POINTS[ROUTE_POINTS.length - 1])
    .bindPopup("Route End<br>Kopargaon Railway Station")
    .addTo(map);

// Fit the map to the complete route
map.fitBounds(routeLine.getBounds(), {
    padding: [30, 30]
});

const eventCountElement = document.getElementById("event-count");
const statusElement = document.getElementById("connection-status");
const detailsElement = document.getElementById("event-details");
const busiestZoneElement = document.getElementById("busiest-zone");
const busiestZoneCountElement = document.getElementById("busiest-zone-count");
const congestionCountElement = document.getElementById("congestion-count");
const eventFiltersElement = document.getElementById("event-filters");

const predictionSeverityElement = document.getElementById("prediction-severity");
const predictionConfidenceElement = document.getElementById("prediction-confidence");
const predictionDelayElement = document.getElementById("prediction-delay");
const predictionZoneElement = document.getElementById("prediction-zone");
const predictionEventsElement = document.getElementById("prediction-events");
const predictionNoteElement = document.getElementById("prediction-note");
const alertTimelineElement = document.getElementById("alert-timeline");
const zoneSummaryZoneElement = document.getElementById("zone-summary-zone");
const zoneSummaryVehiclesElement = document.getElementById("zone-summary-vehicles");
const zoneSummaryIncidentsElement = document.getElementById("zone-summary-incidents");
const zoneSummaryPotholesElement = document.getElementById("zone-summary-potholes");
const zoneSummaryPedestrianElement = document.getElementById("zone-summary-pedestrian");
const zoneSummaryConfidenceElement = document.getElementById("zone-summary-confidence");
const zoneSummaryCongestionElement = document.getElementById("zone-summary-congestion");
const fleetActiveBusesElement = document.getElementById("fleet-active-buses");
const fleetOnlineCamerasElement = document.getElementById("fleet-online-cameras");
const fleetAlertsTodayElement = document.getElementById("fleet-alerts-today");
const fleetHighCongestionZonesElement = document.getElementById("fleet-high-congestion-zones");

const r3BusesOnlineElement = document.getElementById("r3-buses-online");
const r3BusesOfflineElement = document.getElementById("r3-buses-offline");
const r3IncidentsDetectedElement = document.getElementById("r3-incidents-detected");
const r3IncidentsVerifiedElement = document.getElementById("r3-incidents-verified");
const r3ReportsTodayElement = document.getElementById("r3-reports-today");

let eventChart = null;
let heatLayer = null;
let allEvents = [];
let eventMarkers = [];
let fleetMarkers = [];
let round3IncidentMarkers = [];

let dashboardRefreshTimer = null;
let selectedEventTypes = new Set();

function getEventColor(eventType) {
    switch (eventType) {
        case "pothole":
            return "orange";
        case "pedestrian_risk":
            return "red";
        case "congestion":
            return "yellow";
        case "incident":
            return "red";
        default:
            return "blue";
    }
}

function createFleetMarkerIcon(online) {
    const color = online ? "green" : "grey";

    return L.divIcon({
        className: "fleet-marker",
        html: `
            <div style="
                width: 16px;
                height: 16px;
                border-radius: 50%;
                background: ${color};
                border: 3px solid white;
                box-shadow: 0 1px 6px rgba(0,0,0,0.55);
            "></div>
        `,
        iconSize: [16, 16],
        iconAnchor: [8, 8]
    });
}

function createMarkerIcon(color) {
    return L.divIcon({
        className: "event-marker",
        html: `
            <div style="
                width: 14px;
                height: 14px;
                border-radius: 50%;
                background: ${color};
                border: 2px solid white;
                box-shadow: 0 1px 5px rgba(0,0,0,0.5);
            "></div>
        `,
        iconSize: [14, 14],
        iconAnchor: [7, 7]
    });
}

function showEventDetails(event) {
    const isIncident = event.event_type === "incident";

    if (isIncident) {
        const filename = event.frame_path
            ? event.frame_path.split("/").pop()
            : null;

        const evidenceUrl = filename
            ? `${API_URL}/evidence/${encodeURIComponent(filename)}`
            : null;

        const supportingFrames = Array.isArray(event.supporting_frames)
            ? event.supporting_frames.join(", ")
            : "None";

        detailsElement.innerHTML = `
            <h3>🚨 Incident Details</h3>

            <p><strong>Plate:</strong> ${event.plate || "N/A"}</p>

            <p><strong>Plate Source:</strong>
                ${event.plate_source || "N/A"}
            </p>

            <p><strong>Plate Confidence:</strong>
                ${event.plate_confidence ?? "N/A"}
            </p>

            <p><strong>Event Confidence:</strong>
                ${event.confidence ?? "N/A"}
            </p>

            <p><strong>Timestamp:</strong>
                ${event.timestamp || "N/A"}
            </p>

            <p><strong>GPS:</strong>
                ${event.lat}, ${event.lon}
            </p>

            <p><strong>Supporting Frames:</strong>
                ${supportingFrames}
            </p>

            ${
                evidenceUrl
                    ? `
                        <div class="evidence-section">
                            <strong>Primary Evidence</strong>
                            <img
                                class="evidence-image"
                                src="${evidenceUrl}"
                                alt="Incident evidence frame"
                            >
                        </div>
                    `
                    : ""
            }

            ${
                event.ocr_note
                    ? `
                        <p class="ocr-note">
                            <strong>OCR Note:</strong>
                            ${event.ocr_note}
                        </p>
                    `
                    : ""
            }
        `;

        return;
    }

    detailsElement.innerHTML = `
        <h3>Event Details</h3>
        <p><strong>Type:</strong> ${event.event_type}</p>
        <p><strong>Confidence:</strong> ${event.confidence}</p>
        <p><strong>Latitude:</strong> ${event.lat}</p>
        <p><strong>Longitude:</strong> ${event.lon}</p>
        <p><strong>Timestamp:</strong> ${event.timestamp}</p>
    `;
}

function addEventMarker(event, isLive = false) {
    if (
        typeof event.lat !== "number" ||
        typeof event.lon !== "number"
    ) {
        console.warn("Skipping event with invalid GPS coordinates:", event);
        return null;
    }

    const color = getEventColor(event.event_type);

    const marker = L.marker(
        [event.lat, event.lon],
        {
            icon: createMarkerIcon(color)
        }
    ).addTo(map);

    marker.bindPopup(`
        <div class="event-popup">
            <strong>${isLive ? "🚨 LIVE INCIDENT" : event.event_type}</strong><br>
            Type: ${event.event_type}<br>
            Confidence: ${event.confidence}<br>
            GPS: ${event.lat}, ${event.lon}<br>
            Timestamp: ${event.timestamp}
            ${event.plate ? `<br>Plate: ${event.plate}` : ""}
        </div>
    `);

    marker.on("click", () => {
        showEventDetails(event);
    });

    return marker;
}

function showToast(event) {
    const toast = document.createElement("div");
    toast.className = "live-toast";

    toast.innerHTML = `
        <strong>🚨 LIVE INCIDENT</strong>
        <span>${event.event_type} detected</span>
        <small>GPS: ${event.lat}, ${event.lon}</small>
    `;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("hide");

        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 5000);
}

function updateAnalytics(events) {
    const counts = {};

    events.forEach((event) => {
        const type = event.event_type || "unknown";
        counts[type] = (counts[type] || 0) + 1;
    });

    if (congestionCountElement) {
        congestionCountElement.textContent = counts["congestion"] || 0;
    }

    const sortedTypes = Object.entries(counts)
        .sort((a, b) => b[1] - a[1]);

    const labels = sortedTypes.map(([type]) => type);
    const values = sortedTypes.map(([, count]) => count);

    if (eventChart) {
        eventChart.destroy();
    }

    const chartCanvas = document.getElementById("event-chart");

    eventChart = new Chart(chartCanvas, {
        type: "bar",
        data: {
            labels,
            datasets: [
                {
                    label: "Events",
                    data: values
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    ticks: {
                        autoSkip: false,
                        maxRotation: 60,
                        minRotation: 30
                    }
                },
                y: {
                    beginAtZero: true
                }
            }
        }
    });

    const zoneCounts = {};

    events.forEach((event) => {
        if (
            typeof event.lat !== "number" ||
            typeof event.lon !== "number"
        ) {
            return;
        }

        const zone = `${event.lat.toFixed(4)}, ${event.lon.toFixed(4)}`;
        zoneCounts[zone] = (zoneCounts[zone] || 0) + 1;
    });

    const busiestZone = Object.entries(zoneCounts)
        .sort((a, b) => b[1] - a[1])[0];

    if (busiestZone) {
        busiestZoneElement.textContent = busiestZone[0];
        busiestZoneCountElement.textContent =
            `${busiestZone[1]} events`;
    } else {
        busiestZoneElement.textContent = "N/A";
        busiestZoneCountElement.textContent = "";
    }
}

function renderFleetMarkers(buses) {
    fleetMarkers.forEach((marker) => map.removeLayer(marker));
    fleetMarkers = [];

    buses.forEach((bus) => {
        const position = bus.latest_position;

        if (
            !position ||
            typeof position.lat !== "number" ||
            typeof position.lon !== "number"
        ) {
            return;
        }

        const marker = L.marker(
            [position.lat, position.lon],
            {
                icon: createFleetMarkerIcon(bus.online)
            }
        ).addTo(map);

        const source = String(bus.source || "unknown")
            .replace("_", " ")
            .toUpperCase();

        marker.bindPopup(`
            <div class="event-popup">
                <strong>🚌 ${bus.bus_id}</strong><br>
                Route: ${bus.route_id || "N/A"}<br>
                Speed: ${position.speed_kmh ?? "N/A"} km/h<br>
                Status: ${bus.online ? "ONLINE" : "OFFLINE"}<br>
                Source: ${source}<br>
                Last Seen: ${position.ts || "N/A"}
            </div>
        `);

        fleetMarkers.push(marker);
    });

    console.log(`Rendered ${fleetMarkers.length} fleet markers`);
}

function renderRound3IncidentMarkers(incidents) {
    round3IncidentMarkers.forEach((marker) => map.removeLayer(marker));
    round3IncidentMarkers = [];

    (incidents || []).forEach((incident) => {
        if (
            typeof incident.lat !== "number" ||
            typeof incident.lon !== "number"
        ) {
            return;
        }

        const eventType = incident.type || "incident";
        const color = getEventColor(eventType);

        const marker = L.marker(
            [incident.lat, incident.lon],
            {
                icon: createMarkerIcon(color)
            }
        ).addTo(map);

        marker.bindPopup(`
            <div class="event-popup">
                <strong>🚨 ROUND 3 INCIDENT</strong><br>
                Type: ${eventType}<br>
                Status: ${incident.status || "N/A"}<br>
                Severity: ${incident.severity || "N/A"}<br>
                Confidence: ${incident.confidence ?? "N/A"}<br>
                Reports: ${incident.report_count ?? 0}<br>
                Buses: ${incident.bus_count ?? 0}<br>
                GPS: ${incident.lat}, ${incident.lon}<br>
                First Seen: ${incident.first_seen || "N/A"}<br>
                Last Seen: ${incident.last_seen || "N/A"}
            </div>
        `);

        round3IncidentMarkers.push(marker);
    });

    console.log(
        `Rendered ${round3IncidentMarkers.length} Round 3 incident markers`
    );
}

function renderEventMarkers() {
    eventMarkers.forEach((marker) => map.removeLayer(marker));
    eventMarkers = [];

    allEvents.forEach((event) => {
        if (!selectedEventTypes.has(event.event_type)) {
            return;
        }

        const marker = addEventMarker(event);

        if (marker) {
            eventMarkers.push(marker);
        }
    });

    console.log(
        `Rendered ${eventMarkers.length} markers for ${selectedEventTypes.size} selected event types`
    );
}

function createEventFilters(events) {
    const eventTypes = [...new Set(
        events
            .map((event) => event.event_type)
            .filter(Boolean)
    )].sort();

    eventFiltersElement.innerHTML = "";

    eventTypes.forEach((eventType) => {
        selectedEventTypes.add(eventType);

        const label = document.createElement("label");
        label.className = "filter-option";

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = true;
        checkbox.value = eventType;

        checkbox.addEventListener("change", () => {
            if (checkbox.checked) {
                selectedEventTypes.add(eventType);
            } else {
                selectedEventTypes.delete(eventType);
            }

            renderEventMarkers();
        });

        const text = document.createElement("span");
        text.textContent = eventType;

        label.appendChild(checkbox);
        label.appendChild(text);

        eventFiltersElement.appendChild(label);
    });

    console.log(`Created ${eventTypes.length} event-type filters`);
}


function updateFleetPanel(events) {
    const busIds = new Set();
    const cameraIds = new Set();
    const alertTypes = new Set(["incident", "pothole", "pedestrian_risk", "congestion"]);
    const highCongestionZones = new Set();

    events.forEach((event) => {
        if (event.bus_id) {
            busIds.add(event.bus_id);
        }

        if (event.camera_id) {
            cameraIds.add(event.camera_id);
        }

        if (
            event.event_type === "congestion" &&
            typeof event.lat === "number" &&
            typeof event.lon === "number"
        ) {
            const zone = `${event.lat.toFixed(3)},${event.lon.toFixed(3)}`;
            highCongestionZones.add(zone);
        }
    });

    const alertsToday = events.filter((event) =>
        alertTypes.has(event.event_type)
    ).length;

    fleetActiveBusesElement.textContent = busIds.size;
    fleetOnlineCamerasElement.textContent = cameraIds.size;
    fleetAlertsTodayElement.textContent = alertsToday;
    fleetHighCongestionZonesElement.textContent = highCongestionZones.size;

    console.log(
        `Fleet panel updated: ${busIds.size} buses, ` +
        `${cameraIds.size} cameras, ${alertsToday} alerts, ` +
        `${highCongestionZones.size} high-congestion zones`
    );
}


function renderAlertTimeline(events) {
    if (!alertTimelineElement) {
        return;
    }

    const latestEvents = [...events]
        .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
        .slice(-8)
        .reverse();

    if (latestEvents.length === 0) {
        alertTimelineElement.innerHTML = "<p>No recent alerts.</p>";
        return;
    }

    alertTimelineElement.innerHTML = latestEvents
        .map((event) => {
            const date = new Date(event.timestamp);
            const time = Number.isNaN(date.getTime())
                ? "—"
                : date.toISOString().substring(11, 19);

            const eventType = String(event.event_type || "unknown")
                .replace(/_/g, " ")
                .replace(/\b\w/g, (char) => char.toUpperCase());

            return `
                <div class="timeline-item">
                    <span class="timeline-time">${time}</span>
                    <span class="timeline-event">${eventType}</span>
                </div>
            `;
        })
        .join("");
}

async function loadPredictions() {
    try {
        const response = await fetch(`${API_URL}/predictions`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const prediction = await response.json();

        predictionSeverityElement.textContent =
            prediction.congestion_severity.toUpperCase();

        const severityConfidence =
            prediction.severity_probabilities?.[
                prediction.congestion_severity
            ];

        if (typeof severityConfidence === "number") {
            predictionConfidenceElement.textContent =
                `${(severityConfidence * 100).toFixed(0)}% model confidence`;
        } else {
            predictionConfidenceElement.textContent = "";
        }

        predictionDelayElement.textContent =
            `${prediction.estimated_delay_minutes.toFixed(2)}`;

        predictionZoneElement.textContent =
            `Zone: ${prediction.zone}`;

        predictionEventsElement.textContent =
            `${prediction.event_count} events`;

        predictionNoteElement.textContent =
            prediction.delay_note || "";

        console.log("✓ ML predictions loaded:", prediction);
    } catch (error) {
        predictionSeverityElement.textContent = "Unavailable";
        predictionConfidenceElement.textContent = "";
        predictionDelayElement.textContent = "Unavailable";
        predictionZoneElement.textContent = "";
        predictionEventsElement.textContent = "";
        predictionNoteElement.textContent =
            "ML prediction service unavailable.";

        console.error("Failed to load ML predictions:", error);
    }
}


async function loadRound3Dashboard() {
    try {
        const response = await fetch(`${API_URL}/v1/dashboard`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const dashboard = await response.json();

        const stats = dashboard.stats || {};
        r3BusesOnlineElement.textContent = stats.buses_online ?? 0;
        r3BusesOfflineElement.textContent = stats.buses_offline ?? 0;
        r3IncidentsDetectedElement.textContent = stats.incidents_detected ?? 0;
        r3IncidentsVerifiedElement.textContent = stats.incidents_verified ?? 0;
        r3ReportsTodayElement.textContent = stats.reports_today ?? 0;

        renderFleetMarkers(dashboard.buses || []);
        renderRound3IncidentMarkers(dashboard.incidents || []);

        console.log(
            `✓ Round 3 dashboard loaded: ${dashboard.buses?.length || 0} buses, ` +
            `${dashboard.incidents?.length || 0} incidents`
        );

        return dashboard;
    } catch (error) {
        console.error("Failed to load Round 3 dashboard:", error);
        return null;
    }
}

async function loadEvents() {
    try {
        const response = await fetch(`${API_URL}/events`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const events = await response.json();

        allEvents = events;
        updateFleetPanel(events);
        renderAlertTimeline(events);

        eventCountElement.textContent = events.length;

        createEventFilters(events);
        renderEventMarkers();
        updateAnalytics(events);

        statusElement.textContent = "Connected";
        statusElement.classList.add("connected");
        statusElement.classList.remove("error");

        console.log(`Loaded ${events.length} events from TransitNexus API`);
    } catch (error) {
        statusElement.textContent = "Backend unavailable";
        statusElement.classList.remove("connected");
        statusElement.classList.add("error");

        console.error("Failed to load events:", error);
    }
}

async function loadHeatmap() {
    try {
        const response = await fetch(`${API_URL}/heatmap-data`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const heatmapData = await response.json();

        const points = heatmapData
            .filter(
                (point) =>
                    typeof point.lat === "number" &&
                    typeof point.lon === "number"
            )
            .map((point) => [
                point.lat,
                point.lon,
                Math.max(point.count, 1)
            ]);

        if (heatLayer) {
            map.removeLayer(heatLayer);
        }

        if (points.length > 0) {
            heatLayer = L.heatLayer(points, {
                radius: 30,
                blur: 20,
                maxZoom: 17,
                max: 10
            }).addTo(map);

            console.log(
                `Loaded ${points.length} congestion heatmap points`
            );
        } else {
            console.log("No congestion heatmap points returned");
        }
    } catch (error) {
        console.error("Failed to load heatmap data:", error);
    }
}


async function loadZoneSummary() {
    try {
        const response = await fetch(`${API_URL}/zone-summary`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const summaries = await response.json();

        if (!Array.isArray(summaries) || summaries.length === 0) {
            zoneSummaryZoneElement.textContent = "No zone data";
            return;
        }

        const busiestZone = summaries.reduce(
            (current, item) =>
                item.vehicle_count > current.vehicle_count ? item : current,
            summaries[0]
        );

        zoneSummaryZoneElement.textContent =
            `Zone ${busiestZone.zone} · 15-minute window`;

        zoneSummaryVehiclesElement.textContent =
            busiestZone.vehicle_count;

        zoneSummaryIncidentsElement.textContent =
            busiestZone.incident_count;

        zoneSummaryPotholesElement.textContent =
            busiestZone.pothole_count;

        zoneSummaryPedestrianElement.textContent =
            busiestZone.pedestrian_risk_count;

        zoneSummaryConfidenceElement.textContent =
            `${(busiestZone.average_confidence * 100).toFixed(1)}%`;

        zoneSummaryCongestionElement.textContent =
            busiestZone.congestion_level;

        console.log(
            `Loaded zone summary for ${busiestZone.zone}`
        );
    } catch (error) {
        zoneSummaryZoneElement.textContent = "Unavailable";
        console.error("Failed to load zone summary:", error);
    }
}

function connectWebSocket() {
    console.log(`Connecting to WebSocket: ${WS_URL}`);

    const websocket = new WebSocket(WS_URL);

    websocket.onopen = () => {
        console.log("✓ WebSocket connected");
        statusElement.textContent = "Live Connected";
        statusElement.classList.add("connected");
        statusElement.classList.remove("error");
    };

    websocket.onmessage = (message) => {
        try {
            const data = JSON.parse(message.data);

            if (data.type !== "incident" || !data.event) {
                console.warn("Ignoring unknown WebSocket message:", data);
                return;
            }

            const event = data.event;

            addEventMarker(event, true);

            const currentCount =
                Number(eventCountElement.textContent) || 0;

            eventCountElement.textContent = currentCount + 1;

            showToast(event);

            console.log("✓ Live incident received:", event);
        } catch (error) {
            console.error("Failed to process WebSocket message:", error);
        }
    };

    websocket.onerror = (error) => {
        console.error("WebSocket error:", error);
        statusElement.textContent = "Live Alerts Error";
        statusElement.classList.remove("connected");
        statusElement.classList.add("error");
    };

    websocket.onclose = () => {
        console.warn("WebSocket connection closed");
        statusElement.textContent = "Live Alerts Offline";
        statusElement.classList.remove("connected");
    };
}

async function initializeDashboard() {
    await loadRound3Dashboard();
    await loadEvents();
    await loadHeatmap();
    await loadPredictions();
    await loadZoneSummary();
    connectWebSocket();

    dashboardRefreshTimer = setInterval(
        loadRound3Dashboard,
        3000
    );
}

initializeDashboard();
