from dataclasses import dataclass
import math

@dataclass
class Call:
    t_call: float                # seconds (epoch or relative)
    dispatch_delay: float        # seconds
    loc_scene: tuple[int,int]    # (r,c) grid

class Travel:
    def __init__(self, cell_km=2.0, speed_kmph=45.0):
        self.cell_km = cell_km
        self.speed_kmph = speed_kmph

    def distance_km(self, a, b):
        # Manhattan for simplicity
        (r1,c1),(r2,c2) = a,b
        return (abs(r1-r2) + abs(c1-c2)) * self.cell_km

    def eta_sec(self, a, b):
        d = self.distance_km(a,b)
        return (d / self.speed_kmph) * 3600.0

def main():
    # one ambulance sitting at station (10,10)
    amb_loc = (9,10)
    # one call nearby
    call = Call(
        t_call=0.0, dispatch_delay=30.0,
        loc_scene=(11,10)
    )

    travel = Travel(cell_km=2.0, speed_kmph=60.0)
    travel_time = travel.eta_sec(amb_loc, call.loc_scene)
    response_time = call.dispatch_delay + travel_time  # first arrival time – call.t_call

    print(f"Response time (sec): {response_time:.1f}")
    print(f"Response time (min): {response_time/60:.2f}")

if __name__ == "__main__":
    main()