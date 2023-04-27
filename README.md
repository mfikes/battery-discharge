# battery-discharge

A port of the Keithley Battery Discharge sample app for the Keithley 2400 SourceMeter.

# Usage

First ensure that dependencies are installed (using `pip3` for example):

- `pymeasure`
- `inquirer`

Edit `battery_discharge.py` to set up the `smu` variable with respect to your GPIB / Serial parameters.

Run via 

```
python3 battery_discharge.py
```

and follow on-screen prompts.

## License

The code in this project is derived from the [Keithley Battery Discharge sample app](https://github.com/tektronix/keithley/tree/main/Application_Specific/Battery_Simulation/Model_Generation_Script), designed only for use with the Keithley 2400 SourceMeter and is a derivative work licensed under the [Tektronix Sample Source Code License Agreement](https://www.tek.com/sample-license).
