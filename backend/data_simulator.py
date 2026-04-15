"""
AegisPath X — Data Simulator
Generates a realistic city graph with safety attributes for routing.
"""

import random
import math
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class SegmentAttributes:
    """Safety attributes for a road segment."""
    crime_index: float        # 0.0 (safe) → 1.0 (dangerous)
    lighting_level: float     # 0.0 (dark) → 1.0 (bright)
    crowd_density: float      # 0.0 (isolated) → 1.0 (crowded)
    weather_exposure: float   # 0.0 (sheltered) → 1.0 (exposed)
    road_type: str            # highway | main_road | residential | alley | park_path
    area_name: str

    def to_dict(self):
        return asdict(self)


@dataclass
class Node:
    """A point in the city graph."""
    id: str
    lat: float
    lng: float
    area_name: str

    def to_dict(self):
        return {"id": self.id, "lat": self.lat, "lng": self.lng, "area_name": self.area_name}


@dataclass
class Edge:
    """A road segment between two nodes."""
    source: str
    target: str
    distance: float          # km
    attributes: SegmentAttributes

    def to_dict(self):
        return {
            "source": self.source,
            "target": self.target,
            "distance": self.distance,
            "attributes": self.attributes.to_dict(),
        }


class CityGraph:
    """Simulated city graph with safety data."""

    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, List[Edge]] = {}   # adjacency list
        self.incidents: List[dict] = []

    def add_node(self, node: Node):
        self.nodes[node.id] = node
        if node.id not in self.edges:
            self.edges[node.id] = []

    def add_edge(self, edge: Edge):
        if edge.source not in self.edges:
            self.edges[edge.source] = []
        if edge.target not in self.edges:
            self.edges[edge.target] = []
        self.edges[edge.source].append(edge)
        # Bidirectional
        reverse = Edge(
            source=edge.target,
            target=edge.source,
            distance=edge.distance,
            attributes=edge.attributes,
        )
        self.edges[edge.target].append(reverse)

    def get_neighbors(self, node_id: str) -> List[Edge]:
        return self.edges.get(node_id, [])

    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def find_nearest_node(self, lat: float, lng: float) -> str:
        """Find the nearest node to given coordinates."""
        min_dist = float("inf")
        nearest = None
        for nid, node in self.nodes.items():
            dist = math.sqrt((node.lat - lat) ** 2 + (node.lng - lng) ** 2)
            if dist < min_dist:
                min_dist = dist
                nearest = nid
        return nearest

    def to_dict(self):
        all_edges = []
        seen = set()
        for source, edges in self.edges.items():
            for edge in edges:
                key = tuple(sorted([edge.source, edge.target]))
                if key not in seen:
                    seen.add(key)
                    all_edges.append(edge.to_dict())
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": all_edges,
        }


# ── Helpers ──────────────────────────────────────────────────────────


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distance in km between two lat/lng points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 3)


def _jitter(value: float, amount: float) -> float:
    return max(0.0, min(1.0, value + random.uniform(-amount, amount)))


def _road_type_for_area(area: str) -> str:
    mapping = {
        "downtown": "main_road",
        "tech_park": "main_road",
        "old_market": "residential",
        "industrial": "highway",
        "residential_north": "residential",
        "residential_south": "residential",
        "park_district": "park_path",
        "highway_corridor": "highway",
        "university": "main_road",
        "suburb_east": "residential",
    }
    return mapping.get(area, "residential")


# ── City Generator ───────────────────────────────────────────────────


AREA_PROFILES = {
    "downtown":           {"crime": 0.30, "light": 0.90, "crowd": 0.80, "weather": 0.30},
    "tech_park":          {"crime": 0.10, "light": 0.95, "crowd": 0.70, "weather": 0.20},
    "old_market":         {"crime": 0.50, "light": 0.60, "crowd": 0.90, "weather": 0.50},
    "industrial":         {"crime": 0.70, "light": 0.30, "crowd": 0.20, "weather": 0.80},
    "residential_north":  {"crime": 0.20, "light": 0.70, "crowd": 0.50, "weather": 0.40},
    "residential_south":  {"crime": 0.30, "light": 0.60, "crowd": 0.40, "weather": 0.40},
    "park_district":      {"crime": 0.40, "light": 0.40, "crowd": 0.30, "weather": 0.90},
    "highway_corridor":   {"crime": 0.60, "light": 0.50, "crowd": 0.10, "weather": 0.70},
    "university":         {"crime": 0.15, "light": 0.85, "crowd": 0.75, "weather": 0.30},
    "suburb_east":        {"crime": 0.25, "light": 0.50, "crowd": 0.30, "weather": 0.50},
}

# 8×8 grid area layout
AREA_GRID = [
    ["residential_north","residential_north","university",       "university",       "tech_park",       "tech_park",       "suburb_east",      "suburb_east"],
    ["residential_north","residential_north","university",       "downtown",         "tech_park",       "tech_park",       "suburb_east",      "suburb_east"],
    ["park_district",    "residential_north","downtown",         "downtown",         "downtown",        "tech_park",       "suburb_east",      "highway_corridor"],
    ["park_district",    "park_district",    "old_market",       "downtown",         "downtown",        "industrial",      "highway_corridor", "highway_corridor"],
    ["park_district",    "old_market",       "old_market",       "old_market",       "industrial",      "industrial",      "highway_corridor", "highway_corridor"],
    ["residential_south","old_market",       "old_market",       "residential_south","industrial",      "industrial",      "suburb_east",      "highway_corridor"],
    ["residential_south","residential_south","residential_south","residential_south","residential_south","suburb_east",     "suburb_east",      "suburb_east"],
    ["residential_south","residential_south","residential_south","residential_south","suburb_east",     "suburb_east",     "suburb_east",      "suburb_east"],
]


