#!/usr/bin/env python3
"""
Created on Fri May 26 12:50:08 2017

@author: Jackson

Tests fft_plot and bandstop_filter functions of HysteresisData
"""

import matplotlib.pyplot as plt
from os.path import join, dirname, realpath
from context import models as lf
from context import data as hd

plt.close('all')

sampledir = join(dirname(realpath(__file__)), 'testData', 'hfo2_MFM')
tempdir = join(sampledir, 'H9_x9y4_1e4_S3_temps')
tempfiles = hd.dir_read(tempdir)
templkgdir = join(sampledir, 'H9_x9y4_1e4_S3_tempslkg')
templkgfiles = hd.dir_read(templkgdir)

datafile = join(sampledir, 'H9_x9y4_1e4_S3_temps', 'H9 die (9,4) S3 79C 100Hz 3V 1Average Table3.tsv')
lkgfile = join(sampledir, 'H9_x9y4_1e4_S3_tempslkg', 'H9 die (9,4) S3 79C 2s step Table2.tsv')

data = hd.HysteresisData()
data.tsv_read(datafile)

ldata = hd.LeakageData()
ldata.lcm_read(lkgfile)

data.hyst_plot()
ldata.lcm_fit()
ldata.lcm_plot()
compData = data.leakage_compensation(ldata)
compData.hyst_plot()
