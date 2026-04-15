/* ═══════════════════════════════════════════════════════════════════
   AegisPath X — Frontend Application
   ═══════════════════════════════════════════════════════════════════ */

const API = "http://localhost:8001";

// ── State ──────────────────────────────────────────────────────────
let map, heatLayer, routeLayers = [], incidentMarkers = [];
let startMarker = null, endMarker = null;
let startCoords = null, endCoords = null;
let clickMode = "start"; // "start" | "end"
let riskChart = null;
let showHeatmap = true;
let showCompare = false;
let incidentInterval = null;

// ── Initialise ─────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    initMap();
    bindControls();
    fetchIncidents();
    incidentInterval = setInterval(fetchIncidents, 8000);
    fetchInitialWeights();
});

// ── Map Setup ──────────────────────────────────────────────────────
function initMap() {
    map = L.map("map", {
        center: [17.385, 78.4867],
        zoom: 13,
        zoomControl: true,
    });

    // Dark tile layer
    L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
            subdomains: "abcd",
            maxZoom: 19,
        }
    ).addTo(map);

    // Click to set start/end
    map.on("click", (e) => {
        const { lat, lng } = e.latlng;
        if (clickMode === "start") {
            setStartPoint(lat, lng);
            clickMode = "end";
        } else {
            setEndPoint(lat, lng);
            clickMode = "start";
        }
    });

    // Load heatmap
    fetchHeatmap();
}

function setStartPoint(lat, lng) {
    startCoords = [lat, lng];
    if (startMarker) map.removeLayer(startMarker);
    startMarker = L.circleMarker([lat, lng], {
        radius: 8, color: "#10B981", fillColor: "#10B981",
        fillOpacity: 1, weight: 3, className: "start-marker",
    }).addTo(map).bindTooltip("START", { permanent: true, direction: "top", offset: [0, -12] });
}

function setEndPoint(lat, lng) {
    endCoords = [lat, lng];
    if (endMarker) map.removeLayer(endMarker);
    endMarker = L.circleMarker([lat, lng], {
        radius: 8, color: "#EF4444", fillColor: "#EF4444",
        fillOpacity: 1, weight: 3, className: "end-marker",
    }).addTo(map).bindTooltip("END", { permanent: true, direction: "top", offset: [0, -12] });
}

// ── Heatmap ────────────────────────────────────────────────────────
async function fetchHeatmap() {
    try {
        const res = await fetch(`${API}/graph-data`);
        const data = await res.json();
        const weights = getCurrentWeights();

        const points = Object.values(data.nodes).map((n) => {
            // approximate risk from area
            const risk = estimateNodeRisk(n.area_name, weights);
            return [n.lat, n.lng, risk];
        });

        if (heatLayer) map.removeLayer(heatLayer);
        heatLayer = L.heatLayer(points, {
            radius: 30, blur: 20, maxZoom: 17,
            gradient: {
                0.0: "#10B981",
                0.3: "#22D3EE",
                0.5: "#F59E0B",
                0.7: "#F97316",
                1.0: "#EF4444",
            },
        }).addTo(map);

        if (!showHeatmap && heatLayer) map.removeLayer(heatLayer);
    } catch (err) {
        console.error("Heatmap fetch failed:", err);
    }
}

function estimateNodeRisk(area, weights) {
    const profiles = {
        downtown: { crime: 0.3, light: 0.9, crowd: 0.8, weather: 0.3 },
        tech_park: { crime: 0.1, light: 0.95, crowd: 0.7, weather: 0.2 },
        old_market: { crime: 0.5, light: 0.6, crowd: 0.9, weather: 0.5 },
        industrial: { crime: 0.7, light: 0.3, crowd: 0.2, weather: 0.8 },
        residential_north: { crime: 0.2, light: 0.7, crowd: 0.5, weather: 0.4 },
        residential_south: { crime: 0.3, light: 0.6, crowd: 0.4, weather: 0.4 },
        park_district: { crime: 0.4, light: 0.4, crowd: 0.3, weather: 0.9 },
        highway_corridor: { crime: 0.6, light: 0.5, crowd: 0.1, weather: 0.7 },
        university: { crime: 0.15, light: 0.85, crowd: 0.75, weather: 0.3 },
        suburb_east: { crime: 0.25, light: 0.5, crowd: 0.3, weather: 0.5 },
    };
    const p = profiles[area] || profiles.downtown;
    return (
        (weights.crime || 0.25) * p.crime +
        (weights.darkness || 0.25) * (1 - p.light) +
        (weights.weather || 0.25) * p.weather +
        (weights.isolation || 0.25) * (1 - p.crowd)
    );
}

