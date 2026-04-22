import requests


def get_weather(city: str) -> dict:
    """Fetch current weather and forecast for a city from wttr.in."""
    try:
        # Current weather
        resp = requests.get(
            f"https://wttr.in/{city}?format=j1",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        current = data["current_condition"][0]
        return {
            "temp_f": current.get("temp_F", ""),
            "temp_c": current.get("temp_C", ""),
            "feels_like_f": current.get("FeelsLikeF", ""),
            "description": current.get("weatherDesc", [{}])[0].get("value", ""),
            "humidity": current.get("humidity", ""),
            "wind_mph": current.get("windspeedMiles", ""),
            "wind_dir": current.get("winddir16Point", ""),
            "visibility_mi": current.get("visibilityMiles", ""),
            "uv_index": current.get("uvIndex", ""),
            "forecast": data.get("weather", []),
        }
    except Exception:
        return None
