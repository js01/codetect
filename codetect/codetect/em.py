#import pymc3 as pm
from io import StringIO
import math
import numpy as np
import matplotlib.pyplot as plt
#import seaborn as sns
#import theano.tensor as tt
import sys
import random
np.set_printoptions(threshold=sys.maxsize)


c2i = {c:i for i,c in enumerate("ACGT")}
def ham(s1, s2):
    return sum([1 for i in range(len(s1)) if s1[i] != s2[i]])

class EM():
    def __init__(self, ds, EPS):
        self.ds = ds
        self.X = ds.X
        self.N_READS = sum([Xi.count for Xi in self.X])
        self.M = ds.M
        self.V_INDEX = ds.V_INDEX
        self.MIN_COV = 0
        self.CONSENSUS = ds.CONSENSUS
        self.MIN_THRESHOLD = 0.001
        self.MIN_FREQ = 0.03
        self.EPSILON = EPS

    def calc_log_likelihood(self,st,g,mu,pi):
        # We now seek the log likelihood 
        # sum logP(Xi|theta) = log(P(Xi|Zi=1,theta)P(Zi=1|theta) + 
        # P(Xi | Zi=2,theta)P(Zi=2|theta))
        # = log(P(X_i | Zi=1,theta)pi + P(Xi | Zi=2,theta)(1-pi))
        # Do this via logsumexp
        sumo = 0
        for i,Xi in enumerate(self.X):
            a = Xi.logPmajor(g)
            b = Xi.logPminor2(st,mu)
            l1 = a
            l2 = b
            lw1 = np.log(pi)
            lw2 = np.log(1-pi)
            exp1 = np.exp(l1 + lw1)
            exp2 = np.exp(l2 + lw2)
            c = exp1 + exp2
            sumo += np.log(c)
        return sumo

    def print_debug_info(self, Tt, st):
        inds = sorted([i for i in range(len(self.X))], key = lambda i : self.X[i].pos)
        for i in inds:
            print(self.X[i].pos, self.X[i].z, Tt[i], self.X[i].cal_ham(self.CONSENSUS), self.X[i].cal_ham(st))

    def calTi_pair(self,Xi,pi,g,v):
        a = Xi.Pmajor(g)
        b = Xi.Pminor(v)
        assert 0 <= a <= 1
        assert 0 <= b <= 1
        c = pi*a + (1-pi)*b
        t1i = (pi * a) / c
        t2i = ((1-pi) * b) / c
#        print(str(Xi)[:50],Xi.z,Xi.nm)
#        print()
#        print(a,b,c)
        tp = np.array([t1i,t2i])
        assert sum(tp) > 0.999
        return tp

    def calTi_pair2(self,Xi,pi,g,st,mu):
        a = Xi.logPmajor(g)
        b = Xi.logPminor2(st,mu)
#        assert 0 <= a <= 1, a
#        assert 0 <= b <= 1, b
#        print(a,b)
        # pi*e^L1 + (1-pi)e^L2 = e^(L1+logpi) + e^(L2+log(1-pi))
        # 
        l1 = a
        l2 = b
        lw1 = np.log(pi)
        lw2 = np.log(1-pi)
#        alpha = max([l1 + lw1, l2 + lw2])
        exp1 = np.exp(l1 + lw1)
        exp2 = np.exp(l2 + lw2)
#        exp1 = np.exp(l1 + lw1 - alpha)
#        exp2 = np.exp(l2 + lw2 - alpha)
#        assert exp1 > 0
#        assert exp2 > 0
        c = exp1 + exp2
        assert 0 < c <= 1.01,c
        t1i = exp1/c
        t2i = exp2/c
#        c = pi*a + (1-pi)*b
#        t1i = (pi * a) / c
#        t2i = ((1-pi) * b) / c
#        print(str(Xi)[:50],Xi.z,Xi.nm)
#        print("a=",a,"b=",b,"c=",c)
#        print("t=",[t1i,t2i])
        tp = np.array([t1i,t2i])
