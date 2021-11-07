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
