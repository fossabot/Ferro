#!/usr/bin/env python3
"""
HysteresisData class with functions for reading in and plotting hysteresis data.

TODO: move TF-1000 parsing into python, auto-read thickness & freq from metadata

@author: Jackson Anderson, Rochester Institute of Technology jda4923@rit.edu
"""
from warnings import warn
import re
import copy  # used for creating Ilkg compensated copies of exp data
from os import listdir
from os.path import join, isfile
import matplotlib.pyplot as plt
import numpy as np
import csv
from mpldatacursor import datacursor
from scipy.optimize import curve_fit
from scipy import signal
from scipy.ndimage import filters as flt


# matplotlib.rcParams.update({'font.size': 16})

def leakage_func(x, a, b, c, d, e, f, g):
    return a * (x - g) ** 5 + b * (x - g) ** 4 + c * (x - g) ** 3 + d * (x - g) ** 2 + e * (x - g) + f


#    return np.sign(x-d)*a*(np.exp(b*(np.abs(x-d))**c)-1)+np.log(e)

def dir_read(path):
    files = []
    r = re.compile('.*\.tsv$')
    files = [join(path, f) for f in listdir(path) if (isfile(join(path, f)) and r.match(f))]
    return files


def list_read(files, leakagefiles=None, plot=False, **kwargs):
    """
    Reads in several hysteresis measurements and creates objects for them.
    
    Parameters
    ----------
    
    files : list
        Paths to tsv data files of hysteresis measurements
    
    leakagefiles : list 
        Paths to leakage data for files.
        If none, leakage compensation is not performed.
        
    plot: bool
        Triggers plotting of leakage data with fit.
        
    kwargs: args
        Arguements to pass to HysteresisData()
    
    Returns
    -------
    
    dataList : list
        HysteresisData objects created from files.
    """
    dataList = []
    for f in files:
        data = HysteresisData(**kwargs)
        data.tsv_read(f)
        if leakagefiles:
            r = re.compile('.*(_| )' + re.escape(str(data.temp)) + 'K.*')
            tempC = str(data.temp - 273)
            r2 = re.compile('.*(_| )' + re.escape(tempC) + 'C.*')
            noMatch = True
            for j in leakagefiles:
                match = r.match(j)
                match2 = r2.match(j)
                if match or match2:
                    noMatch = False
                    ldata = LeakageData()
                    ldata.lcm_read(j)
                    ldata.lcm_fit()
                    if plot: ldata.lcm_plot()
                    data = data.leakageCompensation(ldata)
                else:
                    next
            if noMatch:
                raise UserWarning('No leakage file found to match data. Compensation cannot be performed.')
        dataList.append(data)

    return dataList


def hyst_plot(data, legend=None, plotE=False):
    """
    Plots V vs P, V vs I, and time vs V given hysteresis measurement data.
    
    Parameters
    ----------
    data : list 
        HysteresisData objects to plot.
    legend : list 
        str labels corresponding to data.
    plotE : bool 
        If True plots E instead of P.
    
    Returns
    -------
    n/a
    """
    fig1 = plt.figure()
    fig1.set_facecolor('white')
    ax1 = fig1.add_subplot(211)
    ax2 = fig1.add_subplot(212)

    # creates unique color for each item
    colormap = plt.cm.viridis  # uniform greyscale for printing
    #    colormap = plt.cm.nipy_spectral # diverse color for colorblindness
    ax1.set_prop_cycle('c', [colormap(i) for i in np.linspace(0, .6, len(data))])
    ax2.set_prop_cycle('c', [colormap(i) for i in np.linspace(0, .6, len(data))])
    lines = []
    for d in data:
        if plotE:
            line = ax1.plot(1E-6 * d.field, 1E6 * d.polarization)
            lines.append(line[0])
            ax1.set_ylabel('Polarization Charge ($\mu{}C/cm^2$)')

            ax2.plot(1E-6 * d.field, 1E6 * d.current)
            ax2.set_xlabel('Electric Field (MV/cm)')
            ax2.set_ylabel('Current ($\mu{}A$)')

        else:
            line = ax1.plot(d.voltage, 1E6 * d.polarization)
            lines.append(line[0])
            ax1.set_ylabel('Polarization Charge ($\mu{}C/cm^2$)')

            ax2.plot(d.voltage, 1E6 * d.current)
            ax2.set_xlabel('Voltage (V)')
            ax2.set_ylabel('Current ($\mu{}A$)')
    if legend:
        box = ax1.get_position()
        ax1.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        box2 = ax2.get_position()
        ax2.set_position([box2.x0, box2.y0, box2.width * 0.8, box2.height])
        fig1.legend(lines, legend, loc='center right')


