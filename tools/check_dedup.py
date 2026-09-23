import argparse
import sys

import requests


def main():
    parser = argparse.ArgumentParser(
        description="Verify TransitNexus multi-bus pothole deduplication"
    )
    parser.add_argument("--buses", type=int, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--read-token", required=True)
    args = parser.parse_args()

    url = args.url.rstrip("/")
    headers = {"X-Read-Token": args.read_token}

    try:
        response = requests.get(
            f"{url}/v1/incidents",
            headers=headers,
            timeout=10,
        )
    except requests.RequestException as exc:
        print(f"FAIL: unable to reach backend: {exc}")
        sys.exit(1)

    if response.status_code != 200:
        print(
            f"FAIL: GET /v1/incidents returned "
            f"HTTP {response.status_code}"
        )
        print(response.text)
        sys.exit(1)

    payload = response.json()
    incidents = (
        payload.get("incidents", [])
        if isinstance(payload, dict)
        else payload
    )

    if not isinstance(incidents, list):
        print("FAIL: unexpected /v1/incidents response format")
        sys.exit(1)

    potholes = [
        incident
        for incident in incidents
        if incident.get("type") == "pothole"
    ]

    if len(potholes) != 1:
        print(
            f"FAIL: expected exactly 1 pothole incident, "
            f"found {len(potholes)}"
        )
        sys.exit(1)

    incident = potholes[0]

    incident_bus_count = incident.get("bus_count")
    status = incident.get("status")

    if incident_bus_count != args.buses:
        print(
            f"FAIL: expected bus_count={args.buses}, "
            f"found {incident_bus_count}"
        )
        sys.exit(1)

    if status != "VERIFIED":
        print(
            f"FAIL: expected status=VERIFIED, "
            f"found {status!r}"
        )
        sys.exit(1)

    print("=" * 64)
    print("S1.5 DEDUP PROOF")
    print("=" * 64)
    print("PASS: 1 pothole incident")
    print(f"PASS: {incident_bus_count} buses")
    print("PASS: status VERIFIED")
    print(f"PASS: incident_id={incident.get('id')}")
    print("=" * 64)
    print("S1.5 DEDUP CHECK: PASS")
    print("=" * 64)


if __name__ == "__main__":
    main()
