#!/usr/bin/env python3
"""
Created on Mon Apr 10 14:53:15 2017

@author: Jackson Anderson, Rochester Institute of Technology jda4923@rit.edu
"""

import copy # used for creating C/Ilkg compensated copies of exp data
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import scipy.constants as sc
from scipy.stats import skew
from scipy.stats import skewnorm
from scipy.optimize import fsolve, minimize, basinhopping, fmin_slsqp
import numpy as np
from mpldatacursor import datacursor
import HysteresisData as hd
from mpl_toolkits.mplot3d import Axes3D

class LandauFilm:
    """
    Base class for Landau Modeling of ferroelectric thin films using alpha
    and beta parameters. 
    
    LandauSimple models behaviour at one temperature (solves for alpha rather
    than alpha0 and Curie Temperature). It also asumes a viscosity coefficient
    of 0.
    
    LandauFull implements rho, Tc, and a0 for more detailed analysis.
    """
    
    def __init__(self, thickness = 13E-7, area = 1E-4, c = 0, pr= 0):
        self.thickness = thickness # cm
        self.area = area # cm^2
        self.c = c # F
        self.pr = pr
        
    def cCalc(self,files, plot = False):
        """
        Calculates non-ferroelectric sample capacitance for the landau film 
        given a list of tf1000 DHM measurement CSV files, 
        with the DHM measurements taken at different frequencies
        
        Calculates non-ferroelectric sample capacitance from the slope of 
        i = C dV/dt using the median abs(current) value at different freq
        (will give non-switching current value)
        
        Parameters
        ----------
        files : array_like of HysteresisData files.
        
        Returns
        -------
        iFit[0] : float
        Capacitance in farads
        """
        
        hystData = []

        for f in files:
            data = hd.HysteresisData(area=1E-4)
            data.tsvRead(f)
            hystData.append(data)
        
        medI = np.zeros(len(hystData))
        freqs = np.zeros(len(hystData))
        dvdt = np.zeros(len(hystData))

        for i, d in enumerate(hystData):
            freqs[i] = d.freq
            
            dt = d.time[1]-d.time[0]
            dvdt[i] = np.mean(np.abs(np.diff(d.voltage)/d.dt))
            medI[i] = np.median(np.abs(d.current))
#            if plot:
#                fig = plt.figure()
#                fig.set_facecolor('white')
#                ax = fig.add_subplot(111)
#                ax.set_xlabel('Current (uA)')
#                ax.set_ylabel('Count')
#                binData = ax.hist(np.abs(d.current)*1E6, bins=20,alpha = 0.6)
#            else:
#                binData = np.histogram(np.abs(d.current)*1E6, bins=20)
#            index = np.where(binData[0] == max(binData[0]))
#            medI[i] = (binData[1][index] + binData[1][index])/2 * 1E-6

        iFit = np.polyfit(dvdt,medI,1)
        iFit_fn = np.poly1d(iFit)
        er = iFit[0]*hystData[0].thickness/(hystData[0].area*sc.epsilon_0*1E-2)
#        print (iFit,er)
        if plot:
            fig2 = plt.figure()
            fig2.set_facecolor('white')       
            ax2 = fig2.add_subplot(111)
            ax2.set_title('Capacitance = {:0.3e} F, er= {:.3f}'.format(iFit[0],er))
            datacursor(ax2.plot(dvdt,medI*1E6,'o',dvdt,1E6*iFit_fn(dvdt),'--k'))
            ax2.set_xlabel('dV/dt (V/s)')
            ax2.set_ylabel('Current ($\mu{}A$)')
        
        print (iFit[0])  
        return iFit[0]
    
    def cCompensation(self, data, plot = False):
        """ 
        Calculates Pr value by subtracting out effect of capacitance in PV curve
        
        Parameters
        ----------
        data: HysteresisData object
            
        Returns
        -------
        compData: HysteresisData object
            identical to input but with C*dv/dt current subtracted out
            and polarization recalculated from new current
        pr: float
            remnant polarization value
        """
        
        #TODO: Test with high leakage current samples

        compData = copy.deepcopy(data) # 
        
        dvdt = np.mean(np.abs(np.diff(data.voltage)/data.dt))
