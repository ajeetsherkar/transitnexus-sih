import asyncio
import json

import websockets


WS_URL = "ws://127.0.0.1:8000/ws/alerts"


async def main():
    print("=" * 60)
    print("TRANSITNEXUS — WEBSOCKET ALERT TEST")
    print("=" * 60)
    print(f"Connecting to: {WS_URL}")

    async with websockets.connect(WS_URL) as websocket:
        print("✓ WebSocket connected")
        print("✓ Waiting for incident broadcast...")

        message = await websocket.recv()

        data = json.loads(message)

        assert data["type"] == "incident"
        assert "event" in data

        event = data["event"]

        assert event["event_type"] == "incident"

        print("\n✓ Broadcast received")
        print(f"✓ Message type: {data['type']}")
        print(f"✓ Event type: {event['event_type']}")
        print(f"✓ Plate: {event['plate']}")
        print(f"✓ Confidence: {event['confidence']}")
        print(f"✓ GPS: {event['lat']}, {event['lon']}")

        print("\n" + "=" * 60)
        print("✅ WEBSOCKET BROADCAST TEST PASSED")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
