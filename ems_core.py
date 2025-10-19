from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Any
import heapq
import math
import random

@dataclass
class Call:
    call_id: int
    # epoch seconds (or any monotonic time unit)
    t_call: float
    # LAS-derived delays (seconds)
    dispatch_delay: float  # t_d
    scene_time: float      # t_sc
    hospital_time: float   # t_h
    handover_time: float   # t_ho
    # required number of resources by type (from data)
    need_ambulances: int
    need_rrc: int
    # patient category: "cardiac", "catA" (life-threatening non-cardiac), "catC" (non-urgent)
    category: str
    # snapped grid locations (row, col) for scene and hospital
    loc_scene: Tuple[int, int]
    loc_hospital: Tuple[int, int]

@dataclass
class Station:
    station_id: int
    grid_rc: Tuple[int, int]  # (row, col)

@dataclass
class Vehicle:
    vehicle_id: int
    kind: str                 # "A" (ambulance) or "R" (rapid response car)
    home_station_id: int
    # dynamic state
    busy: bool = False
    # current route queue as list of waypoints [(r,c), ...]; used by travel model
    route: List[Tuple[int, int]] = field(default_factory=list)
    # current simulated (r,c) location
    loc: Tuple[int, int] = None
    # if assigned to a call, store that call_id
    assigned_call: Optional[int] = None