// ── Controls ───────────────────────────────────────────────────────
function bindControls() {
    document.getElementById("btnFindRoute").addEventListener("click", findRoute);
    document.getElementById("btnRunDemo").addEventListener("click", runDemo);
    document.getElementById("btnHeatmap").addEventListener("click", toggleHeatmap);
    document.getElementById("btnRouteCompare").addEventListener("click", toggleCompare);

    // Update weights on context change
    document.getElementById("userType").addEventListener("change", () => {
        fetchInitialWeights();
        fetchHeatmap();
    });
}

function toggleHeatmap() {
    showHeatmap = !showHeatmap;
    const btn = document.getElementById("btnHeatmap");
    btn.classList.toggle("active", showHeatmap);
    if (showHeatmap && heatLayer) heatLayer.addTo(map);
    else if (heatLayer) map.removeLayer(heatLayer);
}

function toggleCompare() {
    showCompare = !showCompare;
    document.getElementById("btnRouteCompare").classList.toggle("active", showCompare);
    // Re-render routes if available
    if (window._lastRouteData) renderRoutes(window._lastRouteData);
}

// ── Weight Display ─────────────────────────────────────────────────
async function fetchInitialWeights() {
    try {
        const body = {
            user_type: document.getElementById("userType").value,
        };
        const res = await fetch(`${API}/compute-weights`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const data = await res.json();
        updateWeightsFromResponse(data);
        updateLiveContextUI(data.live_context);
    } catch (err) {
        console.error("Failed to fetch starting weights", err);
    }
}

function updateLiveContextUI(liveCtx, isDemo = false) {
    if (!liveCtx) return;
    const tSpan = document.getElementById("autoTimeDisplay");
    const wSpan = document.getElementById("autoWeatherDisplay");
    if (tSpan) {
        // Format e.g., 'afternoon' to 'Afternoon'
        const tStr = liveCtx.time_of_day.replace(/_/g, " ");
        tSpan.textContent = tStr.charAt(0).toUpperCase() + tStr.slice(1) + (isDemo ? " (Demo Simulation)" : " (Auto-detected)");
    }
    if (wSpan) {
        const wStr = liveCtx.weather.replace(/_/g, " ");
        wSpan.textContent = wStr.charAt(0).toUpperCase() + wStr.slice(1) + (isDemo ? " (Demo Simulation)" : " (Live)");
    }
}

function getCurrentWeights() {
    // Return dummy since backend calculates it
    return { crime: 0.25, darkness: 0.25, weather: 0.25, isolation: 0.25 };
}

function animateWeight(barId, valId, value) {
    const bar = document.getElementById(barId);
    const val = document.getElementById(valId);
    bar.style.width = `${Math.round(value * 100)}%`;
    val.textContent = `${Math.round(value * 100)}%`;
}

// ── Find Route ─────────────────────────────────────────────────────
async function findRoute() {
    if (!startCoords || !endCoords) {
        alert("Click on the map to set START and END points first.");
        return;
    }
    showLoading(true);
    try {
        const body = {
            start: startCoords,
            end: endCoords,
            user_type: document.getElementById("userType").value,
        };
        const res = await fetch(`${API}/smart-route`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail?.error || err.detail || "Route computation failed");
        }
        const data = await res.json();
        window._lastRouteData = data;
        renderRoutes(data);
        renderReasoning(data);
        renderTimeline(data);
        renderStats(data);
        renderSmartCard(data);
        updateWeightsFromResponse(data);
        updateLiveContextUI(data.live_context);
        renderHeatmapFromData(data);
    } catch (err) {
        alert("Error: " + err.message);
        console.error(err);
    } finally {
        showLoading(false);
    }
}