#        dvdt = (data.voltage[1]-data.voltage[0])/data.dt
        icap = self.c*dvdt
        
        for j, i in enumerate(data.current):
            if abs(i) >= icap:
                compData.current[j] = i-np.sign(i)*icap
            else:
                compData.current[j] = 0
                
        
        
        testpol = np.zeros(len(data.current))
        for i in range(np.size(testpol)):
            if i == 0:
                next
            else:
                testpol[i] = testpol[i-1] + compData.current[i]*compData.dt/compData.area
                
        pr = (max(testpol)-min(testpol))/2
        offset = max(testpol)-(max(testpol)-min(testpol))/2
        
        testpol = testpol-offset
        compData.polarization = testpol
        
        if plot:
            data.hystPlot()
            compData.hystPlot()
        
        return compData, pr

    def domainGen(self, e, er, prob,n=100, plot = False, retParms = False):
        """
        Creates N ferroelectric domains with Ebias and Ec based on the given
        FORC probability distribution.
        
        Gd: HfO2 forms columnar grains roughly 1:1 aspect ratio:
            n = Area/thickness^2
        (See Hoffmann et al., 2016, DOI: 10.1002/adfm.201602869)
          
        Parameters
        ----------
        e: 1d array of uniformly spaced field values from FORC  
        er: 1d array of uniformly spaced reverse field values from FORC            
        prob: 2d array of probabilities (0 to 1) from FORC calculation        
        n: int, number of domains        
        plot: bool, triggers plotting of generated parms        
        retParms: bool, triggers return of array of domain parms
            
        Returns
        -------
        domainList: list containing domain objects created from generated
                    parameters.

        domains: 2d array of length n by 4 containing domain parameters:
            domains[:,0] = E    
            domains[:,1] = Er  
            domains[:,2] = Ec
            domains[:,3] = Ebias
        """
        

        prob = np.ma.filled(prob,0)
        probf = np.ndarray.flatten(prob)
        index = np.zeros(len(probf))
        for i,v in enumerate(index): 
            if i == 0:
                next
            else:
                index[i]=index[i-1]+1
