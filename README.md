# EMS Simulation & GA Optimization — Minimal Framework

A compact, end-to-end framework to **simulate** emergency ambulance operations and **optimize** fleet allocation and base locations with a **Genetic Algorithm (GA)**.

- **Simulation core**: event-driven EMS model (calls, dispatch, scene/hospital flow, vehicle movement)
- **Optimizer**: GA that encodes station positions, fleet mix, and per-vehicle assignment
- **Example**: tiny trace + grid to demonstrate the full pipeline

---

## 📁 Files

- **`ems_core.py`**
  - Data models: `Call`, `Station`, `Vehicle`
  - Travel: `TravelTimeModel` (grid distance, time-of-week speeds optional)
  - Events: `CALL_ARRIVE`, `SCENE_DEPART`, `JOB_COMPLETE`, `LOC_UPDATE`
  - Simulator: dispatches vehicles, tracks locations, computes KPIs
  - KPI: heterogeneous survival efficiency `eta_s`
  - Helper: `build_vehicles_from_allocation(...)`

- **`ga_opt.py`**
  - `GAOptimizer` with population init (mirrored), tournament selection, uniform+blend crossover, mutation, elitism
  - Chromosome: `[ movable station (r,c) genes | fleet-mix gene (optional) | vehicle→station genes ]`
  - Fitness: runs `Simulation` and returns `eta_s`
  - `GAConfig` for tunables

- **`example_run.py`**
  - Builds a tiny grid/call set
  - Runs GA to optimize station locations, fleet mix, and assignment
  - Decodes best plan and evaluates with the simulator

---

## Scenario (What it models)

- A city represented as a grid of cells (e.g., 26×22, ~2 km per cell)
- Calls arrive over time with categories (`cardiac`, `catA`, `catC`)
- Vehicles (`A` = ambulances, `R` = rapid response cars) start at base stations
- Dispatch is myopic nearest-ETA by required type; vehicles travel, serve, and return
- KPI measures expected patient survival over a study window


## Objective Metric

**Heterogeneous survival efficiency** (higher is better):

$\eta_s=\frac{2\sum s_c+\sum s_a}{2\gamma+\delta}$

- Cardiac: \( s_c=\frac{1}{1+e^{(-0.26+0.139\,T_r)}} \)
- Category A: \( s_a=1 \) if \( T_r \le 8 \) minutes else \( 0 \)
- \( \gamma \) = # cardiac calls, \( \delta \) = # Category A calls



## How the pieces fit

1. **example_run.py**
   - Creates stations (some movable), a travel model, and a tiny call trace
   - Configures GA settings and runs optimization over a 1-hour window

2. **ga_opt.py / GAOptimizer**
   - Encodes a candidate plan into station coordinates, fleet mix, and assignment
   - Calls the simulation for fitness (`eta_s`)
   - Evolves toward better plans

3. **ems_core.py / Simulation**
   - Runs an event loop for calls and vehicle movements
   - Records first-arrival response times
   - Computes `eta_s` for the period


### Quick Start

```bash
python example_run.py
```

### Read More

> McCormack, Richard, and Graham Coates. "A simulation model to enable the optimization of ambulance fleet allocation and base station location for increased patient survival." European journal of operational research 247.1 (2015): 294-309.