#        assert t1i > 0, t1i
#        assert t2i > 0, t2i
        assert sum(tp) > 0.999, sum(tp)
        return tp
 
    def recalc_T(self,pi,g,v):
        res = []
        for Xi in self.X:
            pair = self.calTi_pair(Xi,pi,g,v)
            res.append(pair)
        return np.array(res)

    def recalc_T2(self,pi,g,st,mu):
        res = []
        for Xi in self.X:
            pair = self.calTi_pair2(Xi,pi,g,st,mu)
            res.append(pair)
        return np.array(res)

    def recalc_mu(self,T, S):
        numo = sum([T[i,1]*Xi.count*Xi.cal_ham(S) for i,Xi in enumerate(self.X)])
        deno = sum([T[i,1]*Xi.count*len(Xi.get_aln()) for i,Xi in enumerate(self.X)])
        assert deno > 0
        newmu = numo/deno
        assert 0 <= newmu <= 1,newmu
        return min(newmu,0.5)

    def recalc_gamma(self,T):
        nms = [Xi.nm_major for Xi in self.X]
        Ti0s = T[:,0]
        numo = sum([T[i,0]*Xi.count*Xi.nm_major for i,Xi in enumerate(self.X)])
        deno = sum([T[i,0]*Xi.count*len(Xi.get_aln()) for i,Xi in enumerate(self.X)])
        newgt = numo/deno
        assert 0 <= newgt <= 1,newgt
        return newgt

    def regularize_st(self,ststar,wmat,diff):
     # IF THE MAXIMUM STRING IS TOO CLOSE, GET THE MAXIMUM STRING SUBJECT TO CONSTRAINTS
        maxalts = []
        for k in self.ds.VALID_INDICES:
            bw = wmat[k]
            # IF THE MAXIMUM IS NOT THE REFERENCE, SKIP
            if ststar[k] == self.CONSENSUS[k]:
                maxalt = max([j for j in range(4) if j != self.CONSENSUS[k]], key=lambda x:bw[x])
#                assert self.CONSENSUS[k] != maxalt
#                assert bw[ststar[k]] >= bw[maxalt]
#                assert bw[self.CONSENSUS[k]] >= bw[maxalt], (k,self.CONSENSUS[k], bw, maxalt)
                if bw[maxalt] > 0:
                    loss = bw[ststar[k]]-bw[maxalt]
                    maxalts.append([k,maxalt,loss])
                    assert maxalt != self.CONSENSUS[k]
        maxalts = np.array(maxalts)
        # Assume sorts small to high, take the last -diff, recall
        # diff is negative
        toflip = maxalts[np.argsort(maxalts[:,2])][0:-diff]
        for k,maxalt,loss in toflip:
            assert self.CONSENSUS[int(k)] != maxalt
            ststar[int(k)] = int(maxalt)
            assert ststar[int(k)] != self.CONSENSUS[int(k)]
#            print(k,maxalt,w,wmat[int(k)])
        return ststar        

    def get_weight_base_array(self, T):
        baseweights = np.zeros((len(self.CONSENSUS), 4))
        # FIRST CALCULATE THE MOST WEIGHTY BASE FOR EACH POSITION
        for k in self.ds.VALID_INDICES:
            v = np.zeros(4)
            totalTk = 0
            for j,rl in enumerate(self.V_INDEX[k]):
                for ri in rl:
                    Xri = self.X[ri]
                    assert k in Xri.map, (k,Xri.map)
                    assert j == Xri.map[k]
                    baseweights[k,j] += T[ri,1]
                    totalTk += T[ri,1]
            if totalTk > 0:
                baseweights[k] /= totalTk
        return baseweights

    def recalc_st(self,T,minh):
        # BUILD THE MAXIMUM STRING
        baseweights = self.get_weight_base_array(T)
        ststar = [c for c in self.CONSENSUS]
        for bi in self.ds.VALID_INDICES:
            bw = baseweights[bi]
            maxi = max([j for j in range(4) if len(self.V_INDEX[bi][j]) > self.MIN_COV], key=lambda x:bw[x])
            if sum(bw) > 0:
                ststar[bi] = maxi
            else:
                ststar[bi] = self.CONSENSUS[bi]
        diff = ham(ststar,self.CONSENSUS)-minh
        if diff >= 0:
            return ststar
        else:
            return self.regularize_st(ststar,baseweights,diff)
#            return ststar
 
    def recalc_V(self,T):
        # Regularize by claiming that the probability of a mismatch can never be less than MIN_THRESHOLD
        newv = np.zeros((len(self.V_INDEX),4))
        assert len(self.V_INDEX) == len(self.M)
        for k in range(len(self.V_INDEX)):
            for c in range(4):
                # recalc Vi
                sumo = 0
                # Iterate over reads that mismatch at position k
                # THIS IS THE PROBABILITY THAT THEY ARE NOT THE SAME
                for ri in self.V_INDEX[k][c]:
                    sumo += (T[ri,1])
                assert sum(T[:,1]) > 0
                assert np.isfinite(sumo), sumo
                newv[k,c] = sumo
            newv[k] += self.MIN_THRESHOLD
            assert sum(newv[k]) != 0,(k,newv[k])
            newv[k] /= sum(newv[k])
            assert sum(newv[k]) > 0.99999, (newv[k], sum(newv[k]))
        return newv

    def recalc_pi(self,T):
        return sum([T[i,0]*self.X[i].count for i in range(len(T))])/self.N_READS

    def expected_d(self,v):
        sumo = 0
        assert len(self.CONSENSUS) == len(v)
        for ci, c in enumerate(self.CONSENSUS):
            alts = [v[ci,j] for j in range(4) if j != c]
            sumo += sum(alts)
        return sumo

    def init_st_random(self,M):
        st = [c for c in self.CONSENSUS]
        for vi,vt in enumerate(M):
            st[vi] = np.random.choice([j for j in range(4)],p=vt)
        return st

    def init_st(self,M):
        st = [c for c in self.CONSENSUS]
        second_best = []
        for vi in self.ds.VALID_INDICES:
            vt = M[vi]
            stups = sorted([j for j in range(4)],key=lambda j:vt[j])
            sb = stups[-2]
            if vt[sb] > 0.0 and len(self.V_INDEX[vi][sb]) > self.MIN_COV:
                second_best.append((vt[sb],vi,sb))
        second_best = sorted(second_best,key=lambda x:x[0])
        c = 0