// ── Demo Scenario ──────────────────────────────────────────────────
async function runDemo() {
    showLoading(true);
    try {
        const res = await fetch(`${API}/demo-scenario`);
        const data = await res.json();

        // Set markers
        setStartPoint(data.start[0], data.start[1]);
        setEndPoint(data.end[0], data.end[1]);
        map.fitBounds([data.start, data.end], { padding: [60, 60] });

        // Show day result first
        document.getElementById("userType").value = "solo";
        
        // We simulate what the old weights would have been for demo purposes, 
        // since the backend demo-scenario endpoint already returns pre-computed mock routes!
        updateLiveContextUI({ time_of_day: "afternoon", weather: "clear" }, true);

        window._lastRouteData = data.day_result;
        renderRoutes(data.day_result);
        renderReasoning(data.day_result);
        renderTimeline(data.day_result);
        renderStats(data.day_result);
        renderSmartCard(data.day_result);
        renderHeatmapFromData(data.day_result);

        showLoading(false);

        // After 4s, switch to night
        setTimeout(() => {
            showLoading(true);
            updateLiveContextUI({ time_of_day: "night", weather: "clear" }, true);

            setTimeout(() => {
                window._lastRouteData = data.night_result;
                renderRoutes(data.night_result);
                renderReasoning(data.night_result);
                renderTimeline(data.night_result);
                renderStats(data.night_result);
                renderSmartCard(data.night_result);
                renderHeatmapFromData(data.night_result);

                // Add demo comparison reasoning
                const list = document.getElementById("reasoningList");
                const item = document.createElement("div");
                item.className = "reasoning-item context";
                item.textContent = `🔄 CONTEXT SWITCH: Route changed from DAY → NIGHT. ` +
                    `Day safety: ${data.comparison.day_safety}, ` +
                    `Night safety: ${data.comparison.night_safety}. ` +
                    data.comparison.insight;
                list.prepend(item);

                showLoading(false);
            }, 800);
        }, 4000);
    } catch (err) {
        alert("Demo failed: " + err.message);
        showLoading(false);
    }
}

// ── Render Routes on Map ───────────────────────────────────────────
function renderRoutes(data) {
    // Clear old routes
    routeLayers.forEach((l) => map.removeLayer(l));
    routeLayers = [];

    const rec = data.recommended_route;
    if (!rec) return;

    // Draw alternatives (dimmed)
    if (showCompare && data.alternatives) {
        data.alternatives.forEach((alt, i) => {
            const coords = alt.coordinates.map((c) => [c.lat, c.lng]);
            const line = L.polyline(coords, {
                color: i === 0 ? "#F59E0B" : "#EC4899",
                weight: 4, opacity: 0.45,
                dashArray: "8 6",
            }).addTo(map);
            line.bindTooltip(`Alt ${i + 1}: ${alt.assessment.overall_safety_rating} (${alt.total_distance.toFixed(1)} km)`);
            routeLayers.push(line);
        });
    }

    // Draw fastest (if different, dimmed red)
    if (showCompare && data.fastest_route) {
        const coords = data.fastest_route.coordinates.map((c) => [c.lat, c.lng]);
        const line = L.polyline(coords, {
            color: "#EF4444", weight: 4, opacity: 0.35,
            dashArray: "4 8",
        }).addTo(map);
        line.bindTooltip(`Fastest: ${data.fastest_route.assessment.overall_safety_rating} (${data.fastest_route.total_distance.toFixed(1)} km)`);
        routeLayers.push(line);
    }

    // Draw recommended route (bright)
    const recCoords = rec.coordinates.map((c) => [c.lat, c.lng]);

    // Glow effect
    const glow = L.polyline(recCoords, {
        color: "#00F0FF", weight: 10, opacity: 0.2,
    }).addTo(map);
    routeLayers.push(glow);

    // Coloured segments based on risk
    const segments = rec.assessment.segment_risks;
    for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        const from = rec.coordinates[i];
        const to = rec.coordinates[i + 1];
        if (!from || !to) continue;

        const color = riskColor(seg.risk_score);
        const segLine = L.polyline([[from.lat, from.lng], [to.lat, to.lng]], {
            color, weight: 5, opacity: 0.9,
        }).addTo(map);
        segLine.bindTooltip(
            `<b>${seg.area_name}</b><br>Risk: ${(seg.risk_score * 100).toFixed(0)}% (${seg.risk_level})<br>${seg.contributing_factors.slice(0, 2).join("<br>")}`,
            { sticky: true }
        );
        routeLayers.push(segLine);
    }

    // Danger zone markers
    if (rec.assessment.danger_zones) {
        rec.assessment.danger_zones.forEach((dz) => {
            // Place marker roughly at the midpoint segment
            const midIdx = Math.min(
                Math.floor((dz.start_km / rec.total_distance) * rec.coordinates.length),
                rec.coordinates.length - 1
            );
            const c = rec.coordinates[midIdx];
            if (c) {
                const marker = L.circleMarker([c.lat, c.lng], {
                    radius: 10, color: "#EF4444", fillColor: "#EF4444",
                    fillOpacity: 0.3, weight: 2,
                }).addTo(map);
                marker.bindTooltip(`⚠️ Danger Zone<br>${dz.description}`);
                routeLayers.push(marker);
            }
        });
    }

    // Fit bounds
    map.fitBounds(recCoords, { padding: [50, 50] });
}

