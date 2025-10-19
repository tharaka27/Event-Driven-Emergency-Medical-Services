from dataclasses import dataclass
import heapq, math

@dataclass
class Call:
    call_id: int
    t_call: float
    dispatch_delay: float
    loc_scene: tuple[int,int]

@dataclass
class Vehicle:
    vid: int
    kind: str         # "A" or "R"
    loc: tuple[int,int]
    busy: bool = False

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


class Event:
    def __init__(self, time, etype, payload):
        self.time=time; self.etype=etype; self.payload=payload
    def __lt__(self, other): return self.time<other.time

def simulate(calls, vehicles, travel):
    # events: only CALL_ARRIVE here (keep it tiny)
    evq=[]
    for c in calls:
        heapq.heappush(evq, Event(c.t_call, "CALL_ARRIVE", c))

    now=0.0
    response_times={}
    while evq:
        ev=heapq.heappop(evq)
        now=ev.time
        if ev.etype=="CALL_ARRIVE":
            c=ev.payload
            # nearest idle vehicle by ETA
            idle=[v for v in vehicles if not v.busy]
            if not idle:
                # tiny version: drop if none available
                continue
            best=min(idle, key=lambda v: travel.eta_sec(v.loc, c.loc_scene))
            eta=travel.eta_sec(best.loc, c.loc_scene)
            t_arrive = now + c.dispatch_delay + eta
            response_times[c.call_id]=t_arrive - c.t_call
            # mark busy briefly; then free (tiny: no scene/hospital events)
            best.busy=True
            # tiny: vehicle jumps to scene instantly after arrive (no movement in time)
            best.loc=c.loc_scene
            best.busy=False
    return response_times

def main():
    calls=[
        Call(0, 0.0, 30.0, (11,10)),
        Call(1, 120.0, 20.0, (14,10)),
    ]
    vehicles=[
        Vehicle(0,"A",(10,10)),
        Vehicle(1,"A",(8,8)),
    ]
    travel=Travel()
    rts=simulate(calls, vehicles, travel)
    for k,v in rts.items():
        print(f"Call {k}: response {v:.1f}s ({v/60:.2f}m)")

if __name__=="__main__":
    main()