#        for val,vi,sb in second_best[-len(self.CONSENSUS)//3:]:
        for val,vi,sb in second_best[::-1]:
            if c > self.EPSILON and val < self.MIN_FREQ:
                break
            c += 1
            st[vi] = sb
        return st

    def check_st(self, st):
        for i in range(len(st)):
            if i not in self.ds.VALID_INDICES:
                assert st[i] == self.CONSENSUS[i]

    def do2(self, N_ITS, random_init=False, debug=False):
        pit = 0.5
        gt = 0.01
        mut = 0.01
        if random_init:
            st = self.init_st_random(self.M)
        else:
            st = self.init_st(self.M)
        # Assertions
        for row in self.M:
            for v in row:
                assert not np.isnan(v)
        assert len(self.X) > 0
        for i, Xi in enumerate(self.X):
            for pos,bk in Xi.get_aln():
                assert Xi.i2c(bk) != "-"
                assert i in self.V_INDEX[pos][bk]
                assert self.M[pos,bk] > 0
        for m in self.M:
            if sum([q for q in m]) > 0:
                assert sum(m) > 0.98, m
        assert len(self.V_INDEX) == len(self.M)
        assert 0 <= gt <= 1,gt
        assert ham(st, self.CONSENSUS) >= self.EPSILON, ham(st, self.CONSENSUS)

        for t in range(N_ITS):
            self.check_st(st)
            assert pit <= 0.999
            sys.stderr.write("Iteration:%d" % t + str([pit,gt,mut,ham(st,self.CONSENSUS)]) + "\n")
            assert ham(st, self.CONSENSUS) >= self.EPSILON
            if pit == 1:
                sys.stderr.write("No coinfection detected.\n")
                return False,st,Tt

            Tt = self.recalc_T2(pit,gt,st,mut)
            if debug:
                self.ds.plot_genome(Tt,st)
#            self.print_debug_info(Tt,st)
            self.st = st
            self.Tt = Tt
            self.gt = gt
            self.pit = pit
            if sum(Tt[:,1]) == 0:
                sys.stderr.write("No coinfection detected.\n")
                return self.calc_log_likelihood(st,gt,mut,pit), False,st,Tt

            pit = self.recalc_pi(Tt)
            pit = min(0.98, pit)
            gt = self.recalc_gamma(Tt)
            gt = min(max(gt, 0.0001), 0.05)
            st = self.recalc_st(Tt, self.EPSILON)     
#            mut = gt
            mut = self.recalc_mu(Tt, st)
#            mut = min(max(mut, 0.0001), 0.05)

        if debug:
            self.ds.plot_genome(Tt,st)

        if pit > 0.99:
            sys.stderr.write("No coinfection detected!\n")
            return self.calc_log_likelihood(st,gt,mut,pit), False, st, Tt
        
        sys.stderr.write("Coinfection detected!\n")
        return self.calc_log_likelihood(st,gt,mut,pit),True, st, Tt

        props = sorted(np.random.dirichlet((1.0,1.0,1.0,1.0,1.0)))
        props = [p/2 for p in props]
        props[-1] += 0.5

    def do_one_cluster(self, N_ITS, debug=False):
        pit = 0.5
        gt = 0.01
        mut = gt
        st = self.CONSENSUS
        for t in range(N_ITS):
            sys.stderr.write("Iteration:%d" % t + str([pit,gt,mut,ham(st,self.CONSENSUS)]) + "\n")
            Tt = self.recalc_T2(pit,gt,st,mut)
            gt = self.recalc_gamma(Tt)
            gt = min(max(gt, 0.0001), 0.05)
            mut = gt
        if debug:
            self.ds.plot_genome(Tt,st)       
        sys.stderr.write("Coinfection detected!\n")
        return self.calc_log_likelihood(st,gt,mut,pit),True, st, Tt