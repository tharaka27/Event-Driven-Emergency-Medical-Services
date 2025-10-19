# Step 4 - Genetic Algorithm for Ambulance Fleet Allocation

## Overview

In this tutorial we implement a **Genetic Algorithm (GA)** that optimizes how ambulances are distributed across different stations in an Emergency Medical Services (EMS) network.

It works in combination with the **simulation core** to test each candidate allocation, simulate emergency responses, and evaluate performance based on the **heterogeneous survival efficiency (ηₛ)** — a measure of patient survival probability.


## Goal

Find the best way to distribute a limited number of ambulances (and optionally rapid response cars) among a set of base stations so that the **expected survival probability (ηₛ)** is maximized.

Each possible allocation (distribution of vehicles across stations) is represented as a **chromosome**, and the GA evolves these allocations through selection, crossover, and mutation.

---

## Scenario

Imagine a city with several ambulance stations.  
You know:
- How many **calls** occur, and where.
- The **station locations**.
- The **total number of vehicles** available.

You want to decide:
- How many ambulances (`A`) and cars (`R`) to place at each station.

The genetic algorithm:
1. Creates many random allocation plans (initial population).  
2. Simulates each plan using simulation engine.  
3. Measures the performance (ηₛ) of each plan.  
4. Evolves toward better plans using **genetic operations**.


## Components

### 1. `GAConfig` Dataclass
Defines configuration parameters for the genetic algorithm.

| Field | Description | Default |
|--------|-------------|----------|
| `pop_size` | Number of candidate solutions per generation | 16 |
| `generations` | Number of generations to evolve | 40 |
| `rx` | Crossover rate (probability of crossover) | 0.85 |
| `rm` | Mutation rate (probability of mutation) | 0.05 |
| `elite` | Number of top individuals preserved each generation | 1 |

These control the balance between exploration (diversity) and exploitation (refinement).


### 2. `build_vehicles()` Function
Creates a full list of `Vehicle` objects based on a given **allocation**.

**Input:**  
`allocation`: `{station_id: {"A": n_ambulances, "R": n_cars}}`  
`stations`: Station dictionary with coordinates.

**Output:**  
`{vehicle_id: Vehicle}` — a dictionary of ready-to-simulate vehicles.

Each vehicle is linked to its home station and given a unique ID.

### 3. `GA` Class — The Optimizer

This class runs the evolutionary optimization process.


| Parameter | Description |
|------------|-------------|
| `calls` | List of emergency `Call` objects |
| `stations` | Dictionary of available `Station` objects |
| `total_A` | Total ambulances to allocate |
| `total_R` | Total rapid response cars |
| `t_window` | Simulation time window `(start, end)` in seconds |

The GA uses this setup to evaluate how well each allocation performs through simulation.


### 4. Chromosome Representation

Each chromosome is a **list of real numbers in [0,1]**, representing **how vehicles are distributed**.

| Segment | Meaning |
|----------|----------|
| First *n* genes | Relative shares of ambulances (`A`) across *n* stations |
| Next *n* genes | Relative shares of rapid response cars (`R`) across *n* stations |

> Total chromosome length = 2 × (number of stations)

Example for 3 stations:
```
[0.2, 0.5, 0.3 | 0.1, 0.6, 0.3]
```
The algorithm converts these fractions into **integer allocations** per station.


### 6. `decode()` Method

Converts a chromosome into a valid vehicle allocation plan.

1. Extracts weights for ambulances (`A_weights`) and cars (`R_weights`).
2. Distributes total vehicles proportionally to these weights.
3. Corrects rounding drift to ensure total numbers match exactly.
4. Builds a dictionary:
   ```python
   {
       0: {"A": 2, "R": 0},
       1: {"A": 1, "R": 1},
       2: {"A": 1, "R": 0}
   }
   ```

This defines how many vehicles of each type are at each station.

### 7. `fitness()` Method

Evaluates how “good” a chromosome is.

Steps:
1. Decode chromosome → get allocation.
2. Build vehicles using `build_vehicles()`.
3. Run a **simulation** (`Simulation.run`) for the given time window.
4. Extract the resulting **ηₛ** value.

The **higher ηₛ**, the better the solution.


## The Genetic Algorithm Loop

This is where the evolutionary process happens.

#### Steps:
1. **Initialization**
   - Randomly create half of the population.
   - Create a mirrored version (1–g) for diversity.

2. **Evaluation**
   - Compute the ηₛ fitness of every chromosome using simulation.

3. **Evolution**
   - Repeat for each generation:
     - Keep top `elite` individuals unchanged.
     - Use **tournament selection** to pick parents.
     - Apply **crossover** with rate `rx`.
     - Apply **mutation** to some genes.
     - Replace the old population with the new one.

4. **Crossover Logic**
   - Mix genes between parents (uniform crossover).
   - Blend half of the genes using:
     \\(g' = g_1 + β(g_2 - g_1)\\)
     where β ∈ [0, 1.1].

   This allows small extrapolations beyond the parents to maintain diversity.

5. **Mutation**
   - Randomly alter a small percentage of genes (defined by `rm`).

6. **Elitism**
   - Always carry the best-performing chromosome to the next generation.

7. **Termination**
   - After all generations, return the **best chromosome** and its **ηₛ fitness**.