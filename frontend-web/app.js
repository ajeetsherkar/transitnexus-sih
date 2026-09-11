const API_URL = "http://127.0.0.1:8000";
const WS_URL = API_URL.replace(/^http/, "ws") + "/ws/alerts";

// Same simulated route area used by TransitNexus.
const MAP_CENTER = [19.9000, 74.4900];

const map = L.map("map").setView(MAP_CENTER, 14);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors"
}).addTo(map);

const eventCountElement = document.getElementById("event-count");
const statusElement = document.getElementById("connection-status");
const detailsElement = document.getElementById("event-details");
const busiestZoneElement = document.getElementById("busiest-zone");
const busiestZoneCountElement = document.getElementById("busiest-zone-count");

let eventChart = null;
let heatLayer = null;

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
    detailsElement.innerHTML = `
        <h3>Event Details</h3>
        <p><strong>Type:</strong> ${event.event_type}</p>
        <p><strong>Confidence:</strong> ${event.confidence}</p>
        <p><strong>Latitude:</strong> ${event.lat}</p>
        <p><strong>Longitude:</strong> ${event.lon}</p>
        <p><strong>Timestamp:</strong> ${event.timestamp}</p>
        ${event.plate ? `<p><strong>Plate:</strong> ${event.plate}</p>` : ""}
        ${event.plate_source ? `<p><strong>Plate Source:</strong> ${event.plate_source}</p>` : ""}
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

async function loadEvents() {
    try {
        const response = await fetch(`${API_URL}/events`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const events = await response.json();

        eventCountElement.textContent = events.length;

        events.forEach((event) => {
            addEventMarker(event);
        });

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
    connectWebSocket();
}

initializeDashboard();
