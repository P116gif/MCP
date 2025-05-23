from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

#init fastmcp server
mcp = FastMCP("weather")

#constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"
client = httpx.AsyncClient()

async def make_nws_request(url: str) -> dict[str, Any] | None:
    """
    Make a request to the NWS API and return the response as a dictionary.
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept":"application/geo+json"
    }

    async with client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

def format_alert(feature: dict) -> str:
    """
    Format the alert feature into a string.
    """
    props = feature["properties"]
    return f"""
Event: {props.get('event','Unknown')}
Area: {props.get('areaDesc','Unknown')} 
Severity: {props.get('severity','Unknown')}
Description: {props.get('description','No description available')}
Instructions: {props.get('instruction','No instructions available')}
"""

@mcp.tool()
async def get_alerts(state: str) -> str:
    """
    Get weather alerts for a given state.
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)
    
    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found. Please try again later."
    
    if not data["features"]:
        return "No active alerts found for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n --- \n".join(alerts)

@mcp.tool()
async def get_forecast(lat: float, lon: float) -> str:
    """
    Get the weather forecast for a given latitude and longitude.
    """
    url = f"{NWS_API_BASE}/points/{lat},{lon}"
    data = await make_nws_request(url)
    
    if not data:
        return "Unable to fetch forecast data for this location. Please try again later."

    forecast_url = data["properties"]["forecast"] 
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch forecast data for this location. Please try again later."
    
    periods = forecast_data["properties"]["periods"]
    forecasts = []

    for period in periods[:5]:
        forecast = f"""
        Name: {period['name']}
        Temperature: {period['temperature']}°{period['temperatureUnit']}
        Wind: {period['windSpeed']} {period['windDirection']}
        Detailed Forecast: {period['detailedForecast']}
        """
        forecasts.append(forecast)

    return "\n --- \n".join(forecasts)

if __name__ == "__main__":
    mcp.run(transport='stdio')