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

const API_URL = "http://127.0.0.1:8000";
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

let eventChart = null;
let heatLayer = null;
let allEvents = [];
let eventMarkers = [];
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


async function loadEvents() {
    try {
        const response = await fetch(`${API_URL}/events`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const events = await response.json();

        allEvents = events;

        eventCountElement.textContent = events.length;

        createEventFilters(events);
        renderEventMarkers();
        updateAnalytics(events);

        if (events.length > 0) {
            const validEvents = events.filter(
                (event) =>
                    typeof event.lat === "number" &&
                    typeof event.lon === "number"
            );

            if (validEvents.length > 0) {
                const bounds = L.latLngBounds(
                    validEvents.map((event) => [event.lat, event.lon])
                );

                map.fitBounds(bounds, {
                    padding: [30, 30]
                });
            }
        }

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
    await loadEvents();
    await loadHeatmap();
    await loadPredictions();
    connectWebSocket();
}

initializeDashboard();
