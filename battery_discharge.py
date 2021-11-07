"""
Script: battery_discharge.py
Writen by: Mike Fikes
Original TSP version written by: Keithley Applications Engineering (Al Ivons)

***********************************************************
*** Copyright 2017 Tektronix, Inc.                      ***
*** See www.tek.com/sample-license for licensing terms. ***
***********************************************************

Revision History:
        * Originally released Nov 2021.

This script is example code designed to discharge a battery and create a battery model for use
in a Keithley Model 2281S-20-6 Battery Simulator and Precision DC Power Supply.  It will drive
any of the following Keithley instruments:

        * Model 2400 SourceMeter

WARNING:        This script presently does not include any safeguards to prevent the user from 
                discharging a LITHIUM ION battery beyond safe limits.  It is the user's responsibility 
                to follow all manufacturer's guidelines when setting the discharge current and cut-off 
                voltage for a LITHIUM ION battery to ensure safe operation of the test setup and program.

"""

from pymeasure.instruments.keithley import Keithley2400
from pymeasure.adapters import PrologixAdapter

def delay(interval):
    time.sleep(interval)

def setup_smu():
    adapter = PrologixAdapter('/dev/cu.usbserial-PXEFMYB9')
    return Keithley2400(adapter.gpib(26))

def meas_esr(smu, test_curr, settle_time):

    # load_curr and test_curr are load currents, which are drawn from the battery.
    # To draw current FROM the battery, the programmed current level must be negative (or zero).
    
    test_curr = -abs(test_curr)           # Ensure test_curr has proper sense
    load_curr = smu.source_current        # Will be negative
    vload = smu.voltage                   # Battery voltage at load_curr
    smu.source_current = -abs(test_curr)  # test_curr equal to zero corresponds to an open circuit
    if settle_time > 0:
        delay(settle_time)
    vtest = smu.voltage                   # Battery voltage at test_curr; vtest is Voc if test_curr = 0
    smu.source_current = load_curr
    esr = abs((vtest - vload) / (test_curr - load_curr)) # (V2-V1)/(I2-I1); ensure positive resistance
    return vload, vtest, esr
