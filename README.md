# FlightGear ADS-B Companion 
is a freeware

BSD 3-Clause License
Copyright © SU Nie
All Rights Reserved

Contact me for features or bugs Email can87683 at you know gmail dot com

https://github.com/can87683

This is a Python project experimenting 
working with LLMs. The goal is to 
provide ADS-B based air traffic in 
Flightgear. The project time is 
about 110 hours from inception to binaries.

In a-z order, ChatGPT, DeepSeek, Perplexity
were immense debugging aids. Or the
time needed would be many folds. About
60 hours were levied on debugging/testing.
Platform/tools used are Debian 12, mingw, 
pyinstaller, and vscodium.

Product operation flow:
- Set takeoff airport by ICAO
  (Yor may just watch air 
  traffic without engaging the
  simulator)
- Press ADS-B Fetch to receive data 
  around 250KM.
- Once linked to FlightGear, the 
  position switches to the simulator
- ADS-B based planes would be spawned or 
  despawned around 30KM based on the AI 
  models bundled in FlightGear. Without 
  any matching model, the all-weather 
  c172p is the fallback model.

Note that only the generous adsb.lol
gives global data streams for free. 
Yet I throttle the refresh rate to 
endorse etiquettes. So adsb.lol is
the default source.

