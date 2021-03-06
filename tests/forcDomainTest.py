#!/usr/bin/env python3
"""
Created on Mon Jun 12 10:45:02 2017

@author: Jackson
"""

import matplotlib.pyplot as plt
import numpy as np
from os.path import join, dirname, realpath
from context import models as lf
from context import data as hd

plt.close('all')


sampledir = join(dirname(realpath(__file__)), 'testData', 'RT WhiteA')
RTfreqDir = join(sampledir, 'RTWhiteAFreq')
RTfreqFiles = hd.dir_read(RTfreqDir)
RTfreqData = hd.list_read(RTfreqFiles)
RTfreq100hz = join(RTfreqDir, 'RT WhiteA 100Hz 8V 1Average Table1.tsv')

RT100data = hd.HysteresisData()
RT100data.tsv_read(RTfreq100hz)
RT100data.hyst_plot()

RTWhiteFilm = lf.LandauSimple(thickness=255E-7, area=1E-4)
RTWhiteFilm.c = RTWhiteFilm.c_calc(RTfreqData)
RT100compensated, RTWhiteFilm.pr = RTWhiteFilm.c_compensation(RT100data)

RT100compensated.hyst_plot()

forc_file = join(sampledir, 'RTWhiteAFORC', 'RT WhiteA 0Hz 7V 1Average Table7.tsv')
RTWhiteAFORC = hd.HysteresisData(area=1E-4, thickness=255E-7)
RTWhiteAFORC.tsv_read(forc_file)
RTWhiteAFORC.hyst_plot(plot_e=1)
RTWhiteAFORC.time_plot()
e, er, probs = RTWhiteAFORC.forc_calc(plot=True)

domains = RTWhiteFilm.domain_gen(e, er, probs, n=100, plot=False)

esweep = np.linspace(-0.28E6, 0.28E6, num=1000)
esweep = np.append(esweep, esweep[::-1])
RTWhiteFilm.calc_efe_preisach(esweep, domains, plot=1)