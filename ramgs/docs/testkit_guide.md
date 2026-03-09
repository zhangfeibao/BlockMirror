# RAMViewer Test Automation Library (testkit) User Guide

## Table of Contents

1. [Introduction](#1-introduction)
2. [Prerequisites](#2-prerequisites)
3. [Quick Start](#3-quick-start)
4. [Connection Lifecycle](#4-connection-lifecycle)
5. [Reading Variables](#5-reading-variables)
6. [Writing Variables](#6-writing-variables)
7. [Waiting for Conditions](#7-waiting-for-conditions)
8. [Timing Control](#8-timing-control)
9. [Error Handling](#9-error-handling)
10. [pytest Integration](#10-pytest-integration)
11. [Real-World Examples](#11-real-world-examples)
12. [API Reference](#12-api-reference)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Introduction

### 1.1 Overview

`ramgs.testkit` is a Python library for writing automated MCU test scripts. It provides a `McuConnection` class that wraps `ramgs.exe` CLI calls via `subprocess`, allowing you to read and write MCU RAM variables programmatically.

The library has **zero internal dependencies** on the ramgs Python package -- it only requires `ramgs.exe` to be in the system PATH. This means you can copy `testkit.py` as a standalone file into any project.

### 1.2 Architecture

```
  Your test script (Python)
         |
         v
  McuConnection (testkit.py)
         |  subprocess.run()
         v
  ramgs.exe (CLI)
         |  serial port (open -> read/write -> close per call)
         v
  MCU (RAMViewer library)
```

Each `get()` / `set()` call invokes `ramgs.exe` as a subprocess. The CLI internally opens the serial port, performs the operation, and closes the port. This design keeps testkit completely decoupled from ramgs internals.

### 1.3 Design Philosophy

- **Zero-config constructor**: `McuConnection()` reads all configuration from `~/.ramgs/state.json` -- no parameters needed.
- **Zero dependencies**: Only requires `ramgs.exe` in PATH and Python stdlib. No `pip install` needed.
- **Non-invasive**: The library never writes to `state.json` -- it only reads the configuration set by `ramgs open` and `ramgs create`.
- **Exception-driven**: All errors are reported via a clear exception hierarchy, making it natural to use with pytest and other test frameworks.

### 1.4 Workflow

```
   CLI (one-time setup)                      Python test script
   ======================                    ====================

1. ramgs open --name COM3 --baud 115200  -->  state.json created
2. ramgs create firmware.elf             -->  symbols.json generated
                                              state.json updated
                                                    |
                                                    v
                                         3. McuConnection() reads state.json
                                         4. mcu.open() verifies ramgs.exe works
                                         5. mcu.get()  --> subprocess: ramgs get ...
                                            mcu.set()  --> subprocess: ramgs set ...
                                         6. mcu.close()
```

---

## 2. Prerequisites

### 2.1 ramgs.exe in PATH

The testkit calls `ramgs.exe` via subprocess. Ensure it is accessible:

```bash
# Verify ramgs.exe is in PATH
ramgs --version

# If not, add the dist directory to your system PATH:
# e.g., add F:\works_2026\mcu-terminal\ramgs\dist\ramgs to PATH
```

### 2.2 Using testkit.py

**Option A -- As part of the ramgs package** (if installed):

```python
from ramgs.testkit import McuConnection
```

**Option B -- As a standalone file** (copy to your project):

```bash
# Copy testkit.py to your test project
copy F:\works_2026\mcu-terminal\ramgs\ramgs\testkit.py my_tests\testkit.py
```

```python
from testkit import McuConnection
```

Since testkit.py has no internal ramgs imports (only Python stdlib), it works as a standalone file.

### 2.3 MCU Preparation

Before using testkit, ensure:

1. Your MCU firmware includes the RAMViewer library (`ramviewer.h` / `ramviewer.c`).
2. The MCU is physically connected to your PC via a serial port.
3. The MCU firmware is compiled with debug symbols (ELF file available).

### 2.4 CLI Setup (Required Once)

You must run these CLI commands **before** using testkit:

```bash
# Step 1: Register the serial port and baud rate
ramgs open --name COM3 --baud 115200

# Step 2: Generate symbols.json from your firmware ELF
ramgs create firmware.elf
```

These commands create `~/.ramgs/state.json` with the following information:
- Serial port name (e.g., `COM3`)
- Baud rate (e.g., `115200`)
- Endianness (default: `little`)
- Path to `symbols.json`

You can verify the configuration:

```bash
ramgs status
```

---

## 3. Quick Start

### 3.1 Minimal Example

```python
from ramgs.testkit import McuConnection

with McuConnection() as mcu:
    # Read a variable
    value = mcu.get("counter")
    print(f"counter = {value}")

    # Write a variable
    mcu.set("counter", 0)

    # Verify
    assert mcu.get("counter") == 0
    print("Test passed!")
```

### 3.2 What Happens Under the Hood

1. `McuConnection()` reads `~/.ramgs/state.json` to get port, baud, and symbols path. Validates the config exists.
2. `with ... as mcu:` calls `mcu.open()`, which runs `ramgs status` to verify `ramgs.exe` is callable.
3. `mcu.get("counter")` runs `subprocess.run(["ramgs", "get", "counter"])`, parses the stdout output `counter=42`, and returns `42`.
4. `mcu.set("counter", 0)` runs `subprocess.run(["ramgs", "set", "counter=0"])` and verifies success.
5. When the `with` block exits, `mcu.close()` marks the session as ended.

---

## 4. Connection Lifecycle

### 4.1 Context Manager (Recommended)

```python
from ramgs.testkit import McuConnection

with McuConnection() as mcu:
    print(f"Connected to {mcu.port_name} at {mcu.baud_rate} baud")
    # ... your test code ...
# Session ended
```

### 4.2 Manual Open/Close

For long-running sessions or pytest fixtures, you can manage the lifecycle manually.

```python
mcu = McuConnection()
mcu.open()

try:
    # ... your test code ...
finally:
    mcu.close()
```

### 4.3 Connection State

```python
mcu = McuConnection()
print(mcu.is_connected)  # False -- not opened yet

mcu.open()
print(mcu.is_connected)  # True

mcu.close()
print(mcu.is_connected)  # False
```

### 4.4 Connection Info

```python
mcu = McuConnection()
print(f"Port: {mcu.port_name}")       # e.g., "COM3"
print(f"Baud: {mcu.baud_rate}")       # e.g., 115200
print(f"Symbols: {len(mcu.symbols)}") # e.g., 750
```

> **Note**: `port_name` and `baud_rate` are read from `state.json`. The `symbols` property reads `symbols.json` directly (no CLI call needed).

---

## 5. Reading Variables

### 5.1 Single Variable

```python
with McuConnection() as mcu:
    temp = mcu.get("cal_temp")
    speed = mcu.get("motor_speed")
    flag = mcu.get("status_flags.bit0")
```

### 5.2 Multiple Variables (Single CLI Invocation)

`get_many()` reads all variables in one `ramgs get var1,var2,...` call, which is faster than calling `get()` multiple times (one subprocess vs many).

```python
with McuConnection() as mcu:
    vals = mcu.get_many("temp", "speed", "counter")
    # vals = {"temp": 25.3, "speed": 1200, "counter": 42}

    print(f"Temperature: {vals['temp']}")
    print(f"Speed: {vals['speed']}")
```

### 5.3 Variable Name Syntax

The testkit supports the same variable syntax as the CLI:

| Syntax | Example | Description |
|--------|---------|-------------|
| Simple | `counter` | Simple variable |
| Struct member | `config.baudrate` | Structure member access |
| Array element | `data[0]` | Array element by index |
| Combined | `sensors[2].temp` | Array of structs |
| File filter | `counter@main` | Disambiguate same-named variables |

### 5.4 Listing Available Variables

```python
mcu = McuConnection()
for name in mcu.symbols[:20]:
    print(name)
# Prints first 20 variable names (sorted alphabetically)
```

---

## 6. Writing Variables

### 6.1 Single Variable

```python
with McuConnection() as mcu:
    mcu.set("counter", 0)
    mcu.set("motor_speed", 1500)
    mcu.set("config.mode", 2)
    mcu.set("cal_temp", 25.5)  # float
```

### 6.2 Multiple Variables -- Keyword Arguments

For simple variable names (valid Python identifiers, no dots or brackets):

```python
with McuConnection() as mcu:
    mcu.set_many(counter=0, speed=100, mode=1)
```

### 6.3 Multiple Variables -- Dictionary

For variable names containing dots, brackets, or `@`:

```python
with McuConnection() as mcu:
    mcu.set_dict({
        "config.mode": 2,
        "arr[0]": 10,
        "arr[1]": 20,
        "arr[2]": 30,
    })
```

### 6.4 Read-Modify-Write Pattern

```python
with McuConnection() as mcu:
    current = mcu.get("counter")
    mcu.set("counter", current + 10)
```

---

## 7. Waiting for Conditions

### 7.1 Wait for Exact Value

`wait_until()` polls a variable until the condition is met or the timeout expires.

```python
with McuConnection() as mcu:
    mcu.set("start_calibration", 1)

    # Wait for cal_done to become 1 (up to 10 seconds)
    mcu.wait_until("cal_done", 1, timeout_s=10.0)
    print("Calibration complete!")
```

### 7.2 Wait with Lambda Condition

Pass a callable for more complex conditions:

```python
with McuConnection() as mcu:
    # Wait for temperature to exceed 50 degrees
    final_temp = mcu.wait_until(
        "temperature",
        lambda t: t > 50.0,
        timeout_s=30.0
    )
    print(f"Temperature reached {final_temp}")
```

```python
with McuConnection() as mcu:
    # Wait for counter to be within a range
    mcu.wait_until(
        "counter",
        lambda c: 90 <= c <= 110,
        timeout_s=5.0
    )
```

### 7.3 Custom Poll Interval

The default poll interval is 100ms. For faster or slower polling:

```python
with McuConnection() as mcu:
    # Poll every 500ms for slow processes
    mcu.wait_until("boot_done", 1, timeout_s=60.0, poll_interval_ms=500)
```

> **Note**: Since each poll invokes a subprocess, very short intervals (< 50ms) may not be achievable due to process startup overhead.

### 7.4 Handling Timeout

```python
from ramgs.testkit import McuConnection, TimeoutError

with McuConnection() as mcu:
    try:
        mcu.wait_until("cal_done", 1, timeout_s=5.0)
    except TimeoutError as e:
        print(f"Timed out! Variable: {e.var_name}")
        print(f"Last value: {e.last_value}")
        print(f"Timeout was: {e.timeout_s}s")
```

---

## 8. Timing Control

### 8.1 Constructor Parameter

```python
mcu = McuConnection(
    inter_cmd_delay_ms=50,  # Wait at least 50ms between CLI invocations
)
```

### 8.2 Inter-Command Delay

Some MCUs need a gap between consecutive commands. The `inter_cmd_delay_ms` parameter ensures a minimum delay between any two CLI invocations.

```python
# MCU needs at least 20ms between commands
mcu = McuConnection(inter_cmd_delay_ms=20)

with mcu:
    mcu.set("a", 1)   # executes immediately
    mcu.set("b", 2)   # waits ~20ms, then executes
    mcu.set("c", 3)   # waits ~20ms, then executes
```

The delay is "smart" -- if you already spent time between calls (e.g., doing computation), only the remaining gap is slept.

```python
import time

with McuConnection(inter_cmd_delay_ms=100) as mcu:
    mcu.get("temp")

    # Spend 80ms doing something
    time.sleep(0.08)

    mcu.get("temp")  # Only sleeps ~20ms more (not 100ms)
```

### 8.3 Adjusting at Runtime

```python
with McuConnection() as mcu:
    mcu.inter_cmd_delay_ms = 50   # Slow down
    # ... do slow operations ...
    mcu.inter_cmd_delay_ms = 0    # Back to full speed
```

---

## 9. Error Handling

### 9.1 Exception Hierarchy

```
RamgsError (base)
  +-- ConnectionError      # ramgs.exe not found, state.json missing, port failure
  +-- SymbolError          # Variable not found, symbols file error
  +-- ValueError           # Type conversion / encoding error
  +-- CommunicationError   # MCU communication failure, CLI error
        +-- TimeoutError   # wait_until() timed out
```

### 9.2 Common Exceptions

#### ConnectionError -- No Configuration

```python
from ramgs.testkit import McuConnection, ConnectionError

try:
    mcu = McuConnection()
except ConnectionError as e:
    print(f"Setup error: {e}")
    print("Run 'ramgs open --name COM3 --baud 115200' first")
```

#### ConnectionError -- ramgs.exe Not in PATH

```python
try:
    with McuConnection() as mcu:
        mcu.get("counter")
except ConnectionError as e:
    print(f"Cannot find ramgs.exe: {e}")
    print("Add the ramgs dist directory to your system PATH")
```

#### SymbolError -- Variable Not Found

```python
from ramgs.testkit import McuConnection, SymbolError

with McuConnection() as mcu:
    try:
        mcu.get("nonexistent_var")
    except SymbolError as e:
        print(f"Symbol error: {e}")
```

#### CommunicationError -- MCU Not Responding

```python
from ramgs.testkit import McuConnection, CommunicationError

with McuConnection() as mcu:
    try:
        mcu.get("counter")
    except CommunicationError as e:
        print(f"MCU error: {e}")
        # Check physical connection, MCU power, firmware running
```

### 9.3 Catching All Testkit Errors

```python
from ramgs.testkit import McuConnection, RamgsError

try:
    with McuConnection() as mcu:
        mcu.set("counter", 0)
        mcu.wait_until("counter", 100, timeout_s=5.0)
except RamgsError as e:
    print(f"Test failed: {type(e).__name__}: {e}")
```

---

## 10. pytest Integration

### 10.1 Session-Scoped Fixture

Share one connection across all tests in a session:

```python
# conftest.py
import pytest
from ramgs.testkit import McuConnection

@pytest.fixture(scope="session")
def mcu():
    """Shared MCU connection for the entire test session."""
    conn = McuConnection()
    conn.open()
    yield conn
    conn.close()
```

### 10.2 Function-Scoped Fixture (Isolated)

Each test gets a fresh connection:

```python
# conftest.py
import pytest
from ramgs.testkit import McuConnection

@pytest.fixture
def mcu():
    """Fresh MCU connection per test."""
    with McuConnection() as conn:
        yield conn
```

### 10.3 Test Examples

```python
# test_calibration.py

def test_read_temperature(mcu):
    """Temperature should be within valid range."""
    temp = mcu.get("cal_temp")
    assert -40 <= temp <= 125, f"Temperature out of range: {temp}"


def test_counter_reset(mcu):
    """Counter should be writable and readable."""
    mcu.set("counter", 0)
    assert mcu.get("counter") == 0

    mcu.set("counter", 12345)
    assert mcu.get("counter") == 12345


def test_calibration_flow(mcu):
    """Full calibration process should complete within 10 seconds."""
    # Start calibration
    mcu.set("cal_start", 1)

    # Wait for completion
    mcu.wait_until("cal_done", 1, timeout_s=10.0)

    # Verify results
    cal_result = mcu.get("cal_result")
    assert cal_result == 0, f"Calibration failed with code {cal_result}"


def test_batch_read(mcu):
    """Multiple variables should be readable in one transaction."""
    vals = mcu.get_many("temp", "speed", "mode")
    assert "temp" in vals
    assert "speed" in vals
    assert "mode" in vals
```

### 10.4 Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with detailed output
pytest tests/ -v -s

# Run a specific test
pytest tests/test_calibration.py::test_counter_reset -v
```

### 10.5 Fixture with Reset

Reset MCU state before each test:

```python
# conftest.py
import pytest
from ramgs.testkit import McuConnection

@pytest.fixture(scope="session")
def mcu_conn():
    conn = McuConnection()
    conn.open()
    yield conn
    conn.close()

@pytest.fixture
def mcu(mcu_conn):
    """Reset MCU state before each test."""
    mcu_conn.set_dict({
        "counter": 0,
        "mode": 0,
        "cal_start": 0,
        "cal_done": 0,
    })
    yield mcu_conn
```

---

## 11. Real-World Examples

### 11.1 PID Controller Tuning Validation

```python
from ramgs.testkit import McuConnection

with McuConnection(inter_cmd_delay_ms=10) as mcu:
    # Set PID parameters
    mcu.set_dict({
        "pid.kp": 1.5,
        "pid.ki": 0.1,
        "pid.kd": 0.05,
        "pid.setpoint": 100.0,
    })

    # Enable controller
    mcu.set("pid.enable", 1)

    # Wait for output to reach target (within 5% tolerance)
    mcu.wait_until(
        "pid.output",
        lambda v: 95.0 <= v <= 105.0,
        timeout_s=10.0,
        poll_interval_ms=200,
    )

    # Check for overshoot
    peak = mcu.get("pid.output_peak")
    assert peak < 120.0, f"Excessive overshoot: {peak}"

    print("PID tuning validated!")
```

### 11.2 Communication Protocol Stress Test

```python
import time
from ramgs.testkit import McuConnection, CommunicationError

def test_stress(iterations=100):
    errors = 0

    with McuConnection() as mcu:
        start = time.time()

        for i in range(iterations):
            try:
                mcu.set("counter", i)
                readback = mcu.get("counter")
                if readback != i:
                    print(f"[{i}] Mismatch: wrote {i}, read {readback}")
                    errors += 1
            except CommunicationError as e:
                print(f"[{i}] Error: {e}")
                errors += 1

        elapsed = time.time() - start

    print(f"Completed {iterations} read-write cycles in {elapsed:.1f}s")
    print(f"Throughput: {iterations / elapsed:.1f} ops/s")
    print(f"Errors: {errors} ({errors / iterations * 100:.1f}%)")

test_stress()
```

> **Note**: Throughput is limited by subprocess overhead (~50-200ms per call). For high-speed data collection, use `ramgs chart` or `ramgs image` instead.

### 11.3 Data Logging

```python
import csv
import time
from ramgs.testkit import McuConnection

VARIABLES = ["temp", "pressure", "humidity"]
INTERVAL_S = 1.0  # 1 second (subprocess overhead makes sub-second impractical)
DURATION_S = 60.0

with McuConnection() as mcu:
    with open("data_log.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp"] + VARIABLES)

        start = time.time()
        while time.time() - start < DURATION_S:
            vals = mcu.get_many(*VARIABLES)
            row = [f"{time.time() - start:.3f}"]
            row += [str(vals[v]) for v in VARIABLES]
            writer.writerow(row)

            time.sleep(INTERVAL_S)

    print(f"Logged {DURATION_S}s of data to data_log.csv")
```

### 11.4 Boot Sequence Verification

```python
from ramgs.testkit import McuConnection, TimeoutError

def verify_boot_sequence():
    with McuConnection() as mcu:
        # Step 1: Wait for init to complete
        try:
            mcu.wait_until("init_done", 1, timeout_s=5.0)
        except TimeoutError:
            print("ERROR: MCU did not finish initialization")
            print(f"  init_state = {mcu.get('init_state')}")
            return False

        # Step 2: Verify peripheral status
        status = mcu.get_many(
            "uart_ok", "spi_ok", "adc_ok", "timer_ok"
        )
        for name, ok in status.items():
            if not ok:
                print(f"ERROR: {name} failed")
                return False

        # Step 3: Verify firmware version
        version = mcu.get("firmware_version")
        print(f"Firmware version: {version}")

        print("Boot sequence OK")
        return True

verify_boot_sequence()
```

### 11.5 Array Fill and Verify

```python
from ramgs.testkit import McuConnection

with McuConnection() as mcu:
    # Fill array with known pattern
    for i in range(16):
        mcu.set(f"buffer[{i}]", i * 10)

    # Verify all values
    for i in range(16):
        val = mcu.get(f"buffer[{i}]")
        assert val == i * 10, f"buffer[{i}]: expected {i * 10}, got {val}"

    print("Array test passed!")
```

---

## 12. API Reference

### 12.1 McuConnection

#### Constructor

```python
McuConnection(
    inter_cmd_delay_ms: int = 0,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `inter_cmd_delay_ms` | `int` | `0` | Min gap between consecutive CLI invocations (ms) |

**Raises**: `ConnectionError` if `state.json` missing; `SymbolError` if symbols file missing.

#### Connection Lifecycle

| Method | Returns | Description |
|--------|---------|-------------|
| `open()` | `None` | Verify `ramgs.exe` is callable (runs `ramgs status`). |
| `close()` | `None` | Mark session as closed. Safe to call multiple times. |

| Property | Type | Description |
|----------|------|-------------|
| `is_connected` | `bool` | True after `open()`, False after `close()` |
| `port_name` | `str` | Serial port name from state.json (e.g., `"COM3"`) |
| `baud_rate` | `int` | Baud rate from state.json (e.g., `115200`) |
| `symbols` | `list[str]` | All available variable names (read from symbols.json) |

#### Read Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get(var_name)` | `Any` | Read single variable via `ramgs get` |
| `get_many(*var_names)` | `dict` | Read multiple variables in one CLI call |

#### Write Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `set(var_name, value)` | `None` | Write single variable via `ramgs set` |
| `set_many(**kwargs)` | `None` | Write multiple (keyword args, simple names only) |
| `set_dict(assignments)` | `None` | Write multiple from dict (any variable names) |

#### Wait Method

```python
wait_until(
    var_name: str,
    condition,           # value or callable(value) -> bool
    timeout_s: float = 5.0,
    poll_interval_ms: int = 100,
) -> Any
```

Returns the value that satisfied the condition. Raises `TimeoutError` on timeout.

#### Timing Property

| Property | Type | Description |
|----------|------|-------------|
| `inter_cmd_delay_ms` | `int` | Read/write. Min delay between CLI invocations. |

### 12.2 Exceptions

| Exception | Parent | When |
|-----------|--------|------|
| `RamgsError` | `Exception` | Base for all testkit errors |
| `ConnectionError` | `RamgsError` | ramgs.exe not found, state.json missing, port failure |
| `SymbolError` | `RamgsError` | Variable not found, symbols file error |
| `ValueError` | `RamgsError` | Encoding/decoding type error |
| `CommunicationError` | `RamgsError` | MCU not responding, CLI error |
| `TimeoutError` | `CommunicationError` | `wait_until()` timed out |

`TimeoutError` has additional attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `var_name` | `str` | Variable being polled |
| `timeout_s` | `float` | Timeout duration |
| `last_value` | `Any` | Last value read before timeout |

---

## 13. Troubleshooting

### 13.1 "No connection config found"

**Error**: `ConnectionError: No connection config found.`

**Cause**: `~/.ramgs/state.json` does not exist or lacks port information.

**Fix**:
```bash
ramgs open --name COM3 --baud 115200
```

### 13.2 "No symbols file found"

**Error**: `SymbolError: No symbols file found.`

**Cause**: No symbols file path in `state.json`, or the file was deleted/moved.

**Fix**:
```bash
ramgs create firmware.elf
# Or, if you already have symbols.json:
ramgs load path/to/symbols.json
```

### 13.3 "ramgs.exe not found in PATH"

**Error**: `ConnectionError: ramgs.exe not found in PATH.`

**Cause**: The `ramgs.exe` executable is not in the system PATH.

**Fix**:
```bash
# Add to PATH (Windows)
set PATH=%PATH%;F:\works_2026\mcu-terminal\ramgs\dist\ramgs

# Verify
ramgs --version
```

### 13.4 "Failed to open COMx"

**Error**: `ConnectionError: Failed to open COM3: ...`

**Possible causes**:
- The serial port is occupied by another program (e.g., a terminal emulator, another ramgs instance, or the IDE debugger).
- The COM port number changed (e.g., USB adapter was plugged into a different port).
- The device is not connected.

**Fix**:
```bash
# Check available ports
ramgs ports

# If the port changed, update the configuration
ramgs open --name COM5 --baud 115200
```

### 13.5 "Variable not found"

**Error**: `SymbolError: Variable not found: my_var`

**Possible causes**:
- The variable name is misspelled.
- The variable was optimized out by the compiler.
- The symbols file is outdated (firmware was recompiled but `ramgs create` was not re-run).

**Fix**:
```python
# Check available symbols
mcu = McuConnection()
matching = [s for s in mcu.symbols if "my_var" in s]
print(matching)

# Regenerate symbols if needed
# ramgs create firmware.elf
```

### 13.6 wait_until() Timeout

**Error**: `TimeoutError: Timeout waiting for 'cal_done' (last=0, timeout=5.0s)`

**Possible causes**:
- The MCU process is slower than expected.
- The condition will never be met (logic bug in MCU firmware).

**Fix**:
```python
# 1. Increase timeout
mcu.wait_until("cal_done", 1, timeout_s=30.0)

# 2. Use a callback to debug
try:
    mcu.wait_until("cal_done", 1, timeout_s=5.0)
except TimeoutError as e:
    # Inspect MCU state to understand why
    state = mcu.get("cal_state")
    error = mcu.get("cal_error")
    print(f"cal_state={state}, cal_error={error}, last={e.last_value}")
```

### 13.7 Performance Considerations

Since each `get()` / `set()` call spawns a subprocess (`ramgs.exe`), there is inherent overhead:

- **Typical latency**: 100-300ms per call (process startup + serial open/close + communication)
- **Use `get_many()` / `set_dict()`** to batch operations into a single subprocess call
- **For high-speed data collection** (< 100ms intervals), use `ramgs chart` or `ramgs image` CLI commands directly instead of testkit
- **Use `inter_cmd_delay_ms` only if needed** -- setting it to 0 (default) gives maximum throughput
- **Reuse connections** -- creating a session-scoped pytest fixture avoids repeated `open()` overhead