class TravelTimeModel:
    def __init__(self, n_rows: int, n_cols: int, cell_km: float = 2.0):
        self.n_rows = n_rows
        self.n_cols = n_cols
        self.cell_km = cell_km
        # Example speed profile (km/h) by minute-of-week bucket. Replace with your derived array.
        self.default_speed_kmph = 45.0  # fallback
        self.minute_of_week_speeds = None  # Optional[List[float]] sized 7*24*60

    def _speed_kmph(self, t0_sec: float, kind: str) -> float:
        # TODO: derive from data; optionally vary by vehicle kind and time-of-week
        if self.minute_of_week_speeds:
            minute = int((t0_sec // 60) % (7 * 24 * 60))
            return max(5.0, self.minute_of_week_speeds[minute])
        return self.default_speed_kmph

    def distance(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        # Approximate lattice distance; replace with calibrated “straight-through-neighbors” method if desired.
        (r1, c1), (r2, c2) = a, b
        dr = abs(r1 - r2)
        dc = abs(c1 - c2)
        # Chebyshev or Manhattan are both usable; use 8-neighbor (Chebyshev-like) blended approx:
        steps_diag = min(dr, dc)
        steps_straight = abs(dr - dc)
        # Diagonal costs ~sqrt(2)*cell, straight ~1*cell
        d_km = steps_diag * (self.cell_km * math.sqrt(2)) + steps_straight * self.cell_km
        # TODO: apply calibrated correction factor by path length if you have it
        return d_km

    def travel_time(self, start_rc: Tuple[int, int], end_rc: Tuple[int, int], t0_sec: float, kind: str) -> float:
        d_km = self.distance(start_rc, end_rc)
        v = self._speed_kmph(t0_sec, kind)  # km/h
        # convert to seconds
        return (d_km / max(1e-6, v)) * 3600.0

    def route(self, start_rc: Tuple[int, int], end_rc: Tuple[int, int]) -> List[Tuple[int, int]]:
        # Simple greedy 8-neighbor stepping; replace with your precomputed neighbor-path if preferred
        r, c = start_rc
        rt, ct = end_rc
        path = [(r, c)]
        while (r, c) != (rt, ct):
            dr = 0 if r == rt else (1 if rt > r else -1)
            dc = 0 if c == ct else (1 if ct > c else -1)
            r += dr
            c += dc
            path.append((r, c))
        return path


def survival_cardic_arrest(response_time_sec: float) -> float:
    # Eq (3): sc = 1 / (1 + exp(-0.26 + 0.139*Tr))
    Tr = response_time_sec / 60.0  # minutes
    return 1.0 / (1.0 + math.exp(-0.26 + 0.139 * Tr))

def survival_catA(response_time_sec: float) -> float:
    # Eq (4): sa = 1 for Tr ≤ 8 min else 0
    return 1.0 if (response_time_sec <= 8 * 60.0) else 0.0


class Event:
    __slots__ = ("time", "etype", "payload")
    def __init__(self, time: float, etype: str, payload: Any):
        self.time = time
        self.etype = etype
        self.payload = payload
    def __lt__(self, other):  # heapq ordering
        return self.time < other.time

class Simulation:
    def __init__(
        self,
        calls: List[Call],
        stations: Dict[int, Station],
        vehicles: Dict[int, Vehicle],
        travel: TravelTimeModel,
        loc_update_period: float = 120.0  # seconds between location updates while traveling
    ):
        self.calls = sorted(calls, key=lambda c: c.t_call)
        self.stations = stations
        self.vehicles = vehicles
        self.travel = travel
        self.loc_update_period = loc_update_period

        self.event_q: List[Event] = []
        self.wait_q: List[int] = []  # queue of call_ids
        self.now: float = 0.0

        # outputs
        self.response_times: Dict[int, float] = {}  # call_id -> first vehicle response time (sec)
        self.call_assignments: Dict[int, List[int]] = {}  # call_id -> [vehicle_ids]

        # book-keeping: where are vehicles now?
        for v in self.vehicles.values():
            if v.loc is None:
                v.loc = self.stations[v.home_station_id].grid_rc

    
    def run(self, t_start: float, t_end: float, warmup_buffer: float = 90 * 60.0) -> Dict[str, float]:
        # Warmup: enqueue calls in [t_start - buffer, t_start)
        warm_lo = t_start - warmup_buffer
        for c in self.calls:
            if warm_lo <= c.t_call < t_start:
                heapq.heappush(self.event_q, Event(c.t_call, "CALL_ARRIVE", c))

        self._loop(until=t_start, record_stats=False)

        # Study window
        for c in self.calls:
            if t_start <= c.t_call < t_end:
                heapq.heappush(self.event_q, Event(c.t_call, "CALL_ARRIVE", c))

        self._loop(until=t_end, record_stats=True)

        # compute objective components
        return self._kpis()

    def _loop(self, until: float, record_stats: bool):
        while self.event_q and self.event_q[0].time < until:
            ev = heapq.heappop(self.event_q)
            self.now = ev.time
            et = ev.etype

            if et == "CALL_ARRIVE":
                self._on_call_arrive(ev.payload, record_stats)

            elif et == "SCENE_DEPART":
                self._on_scene_depart(ev.payload)

            elif et == "JOB_COMPLETE":
                self._on_job_complete(ev.payload)

            elif et == "LOC_UPDATE":
                self._on_loc_update(ev.payload)

        # Drain loc updates up to 'until'
        self.now = until

    # ---------- event handlers ----------

    def _on_call_arrive(self, call: Call, record_stats: bool):
        assigned = self._dispatch(call)
        if assigned:
            self._flag_busy(assigned, call.call_id)
            self.call_assignments[call.call_id] = assigned[:]

            # first vehicle ETA used to mark response time:
            first_vehicle = min(
                assigned,
                key=lambda vid: self.travel.travel_time(
                    self.vehicles[vid].loc, call.loc_scene, self.now, self.vehicles[vid].kind
                )
            )
            first_eta = self.travel.travel_time(self.vehicles[first_vehicle].loc, call.loc_scene, self.now, self.vehicles[first_vehicle].kind)
            t_arrive_first = self.now + call.dispatch_delay + first_eta
            if record_stats:
                self.response_times[call.call_id] = t_arrive_first - call.t_call

            # everyone moves to scene; schedule a single SCENE_DEPART (after first arrival + scene_time)
            # We approximate: depart time = first arrival + scene time (matches paper’s line 12–13)
            scene_depart_time = t_arrive_first + call.scene_time
            heapq.heappush(self.event_q, Event(scene_depart_time, "SCENE_DEPART", call))
            # (Vehicles position updates occur via LOC_UPDATE ticks while en route)
            for vid in assigned:
                self._begin_travel_to(vid, call.loc_scene, self.now + call.dispatch_delay)

        else:
            # queue the call_id
            self.wait_q.append(call.call_id)

    def _on_scene_depart(self, call: Call):
        assigned = self.call_assignments.get(call.call_id, [])
        if not assigned:
            return
        # Transport: ensure at least one ambulance transports if needed
        transport_vid = None
        if call.hospital_time > 0.0 and any(self.vehicles[v].kind == "A" for v in assigned):
            # pick first ambulance on scene (simplified)
            for v in assigned:
                if self.vehicles[v].kind == "A":
                    transport_vid = v
                    break

        # schedule JOB_COMPLETE for transporting vehicle
        if transport_vid is not None:
            # depart to hospital now
            self._begin_travel_to(transport_vid, call.loc_hospital, self.now)
            t_arrive_hosp = self.now + self.travel.travel_time(
                self.vehicles[transport_vid].loc, call.loc_hospital, self.now, "A"
            )
            job_complete_time = t_arrive_hosp + call.hospital_time + call.handover_time
            heapq.heappush(self.event_q, Event(job_complete_time, "JOB_COMPLETE", (call.call_id, transport_vid)))

        # non-transport vehicles return to base and become available
        for vid in assigned:
            if vid != transport_vid:
                self._vehicle_become_available(vid)
                self._begin_travel_to(vid, self.stations[self.vehicles[vid].home_station_id].grid_rc, self.now)

        # try to serve queued calls
        self._check_queue()

    def _on_job_complete(self, payload: Tuple[int, int]):
        call_id, transport_vid = payload
        # transport vehicle becomes available and returns to base
        self._vehicle_become_available(transport_vid)
        self._begin_travel_to(transport_vid, self.stations[self.vehicles[transport_vid].home_station_id].grid_rc, self.now)
        # try queued calls
        self._check_queue()

    def _on_loc_update(self, payload: int):
        vid = payload
        v = self.vehicles[vid]
        # Move one “step” along route if any
        if v.route:
            # Already at current waypoint (by construction), pop it and check next
            v.route.pop(0)
            if v.route:
                v.loc = v.route[0]

        # If journey not done, schedule another update
        if v.route:
            heapq.heappush(self.event_q, Event(self.now + self.loc_update_period, "LOC_UPDATE", vid))

    # ---------- helpers ----------

    def _begin_travel_to(self, vid: int, dest: Tuple[int, int], t_depart: float):
        v = self.vehicles[vid]
        # Build route (list of waypoints). First element should be current position.
        v.route = self.travel.route(v.loc, dest)
        # schedule periodic LOC_UPDATE ticks
        heapq.heappush(self.event_q, Event(max(self.now, t_depart) + self.loc_update_period, "LOC_UPDATE", vid))

    def _dispatch(self, call: Call) -> List[int]:
        """
        Greedy nearest-ETA dispatch by type, allowing partial assignment first
        (we send what’s available now; remaining will be covered later by queue handling).
        """
        needA = call.need_ambulances
        needR = call.need_rrc

        idle = [v for v in self.vehicles.values() if not v.busy]
        # sort by ETA to scene
        idle.sort(key=lambda v: self.travel.travel_time(v.loc, call.loc_scene, self.now, v.kind))

        assigned: List[int] = []
        for v in idle:
            if v.kind == "A" and needA > 0:
                assigned.append(v.vehicle_id); needA -= 1
            elif v.kind == "R" and needR > 0:
                assigned.append(v.vehicle_id); needR -= 1
            if needA == 0 and needR == 0:
                break

        return assigned if assigned else []

    def _flag_busy(self, vids: List[int], call_id: int):
        for vid in vids:
            v = self.vehicles[vid]
            v.busy = True
            v.assigned_call = call_id

    def _vehicle_become_available(self, vid: int):
        v = self.vehicles[vid]
        v.busy = False
        v.assigned_call = None

    def _check_queue(self):
        # First-in-first-out: try to assign waiting calls
        if not self.wait_q:
            return
        # NOTE: In a real implementation, you'd retrieve the Call by id quickly (e.g., dict)
        id_to_call = {c.call_id: c for c in self.calls}
        still_waiting = []
        for call_id in self.wait_q:
            c = id_to_call[call_id]
            assigned = self._dispatch(c)
            if assigned:
                self._flag_busy(assigned, c.call_id)
                self.call_assignments[c.call_id] = assigned[:]
                # schedule scene depart
                first_vehicle = min(
                    assigned,
                    key=lambda vid: self.travel.travel_time(
                        self.vehicles[vid].loc, c.loc_scene, self.now, self.vehicles[vid].kind
                    )
                )
                first_eta = self.travel.travel_time(self.vehicles[first_vehicle].loc, c.loc_scene, self.now, self.vehicles[first_vehicle].kind)
                t_arrive_first = self.now + c.dispatch_delay + first_eta
                self.response_times[c.call_id] = t_arrive_first - c.t_call
                scene_depart_time = t_arrive_first + c.scene_time
                heapq.heappush(self.event_q, Event(scene_depart_time, "SCENE_DEPART", c))
                for vid in assigned:
                    self._begin_travel_to(vid, c.loc_scene, self.now + c.dispatch_delay)
            else:
                still_waiting.append(call_id)
        self.wait_q = still_waiting

    # ---------- KPIs / objective ----------

    def _kpis(self) -> Dict[str, float]:
        gamma = 0
        delta = 0
        sum_sc = 0.0
        sum_sa = 0.0
        for c in self.calls:
            if c.call_id not in self.response_times:
                # Unserved or outside window—ignore
                continue
            rt = self.response_times[c.call_id]
            if c.category == "cardiac":
                gamma += 1
                sum_sc += survival_cardic_arrest(rt)
            elif c.category == "catA":
                delta += 1
                sum_sa += survival_catA(rt)

        num = 2.0 * sum_sc + sum_sa
        den = 2.0 * gamma + delta if (2.0 * gamma + delta) > 0 else 1.0
        eta_s = num / den

        return {
            "eta_s": eta_s,
            "cardiac_calls": float(gamma),
            "catA_calls": float(delta),
        }

# ------------------------------
# Utilities to build vehicles from an allocation
# ------------------------------

def build_vehicles_from_allocation(
    allocation: Dict[int, Dict[str, int]]
) -> Dict[int, Vehicle]:
    """
    allocation: {station_id: {"A": nA, "R": nR}}
    Returns {vehicle_id: Vehicle}
    """
    vid = 0
    vehicles = {}
    for sid, counts in allocation.items():
        for _ in range(counts.get("A", 0)):
            vehicles[vid] = Vehicle(vehicle_id=vid, kind="A", home_station_id=sid)
            vid += 1
        for _ in range(counts.get("R", 0)):
            vehicles[vid] = Vehicle(vehicle_id=vid, kind="R", home_station_id=sid)
            vid += 1
    return vehicles