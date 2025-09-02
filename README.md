Add below strings to FlightGear GUI Launch Settings / Additional Settings
    
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
