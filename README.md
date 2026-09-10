# FlightGear ADS-B Companion 
is a freeware

# BSD C3 License

Copyright © SU Nie
All Rights Reserved

Contact me for features or bugs 
Email can87683 at gmail dot com

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

Or the time needed would be many folds. 
About 60 hours were levied on debugging/testing.
Platform/tools used are Debian 12, mingw, pyinstaller, and vscodium.



