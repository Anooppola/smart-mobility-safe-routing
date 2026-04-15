"""
AegisPath X — Routing Engine
A* pathfinding with multi-factor safety-aware cost function.
"""

import heapq
import math
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass

from data_simulator import CityGraph, Edge, Node
from context_engine import RoutingWeights, UserContext
from safety_model import (
    calculate_edge_cost, assess_route,
    generate_route_reasoning, generate_comparison_text,
)


@dataclass
class Route:
    """A computed route with metadata."""
    path: List[str]
    edges: List[Edge]
    total_distance: float
    total_cost: float
    coordinates: List[dict]

    def to_dict(self):
        return {
            "path": self.path,
            "total_distance": round(self.total_distance, 3),
            "total_cost": round(self.total_cost, 3),
            "coordinates": self.coordinates,
        }


# ── A* Search ────────────────────────────────────────────────────────


def _heuristic(graph: CityGraph, node_id: str, goal_id: str) -> float:
    """Haversine admissible heuristic for A*."""
    n = graph.get_node(node_id)
    g = graph.get_node(goal_id)
    if not n or not g:
        return 0.0
    R = 6371
    dlat = math.radians(g.lat - n.lat)
    dlng = math.radians(g.lng - n.lng)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(n.lat))
         * math.cos(math.radians(g.lat))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def a_star_search(
    graph: CityGraph,
    start_id: str,
    goal_id: str,
    context: UserContext,
    excluded_edges: Optional[Set[Tuple[str, str]]] = None,
) -> Optional[Route]:
    """A* with priority queue and multi-factor cost."""
    if excluded_edges is None:
        excluded_edges = set()

    counter = 0
    open_set: list = [(0.0, counter, start_id)]
    came_from: Dict[str, Tuple[str, Edge]] = {}
    g_score: Dict[str, float] = {start_id: 0.0}
    closed: set = set()

    while open_set:
        _, _, current = heapq.heappop(open_set)

        if current == goal_id:
            return _reconstruct(graph, came_from, start_id, goal_id)

        if current in closed:
            continue
        closed.add(current)

        for edge in graph.get_neighbors(current):
            nb = edge.target
            if nb in closed:
                continue
            ek = (edge.source, edge.target)
            if ek in excluded_edges or (edge.target, edge.source) in excluded_edges:
                continue

            tentative = g_score[current] + calculate_edge_cost(edge, context)
            if tentative < g_score.get(nb, float("inf")):
                came_from[nb] = (current, edge)
                g_score[nb] = tentative
                counter += 1
                heapq.heappush(
                    open_set,
                    (tentative + _heuristic(graph, nb, goal_id), counter, nb),
                )

    return None  # no path


def _reconstruct(graph: CityGraph, came_from, start_id, goal_id) -> Route:
    path = [goal_id]
    edges: List[Edge] = []
    cur = goal_id
    while cur != start_id:
        parent, edge = came_from[cur]
        path.append(parent)
        edges.append(edge)
        cur = parent
    path.reverse()
    edges.reverse()

    coords = []
    for nid in path:
        n = graph.get_node(nid)
        coords.append({"lat": n.lat, "lng": n.lng, "node_id": nid, "area": n.area_name})

    return Route(
        path=path,
        edges=edges,
        total_distance=sum(e.distance for e in edges),
        total_cost=sum(
            calculate_edge_cost(e, RoutingWeights(0.25, 0.25, 0.25, 0.25))
            for e in edges
        ),
        coordinates=coords,
    )


# ── Alternative Routes ───────────────────────────────────────────────


def find_alternative_routes(
    graph: CityGraph,
    start_id: str,
    goal_id: str,
    context: UserContext,
    num_alternatives: int = 2,
) -> List[Route]:
    """Edge-penalty method: exclude middle edges of previous best to diversify."""
    primary = a_star_search(graph, start_id, goal_id, context)
    if not primary:
        return []

    alternatives: List[Route] = []
    all_excluded: Set[Tuple[str, str]] = set()

    for i in range(num_alternatives):
        ref = primary if i == 0 else (alternatives[-1] if alternatives else primary)
        edges = ref.edges
        if len(edges) < 3:
            break

        s, e = len(edges) // 3, 2 * len(edges) // 3
        new_excl = {(edges[j].source, edges[j].target) for j in range(s, e + 1) if j < len(edges)}
        combined = all_excluded | new_excl

        alt = a_star_search(graph, start_id, goal_id, context, combined)
        if alt and alt.path != primary.path:
            if not any(a.path == alt.path for a in alternatives):
                alternatives.append(alt)
                all_excluded = combined

    return alternatives


