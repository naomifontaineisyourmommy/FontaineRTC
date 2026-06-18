"""WDTT subsystem (node role).

A second protocol alongside olcrtc: a WireGuard VPN masked as a VK video call.
Unlike olcrtc (one process per instance), WDTT is a single systemd service
(``wdtt.service`` / binary ``wdtt-server``) plus a password database
(``/etc/wdtt/passwords.json``). "Users" are password entries; managing them means
editing that JSON and restarting the service. See tempwdtt/WDTT-README.md.
"""