function riskColor(score) {
    if (score < 0.25) return "#10B981";
    if (score < 0.50) return "#F59E0B";
    if (score < 0.75) return "#F97316";
    return "#EF4444";
}

// ── Render Reasoning ───────────────────────────────────────────────
function renderReasoning(data) {
    const list = document.getElementById("reasoningList");
    list.innerHTML = "";

    if (!data.decision_reasoning) return;

    data.decision_reasoning.forEach((r) => {
        const item = document.createElement("div");
        item.className = "reasoning-item";
        if (r.startsWith("✅")) item.className += " selected";
        else if (r.startsWith("❌")) item.className += " rejected";
        else if (r.startsWith("🌙") || r.startsWith("🛡") || r.startsWith("👤") || r.startsWith("🌧")) item.className += " context";
        else if (r.startsWith("📊")) item.className += " weight";
        else item.className += " info";
        item.textContent = r;
        list.appendChild(item);
    });

    // Add weight explanations
    if (data.weight_explanations) {
        data.weight_explanations.forEach((w) => {
            const item = document.createElement("div");
            item.className = "reasoning-item weight";
            item.textContent = w;
            list.appendChild(item);
        });
    }
}

// ── Risk Timeline Chart ────────────────────────────────────────────
function renderTimeline(data) {
    const section = document.getElementById("timelineSection");
    section.classList.remove("hidden");

    const segments = data.recommended_route?.assessment?.segment_risks;
    if (!segments || segments.length === 0) {
        section.classList.add("hidden");
        return;
    }

    const labels = segments.map((s) => `${s.cumulative_distance.toFixed(1)} km`);
    const risks = segments.map((s) => (1 - s.risk_score) * 100); // safety %
    const bgColors = segments.map((s) => {
        if (s.risk_score < 0.25) return "rgba(16,185,129,0.6)";
        if (s.risk_score < 0.50) return "rgba(245,158,11,0.6)";
        if (s.risk_score < 0.75) return "rgba(249,115,22,0.6)";
        return "rgba(239,68,68,0.6)";
    });
    const borderColors = segments.map((s) => {
        if (s.risk_score < 0.25) return "#10B981";
        if (s.risk_score < 0.50) return "#F59E0B";
        if (s.risk_score < 0.75) return "#F97316";
        return "#EF4444";
    });

    const ctx = document.getElementById("riskTimelineChart").getContext("2d");
    if (riskChart) riskChart.destroy();

    riskChart = new Chart(ctx, {
        type: "line",
        data: {
            labels,
            datasets: [
                {
                    label: "Safety Score (%)",
                    data: risks,
                    borderColor: "#00F0FF",
                    backgroundColor: "rgba(0,240,255,0.08)",
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 5,
                    pointHoverRadius: 8,
                    pointBackgroundColor: borderColors,
                    pointBorderColor: borderColors,
                    pointBorderWidth: 2,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: "index" },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "#151d2e",
                    titleColor: "#F1F5F9",
                    bodyColor: "#94A3B8",
                    borderColor: "rgba(0,240,255,0.3)",
                    borderWidth: 1,
                    padding: 12,
                    callbacks: {
                        afterBody: function (ctx) {
                            const idx = ctx[0].dataIndex;
                            const seg = segments[idx];
                            return [
                                `Risk: ${(seg.risk_score * 100).toFixed(0)}% (${seg.risk_level})`,
                                `Area: ${seg.area_name}`,
                                ...seg.contributing_factors.slice(0, 2),
                            ];
                        },
                    },
                },
            },
            scales: {
                x: {
                    title: { display: true, text: "Distance along route", color: "#64748B", font: { size: 11 } },
                    ticks: { color: "#64748B", font: { size: 10 } },
                    grid: { color: "rgba(148,163,184,0.08)" },
                },
                y: {
                    title: { display: true, text: "Safety Score (%)", color: "#64748B", font: { size: 11 } },
                    min: 0, max: 100,
                    ticks: { color: "#64748B", font: { size: 10 }, stepSize: 25 },
                    grid: { color: "rgba(148,163,184,0.08)" },
                },
            },
        },
    });
}

