# Step 2 — Minimal Event Driven Simulation

## Overview

In this tutorial we expand previous implementation and build a **minimal event-driven simulation model** for an **Emergency Medical Services (EMS)** system.  
It shows the basic logic of **dispatching ambulances to emergency calls** based on proximity and timing.

**Goal:**  
simulate a global “first come, first served” queue using events, and compute **response times** to emergency incidents.


## Scenario

Imagine a simplified city represented by a 2D grid.  
Ambulances are stationed at fixed coordinates, and emergency calls arrive over time at various locations.

The EMS system must:
1. Process each call in **chronological order**.
2. Assign the **nearest available vehicle** to the call.
3. Calculate and store the **response time** (how long it took to reach the scene).

## Code Components

### 1. `Vehicle` dataclass
Represents an ambulance or rapid response vehicle.

| Attribute | Type | Description |
|------------|------|-------------|
| `vid` | `int` | Unique vehicle ID |
| `kind` | `str` | `"A"` for ambulance or `"R"` for rapid response car |
| `loc` | `tuple[int,int]` | Current vehicle location |
| `busy` | `bool` | Indicates whether the vehicle is handling a call |

Each vehicle is free unless assigned to an incident.

### 2. `Event` class
Defines an event in the simulation timeline.

| Attribute | Description |
|------------|-------------|
| `time` | When the event occurs (timestamp) |
| `etype` | Type of event (`"CALL_ARRIVE"`) |
| `payload` | The associated `Call` object |

Events are **sorted by time** using a priority queue (`heapq`) so they occur in chronological order.



##  The Core Simulation Loop

This is the **heart** of the simulation.  
It processes emergency calls as time-ordered events and computes ambulance response times.

#### Steps:
1. **Initialization**: Load all call events into a heap queue (`evq`) by their `t_call` time.
2. **Event processing**:  
   - Pop the earliest event from the queue.  
   - For `"CALL_ARRIVE"` events:
     - Identify **idle vehicles** (not busy).  
     - Select the **nearest vehicle** by travel time (shortest ETA).  
     - Compute **response time** = dispatch delay + travel time.  
     - Record response time in `response_times` dictionary.
3. **Vehicle state update**:
   - Mark the vehicle as busy and instantly update its location to the call site.
   - Free it immediately afterward (simplified assumption).

4. **Return results**:  
   Returns a dictionary mapping `call_id → response_time (seconds)`.

#### Simplifications:
- Only `"CALL_ARRIVE"` events are handled.  
- No travel back to base or hospital transport.  
- Vehicles become instantly available again after each call.  
- Calls are ignored if no vehicles are free.
