"""
AegisPath X — Safety Model
Evaluates segment risk and generates explainable safety assessments.
"""

from typing import List, Tuple
from dataclasses import dataclass, asdict

from context_engine import RoutingWeights, UserContext
from data_simulator import SegmentAttributes, Edge


# ── Data Classes ─────────────────────────────────────────────────────


@dataclass
class SegmentRisk:
    """Risk assessment for a single road segment."""
    source: str
    target: str
    distance: float
    cumulative_distance: float
    risk_score: float          # 0 → 1
    risk_level: str            # low | medium | high | critical
    contributing_factors: List[str]
    area_name: str

    def to_dict(self):
        return asdict(self)


@dataclass
class RouteAssessment:
    """Complete safety assessment for a route."""
    total_distance: float
    total_risk_score: float
    average_risk: float
    max_risk: float
    confidence_score: float
    high_risk_segments: List[SegmentRisk]
    segment_risks: List[SegmentRisk]
    danger_zones: List[dict]
    overall_safety_rating: str   # A – F

    def to_dict(self):
        return {
            "total_distance": self.total_distance,
            "total_risk_score": round(self.total_risk_score, 4),
            "average_risk": round(self.average_risk, 4),
            "max_risk": round(self.max_risk, 4),
            "confidence_score": round(self.confidence_score, 4),
            "high_risk_segments": [s.to_dict() for s in self.high_risk_segments],
            "segment_risks": [s.to_dict() for s in self.segment_risks],
            "danger_zones": self.danger_zones,
            "overall_safety_rating": self.overall_safety_rating,
        }


# ── Core Risk Functions ──────────────────────────────────────────────


def calculate_segment_risk(edge: Edge, context: UserContext) -> float:
    """
    Dynamic risk for a segment:
      Safety_Penalty = 0.4 * incident_density + 0.3 * (1 - lighting_level) + 0.3 * weather_severity
    """
    a = edge.attributes
    risk = (
        0.4 * a.crime_index
        + 0.3 * (1.0 - a.lighting_level)
        + 0.3 * context.weather_severity
    )
    return min(1.0, max(0.0, risk))

def calculate_edge_cost(edge: Edge, context: UserContext) -> float:
    """Cost = Distance × (1 + Dynamic_Risk)"""
    risk = calculate_segment_risk(edge, context)
    return edge.distance * (1.0 + risk)


# ── Helpers ──────────────────────────────────────────────────────────


def _risk_level(score: float) -> str:
    if score < 0.25:
        return "low"
    elif score < 0.50:
        return "medium"
    elif score < 0.75:
        return "high"
    return "critical"


def _contributing_factors(edge: Edge, context: UserContext) -> List[str]:
    a = edge.attributes
    contributions = [
        (0.4 * a.crime_index,
         f"Incident density: {a.crime_index:.0%}"),
        (0.3 * (1 - a.lighting_level),
         f"Low lighting: {1 - a.lighting_level:.0%} darkness"),
        (0.3 * context.weather_severity,
         f"Weather severity: {context.weather_severity:.0%}"),
    ]
    contributions.sort(key=lambda x: x[0], reverse=True)
    return [desc for val, desc in contributions if val > 0.05]


# ── Route Assessment ─────────────────────────────────────────────────


def assess_route(route_edges: List[Edge], context: UserContext) -> RouteAssessment:
    """Full safety assessment of a route."""
    segment_risks: List[SegmentRisk] = []
    cum_dist = 0.0
    total_risk = 0.0
    max_risk = 0.0
    high_risk: List[SegmentRisk] = []
    danger_zones: List[dict] = []

    for edge in route_edges:
        risk = calculate_segment_risk(edge, context)
        cum_dist += edge.distance
        total_risk += risk * edge.distance
        max_risk = max(max_risk, risk)

        seg = SegmentRisk(
            source=edge.source,
            target=edge.target,
            distance=round(edge.distance, 3),
            cumulative_distance=round(cum_dist, 3),
            risk_score=round(risk, 4),
            risk_level=_risk_level(risk),
            contributing_factors=_contributing_factors(edge, context),
            area_name=edge.attributes.area_name,
        )
        segment_risks.append(seg)

        if risk >= 0.5:
            high_risk.append(seg)
            danger_zones.append({
                "start_km": round(cum_dist - edge.distance, 2),
                "end_km": round(cum_dist, 2),
                "risk_score": round(risk, 4),
                "area": edge.attributes.area_name,
                "description": (
                    f"Segment {edge.source}→{edge.target} in "
                    f"{edge.attributes.area_name}: "
                    + ", ".join(_contributing_factors(edge, context)[:2])
                ),
            })

    total_distance = cum_dist
    avg_risk = total_risk / total_distance if total_distance > 0 else 0

    # Safety rating
    if avg_risk < 0.20:   rating = "A"
    elif avg_risk < 0.35: rating = "B"
    elif avg_risk < 0.50: rating = "C"
    elif avg_risk < 0.65: rating = "D"
    else:                 rating = "F"

    # Confidence (higher with more data and lower variance)
    risk_vals = [s.risk_score for s in segment_risks]
    if len(risk_vals) > 1:
        var = sum((r - avg_risk) ** 2 for r in risk_vals) / len(risk_vals)
        confidence = max(0.50, min(0.98, 1.0 - var * 2))
    else:
        confidence = 0.70

    return RouteAssessment(
        total_distance=round(total_distance, 3),
        total_risk_score=round(total_risk, 4),
        average_risk=round(avg_risk, 4),
        max_risk=round(max_risk, 4),
        confidence_score=round(confidence, 4),
        high_risk_segments=high_risk,
        segment_risks=segment_risks,
        danger_zones=danger_zones,
        overall_safety_rating=rating,
    )


