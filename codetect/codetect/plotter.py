    def plot_genome(self,T,st):
        """
        Plot estimated coverage for each cluster across the genome,
        respective posititions, estimated mutations,
        and true values for each.

        Args:
            T: membership probability array per read
            st: estimated sequence for alternative cluster
        """
        cov0 = np.zeros(len(self.get_consensus()))
        cov1 = np.zeros(len(self.get_consensus()))
        for Xi in self.X:
            if Xi.z == 0:
                for p,b in Xi.map.items():
                    cov0[p] += 1
            else:
                assert Xi.z == 1
                for p,b in Xi.map.items():
                    cov1[p] += 1
        self.COV = cov0+cov1
        estcov0 = np.zeros(len(self.get_consensus()))
        estcov1 = np.zeros(len(self.get_consensus()))
        hamarr = np.zeros(len(self.get_consensus()))
        hamarr2 = np.zeros(len(self.get_consensus()))
        for i,hi in enumerate(self.get_consensus()):
            if self.get_consensus()[i] != c2i[self.minor[i]]:
                hamarr[i] = len(self.V_INDEX[i][c2i[self.minor[i]]])
            if st[i] != self.get_consensus()[i]:
                hamarr2[i] = len(self.V_INDEX[i][st[i]])

        for i,Xi in enumerate(self.X):
            Ti = T[i]
            for pos,base in Xi.map.items():
                estcov0[pos] += Ti[0]
                estcov1[pos] += Ti[1]
        plt.plot(hamarr, color='red', alpha=0.5)
        plt.plot(hamarr2, color='blue', alpha=0.5)
        plt.plot(cov0,color='blue')
        plt.plot(cov1,color='orange')
        plt.plot(estcov0,color='purple')
        plt.plot(estcov1,color='pink')
        plt.show()

    def debug_plot(self,emObj):
        """ Plot simulated data statistics for debugging.
    
        Args:
            emObj: an EM object used for parameter estimation
        """
        T = emObj.Tt
        st = emObj.st
        for k in range(len(self.COV)):
            assert self.COV[k] == sum([len(l) for l in self.V_INDEX[k]])
        nms = np.array([Xi.nm_major for Xi in self.X])
        plt.plot(self.COVWALK)
        plt.title("coverage_walk")
        plt.show()
        self.plot_genome()
        inp = [int(l) for l in input("Specify interval").split()]
        l,r = inp
        plt.plot(hamarr[l:r], color='red', alpha=0.5)
        plt.plot(hamarr2[l:r], color='green', alpha=0.5)
        plt.plot(cov0[l:r],color='blue')
        plt.plot(cov1[l:r],color='orange')
        plt.plot(estcov0[l:r],color='purple')
        plt.plot(estcov1[l:r],color='pink')
        plt.show()
        self.debug_interval(emObj)
        readdists = [Xi.nm_major for Xi in self.X if Xi.z == 0]
        plt.hist(readdists,bins=100)
        readdists = [Xi.nm_major for Xi in self.X if Xi.z == 1]
        plt.hist(readdists,bins=100)
        plt.show()        
        plt.hist([Xi.z for Xi in  self.X])
        plt.title("True z")
        plt.show()
        plt.hist([r[0] for r in T])
        plt.title("T0")
        plt.show()
