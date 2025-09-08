## Cummins Generator Integration

Monitor and control your Cummins standby generator directly from Home Assistant.

### Features
- Real-time status monitoring (battery voltage, output voltage, frequency, engine hours)
- Binary sensors for utility status, generator running state, and alerts
- Remote control buttons (start/stop, standby mode, exercise)
- Load management controls (manual/automatic mode, individual load control)
- Exercise schedule configuration

### Requirements
- Cummins generator with web interface
- Network connectivity to generator
- Generator switch in REMOTE position for control functions

### Configuration
After installation, add the integration through the Home Assistant UI and provide:
- Generator IP address
- Web interface password (default: "cummins")
