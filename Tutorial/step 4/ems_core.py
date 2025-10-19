from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any
import heapq, math

@dataclass
class Call:
    call_id: int
    t_call: float
    dispatch_delay: float
    scene_time: float
    loc_scene: tuple[int,int]
    category: str           # "cardiac", "catA", "catC"

@dataclass
class Station:
    station_id: int
    grid_rc: tuple[int,int]

@dataclass
class Vehicle:
    vehicle_id: int
    kind: str               # "A" or "R"
    home_station_id: int
    loc: tuple[int,int]
    busy: bool = False

class Travel:
    def __init__(self, cell_km=2.0, speed_kmph=45.0):
        self.cell_km=cell_km; self.speed_kmph=speed_kmph
    def dist(self,a,b):
        (r1,c1),(r2,c2)=a,b
        return (abs(r1-r2)+abs(c1-c2))*self.cell_km
    def eta(self,a,b):
        return (self.dist(a,b)/self.speed_kmph)*3600.0

def sc(resp_sec: float) -> float:
    # cardiac logistic (paper Eq.3), Tr in minutes
    Tr = resp_sec/60.0
    return 1.0/(1.0+math.exp(-0.26+0.139*Tr))

def sa(resp_sec: float) -> float:
    # category A step (≤8 min)
    return 1.0 if resp_sec<=8*60.0 else 0.0

class Event:
    def __init__(self,time,etype,payload): self.time=time; self.etype=etype; self.payload=payload
    def __lt__(self,o): return self.time<o.time

class Simulation:
    def __init__(self, calls: List[Call], stations: Dict[int,Station], vehicles: Dict[int,Vehicle], travel: Travel):
        self.calls=sorted(calls, key=lambda c:c.t_call)
        self.stations=stations
        self.vehicles=vehicles
        self.travel=travel
        self.evq: List[Event]=[]
        self.wait_q: List[int]=[]
        self.now=0.0
        self.response: Dict[int,float]={}

    def run(self, t_start: float, t_end: float) -> Dict[str,float]:
        # load calls in window (no warmup in mini version)
        for c in self.calls:
            if t_start<=c.t_call<t_end:
                heapq.heappush(self.evq, Event(c.t_call,"CALL",c))
        while self.evq and self.evq[0].time<t_end:
            ev=heapq.heappop(self.evq)
            self.now=ev.time
            if ev.etype=="CALL":
                self._handle_call(ev.payload)
        return self._kpis()

    def _handle_call(self, c: Call):
        idle=[v for v in self.vehicles.values() if not v.busy]
        if not idle:
            self.wait_q.append(c.call_id); return
        best=min(idle, key=lambda v:self.travel.eta(v.loc, c.loc_scene))
        eta=self.travel.eta(best.loc, c.loc_scene)
        arrive=self.now + c.dispatch_delay + eta
        self.response[c.call_id]=arrive - c.t_call
        best.busy=True; best.loc=c.loc_scene; best.busy=False

    def _kpis(self)->Dict[str,float]:
        gamma=delta=0; sum_sc=sum_sa=0.0
        id2call={c.call_id:c for c in self.calls}
        for cid, rt in self.response.items():
            cat=id2call[cid].category
            if cat=="cardiac": gamma+=1; sum_sc+=sc(rt)
            elif cat=="catA": delta+=1; sum_sa+=sa(rt)
        den = 2*gamma + delta if (2*gamma+delta)>0 else 1.0
        eta_s = (2*sum_sc + sum_sa)/den
        return {"eta_s":eta_s, "cardiac":float(gamma), "catA":float(delta)}