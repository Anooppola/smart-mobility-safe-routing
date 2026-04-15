"""
AegisPath X — FastAPI Application
Context-Aware Personalized Safety Routing Engine
"""

import os
import time
import random
import mimetypes

mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from typing import List

from data_simulator import (
    generate_demo_city, generate_live_incidents,
    generate_weather_data, generate_crowd_density_data,
)
from context_engine import build_context, get_weight_explanation, compute_weights
from routing_engine import compute_smart_route

# ── App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="AegisPath X",
    description="Context-Aware Personalized Safety Routing Engine",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
_frontend = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(_frontend):
    # We must mount it AFTER defining API routes to avoid catching API requests,
    # but FastAPI processes mounts in order. It's actually fine if it's mounted last.
    pass

# City graph (initialised once)
city_graph = generate_demo_city()


# ── Request Models ───────────────────────────────────────────────────


class RouteRequest(BaseModel):
    start: List[float]
    end: List[float]
    user_type: str = "solo"
    time: str = "afternoon"
    weather: str = "clear"

    @field_validator("start", "end")
    @classmethod
    def validate_coords(cls, v):
        if len(v) != 2:
            raise ValueError("Coordinates must be [lat, lng]")
        lat, lng = v
        if not (-90 <= lat <= 90):
            raise ValueError(f"Latitude out of range: {lat}")
        if not (-180 <= lng <= 180):
            raise ValueError(f"Longitude out of range: {lng}")
        return v

    @field_validator("user_type")
    @classmethod
    def validate_user_type(cls, v):
        ok = ["solo", "female_traveler", "delivery_rider", "commuter"]
        if v not in ok:
            raise ValueError(f"user_type must be one of {ok}")
        return v

    @field_validator("time")
    @classmethod
    def validate_time(cls, v):
        ok = ["morning", "afternoon", "evening", "night", "late_night"]
        if v not in ok:
            raise ValueError(f"time must be one of {ok}")
        return v


class WeightsRequest(BaseModel):
    user_type: str = "solo"
    time: str = "afternoon"
    weather: str = "clear"


# ── Endpoints ────────────────────────────────────────────────────────



from live_context import get_ist_time_of_day, get_live_weather

@app.post("/smart-route")
async def smart_route(request: RouteRequest):
    """Main routing endpoint with explainable AI."""
    try:
        live_time = get_ist_time_of_day()
        live_weather = get_live_weather(request.start[0], request.start[1])
        
        ctx = build_context(request.user_type, live_time, live_weather["condition"])
        # We inject severity directly into the context object so safety_model can use it
        ctx.weather_severity = live_weather["severity"]
        
        result = compute_smart_route(city_graph, request.start, request.end, ctx)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result)
            
        result["weight_explanations"] = get_weight_explanation(ctx)
        result["live_context"] = {
            "time_of_day": live_time,
            "weather": live_weather["condition"],
            "severity": live_weather["severity"]
        }
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing failed: {e}")


@app.post("/compute-weights")
async def get_weights(request: WeightsRequest):
    # Dummy lat/lng for weight preview mapping
    live_time = get_ist_time_of_day()
    live_weather = get_live_weather(17.385, 78.4867) 
    ctx = build_context(request.user_type, live_time, live_weather["condition"])
    ctx.weather_severity = live_weather["severity"]
    return {
        "weights": ctx.weights.to_dict(),
        "explanations": get_weight_explanation(ctx),
        "context": ctx.to_dict(),
        "live_context": {
            "time_of_day": live_time,
            "weather": live_weather["condition"],
            "severity": live_weather["severity"]
        }
    }


@app.get("/live-incidents")
async def live_incidents():
    data = generate_live_incidents(city_graph, count=random.randint(3, 7))
    return {"incidents": data, "timestamp": time.time(), "total_active": len(data)}


@app.get("/weather")
async def weather():
    return generate_weather_data()


@app.get("/crowd-density")
async def crowd_density(time_of_day: str = "afternoon"):
    ok = ["morning", "afternoon", "evening", "night", "late_night"]
    if time_of_day not in ok:
        raise HTTPException(400, f"time_of_day must be one of {ok}")
    return {
        "densities": generate_crowd_density_data(city_graph, time_of_day),
        "time_of_day": time_of_day,
        "timestamp": time.time(),
    }


@app.get("/graph-data")
async def graph_data():
    return city_graph.to_dict()


@app.get("/demo-scenario")
async def demo_scenario():
    """
    CRITICAL demo: same origin/destination, three contexts.
    Shows how the route changes dynamically.
    """
    start = [17.413, 78.4547]
    end   = [17.365, 78.519]

    day_ctx   = build_context("solo",            "afternoon", "clear")
    night_ctx = build_context("solo",            "night",     "clear")
    fem_ctx   = build_context("female_traveler", "night",     "clear")

    day_r   = compute_smart_route(city_graph, start, end, day_ctx)
    night_r = compute_smart_route(city_graph, start, end, night_ctx)
    fem_r   = compute_smart_route(city_graph, start, end, fem_ctx)

    return {
        "scenario": "Same route, different contexts",
        "start": start, "end": end,
        "day_result": day_r,
        "night_result": night_r,
        "female_night_result": fem_r,
        "comparison": {
            "day_safety": day_r.get("recommended_route", {})
                              .get("assessment", {})
                              .get("overall_safety_rating", "N/A"),
            "night_safety": night_r.get("recommended_route", {})
                                   .get("assessment", {})
                                   .get("overall_safety_rating", "N/A"),
            "female_night_safety": fem_r.get("recommended_route", {})
                                       .get("assessment", {})
                                       .get("overall_safety_rating", "N/A"),
            "route_changed": (
                day_r.get("recommended_route", {}).get("path")
                != night_r.get("recommended_route", {}).get("path")
            ),
            "insight": (
                "The system dynamically re-routes based on context. "
                "At night, isolated and poorly lit segments are heavily "
                "penalized, causing route changes."
            ),
        },
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "AegisPath X",
        "version": "1.0.0",
        "graph_nodes": len(city_graph.nodes),
        "graph_edges": sum(len(e) for e in city_graph.edges.values()) // 2,
    }

from fastapi.responses import FileResponse

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(_frontend, "index.html"))

@app.get("/style.css")
async def serve_css():
    return FileResponse(os.path.join(_frontend, "style.css"), media_type="text/css")

@app.get("/app.js")
async def serve_js():
    return FileResponse(os.path.join(_frontend, "app.js"), media_type="application/javascript")
