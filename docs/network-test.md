# Network Test & Node Registry

The devices in the team's Tailscale network (card S2-09). Tailscale addresses
(`100.x.y.z`) stay the same as long as a device stays in the tailnet.

| Member | Machine name | Tailscale IP | Status | Note |
| --- | --- | --- | --- | --- |
| Abdurrahman | desktop-fpk67ek-1 | 100.65.149.96 | Active | |
| Can | cankolcu | 100.70.38.52 | Active | |
| Eray | eray-macbook-air | 100.86.105.86 | Active | |
| Fatma | laptop-7j5tfd0a | 100.76.112.75 | Active | |
| Hamza | hamzah | 100.116.89.127 | Active | |
| Hamza | fedora | 100.98.44.118 | Active | |
| Hamza | redmi-note-11-pro | 100.93.44.9 | Active | phone, not an agent PC |
| Okan | user | 100.109.95.6 | Active | |

"Active" means the device was online in the Tailscale admin list. Whether the
master can be reached from each PC is checked with the steps below.

## Verification steps

1. Tailscale runs on both PCs: `tailscale status`.
2. From the worker PC: `ping <master Tailscale IP>`.
3. From the worker PC open `http://<master Tailscale IP>:8000/api/v1/health`.
4. Start the worker (`python -m dap.worker.main`); it appears on the master's
   Agents page as `idle`, and stays there while it sends heartbeats.
