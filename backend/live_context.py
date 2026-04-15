import datetime
import httpx
import pytz

def get_ist_time_of_day():
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.datetime.now(ist)
    
    # 6 PM (18:00) to 6 AM (06:00) is NIGHT
    if now.hour >= 18 or now.hour < 6:
        return "night"
    return "afternoon"

def get_live_weather(lat: float, lng: float) -> dict:
    default_weather = {"condition": "clear", "severity": 0.1, "visibility": "good"}
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=precipitation,weather_code,visibility"
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                current = data.get("current", {})
                code = current.get("weather_code", 0)
                
                # Convert WMO code to condition and severity
                if code == 0:
                    return {"condition": "clear", "severity": 0.1, "visibility": "good"}
                elif code in [1, 2, 3]:
                    return {"condition": "cloudy", "severity": 0.2, "visibility": "fair"}
                elif code in [45, 48]:
                    return {"condition": "fog", "severity": 0.9, "visibility": "poor"}
                elif code in [51, 53, 55, 61]:
                    return {"condition": "light_rain", "severity": 0.4, "visibility": "fair"}
                elif code in [63, 65, 80, 81, 82]:
                    return {"condition": "heavy_rain", "severity": 0.8, "visibility": "poor"}
                elif code >= 95:
                    return {"condition": "storm", "severity": 1.0, "visibility": "poor"}
    except Exception as e:
        print(f"Weather API failed: {e}")
        pass
    
    return default_weather