def ncv_plot(data, legend=None, plotE=False):
    """
    Plots dP/dV (capacitance) of PV data.
    
    Parameters
    ----------
    data : list 
        HysteresisData objects to plot.
    legend : list 
        str labels corresponding to data.
    plotE : bool 
        If True plots E instead of P.
    
    Returns
    -------
    n/a
    """
    fig1 = plt.figure()
    fig1.set_facecolor('white')
    ax1 = fig1.add_subplot(111)

    # creates unique color for each item
    colormap = plt.cm.viridis  # uniform greyscale for printing
    #    colormap = plt.cm.nipy_spectral # diverse color for colorblindness
    ax1.set_prop_cycle('c', [colormap(i) for i in np.linspace(0, .6, len(data))])
    lines = []
    for d in data:
        ncv = np.diff(d.polarization) / np.diff(d.voltage)
        ncv_v = 0.5 * (d.voltage[1:] + d.voltage[:-1])
        if plotE:
            line = ax1.plot(1E-6 * ncv_v / d.thickness, 1E6 * ncv)
            lines.append(line[0])
            ax1.set_xlabel('Electric Field (MV/cm)')
            ax1.set_ylabel('Capacitance ($\mu{}F/cm^2$)')


        else:
            line = ax1.plot(ncv_v, 1E6 * ncv)
            lines.append(line[0])
            ax1.set_xlabel('Voltage (V)')
            ax1.set_ylabel('Capacitance ($\mu{}F/cm^2$)')

    if legend:
        box = ax1.get_position()
        ax1.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        fig1.legend(lines, legend, loc='center right')


def lcm_plot(data, legend=None):
    """
    Plots leakage current as a function of voltage for a list of LeakageData.
    If parameters have been fit to data, will plot modeled leakage as well.
    
    Parameters
    ----------
    data : list 
        LeakageData objects to plot
    legend : list 
        Str labels corresponding to data
    
    Returns
    -------
    n/a
    """

    fig = plt.figure()
    fig.set_facecolor('white')
    plt.cla()
    ax = fig.add_subplot(111)

    # creates unique color for each item
    #    colormap = plt.cm.viridis # uniform greyscale for printing
    colormap = plt.cm.nipy_spectral  # diverse color for colorblindness
    ax.set_prop_cycle('c', [colormap(i) for i in np.linspace(0, 1, len(data))])

    lines = []
    for d in data:
        line = ax.plot(d.lcmVoltage, 1E6 * d.lcmCurrent)
        lines.append(line[0])
        if d.lcmParms != []:
            ax.plot(d.lcmVoltage, 1E6 * leakage_func(d.lcmVoltage, *d.lcmParms))
    ax.set_xlabel('Voltage (V)')
    ax.set_ylabel('Leakage Current ($\mu{}A$)')

    if legend:
        box = ax.get_position()
        ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        fig.legend(lines, legend, loc='center right')


class SampleData:
    def __init__(self, thickness=13E-7, area=1E-4, temperature=300):
        """
        Parameters
        ----------
        thickness : float
            Thickness of the sample in cm (used to calculate field)
            
        area: float
            Area of the sample in cm^2. This should match the area that was
            used to calculate polarization charge per unit area for the data.
            
        temperature: int
            Temperature (in Kelvin) at which the measurement was taken.
        
        Returns
        -------
        n/a
        """
        self.fileName = ''
        self.thickness = thickness  # cm
        self.area = area  # cm^2
        self.temp = temperature  # K


