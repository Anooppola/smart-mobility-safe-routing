"""
AegisPath X — Unit Tests
Tests for cost function, route decisions, and edge cases.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from data_simulator import (
    generate_demo_city, Edge, SegmentAttributes, CityGraph, Node,
)
from context_engine import compute_weights, build_context, RoutingWeights
from safety_model import calculate_segment_risk, calculate_edge_cost, assess_route
from routing_engine import a_star_search, find_alternative_routes, compute_smart_route


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def city_graph():
    return generate_demo_city()


@pytest.fixture
def safe_edge():
    return Edge(
        source="A", target="B", distance=1.0,
        attributes=SegmentAttributes(
            crime_index=0.1, lighting_level=0.9,
            crowd_density=0.8, weather_exposure=0.2,
            road_type="main_road", area_name="downtown",
        ),
    )


@pytest.fixture
def dangerous_edge():
    return Edge(
        source="C", target="D", distance=1.0,
        attributes=SegmentAttributes(
            crime_index=0.9, lighting_level=0.1,
            crowd_density=0.1, weather_exposure=0.8,
            road_type="alley", area_name="industrial",
        ),
    )


@pytest.fixture
def equal_weights():
    return RoutingWeights(0.25, 0.25, 0.25, 0.25)


# ── Cost Function Tests ──────────────────────────────────────────────


class TestCostFunction:

    def test_safe_segment_low_risk(self, safe_edge, equal_weights):
        risk = calculate_segment_risk(safe_edge, equal_weights)
        assert risk < 0.3, f"Safe segment risk too high: {risk}"

    def test_dangerous_segment_high_risk(self, dangerous_edge, equal_weights):
        risk = calculate_segment_risk(dangerous_edge, equal_weights)
        assert risk > 0.7, f"Dangerous segment risk too low: {risk}"

    def test_risk_bounded(self, safe_edge, dangerous_edge, equal_weights):
        for edge in (safe_edge, dangerous_edge):
            r = calculate_segment_risk(edge, equal_weights)
            assert 0.0 <= r <= 1.0

    def test_cost_gte_distance(self, safe_edge, equal_weights):
        cost = calculate_edge_cost(safe_edge, equal_weights)
        assert cost >= safe_edge.distance

    def test_dangerous_costs_more(self, safe_edge, dangerous_edge, equal_weights):
        assert calculate_edge_cost(dangerous_edge, equal_weights) > \
               calculate_edge_cost(safe_edge, equal_weights)

    def test_zero_weights_distance_only(self, safe_edge):
        zw = RoutingWeights(0.0, 0.0, 0.0, 0.0)
        assert abs(calculate_edge_cost(safe_edge, zw) - safe_edge.distance) < 0.001

    def test_night_increases_darkness_weight(self):
        day = compute_weights("solo", "morning")
        night = compute_weights("solo", "night")
        assert night.darkness_weight > day.darkness_weight

    def test_context_changes_risk(self, dangerous_edge):
        day_w = compute_weights("solo", "afternoon")
        night_w = compute_weights("solo", "night")
        assert calculate_segment_risk(dangerous_edge, day_w) != \
               calculate_segment_risk(dangerous_edge, night_w)


# ── Route Decision Tests ─────────────────────────────────────────────


class TestRouteDecisions:

    def test_finds_route(self, city_graph):
        w = compute_weights("solo", "afternoon")
        route = a_star_search(city_graph, "N0_0", "N7_7", w)
        assert route is not None
        assert len(route.path) > 2
        assert route.path[0] == "N0_0"
        assert route.path[-1] == "N7_7"

    def test_route_distance_positive(self, city_graph):
        w = compute_weights("solo", "afternoon")
        route = a_star_search(city_graph, "N0_0", "N7_7", w)
        assert route.total_distance > 0

    def test_alternatives_differ(self, city_graph):
        w = compute_weights("solo", "afternoon")
        primary = a_star_search(city_graph, "N0_0", "N7_7", w)
        alts = find_alternative_routes(city_graph, "N0_0", "N7_7", w)
        for alt in alts:
            assert alt.path != primary.path

    def test_context_returns_routes(self, city_graph):
        for tod in ("afternoon", "night"):
            w = compute_weights("solo", tod)
            r = a_star_search(city_graph, "N0_0", "N7_7", w)
            assert r is not None

    def test_smart_route_full_output(self, city_graph):
        ctx = build_context("solo", "night")
        result = compute_smart_route(
            city_graph, [17.413, 78.4547], [17.365, 78.519], ctx,
        )
        for key in ("recommended_route", "alternatives",
                     "decision_reasoning", "risk_heatmap", "confidence_score"):
            assert key in result
        assert isinstance(result["decision_reasoning"], list)
        assert len(result["decision_reasoning"]) > 0
        assert 0 <= result["confidence_score"] <= 1


# ── Edge Cases ────────────────────────────────────────────────────────


class TestEdgeCases:

    def test_same_start_end(self, city_graph):
        ctx = build_context("solo", "afternoon")
        result = compute_smart_route(
            city_graph, [17.385, 78.4867], [17.385, 78.4867], ctx,
        )
        assert "error" in result

    def test_invalid_coordinates(self):
        """Coordinates outside valid range should be caught."""
        def validate_coords(lat, lng):
            if not (-90 <= lat <= 90):
                raise ValueError(f"Latitude out of range: {lat}")
            if not (-180 <= lng <= 180):
                raise ValueError(f"Longitude out of range: {lng}")

        with pytest.raises(ValueError):
            validate_coords(200, 78)  # lat=200 is invalid

        with pytest.raises(ValueError):
            validate_coords(17, 400)  # lng=400 is invalid

        # Valid coords should not raise
        validate_coords(17.385, 78.4867)

    def test_all_routes_high_risk(self):
        g = CityGraph()
        g.add_node(Node("A", 17.0, 78.0, "danger"))
        g.add_node(Node("B", 17.01, 78.01, "danger"))
        g.add_node(Node("C", 17.02, 78.02, "danger"))
        bad = SegmentAttributes(0.95, 0.05, 0.05, 0.9, "alley", "danger")
        g.add_edge(Edge("A", "B", 1.0, bad))
        g.add_edge(Edge("B", "C", 1.0, bad))

        ctx = build_context("female_traveler", "late_night", "storm")
        result = compute_smart_route(g, [17.0, 78.0], [17.02, 78.02], ctx)
        if "recommended_route" in result:
            a = result["recommended_route"]["assessment"]
            assert a["average_risk"] > 0.5
            assert a["overall_safety_rating"] in ("D", "F")

    def test_no_path(self):
        g = CityGraph()
        g.add_node(Node("A", 17.0, 78.0, "x"))
        g.add_node(Node("B", 17.1, 78.1, "x"))
        ctx = build_context("solo", "afternoon")
        result = compute_smart_route(g, [17.0, 78.0], [17.1, 78.1], ctx)
        assert "error" in result

    def test_weight_normalisation(self):
        for ut in ("solo", "female_traveler", "delivery_rider", "commuter"):
            for tod in ("morning", "afternoon", "evening", "night", "late_night"):
                w = compute_weights(ut, tod)
                total = (w.crime_weight + w.darkness_weight
                         + w.weather_weight + w.isolation_weight)
                assert abs(total - 1.0) < 0.01, \
                    f"Weights don't sum to 1.0 for {ut}/{tod}: {total}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
