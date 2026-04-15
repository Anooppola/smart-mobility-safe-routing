"""
AegisPath X — Context Engine
Dynamically adjusts routing weights based on user type, time, and weather.
"""

from dataclasses import dataclass, asdict
from typing import List


@dataclass
class RoutingWeights:
    """Dynamic weights for the multi-factor cost function."""
    crime_weight: float       # W1
    darkness_weight: float    # W2
    weather_weight: float     # W3
    isolation_weight: float   # W4

    def to_dict(self):
        return asdict(self)

    def total(self):
        return (self.crime_weight + self.darkness_weight
                + self.weather_weight + self.isolation_weight)


@dataclass
class UserContext:
    """Full context for a routing request."""
    user_type: str            # solo | female_traveler | delivery_rider | commuter
    time_of_day: str          # morning | afternoon | evening | night | late_night
    weather_condition: str    # clear | cloudy | light_rain | heavy_rain | fog | storm
    weights: RoutingWeights = None
    weather_severity: float = 0.1

    def to_dict(self):
        return {
            "user_type": self.user_type,
            "time_of_day": self.time_of_day,
            "weather_condition": self.weather_condition,
            "weather_severity": self.weather_severity,
            "weights": self.weights.to_dict() if self.weights else None,
        }


# ── Base Profiles ────────────────────────────────────────────────────

USER_TYPE_PROFILES = {
    "solo": {
        "crime_weight": 0.30, "darkness_weight": 0.25,
        "weather_weight": 0.15, "isolation_weight": 0.30,
    },
    "female_traveler": {
        "crime_weight": 0.35, "darkness_weight": 0.30,
        "weather_weight": 0.10, "isolation_weight": 0.25,
    },
    "delivery_rider": {
        "crime_weight": 0.20, "darkness_weight": 0.15,
        "weather_weight": 0.35, "isolation_weight": 0.30,
    },
    "commuter": {
        "crime_weight": 0.25, "darkness_weight": 0.20,
        "weather_weight": 0.20, "isolation_weight": 0.35,
    },
}

# Multiplicative time modifiers
TIME_MODIFIERS = {
    "morning":    {"crime_weight": 0.8, "darkness_weight": 0.5,
                   "weather_weight": 1.0, "isolation_weight": 0.7},
    "afternoon":  {"crime_weight": 0.9, "darkness_weight": 0.3,
                   "weather_weight": 1.0, "isolation_weight": 0.6},
    "evening":    {"crime_weight": 1.0, "darkness_weight": 1.2,
                   "weather_weight": 0.9, "isolation_weight": 1.1},
    "night":      {"crime_weight": 1.3, "darkness_weight": 1.8,
                   "weather_weight": 0.8, "isolation_weight": 1.5},
    "late_night": {"crime_weight": 1.5, "darkness_weight": 2.0,
                   "weather_weight": 0.7, "isolation_weight": 1.8},
}

WEATHER_MODIFIERS = {
    "clear":      {"weather_weight": 0.3, "darkness_weight": 1.0},
    "cloudy":     {"weather_weight": 0.5, "darkness_weight": 1.1},
    "light_rain": {"weather_weight": 1.2, "darkness_weight": 1.2},
    "heavy_rain": {"weather_weight": 1.8, "darkness_weight": 1.4},
    "fog":        {"weather_weight": 1.5, "darkness_weight": 1.6},
    "storm":      {"weather_weight": 2.5, "darkness_weight": 1.5},
}


# ── Weight Computation ───────────────────────────────────────────────


def compute_weights(user_type: str, time_of_day: str,
                    weather: str = "clear") -> RoutingWeights:
    """Compute dynamic routing weights; normalized to sum to 1."""
    profile = USER_TYPE_PROFILES.get(user_type, USER_TYPE_PROFILES["solo"])
    t_mod = TIME_MODIFIERS.get(time_of_day, TIME_MODIFIERS["afternoon"])
    w_mod = WEATHER_MODIFIERS.get(weather, WEATHER_MODIFIERS["clear"])

    crime_w = profile["crime_weight"] * t_mod["crime_weight"]
    dark_w  = (profile["darkness_weight"] * t_mod["darkness_weight"]
               * w_mod.get("darkness_weight", 1.0))
    weath_w = (profile["weather_weight"] * t_mod["weather_weight"]
               * w_mod.get("weather_weight", 1.0))
    iso_w   = profile["isolation_weight"] * t_mod["isolation_weight"]

    total = crime_w + dark_w + weath_w + iso_w
    if total > 0:
        crime_w /= total
        dark_w  /= total
        weath_w /= total
        iso_w   /= total

    return RoutingWeights(
        crime_weight=round(crime_w, 4),
        darkness_weight=round(dark_w, 4),
        weather_weight=round(weath_w, 4),
        isolation_weight=round(iso_w, 4),
    )


def build_context(user_type: str, time_of_day: str,
                  weather: str = "clear") -> UserContext:
    """Build a complete UserContext with computed weights."""
    weights = compute_weights(user_type, time_of_day, weather)
    return UserContext(
        user_type=user_type,
        time_of_day=time_of_day,
        weather_condition=weather,
        weights=weights,
    )


def get_weight_explanation(context: UserContext) -> List[str]:
    """Human-readable explanation of weight adjustments."""
    explanations: List[str] = []

    # Time
    if context.time_of_day in ("night", "late_night"):
        explanations.append("⚠️ Nighttime travel: Darkness and isolation weights significantly increased")
        explanations.append("🔦 Low lighting areas will be penalized more heavily")
    elif context.time_of_day == "evening":
        explanations.append("🌆 Evening travel: Moderate increase in darkness awareness")
    elif context.time_of_day == "morning":
        explanations.append("🌅 Morning travel: Lower risk profile, standard routing")

    # User type
    if context.user_type == "female_traveler":
        explanations.append("👤 Female traveler profile: Prioritizing well-lit, populated routes")
        explanations.append("🛡️ Crime and darkness weights elevated for enhanced safety")
    elif context.user_type == "solo":
        explanations.append("👤 Solo traveler: Isolation penalty active to avoid deserted areas")
    elif context.user_type == "delivery_rider":
        explanations.append("🏍️ Delivery rider: Weather impact weighted higher for road safety")
    elif context.user_type == "commuter":
        explanations.append("🚶 Commuter: Balanced safety profile with isolation awareness")

    # Weather
    if context.weather_condition in ("heavy_rain", "storm"):
        explanations.append("🌧️ Severe weather: Routing prioritizes sheltered paths")
    elif context.weather_condition == "fog":
        explanations.append("🌫️ Low visibility: Darkness penalty amplified")
    elif context.weather_condition == "light_rain":
        explanations.append("🌦️ Light rain: Slight preference for covered routes")

    w = context.weights
    explanations.append(
        f"📊 Active weights → Crime: {w.crime_weight:.0%} | "
        f"Darkness: {w.darkness_weight:.0%} | Weather: {w.weather_weight:.0%} | "
        f"Isolation: {w.isolation_weight:.0%}"
    )
    return explanations
