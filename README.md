# Cummins Generator Home Assistant Integration

[![Integration Usage][integration-usage-shield]][integration-usage]
[![GitHub Downloads][downloads-shield]][releases]
[![GitHub Latest Downloads][downloads-latest-shield]][releases]
[![GitHub Release][releases-shield]][releases]
[![GitHub Release Date][release-date-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]

A Home Assistant integration for monitoring and controlling Cummins standby generators with web interfaces.

## Features

### Sensors
- **Generator Status** - Current operational state (Stopped, Running, Starting, etc.)
- **Battery Voltage** - DC battery voltage with 1 decimal precision
- **Output Voltage** - AC output voltage 
- **Frequency** - Output frequency in Hz
- **Engine Hours** - Total runtime hours
- **Load Line 1 & 2** - Current load percentages
- **Time Drift** - Signed minutes representing the difference between the generator clock and Home Assistant's clock

### Binary Sensors
- **Utility Present** - Utility power availability
- **Utility Connected** - Utility connection status
- **Genset Running** - Generator running state
- **Standby Disabled** - Standby mode status
- **Action Required** - Maintenance or fault indicator

### Controls
- **Start/Stop Genset** - Manual generator control
- **Enable/Disable Standby** - Standby mode control
- **Exercise Now** - Trigger immediate exercise cycle
- **Load Management** - Manual/Automatic mode with individual load control
- **Exercise Schedule** - Configure frequency, day, and time

## Polling Intervals

The integration polls the generator's web interface on a per-platform cadence:

| Platform / entity group | Interval | Endpoint |
|---|---|---|
| Sensors (status, voltages, frequency, engine hours, loads) | 30 s | `/index_data.html` |
| Binary sensors (utility, running, standby, action required) | 30 s | shares the sensor poll |
| Load & exercise selects | 100 s per endpoint, rotating (~5 min per endpoint) | `/loads_data.html`, `/loads.html`, `/exercise.html` |
| Date/time entity | 1 h | `/timedate.html` |
| Buttons | on demand | control endpoints only |

Requests are additionally spaced out by a configurable minimum request gap (default 2000 ms) to avoid overwhelming the generator's embedded network stack. For the reasoning — including source-level analysis of the InterNiche 2.0 TCP/IP stack — see [docs/generator-network-stack.md](docs/generator-network-stack.md).

## Installation

1. Copy the `custom_components/cummins_generator` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Go to **Settings** → **Devices & Services** → **Add Integration**
4. Search for "Cummins Generator"
5. Enter your generator's IP address and password (default: "cummins")

## Configuration

The integration requires:
- **Host**: IP address of your Cummins generator
- **Password**: Web interface password (default: "cummins")

## Requirements

- Cummins generator with web interface
- Network connectivity to generator
- Generator switch in REMOTE position for control functions

## Securing Your Generator

The embedded web interface on these controllers runs an old
InterNiche Technologies TCP/IP stack (version 2.0, circa 2004). The
same family of stacks shows up widely in operational technology (OT)
gear — PLCs, transfer switches, water and power infrastructure — and
its known vulnerabilities are actively exploited. There are no
firmware patches available for most of these controllers, so
protecting the generator is a matter of controlling who can reach it
on the network. This guidance mirrors what agencies like CISA and
the Washington State Department of Health tell operators of
unpatchable OT devices (see the [WA DOH bulletin][wadoh] for a
recent example).

**Do not expose the generator's web interface to the public
internet.** Do not forward ports to it, do not put it on a DMZ, and
do not rely on the built-in password as a security boundary — HTTP
Basic auth over cleartext HTTP is trivially observed. If you need
remote access, reach it through your Home Assistant instance over a
VPN.

**Isolate the generator on a segmented network.** Put it on a
management or IoT VLAN with firewall rules that only permit
inbound traffic from your Home Assistant host on TCP/80. Block all
outbound traffic from the generator; it has no business initiating
connections. If your router supports client isolation on the VLAN,
enable it.

**Change the default password.** The factory password is `cummins`
and is documented publicly. Set something unique, and store it in a
password manager. The integration's options flow lets you rotate it
without re-adding the integration.

**Monitor for the unexpected.** If you keep any kind of network
telemetry (firewall logs, Home Assistant recorder for the
integration's request-error entities, packet capture), watch for
inbound connection attempts to the generator from anything other
than your HA host, and for outbound traffic from the generator
itself. Alerts on either are a strong signal something is wrong.

**Keep physical controls in the loop.** The generator's front-panel
switch remains authoritative. Leave it in REMOTE only when you
actually need the integration's control features to work; otherwise
the physical position of the switch is a hard stop that no network
attacker can bypass.

If you suspect the generator has been tampered with over the
network, isolate it (pull the Ethernet cable) and reset it to
factory settings. Operators of public infrastructure or systems
tied to a federal reporting obligation should report the incident
through their usual channel (e.g. [CISA][cisa]); for a residential
install this generally isn't required, but the same isolate-then-
rebuild steps still apply.

[wadoh]: https://content.govdelivery.com/accounts/WADOH/bulletins/422e976
[cisa]: https://www.cisa.gov/report

## Supported Models

This integration works with Cummins generators that have the standard web interface with the following endpoints:
- `index_data.html` - Status data
- `loads_data.html` - Load status
- `loads.html` - Load configuration
- `exercise.html` - Exercise settings
- `wr_logical.cgi` - Control commands

## Troubleshooting

- The web interface may become unresponsive when modern web browsers
  use multiple connections or other advanced features. It's a "site
  best viewed in IE7" era web app. The polling from this integration
  works without issue, but elements may become "unavailable" if you
  use a browser at the same time.
- Ensure generator is accessible on the network
- Verify correct IP address and password
- Check that generator switch is in REMOTE position for controls
- Review Home Assistant logs for connection errors

## AI Tooling Disclosure

This work was produced with AI, namely the Amazon Q Developer CLI
(which has subsequently been rebranded "Kiro CLI") in September
2025. JavaScript functions from the web interface was extracted into
files like `read-status.js` and then prompts such as

> write a Home Assistant integration for a Cummins generator with a
web browser interface. JavaScript to read the status of the generator
has been extracted in read-status.js

Everything in this repository is predominately the output of AI
tooling, except for some sections of this README.md such as this one.

## License

As this is a machine-produced integration, I make no claims of human
authorship. For any exclusive rights that are awarded to me that _can_
be licensed with the Apache License 2.0, that is the legal instrument
I elect to use to grant license to you.


[integration-usage-shield]: https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.cummins_generator.total&style=for-the-badge
[integration-usage]: https://analytics.home-assistant.io/custom_integrations.json
[commits-shield]: https://img.shields.io/github/last-commit/mswilson/cummins-hass-integration?style=for-the-badge
[commits]: https://github.com/mswilson/cummins-hass-integration/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/mswilson/cummins-hass-integration.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/Maintainers-%40mswilson-blue.svg?style=for-the-badge
[downloads-shield]: https://img.shields.io/github/downloads/mswilson/cummins-hass-integration/total.svg?style=for-the-badge
[downloads-latest-shield]: https://img.shields.io/github/downloads-pre/mswilson/cummins-hass-integration/latest/total?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/mswilson/cummins-hass-integration.svg?style=for-the-badge
[release-date-shield]: https://img.shields.io/github/release-date/mswilson/cummins-hass-integration?style=for-the-badge
[releases]: https://github.com/mswilson/cummins-hass-integration/releases