def generate_demo_city() -> CityGraph:
    """Build an 8×8 demo city centered around a metropolitan area."""
    graph = CityGraph()
    center_lat, center_lng = 17.385, 78.4867
    grid_size = 8
    spacing = 0.008  # ~0.8 km between nodes

    random.seed(42)

    # — Nodes —
    for r in range(grid_size):
        for c in range(grid_size):
            nid = f"N{r}_{c}"
            lat = center_lat + (grid_size / 2 - r) * spacing
            lng = center_lng + (c - grid_size / 2) * spacing
            area = AREA_GRID[r][c]
            graph.add_node(Node(id=nid, lat=lat, lng=lng, area_name=area))

    # — Edges (horizontal, vertical, sparse diagonals) —
    for r in range(grid_size):
        for c in range(grid_size):
            src = f"N{r}_{c}"
            src_node = graph.get_node(src)

            def _make_edge(tgt_id):
                tgt_node = graph.get_node(tgt_id)
                area = AREA_GRID[r][c]
                p = AREA_PROFILES[area]
                dist = _haversine(src_node.lat, src_node.lng, tgt_node.lat, tgt_node.lng)
                attrs = SegmentAttributes(
                    crime_index=_jitter(p["crime"], 0.10),
                    lighting_level=_jitter(p["light"], 0.10),
                    crowd_density=_jitter(p["crowd"], 0.15),
                    weather_exposure=_jitter(p["weather"], 0.10),
                    road_type=_road_type_for_area(area),
                    area_name=area,
                )
                graph.add_edge(Edge(source=src, target=tgt_id, distance=dist, attributes=attrs))

            if c < grid_size - 1:
                _make_edge(f"N{r}_{c+1}")
            if r < grid_size - 1:
                _make_edge(f"N{r+1}_{c}")
            if r < grid_size - 1 and c < grid_size - 1 and random.random() < 0.3:
                _make_edge(f"N{r+1}_{c+1}")

    return graph


# ── Real-Time Simulation ─────────────────────────────────────────────


_INCIDENT_TYPES = [
    {"type": "accident",            "severity": "high",   "impact": "Road partially blocked"},
    {"type": "construction",        "severity": "medium", "impact": "Lane closure"},
    {"type": "suspicious_activity", "severity": "high",   "impact": "Area flagged unsafe"},
    {"type": "poor_lighting",       "severity": "medium", "impact": "Street lights out"},
    {"type": "flooding",            "severity": "high",   "impact": "Road waterlogged"},
    {"type": "crowd_surge",         "severity": "low",    "impact": "Heavy pedestrian traffic"},
    {"type": "power_outage",        "severity": "high",   "impact": "No street lighting"},
    {"type": "vehicle_breakdown",   "severity": "low",    "impact": "Slow traffic"},
]


def generate_live_incidents(graph: CityGraph, count: int = 5) -> List[dict]:
    node_ids = list(graph.nodes.keys())
    incidents = []
    for _ in range(count):
        node = graph.nodes[random.choice(node_ids)]
        tpl = random.choice(_INCIDENT_TYPES)
        incidents.append({
            "id": f"INC-{random.randint(1000, 9999)}",
            "type": tpl["type"],
            "severity": tpl["severity"],
            "impact": tpl["impact"],
            "lat": node.lat + random.uniform(-0.002, 0.002),
            "lng": node.lng + random.uniform(-0.002, 0.002),
            "area": node.area_name,
            "timestamp": time.time() - random.randint(0, 3600),
            "active": True,
        })
    return incidents


def generate_weather_data() -> dict:
    conditions = ["clear", "cloudy", "light_rain", "heavy_rain", "fog", "storm"]
    weights = [0.30, 0.25, 0.20, 0.10, 0.10, 0.05]
    cond = random.choices(conditions, weights=weights, k=1)[0]
    impact = {"clear": 0.0, "cloudy": 0.05, "light_rain": 0.2,
              "heavy_rain": 0.5, "fog": 0.4, "storm": 0.8}
    return {
        "condition": cond,
        "impact_score": impact[cond],
        "visibility": max(0.2, 1.0 - impact[cond]),
        "temperature": random.randint(18, 38),
        "humidity": random.randint(40, 95),
        "wind_speed": random.randint(0, 50),
    }


def generate_crowd_density_data(graph: CityGraph, time_of_day: str) -> Dict[str, float]:
    multiplier = {"morning": 0.6, "afternoon": 0.8, "evening": 1.0,
                  "night": 0.2, "late_night": 0.1}.get(time_of_day, 0.5)
    area_base = {
        "downtown": 0.8, "tech_park": 0.7, "old_market": 0.9,
        "industrial": 0.3, "residential_north": 0.5, "residential_south": 0.4,
        "park_district": 0.4, "highway_corridor": 0.2, "university": 0.7,
        "suburb_east": 0.3,
    }
    densities = {}
    for nid, node in graph.nodes.items():
        base = area_base.get(node.area_name, 0.5)
        densities[nid] = min(1.0, base * multiplier * random.uniform(0.7, 1.3))
    return densities