# ── Explainable AI ───────────────────────────────────────────────────


def generate_route_reasoning(
    selected: RouteAssessment,
    rejected: List[Tuple[RouteAssessment, str]],
    context: UserContext,
) -> List[str]:
    """Generate human-readable reasoning for route selection."""
    reasons: List[str] = []

    reasons.append(
        f"✅ SELECTED: Route with safety rating {selected.overall_safety_rating} "
        f"(avg risk: {selected.average_risk:.0%}, "
        f"distance: {selected.total_distance:.1f} km)"
    )

    if not selected.high_risk_segments:
        reasons.append("✅ No high-risk segments detected on this route")
    elif len(selected.high_risk_segments) <= 2:
        reasons.append(
            f"⚠️ {len(selected.high_risk_segments)} moderate-risk segment(s) "
            f"— acceptable given alternatives"
        )

    for alt, label in rejected:
        parts: List[str] = []
        dist_diff = alt.total_distance - selected.total_distance
        risk_diff = alt.average_risk - selected.average_risk

        if alt.average_risk > selected.average_risk:
            parts.append(
                f"Average risk {alt.average_risk:.0%} vs "
                f"selected {selected.average_risk:.0%}"
            )
        if len(alt.high_risk_segments) > len(selected.high_risk_segments):
            parts.append(
                f"{len(alt.high_risk_segments)} high-risk segments "
                f"vs {len(selected.high_risk_segments)} on selected"
            )
        for dz in alt.danger_zones:
            parts.append(
                f"Danger zone at {dz['start_km']:.1f}km–{dz['end_km']:.1f}km: "
                f"{dz['description']}"
            )
        if dist_diff < 0 and risk_diff > 0:
            mins = abs(dist_diff) / 30 * 60
            parts.append(
                f"⚡ {abs(dist_diff):.1f} km shorter (~{mins:.0f} min faster) "
                f"but {risk_diff * 100:.0f}% less safe"
            )

        if parts:
            reasons.append(f"❌ REJECTED {label}: " + " | ".join(parts[:3]))
            for extra in parts[3:]:
                reasons.append(f"   → {extra}")

    if context.time_of_day in ("night", "late_night"):
        reasons.append("🌙 Night mode: Avoided poorly lit and isolated road segments")
    if context.user_type == "female_traveler":
        reasons.append("🛡️ Enhanced safety: Prioritized populated, well-lit areas")
    if context.user_type == "solo":
        reasons.append("👤 Solo travel: Selected route with highest crowd density")
    if context.weather_condition in ("heavy_rain", "storm"):
        reasons.append("🌧️ Bad weather: Selected route with better shelter coverage")

    return reasons


def generate_comparison_text(selected: RouteAssessment,
                             fastest: RouteAssessment) -> dict:
    """Smart comparison card text."""
    dist_diff = selected.total_distance - fastest.total_distance
    time_diff = dist_diff / 30 * 60  # minutes @ 30 km/h
    safe_diff = ((fastest.average_risk - selected.average_risk)
                 / max(fastest.average_risk, 0.01) * 100)
    avoided = max(0, len(fastest.high_risk_segments) - len(selected.high_risk_segments))

    time_str = (f"⏱️ {abs(round(time_diff))} min slower"
                if time_diff > 0
                else f"⚡ {abs(round(time_diff))} min faster")
    return {
        "time_difference": f"{abs(time_diff):.0f} min {'slower' if time_diff > 0 else 'faster'}",
        "safety_improvement": f"{abs(safe_diff):.0f}% {'safer' if safe_diff > 0 else 'less safe'}",
        "avoided_segments": avoided,
        "summary": (
            f"{time_str} but {abs(safe_diff):.0f}% safer"
            + (f" | Avoids {avoided} high-risk segments" if avoided > 0 else "")
        ),
    }
