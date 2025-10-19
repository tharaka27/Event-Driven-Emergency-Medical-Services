from ems_core import Call, Station, TravelTimeModel, build_vehicles_from_allocation, Simulation
from ga_opt import GAOptimizer, GAConfig
import random
import time

def mock_calls() -> list[Call]:
    """
    Replace with your trace-driven calls (LAS-format). This is a tiny synthetic set
    just to show wiring.
    """
    t0 = 1_700_000_000  # arbitrary epoch
    calls = []
    grid_points = [(10,10),(11,10),(10,11),(12,12),(8,9)]
    hospitals = [(5,5)] * 5
    cats = ["cardiac","catA","catA","catA","catC"]
    for i in range(5):
        calls.append(Call(
            call_id=i,
            t_call=t0 + i*180,                 # one every 3 minutes
            dispatch_delay=30.0,               # seconds
            scene_time=600.0,                  # 10 minutes
            hospital_time=900.0,               # 15 minutes travel (placeholder)
            handover_time=300.0,               # 5 minutes
            need_ambulances=1,
            need_rrc=0,
            category=cats[i],
            loc_scene=grid_points[i],
            loc_hospital=hospitals[i],
        ))
    return calls

def main():
    # Stations: 4 total; 2 movable
    stations = {
        0: Station(0, (10, 10)),
        1: Station(1, (9, 12)),
        2: Station(2, (12, 9)),
        3: Station(3, (7, 7))
    }
    movable = [1, 2]  # allow GA to move these

    # Travel model (26x22 like paper; here small values are fine since we use relative units)
    travel = TravelTimeModel(n_rows=26, n_cols=22, cell_km=2.0)
    travel.default_speed_kmph = 45.0

    # Study window (1h)
    calls = mock_calls()
    t_start = calls[0].t_call
    t_end = t_start + 3600

    # Total fleet size
    total_vehicles = 6

    # GA: optimize station positions + fleet ratio + vehicle-to-station assignment
    ga = GAOptimizer(
        calls=calls,
        stations_fixed=stations,
        movable_station_ids=movable,
        N_grid=(26,22),
        total_vehicles=total_vehicles,
        fleet_ratio_fixed=None,     # optimize A vs R
        t_window=(t_start, t_end),
        travel=travel,
        ga_cfg=GAConfig(pop_size=16, generations=40, rx=0.85, rm=0.04, elite_k=1),
        seed=123
    )

    best_ch, best_fit = ga.run()
    print(f"Best fitness (eta_s): {best_fit:.4f}")

    stations_decoded, allocation = ga.decode_plan(best_ch)
    print("\nDecoded movable station positions:")
    for sid in sorted(stations_decoded):
        print(f"  Station {sid}: rc={stations_decoded[sid].grid_rc}")

    print("\nDecoded allocation (per station):")
    for sid in sorted(allocation):
        print(f"  Station {sid}: A={allocation[sid]['A']}, R={allocation[sid]['R']}")

    # (Optional) Evaluate the decoded plan explicitly:
    from ems_core import Simulation
    vehicles = build_vehicles_from_allocation(allocation)
    sim = Simulation(calls, stations_decoded, vehicles, travel)
    kpi = sim.run(t_start=t_start, t_end=t_end, warmup_buffer=90*60.0)
    print("\nSimulation KPIs:", kpi)

if __name__ == "__main__":
    main()