#        print (probf)
        domainList = []
        domains = np.zeros([n,4])
        for i in range(n):
            j = int(np.random.choice(index, p=probf))
            egrain = e[j % prob.shape[1]]
            ergrain = er[j // prob.shape[1]]
            domains[i,0] = egrain
            domains[i,1] = ergrain
            domains[i,2] = (egrain-ergrain)/2 # ec
            domains[i,3] = (egrain+ergrain)/2 # ebias
            genDomain = LandauDomain(self,self.area/n,domains[i,2],domains[i,3])
            domainList.append(genDomain)

        
        
        if plot:
            fig1 = plt.figure()
            fig1.set_facecolor('white')
            plt.cla()
            ax1 = fig1.add_subplot(111)
            ax1.plot(1E-6*domains[:,0],1E-6*domains[:,1],'o')
            ax1.set_title("Randomly Generated Grain Distribution")
            ax1.set_xlabel("E (MV/cm)")
            ax1.set_ylabel("$E_r$ (MV/cm)")
        
        
        if retParms:
            return (domainList, domains)
        else:
            return domainList
    
    def getUfe(self, pvals, domains):
        """
        Sums potential energy of all ferroelectric domains in a film to get
        the overall energy landscape.
          
        Parameters
        ----------
        pvals: np array of polarization values at which to solve Ufe
        domains: list containing all domain objects in the film
            
        Returns
        -------
            uFE: potential energy density landscape of film
        """        
        
        u = np.zeros(len(pvals))
        for i in domains:
            u = u + i.getUfe(pvals)
            
        return u

    def calcEfePreisach(self, esweep, domains, initState = None, plot = False):
        """
        Models domains as simple hystereons using ec, pr
        
        Parameters
        ----------
        esweep: np array of field values for which to calculate Pr
        domains: list containing all domain objects in the film
        initState: np array containing initial state of hysterons (-1 or 1)
        plot: bool, triggers plotting of generated hysteresis curve
            
        Returns
        -------
        p: np array, polarization charge values for film (C/cm^2)
        state: np array, final state of hysterons
        """        
        if initState == None:
            state = -np.ones(len(domains))
        else:
            state = initState
      
        sweepDir = np.gradient(esweep)        

        p = np.zeros(len(esweep))
        for j,e in enumerate(esweep):
            for i,d in enumerate(domains):
                if sweepDir[j] > 0:
                    if e >= d.ec+d.ebias:
                        state[i] = 1
                elif sweepDir[j] < 0:
                    if e <= -d.ec+d.ebias:
                        state[i] = -1
                # Need to sum actual charge rather than charge density
                p[j] = p[j] + d.pr*d.area*state[i] 
        
        # convert back into charge density        
#        p = (p+ esweep*self.thickness*self.c)/self.area
        p = p/self.area
        
        if plot:
            fig1 = plt.figure()
            fig1.set_facecolor('white')
            plt.cla()
            ax1 = fig1.add_subplot(111)
            ax1.set_title('Presiach Modeled Hysteresis')
            datacursor(ax1.plot(esweep*1E-6, 1E6* p))
            ax1.set_xlabel('Electric Field (MV/cm)')
            ax1.set_ylabel('Polarization Charge ($\mu{}C/cm^2$)')
            
        return p, state

    def uPlot(self, pVals, uFe):
        """
        Plots U vs P for landau film.
        
        Parameters
        ----------
        pVals: 1d np array of polarization charge values
        uFe: 1d np array of energy densities calculated at xVals.
            
        Returns
        -------
        n/a
        """
        
        fig1 = plt.figure()
        fig1.set_facecolor('white')
        plt.cla()
        ax1 = fig1.add_subplot(111)
        datacursor(ax1.plot(pVals*1E6, uFe))
        ax1.set_xlabel('Polarization Charge, P (uC/cm^2)')
        ax1.set_ylabel('Energy, U')

    def ePlot(self, pVals, eFe, ec= None, ebias = 0):
        """
        Plots E vs P for landau film.
        
        Parameters
        ----------
        pVals: 1d np array of polarization charge values
        eFe: 1d np array of electric field calculated at xVals.
        ec: float, overlays dotted line at ec+ebias and -ec+ebias on plot
        ebias: float, defines ebias. Used only if ec defined
            
        Returns
        -------
        n/a
        """

            
        
        fig1 = plt.figure()
        fig1.set_facecolor('white')
        plt.cla()
        ax1 = fig1.add_subplot(111)
        datacursor(ax1.plot(eFe*1E-6, pVals*1E6))
        ax1.set_ylabel('Polarization Charge, P (uC/cm^2)')
        ax1.set_xlabel('Electric Field, MV/cm')
        if ec != None:
            e1 = (-ec-ebias)*1E-6
            e2 = (ec-ebias)*1E-6
            ax1.plot([e1,e1],[np.min(pVals)*1E6,np.max(pVals)*1E6],'r--')
            ax1.plot([e2,e2],[np.min(pVals)*1E6,np.max(pVals)*1E6],'r--')
    
class LandauSimple(LandauFilm):
    """
    Simplified implementation of Landau model. See LandauBase for more info.
    """
    def __init__(self, a = 0, **kwargs):
        LandauFilm.__init__(self, **kwargs) 
        self.a = a

    def aCalc(self, c = None, t = None):
        if c is None:
            c = self.c
        if t is None:
            t = self.thickness
        a = -1/(4*c*t) # cm/F
        return a
         
class LandauFull(LandauFilm):
    """
    Full implementation of Landau model. See LandauBase for more info.
    """
    
    def __init__(self, a0 = 0, T0 = 0, rho = 0, **kwargs):
        LandauFilm.__init__(self, **kwargs)
        self.a0 = a0
        self.T0 = T0
        self.rho = rho
        
    def rhoCalc(self, files):
        """
        IN DEVELOPMENT - needs further testing
        
        Calculates a viscosity coefficient for the landau film given a list
        of tf1000 DHM measurement CSV files, with the DHM measurements 
        taken at different frequencies

        Parameters
        ----------
        files : array_like of HysteresisData files.
        
        Returns
        -------
        n/a - not implemented yet 
        """
        # TODO: work on improving rho calculation (noise from C, leakage I)
        cComp = 0
        hystData = []
        pmax = []
        for f in files:
            data = hd.HysteresisData()
            data.tsvRead(f)
            hystData.append(data)
            pmax.append(np.max(data.polarization))
#            print (data.freq)
        
        pmax = np.asfarray(pmax)
        p = np.min(pmax)
#        print(p)
        dpdt = np.zeros(len(hystData))
        e = np.zeros(len(hystData))

               
        for i, d in enumerate(hystData):
            dt = d.time[1]-d.time[0]
            #print(dvdt[i],"\n", d.fileName)
            dvdt = (d.voltage[1]-d.voltage[0])/dt
            
            
            for j, q in enumerate(d.polarization):
                if j == 0:
                    next
                else:
                    if cComp == 1:
                        dvdt = (d.voltage[j]-d.voltage[j-1])/dt
                        d.current[j] = d.current[j] - self.c*dvdt
           
                    
                if q < p:
                    next
                elif q >= p:
                    dpdt[i] = (q - d.polarization[j+1])/dt
                    f = (p-d.polarization[j-1])/(q-d.polarization[j-1])
                    e[i] = d.field[j-1]*(1-f)+f*d.field[j]
#                    print (d.polarization[j-1],p,q, '    ',d.field[j-1],e[i],d.field[j])
                    break
#            d.hystPlot()
            dvdt_filtered = d.lpFilter(np.diff(d.voltage)/d.dt)
#            d.fftPlot(np.diff(d.voltage)/d.dt)
#            d.fftPlot(dvdt_filtered)

        
        fig1 = plt.figure()
        fig1.set_facecolor('white')
        plt.cla()
        ax1 = fig1.add_subplot(111)
        datacursor(ax1.plot(dpdt, e))
        ax1.set_xlabel('dP/dt')
        ax1.set_ylabel('dE')   

    def a0Calc(self, files, leakageComp=False, leakagefiles= None):
        """
        IN DEVELOPMENT - needs further testing
        
        Calculates an a0 for the landau film given a list
        of tf1000 DHM measurement CSV files, with the DHM measurements 
        taken at different frequencies  
        
        Parameters
        ----------
        files : array_like of HysteresisData files.
        leakageComp: bool, tell whether to subtract leakage current from
            data before performing analysis. Experimental feature
        leakagefiles: array_like of leakage current data. 
            Must have a leakage file for each temperature represented in files.
        
        Returns
        -------
        n/a - not implemented yet       
        """
        #FIXME: a0 is an order of magnitude too high - need better temp data
        cComp = 0
        hystData = []
        pmax = []
        for f in files:
            data = hd.HysteresisData()
            data.tsvRead(f)
            if leakageComp: # matches LCM to DHM if leakage comp to be done
                if leakagefiles:
                    r = re.compile('.* '+re.escape(data.temp)+'C.*')
                    for j in leakagefiles:
                        match = r.match(j)
                        if match:
                            data.lcmRead(j)
                            data.lcmFit()
                            data.leakageCompensation()
                        else:
                            next
                else:
                    raise UserWarning('Leakage compensation selected but no leakage files defined. Compensation cannot be performed.')
            
            
            hystData.append(data)
            pmax.append(np.max(data.polarization))
        
        pmax = np.asfarray(pmax)
        p = np.min(pmax)
#        print(p)
        dpdt = np.zeros(len(hystData))
        e = np.zeros(len(hystData))
        temp = np.zeros(len(hystData))

               
        for i, d in enumerate(hystData):
            temp[i] = d.temp
            dt = d.time[1]-d.time[0]
            #print(dvdt[i],"\n", d.fileName)
            dvdt = (d.voltage[1]-d.voltage[0])/dt
            
            
            for j, q in enumerate(d.polarization):
                if j == 0:
                    next
                else:
                    if cComp == 1:
                        dvdt = (d.voltage[j]-d.voltage[j-1])/dt
                        d.current[j] = d.current[j] - self.c*dvdt
           
                    
                if q < p:
                    next
                elif q >= p:
                    dpdt[i] = (q - d.polarization[j+1])/dt
                    f = (p-d.polarization[j-1])/(q-d.polarization[j-1])
                    e[i] = d.field[j-1]*(1-f)+f*d.field[j] # linear interp
#                    print (d.polarization[j-1],p,q, '    ',d.field[j-1],e[i],d.field[j])
                    break
#            d.hystPlot()
            dvdt_filtered = d.lpFilter(np.diff(d.voltage)/d.dt)
#            d.fftPlot(np.diff(d.voltage)/d.dt)
#            d.fftPlot(dvdt_filtered)

        a0fit = np.polyfit(temp,e,1)
        a0fit_fn = np.poly1d(a0fit)
        a0 = a0fit[0]/(2*p) # cm/(F*K)
        Tc = 1/(4*self.c*a0*self.thickness)+300 # 300K temp at which C calced
#        print (a0,Tc)
        
        fig1 = plt.figure()
        fig1.set_facecolor('white')
        plt.cla()
        ax1 = fig1.add_subplot(111)
        datacursor(ax1.plot(temp, e, 'o', temp, a0fit_fn(temp)))
        ax1.set_title('a0 = {:0.3e}'.format(a0))
        ax1.set_xlabel('T (C)')
        ax1.set_ylabel('E (V/cm)')   
        
class LandauDomain():
    """
    IN DEVELOPMENT - includes different experimental solving methods for 
        landau parameters
    
    Represents individual ferroelectric domains in the film.
    Used to calculate domain-specific beta parameter for multidomain simulation.
    aTerm is alpha or alpha*(T-Tc) coefficient, depending on film model used.
    """
    def __init__(self, landau, area, ec, ebias, aTerm = 0, b = 0, g = 0):
        self.pr = landau.pr
        self.t = landau.thickness
        self.c = landau.c
        self.ec = ec
        self.ebias = ebias
        self.a = aTerm        
        self.b = b
        self.g = g
        self.area = area

    def eqns(self, p):
        a, b, g = p
#        print (a,b,g,self.c,self.t,self.pr,self.ec,self.ebias)
        eq1 = self.ec-self.ebias+1*a*self.pr+1*b*self.pr**3+1*g*self.pr**5
        eq2 = 2*a*self.pr+4*b*self.pr**3+6*g*self.pr**5+self.ebias+self.ec
        eq3 = (2*a+12*b*self.pr**2+30*g*self.pr**4)-1/(self.c*self.t)/self.area
#        print (eq1, eq2, eq3)
        eq4 = 2*a+12*b*self.pr**2+30*g*self.pr**4
#        if (a<0 and b>0 and g>0):
#            return(eq1, eq2, eq3)
#        else:
#            return(1E4+a,1E4+a,1E4+a)
#        if(eq4 > 0 and a<0):
#            return(eq1, eq2, eq3)
#        else:
#            return(1E8,1E8,1E8)
#        return(eq1, eq2, eq3)

    def eqns1(self, p):
        a, b, g = p
#        print (a,b,g,self.pr,self.ec,self.ebias)
        eq1 = (self.ec-self.ebias+1*a*self.pr+1*b*self.pr**3+1*g*self.pr**5)**2
        eq2 = (2*a*self.pr+4*b*self.pr**3+6*g*self.pr**5+self.ebias+self.ec)**2
        eq3 = ((2*a+12*b*self.pr**2+30*g*self.pr**4)-1/(self.c*self.t)/self.area)**2
#        print (eq1, eq2, eq3)
        

        return(eq1, eq2, eq3)
    
    def con(self,p):
        """
        Defines parameter constraints.
        """
        a, b, g = p
        eq4 = 2*a+12*b*self.pr**2+30*g*self.pr**4
        return eq4
        
    def parmCalc(self):
        guess = np.asarray((-2/self.pr**2,1/(2*self.pr**4),1/self.pr**6))
#        self.a,self.b,self.g = fsolve(self.eqns, guess)


#        print (guess)
        parms = minimize(self.eqns1,
                         x0 = np.asarray((-2/self.pr**2,1/(2*self.pr**4),1/self.pr**6)),
                         bounds = ((None,0),(0,None),(0,None)),
#                         constraints = ({'type':'ineq', 'fun':self.con}),
                         method = 'COBYLA')     
#        kwargs = {"method": "COBYLA",
#                  "bounds" : ((None,0),(0,None),(0,None)),
#                  "constraints" : ({'type':'ineq', 'fun':self.con})}
#        parms = basinhopping(self.eqns1,
#                             x0 = guess,
#                             niter = 100,
#                             minimizer_kwargs = kwargs,
#                             stepsize = self.pr,
#                             T = 1/self.pr**2)   
        self.a,self.b,self.g = parms.x

    def parmFit(self,plot = False):
        guess = np.asarray((-2/self.pr**2,1/(2*self.pr**4),1/self.pr**6))
        aGuess, bGuess, gGuess = guess
        guessRes = 26
        
        avals = np.linspace(aGuess/1E3,aGuess*1E3,guessRes)
        bvals = np.linspace(bGuess/1E3,bGuess*1E3,guessRes)
        gvals = np.linspace(gGuess/1E4,gGuess*1E4,guessRes)
        
        err = np.empty([guessRes,guessRes,guessRes])
        for i,a in enumerate(avals):
            for j,b in enumerate(bvals):
                vals = np.asfarray(self.eqns1((a,b,gvals)))
                err[i,j,:] = np.sum(vals**2,0)
        
        if plot:
            x = np.empty(guessRes**3)
            y = np.empty(guessRes**3)
            z = np.empty(guessRes**3)
            d = np.empty(guessRes**3)
            for i,r in enumerate(err.flatten()):
                xcord = i % guessRes
                ycord = (i // guessRes) % guessRes
                zcord = i // guessRes**2
                
                x[i] = avals[xcord]
                y[i] = bvals[ycord]
                z[i] = gvals[zcord]
                d[i] = r
            
            
            fig1 = plt.figure()
    #        colormap = plt.cm.viridis # uniform greyscale for printing
            colormap = plt.cm.nipy_spectral # diverse color for colorblindness
            plt.clf()
            ax1 = fig1.add_subplot(111, projection='3d')
#            ax1.set_xscale('log')
#            ax1.set_yscale('log')
#            ax1.set_zscale('log')
            p = ax1.scatter(np.abs(x),y,z,c=d, alpha = 0.5, s = 15, lw = 0, cmap=colormap,norm=Normalize() )
            ax1.set_xlabel(r"-$\alpha{}$ Guess")
            ax1.set_ylabel(r'$\beta{}$ Guess')
            ax1.set_zlabel(r'$\gamma{}$ Guess')
            plt.colorbar(p,ax=ax1)

        
    def getUfe(self, pvals):
        """
        Parameters
        ----------
        pvals: np array of p values for which to solve ufe
        
        Returns
        -------
        np array of ufe values
        """
        return self.a*pvals**2+self.b*pvals**4+self.g*pvals**6-self.ebias*pvals
    
    def getEfe(self,pvals):
        """
        Parameters
        ----------
        pvals: np array of p values for which to solve efe
        
        Returns
        -------
        np array of efe values
        """
        return 2*self.a*pvals+4*self.b*pvals**3+6*self.g*pvals**5-self.ebias

def main():
    plt.close('all')

    freqdir = r"D:\Google Drive\Ferroelectric Research\FE_20162017\Testing\Karine NaMLab MFM samples\H9\H9_x9y4_1e4_freq"
    freqfiles = hd.dirRead(freqdir)
    hfo2 = LandauFull()
    
    hfo2.c = hfo2.cCalc(freqfiles, plot=1)
#    hfo2.rhoCalc(freqfiles)
    
#    tempdir = r"D:\Google Drive\Ferroelectric Research\FE_20162017\Testing\Karine NaMLab MFM samples\H9\H9_x9y4_1e4_S3_temps"
#    tempfiles = hd.dirRead(tempdir)
#    templkgdir = r"D:\Google Drive\Ferroelectric Research\FE_20162017\Testing\Karine NaMLab MFM samples\H9\H9_x9y4_1e4_S3_tempslkg"
#    templkgfiles = hd.dirRead(tempdir)
    
#    hfo2.a0 = hfo2.a0Calc(tempfiles, 0, templkgfiles)
    
#    RTfreqDir = r"D:\Google Drive\Ferroelectric Research\FE_20162017\Testing\RT WhiteA\RTWhiteAFreq"
#    RTfreqData = hd.dirRead(RTfreqDir)
#    RTfreq100hz = r"D:\Google Drive\Ferroelectric Research\FE_20162017\Testing\RT WhiteA\RTWhiteAFreq\RT WhiteA 100Hz 8V 1Average Table1.tsv"
#
#    RT100data = hd.HysteresisData()
#    RT100data.tsvRead(RTfreq100hz)
#    RT100data.hystPlot
#    
#    RTWhiteFilm = LandauSimple(thickness = 255E-7, area=1E-4)
#    RTWhiteFilm.c = RTWhiteFilm.cCalc(RTfreqData, plot = 1)
#    RT100compensated, RTWhiteFilm.pr = RTWhiteFilm.cCompensation(RT100data, plot = 1)
#
#    forcFile = "D:\Google Drive\Ferroelectric Research\FE_20162017\Testing\FORC\RTWhiteAFORC\RT WhiteA 0Hz 7V 1Average Table7.tsv"
#    RTWhiteAFORC = hd.HysteresisData(area=1E-4, thickness=255E-7)
#    RTWhiteAFORC.tsvRead(forcFile)
#    RTWhiteAFORC.hystPlot(plotE=1)
##    RTWhiteA.lcmPlot()
#    e, er, probs = RTWhiteAFORC.forcCalc(plot = False)
#    
#    # 1:1 grain aspect ratio
#    nDomains = int(RTWhiteAFORC.area/RTWhiteAFORC.thickness**2)
#    
#    domains = RTWhiteFilm.domainGen(e, er, probs, n=100, plot = False)
#    for i in domains:
#        i.parmCalc()
#    pvals = np.linspace(-32E-6,32E-6,100)
##    u = domains[0].getUfe(pvals)
##    u1 = RTWhiteFilm.getUfe(pvals,domains)
##    RTWhiteFilm.uPlot(pvals,u1)
#    e1 = domains[0].getEfe(pvals)
#    
#    esweep = np.linspace(-0.3E6,0.3E6,num=1000)
#    esweep = np.append(esweep,esweep[::-1])
#    RTWhiteFilm.calcEfePreisach(esweep, domains, plot=1)


#    RTWhiteFilm.ePlot(pvals,e1,domains[0].ec,domains[0].ebias)
#    RTWhiteFilm.ePlot(pvals,e2)
    
#    RTWhiteFilm.rhoCalc(RTfreqData)
    



#    #filename = "D:\Google Drive\Ferroelectric Research\FE_20162017\Testing\FORC\RTWhiteAFORC\RT WhiteA 0Hz 7V 1Average Table7.tsv"
#    filename = freqfiles[1]
#    print(filename)
##    filename = "D:\Google Drive\Ferroelectric Research\FE_20162017\Testing\Karine NaMLab MFM samples\H9\H9_x9y4_1e4_forc\H9 die (9,4) 0Hz 4V 1Average Table6.tsv"
##    lcmfile = "D:\Google Drive\Ferroelectric Research\FE_20162017\Testing\Karine NaMLab MFM samples\H9\H9_x9y4_1e4sq\H9 die (9,4) 2s step Table3.tsv"
#    RTWhiteA = hd.HysteresisData()
#    RTWhiteA.tsvRead(filename)
#    RTWhiteA.lcmRead(lcmfile)
#    RTWhiteA.lcmFit()
#    RTWhiteA.leakageCompensation()
#    RTWhiteA.hystPlot()
#    RTWhiteA.fftPlot(RTWhiteA.dt,RTWhiteA.polarization)
#    RTWhiteA.lcmPlot()
#    RTWhiteA.forcPlot()
    
#    FeFETD2 = HysteresisData()
#    FeFETD2.tsvRead(r'D:\Google Drive\Ferroelectric Research\FE_20152016\SeniorDesign\Testing\FETester\NaMLab_FeFETD2_die24_100x100_450V_data.csv')
#    FeFETD2.hystPlot()

#    FeFETD2 = HysteresisData()
#    FeFETD2.tsvRead(r'D:\Google Drive\Ferroelectric Research\FE_20142015\TF-1000\Measurements\RadiantFEcaps_MIM_DiscreteCap\tool_tests\10uF discrete cap 100Hz 5V.tsv')
#    FeFETD2.hystPlot()

if __name__ == "__main__": # Executes main automatically if this file run directly rather than imported
    main()