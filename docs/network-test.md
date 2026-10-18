# Network Test & Node Registry

This document tracks the active nodes and Tailscale IP addresses participating in the distributed AI platform.

|  Machine Name |     Role             |Tailscale IP (`100.x.x.x`) | Status |
   desktop-fpk67ek-1  aarbc0@           100.65.149.96                Active
   cankolcu           cankolcu2004@     100.70.38.52                 Active  
   eray-macbook-air   eraytugay844@     100.86.105.86                Active  
   fedora             blabl102810@      100.98.44.118                Active
   hamzah             blabl102810@      100.116.89.127               Active
   laptop-7j5tfd0a    fatmanuratalay04@ 100.76.112.75                Active
   redmi-note-11-pro  blabl102810@      100.93.44.9                  Active 
   user               camciokancan@     100.109.95.6                 Active

## Verification Steps
1. Ensure Tailscale is running on both machines.
2. Ping the orchestrator from the worker: `ping 100.x.x.Y`
3. Verify heartbeat signals between nodes.