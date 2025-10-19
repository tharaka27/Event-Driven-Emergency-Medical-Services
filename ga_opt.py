from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Callable
import math
import random
import copy

from ems_core import (
    Simulation, Station, TravelTimeModel, build_vehicles_from_allocation
)

@dataclass
class GAConfig:
    pop_size: int = 25
    rx: float = 0.85     # crossover rate
    rm: float = 0.04     # mutation rate
    elite_k: int = 1     # keep best 1
    generations: int = 180

class GAOptimizer:
    def __init__(
        self,
        calls,
        stations_fixed: Dict[int, Station],
        movable_station_ids: List[int],     # stations whose (r,c) we can change
        N_grid: Tuple[int, int],            # (n_rows, n_cols)
        total_vehicles: int,                # m
        fleet_ratio_fixed: Tuple[int, int] = None,  # (nA, nR) or None to optimize ratio
        t_window: Tuple[float, float] = None,
        travel: TravelTimeModel = None,
        ga_cfg: GAConfig = GAConfig(),
        seed: int = 42
    ):
        random.seed(seed)
        self.calls = calls
        self.stations_fixed = stations_fixed
        self.movable_station_ids = movable_station_ids[:]  # length n
        self.n_rows, self.n_cols = N_grid
        self.total_vehicles = total_vehicles
        self.fleet_ratio_fixed = fleet_ratio_fixed
        self.travel = travel
        self.t_window = t_window
        self.ga_cfg = ga_cfg

        self.N_total_stations = len(stations_fixed)  # assuming movable are included in this dict

        # chromosome length
        self.n = len(self.movable_station_ids)
        self.m = total_vehicles
        self.chrom_len = 2 * self.n + (0 if fleet_ratio_fixed else 1) + self.m

    def _decode(self, chrom: List[float]) -> Tuple[Dict[int, Station], Dict[int, Dict[str, int]]]:

        # 1) decode movable station (row, col) integers
        stations = copy.deepcopy(self.stations_fixed)
        idx = 0
        for sid in self.movable_station_ids:
            r = int(round(chrom[idx] * (self.n_rows - 1))); idx += 1
            c = int(round(chrom[idx] * (self.n_cols - 1))); idx += 1
            stations[sid] = Station(station_id=sid, grid_rc=(r, c))

        # 2) decode fleet mix
        if self.fleet_ratio_fixed is None:
            # use g -> int count of A; rest R
            g_ratio = chrom[idx]; idx += 1
            nA = int(round(g_ratio * self.m))
            nA = max(0, min(self.m, nA))
            nR = self.m - nA
        else:
            nA, nR = self.fleet_ratio_fixed

        # 3) per-vehicle station index [0..N-1]
        station_ids = list(stations.keys())  # stable order
        N = len(station_ids)
        alloc_counts = {sid: {"A": 0, "R": 0} for sid in station_ids}

        # We’ll assign A first, then R; each gene maps to a station
        for k in range(nA):
            s_idx = int(round(chrom[idx] * (N - 1))); idx += 1
            alloc_counts[station_ids[s_idx]]["A"] += 1
        for k in range(nR):
            s_idx = int(round(chrom[idx] * (N - 1))); idx += 1
            alloc_counts[station_ids[s_idx]]["R"] += 1

        return stations, alloc_counts

    def _fitness(self, chrom: List[float]) -> float:
        stations_decoded, allocation = self._decode(chrom)
        vehicles = build_vehicles_from_allocation(allocation)

        sim = Simulation(
            calls=self.calls,
            stations=stations_decoded,
            vehicles=vehicles,
            travel=self.travel,
        )
        t0, t1 = self.t_window
        kpi = sim.run(t_start=t0, t_end=t1, warmup_buffer=90 * 60.0)
        # higher ηs is better
        return kpi["eta_s"]

    def _init_population(self) -> List[List[float]]:
        P = []
        half = self.ga_cfg.pop_size // 2
        for _ in range(half):
            chrom = [random.random() for _ in range(self.chrom_len)]
            P.append(chrom)
        # complementary init (mirror)
        for chrom in P[:half]:
            P.append([1.0 - g for g in chrom])
        # adjust if odd pop_size
        while len(P) < self.ga_cfg.pop_size:
            P.append([random.random() for _ in range(self.chrom_len)])
        return P[:self.ga_cfg.pop_size]

    def _tournament_select(self, P: List[List[float]], F: List[float], k: int = 3) -> List[float]:
        best = None; bestf = -1e9
        for _ in range(k):
            i = random.randrange(len(P))
            if F[i] > bestf:
                bestf = F[i]; best = P[i]
        return best[:]

    def _crossover(self, p1: List[float], p2: List[float]) -> Tuple[List[float], List[float]]:
        c1 = p1[:]; c2 = p2[:]
        # (1) uniform swap
        for i in range(len(p1)):
            if random.random() < 0.5:
                c1[i], c2[i] = c2[i], c1[i]
        # (2) blend half the genes
        idxs = random.sample(range(len(p1)), k=max(1, len(p1)//2))
        beta = random.uniform(0.0, 1.1)
        for i in idxs:
            g1, g2 = c1[i], c2[i]
            c1[i] = g1 + beta * (g2 - g1)
            c2[i] = g2 + beta * (g1 - g2)
        # clip [0,1]
        c1 = [min(1.0, max(0.0, x)) for x in c1]
        c2 = [min(1.0, max(0.0, x)) for x in c2]
        return c1, c2

    def _mutate(self, P: List[List[float]]):
        # keep elite immune elsewhere; here we mutate all provided
        n_genes = len(P) * self.chrom_len
        n_mut = int(round(self.ga_cfg.rm * n_genes))
        for _ in range(n_mut):
            i = random.randrange(len(P))
            j = random.randrange(self.chrom_len)
            P[i][j] = random.random()

    def run(self) -> Tuple[List[float], float]:
        P = self._init_population()
        F = [self._fitness(ch) for ch in P]

        best_idx = max(range(len(P)), key=lambda i: F[i])
        best_ch = P[best_idx][:]
        best_fit = F[best_idx]

        for gen in range(self.ga_cfg.generations):
            # Elites
            elite_pairs = sorted(zip(P, F), key=lambda x: x[1], reverse=True)[:self.ga_cfg.elite_k]
            elites = [copy.deepcopy(ch) for ch, _ in elite_pairs]

            P_next: List[List[float]] = []
            P_next.extend(elites)

            # Fill
            while len(P_next) < self.ga_cfg.pop_size:
                if random.random() < self.ga_cfg.rx:
                    p1 = self._tournament_select(P, F, k=3)
                    p2 = self._tournament_select(P, F, k=3)
                    c1, c2 = self._crossover(p1, p2)
                    P_next.append(c1)
                    if len(P_next) < self.ga_cfg.pop_size:
                        P_next.append(c2)
                else:
                    p = self._tournament_select(P, F, k=3)
                    P_next.append(p)

            # Mutate (non-elite region)
            self._mutate(P_next[self.ga_cfg.elite_k:])

            # Evaluate
            P = P_next
            F = [self._fitness(ch) for ch in P]

            # Track best
            idx = max(range(len(P)), key=lambda i: F[i])
            if F[idx] > best_fit:
                best_fit = F[idx]
                best_ch = P[idx][:]

        return best_ch, best_fit

    # Helper to decode best chromosome into human-readable plan
    def decode_plan(self, chrom: List[float]):
        return self._decode(chrom)