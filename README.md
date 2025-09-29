# FlightGear ADS-B Companion 
is a freeware

https://github.com/can87683

BSD 3-Clause License
Copyright (c) 2025 SU Nie
All Rights Reserved

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

        
-----------------------------------------------------

Add strings to FlightGear GUI Launch Settings / Additional Settings
    
    --log-level=debug
    --telnet=5500
    --prop:/sim/telnet/enabled=true
    --httpd=8080
    --multiplay=bi
    --ai-scenario=scripted
    --disable-distance-attenuation
    --disable-random-objects
    --disable-specular-highlight
    --enable-ai-models
    --prop:/sim/ai/enabled=true
    --prop:/sim/rendering/ai-anti-collision-light=true
    --prop:/sim/rendering/ai-label-scale=1.5
    --prop:/sim/rendering/random-objects/enabled=false
    --prop:/sim/rendering/models/enable-distance-culling=false
    --prop:/autopilot/settings/target-altitude-ft=3000
    --prop:/autopilot/settings/true-heading-deg=180
    --prop:/autopilot/settings/target-speed-kt=300
