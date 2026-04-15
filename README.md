# smart-mobility-safe-routing
# 🚦 AegisPath X – Context-Aware Safety Routing System

AegisPath X is an AI-powered smart mobility solution that prioritizes **user safety over speed** by dynamically analyzing environmental and contextual risks in real-time.

Unlike traditional navigation systems that focus only on shortest or fastest routes, AegisPath X introduces **Antigravity Routing**, where unsafe zones repel route selection, ensuring safer travel decisions.

---

## 🧠 Problem Statement

Urban commuters often face:
- Unsafe routes at night 🌙
- Poorly lit roads 💡
- High crime zones 🚨
- Weather-related risks 🌧️

Existing navigation systems do not consider **personal safety**.

👉 AegisPath X solves this by recommending the **safest route instead of the fastest route**.

---

## 🚀 Key Features

### 🔹 Antigravity Routing Engine
- Modified A* algorithm
- Cost function:
  
  `Cost = Distance × (1 + Safety_Penalty)`

- Unsafe areas act as **repulsive forces**

---

### 🔹 Context-Aware Intelligence
Routes adapt dynamically based on:
- 🕒 Time (Auto-detected IST)
- 🌦️ Weather (Live API)
- 👤 User type (e.g., solo traveler)
- 🌍 Environmental conditions

---

### 🔹 Real-Time Safety Analysis
- Crime risk estimation
- Lighting conditions
- Weather severity
- Isolation factor

---

### 🔹 Explainable AI (XAI)
- Shows **why routes are rejected**
- Highlights unsafe segments
- Provides human-readable explanations:

> “This route is faster but passes through a poorly lit high-risk area.”

---

### 🔹 Dynamic Route Visualization
- 🟢 Safest route (selected)
- 🟡 Balanced route
- 🔴 Fast but risky route
- ➖ Dotted lines = **Rejected unsafe paths**

---

### 🔹 Simulated Live Intelligence Feed
- Accident alerts
- Crowd density signals
- Environmental updates

---

### 🔹 Risk Heatmap
- Visual representation of dangerous zones
- Enhances situational awareness

---

## 🏗️ Tech Stack

### Backend:
- Python
- FastAPI
- A* Pathfinding Algorithm

### Frontend:
- HTML, CSS, JavaScript
- Map Visualization (Leaflet / Mapbox)

### APIs:
- Weather API (real-time conditions)
- System clock (IST time detection)

---

## ⚙️ Project Structure

AI-powered safest route finder using antigravity routing (risk-aware pathfinding with A*).
