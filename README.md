# Cummins Generator Home Assistant Integration

A Home Assistant custom integration for monitoring and controlling Cummins standby generators with web interfaces.

## Features

### Sensors
- **Generator Status** - Current operational state (Stopped, Running, Starting, etc.)
- **Battery Voltage** - DC battery voltage with 1 decimal precision
- **Output Voltage** - AC output voltage 
- **Frequency** - Output frequency in Hz
- **Engine Hours** - Total runtime hours
- **Load Line 1 & 2** - Current load percentages

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

## Supported Models

This integration works with Cummins generators that have the standard web interface with the following endpoints:
- `index_data.html` - Status data
- `loads_data.html` - Load status
- `loads.html` - Load configuration
- `exercise.html` - Exercise settings
- `wr_logical.cgi` - Control commands

## Troubleshooting

- Ensure generator is accessible on the network
- Verify correct IP address and password
- Check that generator switch is in REMOTE position for controls
- Review Home Assistant logs for connection errors

## License

This project is licensed under the Apache License 2.0.
