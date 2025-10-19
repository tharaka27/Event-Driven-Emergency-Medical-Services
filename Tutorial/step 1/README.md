### Step 1 — Minimal Simulation

**Goal:**  
In this very first implementation let's create a very simple implemtnation with capability to compute a single ambulance’s response time for one emergency call, assuming constant travel speed.

**Features**
- One ambulance located at `(10, 10)`
- One call nearby at `(11, 10)`
- Constant speed (e.g., 45 km/h)
- Manhattan distance model  
- Response time = dispatch delay + travel time

**Assumptions**
- Flat 2-D grid
- Constant travel speed
- No hospital transport or queuing delays

## Code Components

### 1. `Call` dataclass
Represents an emergency incident.

| Attribute | Description |
|------------|-------------|
| `call_id` | Unique identifier |
| `t_call` | Time the call arrives (seconds) |
| `dispatch_delay` | Time taken to dispatch an ambulance |
| `loc_scene` | Grid coordinates (row, col) of the incident |

### 2. `Travel` class
Encapsulates basic distance and travel-time calculations.

- **Distance model:** Manhattan distance  
  (i.e., grid-based “city block” distance)
- **Travel time:**  
  Travel Time (sec) = Distance (km) / Speed (km/h) * 3600