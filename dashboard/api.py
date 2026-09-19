import requests
import streamlit as st


def _config():
    try:
        base_url = st.secrets["API_BASE_URL"].rstrip("/")
        read_token = st.secrets["READ_TOKEN"]
    except KeyError as exc:
        raise RuntimeError(
            f"Missing Streamlit secret: {exc.args[0]}"
        ) from exc

    return base_url, read_token


def _headers():
    _, read_token = _config()
    return {"X-Read-Token": read_token}


@st.cache_data(ttl=2)
def get_buses():
    base_url, _ = _config()

    response = requests.get(
        f"{base_url}/v1/buses",
        headers=_headers(),
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise RuntimeError("Expected /v1/buses to return a list")

    return data


@st.cache_data(ttl=2)
def get_incidents():
    base_url, _ = _config()

    response = requests.get(
        f"{base_url}/v1/incidents",
        headers=_headers(),
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise RuntimeError("Expected /v1/incidents to return a list")

    return data