class HysteresisData(SampleData):
    def __init__(self, freq=100, **kwargs):
        """
        Inherits SampleData. See that class for info on thickness, area, 
        and temperature
        
        Parameters
        ----------
        thickness : float
            Thickness of the sample in cm (used to calculate field)
            
        area: float
            Area of the sample in cm^2. This should match the area that was
            used to calculate polarization charge per unit area for the data.
            
        temperature: int
            Temperature (in Kelvin) at which the measurement was taken.
        
        Returns
        -------
        n/a
        """
        SampleData.__init__(self, **kwargs)
        self.time = []
        self.voltage = []
        self.current = []
        self.polarization = []
        self.capacitance = []
        self.freq = freq  # Hz
        self.dt = 0

    def tsv_read(self, filename):
        """
        Imports TSV measurement data previously parsed by tfDataTSV_v4.pl. 
        For use with TF-1000 hysteresis measurement data.
        
        Parameters
        ----------
        filename : str
            tsv file (with path) to open and parse. Stores data as 
            the associated HysteresisData object's attributes
        
        Returns
        -------
        n/a
        """
        self.fileName = filename

        r = re.compile('.*(_| )(\d+)C.*')
        try:
            self.temp = int(r.match(filename).group(2)) + 273
        except AttributeError:
            try:
                r = re.compile('.*(\d+)K.*')
                self.temp = int(r.match(filename).group(2))
            except AttributeError:
                print("No temperature specified. Defaulting to 300K")
                next

        r = re.compile('.*(_| )(\d+)Hz.*')
        try:
            self.freq = r.match(filename).group(2)
        except AttributeError:
            print("No frequency specified. Defaulting to 100Hz")
            next

        with open(filename, 'r') as data:
            headerLine = data.readline()  # skips first line and saves it for later
            data = csv.reader(data, delimiter='\t')

            for row in data:
                if row:  # ignores blank lines
                    self.time.append(row[0])
                    self.voltage.append(row[1])
                    self.current.append(row[3])
                    self.polarization.append(row[4])

        self.time = np.asfarray(self.time)
        self.voltage = np.asfarray(self.voltage)
        self.current = np.asfarray(self.current)  # A
        self.polarization = 1E-6 * np.asfarray(self.polarization)  # C/cm^2
        self.field = self.voltage / (self.thickness)  # V/cm
        self.dt = self.time[1] - self.time[0]  # s

    def leakage_compensation(self, leakageData):
        """
        Removes leakage current contribution from hysteresis data using 
        model fit to lcm data.

        Parameters
        ----------
        leakageData: LeakageData 
            Object to use in compensation.
        
        Returns
        -------
        compData: HysteresisData
            Deep copy of self with leakage current removed.
        """
        ld = leakageData

        if ld.lcmParms == []:
            warn("Please run lcm_fit on the Leakage Data before attempting compensation.",
                 RuntimeWarning)
            return self

        compData = copy.deepcopy(self)  #

        for j, i in enumerate(compData.current):
            ilkg = leakage_func(self.voltage[j], *ld.lcmParms)
            compData.current[j] = i - ilkg

        compData.current = compData.current - np.mean(compData.current)

        testpol = np.zeros(len(compData.current))
        for i in range(np.size(testpol)):
            if i == 0:
                next
            else:
                testpol[i] = testpol[i - 1] + compData.current[i] * self.dt / self.area

        offset = max(testpol) - (max(testpol) - min(testpol)) / 2

        testpol = testpol - offset
        compData.polarization = testpol

        return compData

    def bandstop_filter(self, y, freqs=[50, 70], plot=False):
        """
        Experimental
        
        Removes high freq noise from measurement data.
        Filter edge set to 2 times measurement switching frequency.
        Includes some code from scipy.signal.iirfilter example code.
        
        
        Parameters
        ----------
        y : array_like 
            The data to be filtered.
        freqs : list 
            The two freqs defining the edge of the bandstop filter.
        plot : bool
            If True, plots filter response
        
        Returns
        -------
        y : complex ndarray 
            The filtered input data (y). Returned in time domain.
        """
        N = len(y)

        f = np.fft.fftfreq(N, self.dt)  # cycles/sec
        f = 2 * np.pi * self.dt * f  # rad/sample

        b, a = signal.butter(1, freqs / (0.5 / self.dt), btype='bandstop')
        w, h = signal.freqz(b, a, f)

        p = signal.filtfilt(b, a, y)

        if plot:
            fig = plt.figure()
            fig.set_facecolor('white')
            ax = fig.add_subplot(111)
            ax.plot(w / np.pi * (0.5 / self.dt), 20 * np.log10(abs(h)), 'o')
            ax.set_xscale('log')
            ax.set_xlabel('Frequency [radians / second]')
            ax.set_ylabel('Amplitude [dB]')
            ax.axis((float(self.freq), 0.5 / self.dt, -100, 10))
            ax.grid(which='both', axis='both')

        return p

    def fft_plot(self, y):
        """
        Takes fft of data and plots in frequency domain.
         
        Parameters
        ----------
        y : np array 
            Data to be plotted
        
        Returns
        -------
        n/a
        """
        N = len(self.time)

        pf = np.fft.fft(y)
        tf = np.linspace(0, 1 / (2 * self.dt), N // 2)

        fig1 = plt.figure()
        fig1.set_facecolor('white')
        plt.cla()
        ax1 = fig1.add_subplot(111)
        ax1.set_title(str(self.freq) + ' Hz ' + str(self.temp) + ' K')
        datacursor(ax1.plot(tf, 2.0 / N * np.abs(pf[0:N // 2])))
        ax1.set_xlabel('frequency')

    #        ax1.set_ylabel('Polarization Charge ($\mu{}C/cm^2$)')

    def hyst_plot(self, plotE=False):
        """
        Plots V vs P, V vs I, and time vs V given hysteresis measurement data.
        
        Parameters
        ----------
        plotE : bool
            If True plots E instead of P
        """
        if plotE:
            fig1 = plt.figure()
            fig1.set_facecolor('white')
            ax1 = fig1.add_subplot(211)
            ax1.set_title(str(self.freq) + ' Hz ' + str(self.temp) + ' K')
            datacursor(ax1.plot(1E-6 * self.field, 1E6 * self.polarization))
            ax1.set_ylabel('Polarization Charge ($\mu{}C/cm^2$)')

            ax2 = fig1.add_subplot(212)
            datacursor(ax2.plot(1E-6 * self.field, 1E6 * self.current))
            ax2.set_xlabel('Electric Field (MV/cm)')
            ax2.set_ylabel('Current ($\mu{}A$)')

        else:
            fig1 = plt.figure()
            fig1.set_facecolor('white')
            ax1 = fig1.add_subplot(211)
            ax1.set_title(str(self.freq) + ' Hz ' + str(self.temp) + ' K')
            datacursor(ax1.plot(self.voltage, 1E6 * self.polarization))
            ax1.set_ylabel('Polarization Charge ($\mu{}C/cm^2$)')

            ax2 = fig1.add_subplot(212)
            datacursor(ax2.plot(self.voltage, 1E6 * self.current))
            ax2.set_xlabel('Voltage (V)')
            ax2.set_ylabel('Current ($\mu{}A$)')

    def time_plot(self):
        """
        Plots forced voltage and measured current vs. time on same plot
        """
        fig2 = plt.figure()
        fig2.set_facecolor('white')
        plt.clf()
        ax4 = fig2.add_subplot(111)
        ax4.plot(self.time, self.voltage, '--')
        ax4.set_xlabel("time (s)")
        ax4.set_ylabel("Voltage (V)")
        ax41 = ax4.twinx()
        ax41.plot(self.time, self.current * 1E6)
        ax41.set_ylabel("Current ($\mu{}A$)")

    def dvdt_plot(self):
        """
        Plots abs(dvdt) of a measurement. 
        Can be used to investigate noise in capacitance extraction.
        """

        dvdt = np.abs(np.diff(self.voltage) / self.dt)
        avg = np.mean(dvdt)

        fig1 = plt.figure()
        fig1.set_facecolor('white')
        plt.cla()
        ax1 = fig1.add_subplot(111)
        ax1.set_title(self.freq + ' Hz')
        datacursor(ax1.plot(dvdt, 'r.'))
        ax1.plot([0, len(dvdt)], [avg, avg], 'k--', linewidth=2)
        ax1.set_xlabel('count')
        ax1.set_ylabel('abs(dv/dt) (V/s)')

    def ncv_plot(self, plotE=False):
        """
        Plots dP/dV (capacitance) of PV data.
        
        Parameters
        ----------
        plotE : bool 
            If True plots E instead of P.
        
        Returns
        -------
        n/a
        """
        fig1 = plt.figure()
        fig1.set_facecolor('white')
        ax1 = fig1.add_subplot(111)

        ncv = np.diff(self.polarization) / np.diff(self.voltage)
        ncv_v = 0.5 * (self.voltage[1:] + self.voltage[:-1])
        if plotE:
            ax1.plot(1E-6 * ncv_v / self.thickness, 1E6 * ncv)
            ax1.set_xlabel('Electric Field (MV/cm)')
            ax1.set_ylabel('Capacitance ($\mu{}F/cm^2$)')


        else:
            ax1.plot(ncv_v, 1E6 * ncv)
            ax1.set_xlabel('Voltage (V)')
            ax1.set_ylabel('Capacitance ($\mu{}F/cm^2$)')

    def forc_calc(self, plot=False, linear=True,
                  filtIter=None, filtDim=[1, 1]):
        """
        Finds minima/maxima in voltage data, cuts down data to only reversal 
        curves, interpolates data onto a linear grid using griddata, and 
        makes contour plot for FORC measurements. 
        
        Note that griddata uses the natgrid library. If you are on windows and
        don't have a visual studio c++ compiler for setup.py, pre-built wheels 
        found at http://www.lfd.uci.edu/~gohlke/pythonlibs/#natgrid.
        (pip install the wheel file directly).
        
        You can also use linear interpolation instead.
        
        Parameters
        ----------
            plot : bool
                Turns plotting of results on if set to True
            linear : bool 
                Switches to linear interpolation
            filtIter : int
                Number of rolling average filter iterations to apply to the 
                mixed partial derivative of p.
            filtDim : len 2 sequence of ints
                Size of filter for E & Er axes.
            
        Returns
        ----------
            uniformE : 1d np array 
                E values that correspond to prob
            uniformEr : 1d np array
                Er values that correspond to prob
            prob : 2d numpy array
                Prob distribution of grains for given E,Er
        """

        minimaIndex = []
        maximaIndex = []
        for i, v in enumerate(self.voltage):
            if i == 0:
                continue
            elif i == len(self.voltage) - 2:
                break
            if (v < self.voltage[i - 1]) & (v < self.voltage[i + 1]):
                minimaIndex.append(i)
            if (v > self.voltage[i - 1]) & (v > self.voltage[i + 1]):
                maximaIndex.append(i)

        if len(minimaIndex) < 2:
            raise ValueError("Could not find two minima for FORC calculation. Aborting.")

        vrFORC = []
        vFORC = []
        pFORC = []
        for i, v in enumerate(minimaIndex):
            vrFORC.extend([self.voltage[v - 1]] * (maximaIndex[i + 1] - v))
            vFORC.extend(self.voltage[v:maximaIndex[i + 1]])
            pFORC.extend(self.polarization[v:maximaIndex[i + 1]])

        eFORC = np.asfarray(vFORC) / (self.thickness)  # V/cm
        erFORC = np.asfarray(vrFORC) / (self.thickness)  # V/cm

        uniformE = np.linspace(eFORC.min(), eFORC.max(), 200)
        uniformEr = np.unique(np.sort(erFORC))
        uniformV = np.linspace(np.asfarray(vFORC).min(), np.asfarray(vFORC).max(), 200)
        uniformVr = np.unique(np.sort(np.asfarray(vrFORC)))

        if linear:
            grid = plt.mlab.griddata(eFORC, erFORC, pFORC, uniformE, uniformEr, 'linear')
        else:
            grid = plt.mlab.griddata(eFORC, erFORC, pFORC, uniformE, uniformEr)
        dE, dEr = np.gradient(grid, uniformVr[1] - uniformVr[0], uniformV[1] - uniformV[0])
        dEdE, dEdEr = np.gradient(dE, uniformVr[1] - uniformVr[0], uniformV[1] - uniformV[0])
        if filtIter != None:
            mask = np.ma.getmask(dEdEr)  # store mask for later
            dEdEr = dEdEr.filled(0)  # fill mask to prevent filter NaN errors
            for i in range(filtIter): dEdEr = flt.uniform_filter(dEdEr, filtDim)
            dEdEr = np.ma.masked_where(mask, dEdEr)  # reapply mask
        prob = abs(dEdEr) / np.sum(abs(dEdEr))  # normalize for prob dist

        if plot:
            fig4 = plt.figure()
            fig4.set_facecolor('white')
            plt.clf()
            ax4 = fig4.add_subplot(111)
            plt.set_cmap('jet')
            #            FORCplot = ax4.contourf(uniformV,uniformVr,1E6*-dEdEr,75)
            FORCplot = ax4.contourf(1E-6 * uniformE, 1E-6 * uniformEr, prob, 75)
            cbar = plt.colorbar(FORCplot)
            #        cbar.formatter.set_scientific(True)
            cbar.update_ticks()
            cbar.set_label(r'Probability')
            plt.ticklabel_format(style='sci', axis='x', scilimits=(-2, 3))
            plt.ticklabel_format(style='sci', axis='y', scilimits=(-2, 3))
            ax4.set_xlabel("E (MV/cm)")
            ax4.set_ylabel("$E_r$ (MV/cm)")
            ax4.set_title('FORC Plot')
            #            ax4.plot([uniformVr[0],uniformVr[-1]],[uniformVr[0],uniformVr[-1]],'k-')

            fig5 = plt.figure()
            fig5.set_facecolor('white')
            plt.clf()
            ax5 = fig5.add_subplot(111)
            ax5 = plt.scatter(vFORC, np.asfarray(pFORC) * 1E6, c=vrFORC, alpha=0.25)
            plt.xlabel("$V (V)$")
            plt.ylabel('$P_r (\mu{}C/cm^2)$')
            cb = plt.colorbar(ax5)
            cb.set_label('$V_r$')
            plt.title('$\\rho{}^-$ as Used for FORC Plot')

            fig5 = plt.figure()
            fig5.set_facecolor('white')
            plt.clf()
            ax5 = fig5.add_subplot(111)
            ax5 = plt.scatter(eFORC * 1E-6, np.asfarray(pFORC) * 1E6, c=erFORC * 1E-6, alpha=0.25)
            plt.xlabel("E (MV/cm)")
            plt.ylabel('$P_r (\mu{}C/cm^2)$')
            cb = plt.colorbar(ax5)
            cb.set_label("$E_r$ (MV/cm)")
            plt.title('$\\rho{}^-$ as Used for FORC Plot')

        return uniformE, uniformEr, prob


class LeakageData(SampleData):
    def __init__(self, **kwargs):
        SampleData.__init__(self, **kwargs)
        self.lcmVoltage = []
        self.lcmCurrent = []
        self.lcmParms = []

    def lcm_read(self, filename):
        """
        Imports TSV measurement data previously parsed by tfDataTSV_v5.pl
        For use with TF-1000 leakage current measurement data
        
        Parameters
        ----------
        filename : str
            tsv file (with path) to open and parse. Stores data as 
            the associated HysteresisData object's attributes
        
        Returns
        -------
        n/a
        """
        self.fileName = filename

        r = re.compile('.*(_| )(\d+)C.*')
        try:
            self.temp = int(r.match(filename).group(2)) + 273
        except AttributeError:
            try:
                r = re.compile('.*(_| )(\d+)K.*')
                self.temp = int(r.match(filename).group(2))
            except AttributeError:
                print("No temperature specified. Defaulting to 300K")
                next

        with open(filename, 'r') as data:
            headerLine = data.readline()  # skips first line and saves for later
            data = csv.reader(data, delimiter='\t')

            for row in data:
                if row:  # ignores blank lines
                    self.lcmVoltage.append(row[0])
                    self.lcmCurrent.append(row[1])

        self.lcmVoltage = np.asfarray(self.lcmVoltage)  # V
        self.lcmCurrent = self.area * 1E-6 * np.asfarray(self.lcmCurrent)  # A

    def lcm_fit(self, func=leakage_func,
                initGuess=np.array([2E-10, 2E-10, .8E-6, -1E-6, 1E-6, 0, -1])):
        """
        Attempts to fit parameters to leakage current, stores in hd object
        
        Parameters
        ----------
        func : function 
            Defines eqn to be used to fit data
        initGuess : np array of appropriate length to match func            
            Provides initial values for curve_fit
        Returns
        -------
        n/a
        """
        # FIXME: curve_fit has trouble converging with some data
        self.lcmParms, pcov = curve_fit(func, self.lcmVoltage,
                                        self.lcmCurrent, p0=initGuess)
        print('Fit Parms:', self.lcmParms)
        print('Std Dev:', np.sqrt(np.diag(pcov)))

    def lcm_plot(self, func=leakage_func):
        """ 
        Plots measured leakage current with fit data.
        """
        fig = plt.figure()
        fig.set_facecolor('white')
        plt.cla()
        ax = fig.add_subplot(111)
        #        datacursor(ax.plot(self.lcmVoltage,np.log(np.abs(self.lcmCurrent))))
        datacursor(ax.plot(self.lcmVoltage, 1E6 * self.lcmCurrent, 'o'))
        if self.lcmParms != []:
            #            ax.plot(self.lcmVoltage,np.log(np.abs(leakage_func(self.lcmVoltage,*self.lcmParms))))
            ax.plot(self.lcmVoltage, 1E6 * func(self.lcmVoltage, *self.lcmParms))
        ax.set_xlabel('Voltage (V)')
        ax.set_ylabel('Leakage Current ($\mu{}A$)')


def main():
    plt.close("all")


if __name__ == "__main__":  # Executes main automatically if this file run directly rather than imported
    main()