// ── Stats ──────────────────────────────────────────────────────────
function renderStats(data) {
    const bar = document.getElementById("statsBar");
    bar.classList.remove("hidden");

    const a = data.recommended_route?.assessment;
    if (!a) return;

    setStatValue("statDistance", `${a.total_distance.toFixed(1)} km`);

    const ratingEl = document.querySelector("#statSafety .stat-value");
    ratingEl.textContent = a.overall_safety_rating;
    ratingEl.className = `stat-value rating-${a.overall_safety_rating}`;

    setStatValue("statRisk", `${(a.average_risk * 100).toFixed(0)}%`);
    setStatValue("statConfidence", `${(a.confidence_score * 100).toFixed(0)}%`);
    setStatValue("statDanger", `${a.danger_zones.length}`);
}

function setStatValue(id, text) {
    document.querySelector(`#${id} .stat-value`).textContent = text;
}

// ── Smart Card ─────────────────────────────────────────────────────
function renderSmartCard(data) {
    const card = document.getElementById("smartCard");
    const body = document.getElementById("smartCardBody");

    if (!data.comparison_card) {
        card.classList.add("hidden");
        return;
    }

    const c = data.comparison_card;
    body.innerHTML = `
        <div style="margin-bottom:6px">
            <span class="highlight">⏱️ ${c.time_difference}</span> but
            <span class="highlight">${c.safety_improvement}</span>
        </div>
        ${c.avoided_segments > 0
            ? `<div><span class="warn">🚫 Avoids ${c.avoided_segments} high-risk segment${c.avoided_segments > 1 ? "s" : ""}</span></div>`
            : ""
        }
        <div style="margin-top:8px;padding-top:8px;border-top:1px solid rgba(148,163,184,0.12);font-size:.72rem">
            ${c.summary}
        </div>
    `;
    card.classList.remove("hidden");
}

// ── Update Weights from Response ───────────────────────────────────
function updateWeightsFromResponse(data) {
    if (data.context?.weights) {
        const w = data.context.weights;
        animateWeight("wCrime", "wCrimeVal", w.crime_weight);
        animateWeight("wDarkness", "wDarknessVal", w.darkness_weight);
        animateWeight("wWeather", "wWeatherVal", w.weather_weight);
        animateWeight("wIsolation", "wIsolationVal", w.isolation_weight);
    }
}

// ── Heatmap from Route Data ────────────────────────────────────────
function renderHeatmapFromData(data) {
    if (!data.risk_heatmap) return;
    const points = data.risk_heatmap.map((p) => [p.lat, p.lng, p.risk]);
    if (heatLayer) map.removeLayer(heatLayer);
    heatLayer = L.heatLayer(points, {
        radius: 30, blur: 20, maxZoom: 17,
        gradient: {
            0.0: "#10B981",
            0.3: "#22D3EE",
            0.5: "#F59E0B",
            0.7: "#F97316",
            1.0: "#EF4444",
        },
    });
    if (showHeatmap) heatLayer.addTo(map);
}

// ── Incidents ──────────────────────────────────────────────────────
async function fetchIncidents() {
    try {
        const res = await fetch(`${API}/live-incidents`);
        const data = await res.json();
        renderIncidents(data.incidents);
    } catch (err) {
        // silent — system may not be running
    }
}

function renderIncidents(incidents) {
    const list = document.getElementById("incidentList");
    const badge = document.getElementById("incidentCount");
    list.innerHTML = "";
    badge.textContent = incidents.length;

    // Remove old markers
    incidentMarkers.forEach((m) => map.removeLayer(m));
    incidentMarkers = [];

    incidents.forEach((inc) => {
        // List item
        const item = document.createElement("div");
        item.className = "incident-item";
        item.innerHTML = `
            <span class="incident-dot ${inc.severity}"></span>
            <span class="incident-text">${inc.type.replace(/_/g, " ")} — ${inc.impact}</span>
            <span class="incident-area">${inc.area.replace(/_/g, " ")}</span>
        `;
        list.appendChild(item);

        // Map marker
        const color = inc.severity === "high" ? "#EF4444" : inc.severity === "medium" ? "#F59E0B" : "#10B981";
        const marker = L.circleMarker([inc.lat, inc.lng], {
            radius: 6, color, fillColor: color,
            fillOpacity: 0.5, weight: 2,
        }).addTo(map).bindTooltip(
            `<b>${inc.type.replace(/_/g, " ")}</b><br>${inc.impact}<br><i>${inc.area.replace(/_/g, " ")}</i>`
        );
        incidentMarkers.push(marker);
    });
}

// ── Loading ────────────────────────────────────────────────────────
function showLoading(show) {
    document.getElementById("loadingOverlay").classList.toggle("hidden", !show);
}
