const API_URL = "http://127.0.0.1:8000";

// Same simulated route area used by TransitNexus.
const MAP_CENTER = [19.9000, 74.4900];

const map = L.map("map").setView(MAP_CENTER, 14);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

const eventCountElement = document.getElementById("event-count");
const statusElement = document.getElementById("connection-status");
const detailsElement = document.getElementById("event-details");

function getEventColor(eventType) {
    switch (eventType) {
        case "pothole":
            return "orange";
        case "pedestrian_risk":
            return "red";
        case "congestion":
            return "yellow";
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
    `;
}

async function loadEvents() {
    try {
        statusElement.textContent = "Connected";
        statusElement.classList.add("connected");
        statusElement.classList.remove("error");

        const response = await fetch(`${API_URL}/events`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const events = await response.json();

        eventCountElement.textContent = events.length;

        events.forEach((event) => {
            if (
                typeof event.lat !== "number" ||
                typeof event.lon !== "number"
            ) {
                return;
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
                    <strong>${event.event_type}</strong><br>
                    Confidence: ${event.confidence}<br>
                    GPS: ${event.lat}, ${event.lon}<br>
                    Timestamp: ${event.timestamp}
                </div>
            `);

            marker.on("click", () => {
                showEventDetails(event);
            });
        });

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

        console.log(`Loaded ${events.length} events from TransitNexus API`);
    } catch (error) {
        statusElement.textContent = "Backend unavailable";
        statusElement.classList.remove("connected");
        statusElement.classList.add("error");

        console.error("Failed to load events:", error);
    }
}

loadEvents();
