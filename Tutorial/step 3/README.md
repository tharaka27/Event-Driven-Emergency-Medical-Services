# Step 3 - Minimal Ambulance Fleet Simulation with Survival Efficiency

## Overview

In this tutorial we calculate first metrics using our simulation model.

It models how ambulances respond to emergency calls, measures their effectiveness using a **patient survival metric**, and forms the foundation for more advanced EMS optimization.

**Goal:**  
Compute the **heterogeneous survival efficiency (ηₛ)** — a measure of system performance based on patient survival probability.


## Scenario

An **Emergency Medical Service (EMS)** operates several base stations, each housing one or more ambulances.  
When an emergency call occurs:
1. The system identifies **available vehicles**.
2. The **nearest free ambulance** is dispatched.
3. The response time is recorded.
4. The outcome contributes to the **overall survival efficiency** of the system.

If all ambulances are busy, the call is placed into a **waiting queue** (FIFO).  
Once the simulation finishes, we evaluate how well the current ambulance allocation performed.

## Code Components

### 1. `Call` — Emergency Incident
Represents a single emergency call.

| Field | Description |
|--------|-------------|
| `call_id` | Unique identifier for the call |
| `t_call` | Time of call arrival (seconds) |
| `dispatch_delay` | Time before an ambulance leaves the station |
| `scene_time` | Time spent at the scene (not used here) |
| `loc_scene` | Location of incident as grid coordinates `(row, col)` |
| `category` | Type of call: `"cardiac"`, `"catA"`, or `"catC"` |

---

### 2. `Station` — Ambulance Base
Represents a fixed ambulance station.

| Field | Description |
|--------|-------------|
| `station_id` | Station identifier |
| `grid_rc` | Grid coordinates of the station `(row, col)` |

### 3. `Event` — Simulation Event

| Field | Description |
|--------|-------------|
| `time` | when the event occurs |
| `etype` | event type ("CALL" in this simplified version) |
| `payload` | the Call object linked to the event |

Events are processed in chronological order using Python’s built-in heapq priority queue.


## Metrics - Survival Functions

These functions estimate the probability of patient survival based on ambulance response time.

a. Cardiac Arrest (sc)


$s_c = \frac{1}{1 + e^{(-0.26 + 0.139T_r)}}$

where (T_r) = response time in minutes.
This logistic model reflects how survival probability rapidly drops with longer response times.

b. Life-Threatening Category A (sa)

s_a = 1 if T_r ≤ 8 minutes,  
s_a = 0 otherwise$



## Simulation — The Core Engine

Handles all dispatch logic, event management, and metric computation.

### Attributes

| Field | Description |
|--------|-------------|
| `calls` | List of all call objects |
| `stations` | Dictionary of base stations. |
| `vehicles` | Dictionary of all ambulances/response cars|
| `evq` | Priority queue of future events |
| `wait_q` | FIFO queue for waiting calls |
| `response` | Stores response times for completed calls |

### Key Methods

#### run(t_start, t_end)
1. Loads calls within the specified time range.
2. Processes all "CALL" events.
3. Returns computed KPIs (ηₛ, number of cardiac calls, number of Category A calls).

#### _handle_call(c: Call)
1. Selects the nearest idle vehicle.
2. Calculates travel time to the scene.
3. Records response time (dispatch delay + travel time).
4. If no vehicle is available, adds the call to wait_q.

#### _kpis()

Computes the heterogeneous survival efficiency (ηₛ):


$η_s = \frac{2 \sum s_c + \sum s_a}{2γ + δ}$

where:
1. ( γ ) = number of cardiac calls,
2. ( δ ) = number of Category A calls,
3. ( s_c, s_a ) = survival scores.

This performance metric rewards fast responses and penalizes delays.