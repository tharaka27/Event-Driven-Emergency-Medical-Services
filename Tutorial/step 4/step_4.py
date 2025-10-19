from dataclasses import dataclass
from typing import Dict, List, Tuple
import random, copy

from ems_core import Call, Station, Vehicle, Travel, Simulation

@dataclass
class GAConfig:
    pop_size:int=16
    generations:int=40
    rx:float=0.85
    rm:float=0.05
    elite:int=1

def build_vehicles(allocation: Dict[int, Dict[str,int]], stations: Dict[int,Station]) -> Dict[int,Vehicle]:
    out={}; vid=0
    for sid, counts in allocation.items():
        for _ in range(counts.get("A",0)):
            out[vid]=Vehicle(vid,"A",sid,stations[sid].grid_rc); vid+=1
        for _ in range(counts.get("R",0)):
            out[vid]=Vehicle(vid,"R",sid,stations[sid].grid_rc); vid+=1
    return out

class GA:
    def __init__(self, calls, stations, total_A:int, total_R:int, t_window:Tuple[float,float]):
        self.calls=calls; self.stations=stations
        self.total_A=total_A; self.total_R=total_R
        self.t0,self.t1=t_window
        self.ids=list(stations.keys())

    def chrom_len(self): return len(self.ids)*2  # [A share per station | R share per station], values in [0,1]

    def decode(self, chrom: List[float]) -> Dict[int,Dict[str,int]]:
        n=len(self.ids)
        A_weights=chrom[:n]; R_weights=chrom[n:]
        def distribute(total, weights):
            s=sum(weights)+1e-9
            raw=[w/s*total for w in weights]
            ints=[int(round(x)) for x in raw]
            # fix rounding drift
            diff=total - sum(ints)
            for _ in range(abs(diff)):
                i=random.randrange(n)
                ints[i]+= 1 if diff>0 else -1
            return ints
        A_counts=distribute(self.total_A, A_weights)
        R_counts=distribute(self.total_R, R_weights)
        alloc={}
        for i,sid in enumerate(self.ids):
            alloc[sid]={"A":max(0,A_counts[i]), "R":max(0,R_counts[i])}
        return alloc

    def fitness(self, chrom: List[float]) -> float:
        allocation=self.decode(chrom)
        vehicles=build_vehicles(allocation, self.stations)
        sim=Simulation(self.calls, self.stations, vehicles, Travel())
        kpi=sim.run(self.t0, self.t1)
        return kpi["eta_s"]

    def run(self, cfg=GAConfig(), seed=123):
        random.seed(seed)
        L=self.chrom_len()
        # init + mirror
        P=[[random.random() for _ in range(L)] for _ in range(cfg.pop_size//2)]
        P+= [[1.0-g for g in ch] for ch in P]
        while len(P)<cfg.pop_size: P.append([random.random() for _ in range(L)])

        F=[self.fitness(ch) for ch in P]
        best=max(zip(P,F), key=lambda x:x[1])

        for _ in range(cfg.generations):
            # elites
            ranked=sorted(zip(P,F), key=lambda x:x[1], reverse=True)
            elites=[copy.deepcopy(ranked[i][0]) for i in range(cfg.elite)]
            Pnext=elites[:]
            # fill
            while len(Pnext)<cfg.pop_size:
                if random.random()<cfg.rx:
                    p1=max(random.sample(list(zip(P,F)), k=3), key=lambda x:x[1])[0]
                    p2=max(random.sample(list(zip(P,F)), k=3), key=lambda x:x[1])[0]
                    c1=p1[:]; c2=p2[:]
                    # uniform + blend
                    for i in range(L):
                        if random.random()<0.5: c1[i],c2[i]=c2[i],c1[i]
                    idxs=random.sample(range(L), k=max(1,L//2))
                    beta=random.uniform(0.0,1.1)
                    for i in idxs:
                        g1,g2=c1[i],c2[i]
                        c1[i]=min(1,max(0,g1+beta*(g2-g1)))
                        c2[i]=min(1,max(0,g2+beta*(g1-g2)))
                    Pnext+= [c1,c2][:cfg.pop_size-len(Pnext)]
                else:
                    p=max(random.sample(list(zip(P,F)), k=3), key=lambda x:x[1])[0]
                    Pnext.append(p[:])
            # mutate non-elites
            nmut=int(round(cfg.rm*L*(cfg.pop_size-cfg.elite)))
            for _ in range(nmut):
                i=random.randrange(cfg.elite, cfg.pop_size); j=random.randrange(L)
                Pnext[i][j]=random.random()
            P=Pnext
            F=[self.fitness(ch) for ch in P]
            best=max(zip(P,F), key=lambda x:x[1], default=best)
        return best

if __name__=="__main__":
    # tiny demo
    calls=[Call(0,0.0,30.0,600.0,(11,10),"cardiac"),
           Call(1,120.0,20.0,300.0,(14,10),"catA"),
           Call(2,300.0,20.0,300.0,(9,9),"catA")]
    stations={0:Station(0,(10,10)),1:Station(1,(8,8)),2:Station(2,(12,12))}
    ga=GA(calls, stations, total_A=4, total_R=0, t_window=(0.0, 3600.0))
    (best_ch, best_fit)=ga.run()
    print("Best eta_s:", best_fit)