# ── Main Routing Function ────────────────────────────────────────────


def compute_smart_route(
    graph: CityGraph,
    start_coords: List[float],
    end_coords: List[float],
    context: UserContext,
) -> dict:
    """Compute recommended route + alternatives with full explainability."""
    start_id = graph.find_nearest_node(start_coords[0], start_coords[1])
    end_id = graph.find_nearest_node(end_coords[0], end_coords[1])

    if not start_id or not end_id:
        return {"error": "Could not find nodes near the given coordinates"}
    if start_id == end_id:
        return {"error": "Start and end points are too close together"}

    weights = context.weights

    # Primary (safety-optimised)
    primary = a_star_search(graph, start_id, end_id, context)
    if not primary:
        return {
            "error": "No safe path found",
            "decision_reasoning": [
                "All routes contain critical risk segments",
                "Consider alternative transportation",
            ],
            "confidence_score": 0.0,
        }

    # Alternatives
    alternatives = find_alternative_routes(
        graph, start_id, end_id, context, num_alternatives=2
    )

    # Fastest (distance-only)
    zero_context = UserContext(
        user_type="solo", time_of_day="afternoon", weather_condition="clear"
    )
    zero_context.weather_severity = 0.0
    # Overwrite the safety calculation variables strictly for the fastest path
    # Actually, we need a way to make it zero. We will handle fastest path differently or construct a special context.
    # Instead, let's just make it zero.
    zero_w = RoutingWeights(0.0, 0.0, 0.0, 0.0)
    zero_context.weights = zero_w
    
    # We will compute fastest using standard A* without penalties. 
    # To do this safely, fastest_a_star_search should just use heuristics:
    fastest = a_star_search(graph, start_id, end_id, zero_context)

    # Assessments
    primary_assess = assess_route(primary.edges, context)
    alt_assess_pairs = [
        (assess_route(a.edges, context), f"Alternative {i+1}")
        for i, a in enumerate(alternatives)
    ]

    fastest_assess = None
    if fastest and fastest.path != primary.path:
        fastest_assess = assess_route(fastest.edges, context)
        if fastest_assess.average_risk > primary_assess.average_risk:
            alt_assess_pairs.append((fastest_assess, "Fastest Route"))

    reasoning = generate_route_reasoning(primary_assess, alt_assess_pairs, context)

    comparison = None
    if fastest_assess and fastest.path != primary.path:
        comparison = generate_comparison_text(primary_assess, fastest_assess)

    # Risk heatmap
    heatmap = []
    for nid, node in graph.nodes.items():
        edges = graph.get_neighbors(nid)
        if edges:
            avg_r = sum(
                0.4 * e.attributes.crime_index
                + 0.3 * (1 - e.attributes.lighting_level)
                + 0.3 * context.weather_severity
                for e in edges
            ) / len(edges)
        else:
            avg_r = 0
        heatmap.append({
            "lat": node.lat, "lng": node.lng,
            "risk": round(min(1.0, avg_r), 4),
            "area": node.area_name,
        })

    result = {
        "recommended_route": {
            **primary.to_dict(),
            "assessment": primary_assess.to_dict(),
        },
        "alternatives": [],
        "fastest_route": None,
        "decision_reasoning": reasoning,
        "risk_heatmap": heatmap,
        "confidence_score": primary_assess.confidence_score,
        "context": context.to_dict(),
        "comparison_card": comparison,
        "start_node": start_id,
        "end_node": end_id,
    }

    for i, alt in enumerate(alternatives):
        a_assess = assess_route(alt.edges, context)
        result["alternatives"].append({
            **alt.to_dict(),
            "assessment": a_assess.to_dict(),
            "label": f"Alternative {i + 1}",
        })

    if fastest and fastest.path != primary.path:
        result["fastest_route"] = {
            **fastest.to_dict(),
            "assessment": fastest_assess.to_dict(),
            "label": "Fastest Route",
        }

    return result
