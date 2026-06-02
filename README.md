# PicoCore Logs

Interactive CLI and Python toolkit for managing, downloading, and converting binary log files from PicoCore / ESP32 MicroPython devices.

## Features

* **Interactive CLI** – Menu-driven interface for managing logs directly from your device
* **Log Conversion** – Convert binary logs to **text, CSV, JSON, or table** formats
* **Severity Filtering** – Filter logs by level (TRACE → FATAL)
* **Device Integration** – Works directly over USB using `mpremote`
* **Rich UI** – Clean terminal interface with progress bars and structured output

## Installation

### Requirements

* Python **3.14+**
* [`uv`](https://astral.sh/uv/) (recommended)
* ESP32 / PicoCore device connected via USB

### Standard Install (Recommended)

```bash
# Install globally
uv tool install mpremote
uv tool install git+https://github.com/PauWol/PicoCore-Logs.git
```

The CLI is now available from your system terminal (if the command is not found, reopen your terminal so the installation path is refreshed).

```bash
picologs
```

**Note:** Run from your system terminal (not VS Code integrated terminal) to avoid path confusion.

### Uninstall

```bash
uv tool uninstall picologs
uv tool uninstall mpremote
```

### Alternative (pip)

```bash
git clone https://github.com/PauWol/PicoCore-Logs.git
cd PicoCore-Logs

pip install .
```

or this simple oneliner

```bash
pip install git+https://github.com/PauWol/PicoCore-Logs.git
```

### Troubleshooting / Device Access Disclaimer

If `picologs` runs but no files are found, or operations like listing the filesystem, downloading logs, or deleting logs fail while the device is correctly connected, this is often caused by **serial port permission issues or device access restrictions**.

As a quick temporary fix, you can grant direct access to the device port and rerun the CLI:

```bash
sudo chmod 666 /dev/<your-device> && picologs
```

Replace `/dev/<your-device>` with your actual serial port (for example `/dev/ttyACM0`, `/dev/ttyUSB0`, etc.).

Example:

```bash
sudo chmod 666 /dev/ttyACM0 && picologs
```

**Note:**

* This is a temporary fix and will reset after unplugging the device or rebooting.
* If the issue persists, ensure no other program is using the port (e.g. serial monitors, IDEs).
* For a permanent fix, add your user to the appropriate serial group (e.g. `uucp` or `dialout`) and re-login.


### Development Setup

```bash
git clone https://github.com/PauWol/PicoCore-Logs.git
cd PicoCore-Logs

uv sync
```

Run without installing:

```bash
uv run picologs/main.py
```

## Usage

### Running the CLI

From your system terminal:

```bash
picologs
```

Or if using development setup:

```bash
uv run main.py
```

### What you can do

* Select your ESP32 / PicoCore device
* Download log files
* Convert logs automatically
* Filter by severity level
* Delete logs from device
* Inspect device filesystem

## Programmatic Usage

Use the converter in your own Python scripts:

```python
from picologs.log_conv import parse_log_file, convert

records = parse_log_file("logs.bin", min_level=3)  # WARN+

convert(records, fmt="csv", output_path="output.csv")
```

## Dependencies

* `mpremote` ≥ 1.28.0 — MicroPython communication
* `pyserial` ≥ 3.5 — Serial interface
* `questionary` ≥ 2.1.1 — CLI prompts
* `rich` ≥ 15.0.0 — UI rendering

## Log Format

Binary logs are stored as:

```text
[1 byte: level] [4 bytes: uptime_ms (LE)] [N bytes: ASCII message]
```

* No delimiters between records
* Records are detected via non-printable level bytes (1–6)
* Messages are ASCII (0x20–0x7E)

**Note:** Messages may be truncated due to device buffer limits.

## License

MIT
