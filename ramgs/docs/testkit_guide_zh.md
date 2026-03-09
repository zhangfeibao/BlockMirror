# RAMViewer 测试自动化库 (testkit) 使用指南

## 目录

1. [简介](#1-简介)
2. [前置条件](#2-前置条件)
3. [快速入门](#3-快速入门)
4. [连接生命周期](#4-连接生命周期)
5. [读取变量](#5-读取变量)
6. [写入变量](#6-写入变量)
7. [等待条件](#7-等待条件)
8. [时序控制](#8-时序控制)
9. [错误处理](#9-错误处理)
10. [pytest 集成](#10-pytest-集成)
11. [实战示例](#11-实战示例)
12. [API 参考](#12-api-参考)
13. [故障排除](#13-故障排除)

---

## 1. 简介

### 1.1 概述

`ramgs.testkit` 是一个用于编写 MCU 自动化测试脚本的 Python 库。它提供了 `McuConnection` 类，通过 `subprocess` 调用 `ramgs.exe` CLI 来读写 MCU RAM 变量。

该库**零内部依赖** -- 不依赖 ramgs Python 包的任何内部模块，仅需 `ramgs.exe` 在系统 PATH 中。你可以将 `testkit.py` 作为独立文件复制到任何项目中使用。

### 1.2 架构

```
  你的测试脚本 (Python)
         |
         v
  McuConnection (testkit.py)
         |  subprocess.run()
         v
  ramgs.exe (CLI)
         |  串口 (每次调用: 打开 -> 读写 -> 关闭)
         v
  MCU (RAMViewer library)
```

每次 `get()` / `set()` 调用都会启动一个 `ramgs.exe` 子进程。CLI 内部自行打开串口、执行操作、关闭串口。这种设计使 testkit 与 ramgs 内部实现完全解耦。

### 1.3 设计理念

- **零参数构造函数**: `McuConnection()` 从 `~/.ramgs/state.json` 读取所有配置 -- 无需传入任何参数。
- **零依赖**: 仅需 `ramgs.exe` 在 PATH 中 + Python 标准库。无需 `pip install`。
- **非侵入性**: 测试库绝不写入 `state.json` -- 它只读取由 `ramgs open` 和 `ramgs create` 设置的配置。
- **异常驱动**: 所有错误通过清晰的异常层次结构报告，天然适配 pytest 等测试框架。

### 1.4 工作流程

```
   CLI (一次性配置)                        Python 测试脚本
   ==================                    ====================

1. ramgs open --name COM3 --baud 115200  -->  state.json 已创建
2. ramgs create firmware.elf             -->  symbols.json 已生成
                                              state.json 已更新
                                                    |
                                                    v
                                         3. McuConnection() 读取 state.json
                                         4. mcu.open() 验证 ramgs.exe 可用
                                         5. mcu.get()  --> 子进程: ramgs get ...
                                            mcu.set()  --> 子进程: ramgs set ...
                                         6. mcu.close()
```

---

## 2. 前置条件

### 2.1 ramgs.exe 加入 PATH

testkit 通过 subprocess 调用 `ramgs.exe`。确保它可被访问：

```bash
# 验证 ramgs.exe 在 PATH 中
ramgs --version

# 如果不在，将 dist 目录加入系统 PATH：
# 例如，将 F:\works_2026\mcu-terminal\ramgs\dist\ramgs 加入 PATH
```

### 2.2 使用 testkit.py

**方式 A -- 作为 ramgs 包的一部分**（如已安装）：

```python
from ramgs.testkit import McuConnection
```

**方式 B -- 作为独立文件**（复制到你的项目中）：

```bash
# 将 testkit.py 复制到你的测试项目中
copy F:\works_2026\mcu-terminal\ramgs\ramgs\testkit.py my_tests\testkit.py
```

```python
from testkit import McuConnection
```

由于 testkit.py 没有任何 ramgs 内部导入（仅使用 Python 标准库），它可以作为独立文件工作。

### 2.3 MCU 准备

使用 testkit 前，请确保：

1. 你的 MCU 固件已集成 RAMViewer 库（`ramviewer.h` / `ramviewer.c`）。
2. MCU 已通过串口物理连接到 PC。
3. MCU 固件已带调试符号编译（ELF 文件可用）。

### 2.4 CLI 配置（仅需一次）

使用 testkit **之前**，必须运行以下 CLI 命令：

```bash
# 第1步：注册串口和波特率
ramgs open --name COM3 --baud 115200

# 第2步：从固件 ELF 文件生成 symbols.json
ramgs create firmware.elf
```

这些命令会创建 `~/.ramgs/state.json`，内容包括：
- 串口名称（如 `COM3`）
- 波特率（如 `115200`）
- 字节序（默认：`little`）
- `symbols.json` 文件路径

你可以验证当前配置：

```bash
ramgs status
```

---

## 3. 快速入门

### 3.1 最简示例

```python
from ramgs.testkit import McuConnection

with McuConnection() as mcu:
    # 读取变量
    value = mcu.get("counter")
    print(f"counter = {value}")

    # 写入变量
    mcu.set("counter", 0)

    # 验证
    assert mcu.get("counter") == 0
    print("Test passed!")
```

### 3.2 内部执行过程

1. `McuConnection()` 读取 `~/.ramgs/state.json` 获取串口、波特率、符号文件路径，验证配置有效。
2. `with ... as mcu:` 调用 `mcu.open()`，运行 `ramgs status` 验证 `ramgs.exe` 可用。
3. `mcu.get("counter")` 运行 `subprocess.run(["ramgs", "get", "counter"])`，解析 stdout 输出 `counter=42`，返回 `42`。
4. `mcu.set("counter", 0)` 运行 `subprocess.run(["ramgs", "set", "counter=0"])`，验证执行成功。
5. `with` 块退出时，`mcu.close()` 标记会话结束。

---

## 4. 连接生命周期

### 4.1 上下文管理器（推荐）

```python
from ramgs.testkit import McuConnection

with McuConnection() as mcu:
    print(f"Connected to {mcu.port_name} at {mcu.baud_rate} baud")
    # ... 你的测试代码 ...
# 会话结束
```

### 4.2 手动打开/关闭

对于长时间运行的会话或 pytest fixture，你可以手动管理生命周期。

```python
mcu = McuConnection()
mcu.open()

try:
    # ... 你的测试代码 ...
finally:
    mcu.close()
```

### 4.3 连接状态

```python
mcu = McuConnection()
print(mcu.is_connected)  # False -- 尚未打开

mcu.open()
print(mcu.is_connected)  # True

mcu.close()
print(mcu.is_connected)  # False
```

### 4.4 连接信息

```python
mcu = McuConnection()
print(f"Port: {mcu.port_name}")       # 如 "COM3"
print(f"Baud: {mcu.baud_rate}")       # 如 115200
print(f"Symbols: {len(mcu.symbols)}") # 如 750
```

> **注意**: `port_name` 和 `baud_rate` 从 `state.json` 读取。`symbols` 属性直接读取 `symbols.json`（无需 CLI 调用）。

---

## 5. 读取变量

### 5.1 单个变量

```python
with McuConnection() as mcu:
    temp = mcu.get("cal_temp")
    speed = mcu.get("motor_speed")
    flag = mcu.get("status_flags.bit0")
```

### 5.2 批量读取（单次 CLI 调用）

`get_many()` 在一次 `ramgs get var1,var2,...` 调用中读取所有变量，比多次调用 `get()` 快（一个子进程 vs 多个）。

```python
with McuConnection() as mcu:
    vals = mcu.get_many("temp", "speed", "counter")
    # vals = {"temp": 25.3, "speed": 1200, "counter": 42}

    print(f"Temperature: {vals['temp']}")
    print(f"Speed: {vals['speed']}")
```

### 5.3 变量名语法

testkit 支持与 CLI 相同的变量语法：

| 语法 | 示例 | 说明 |
|------|------|------|
| 简单变量 | `counter` | 简单变量 |
| 结构体成员 | `config.baudrate` | 结构体成员访问 |
| 数组元素 | `data[0]` | 按索引访问数组元素 |
| 组合访问 | `sensors[2].temp` | 结构体数组 |
| 文件过滤 | `counter@main` | 消除同名变量歧义 |

### 5.4 列出可用变量

```python
mcu = McuConnection()
for name in mcu.symbols[:20]:
    print(name)
# 输出前20个变量名（按字母排序）
```

---

## 6. 写入变量

### 6.1 单个变量

```python
with McuConnection() as mcu:
    mcu.set("counter", 0)
    mcu.set("motor_speed", 1500)
    mcu.set("config.mode", 2)
    mcu.set("cal_temp", 25.5)  # 浮点数
```

### 6.2 批量写入 -- 关键字参数

适用于简单变量名（合法的 Python 标识符，无点号或方括号）：

```python
with McuConnection() as mcu:
    mcu.set_many(counter=0, speed=100, mode=1)
```

### 6.3 批量写入 -- 字典

适用于包含点号、方括号或 `@` 的变量名：

```python
with McuConnection() as mcu:
    mcu.set_dict({
        "config.mode": 2,
        "arr[0]": 10,
        "arr[1]": 20,
        "arr[2]": 30,
    })
```

### 6.4 读-改-写 模式

```python
with McuConnection() as mcu:
    current = mcu.get("counter")
    mcu.set("counter", current + 10)
```

---

## 7. 等待条件

### 7.1 等待精确值

`wait_until()` 轮询变量，直到条件满足或超时。

```python
with McuConnection() as mcu:
    mcu.set("start_calibration", 1)

    # 等待 cal_done 变为 1（最多10秒）
    mcu.wait_until("cal_done", 1, timeout_s=10.0)
    print("Calibration complete!")
```

### 7.2 使用 Lambda 条件

传入可调用对象实现更复杂的条件判断：

```python
with McuConnection() as mcu:
    # 等待温度超过50度
    final_temp = mcu.wait_until(
        "temperature",
        lambda t: t > 50.0,
        timeout_s=30.0
    )
    print(f"Temperature reached {final_temp}")
```

```python
with McuConnection() as mcu:
    # 等待计数器进入某个范围
    mcu.wait_until(
        "counter",
        lambda c: 90 <= c <= 110,
        timeout_s=5.0
    )
```

### 7.3 自定义轮询间隔

默认轮询间隔为 100ms。可以根据需要调整：

```python
with McuConnection() as mcu:
    # 每500ms轮询一次，用于慢速过程
    mcu.wait_until("boot_done", 1, timeout_s=60.0, poll_interval_ms=500)
```

> **注意**: 由于每次轮询都启动一个子进程，过短的间隔（< 50ms）可能无法实现，因为进程启动本身有开销。

### 7.4 处理超时

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

## 8. 时序控制

### 8.1 构造函数参数

```python
mcu = McuConnection(
    inter_cmd_delay_ms=50,  # CLI 调用之间至少间隔 50ms
)
```

### 8.2 命令间延迟

某些 MCU 在连续命令之间需要间隔。`inter_cmd_delay_ms` 参数确保任意两次 CLI 调用之间保持最小延迟。

```python
# MCU 需要命令间至少20ms间隔
mcu = McuConnection(inter_cmd_delay_ms=20)

with mcu:
    mcu.set("a", 1)   # 立即执行
    mcu.set("b", 2)   # 等待 ~20ms 后执行
    mcu.set("c", 3)   # 等待 ~20ms 后执行
```

延迟是 "智能" 的 -- 如果你在两次调用之间已经花费了时间（如做计算），只会补充剩余的间隔。

```python
import time

with McuConnection(inter_cmd_delay_ms=100) as mcu:
    mcu.get("temp")

    # 花了80ms做其他事
    time.sleep(0.08)

    mcu.get("temp")  # 只再等 ~20ms（而非100ms）
```

### 8.3 运行时调整

```python
with McuConnection() as mcu:
    mcu.inter_cmd_delay_ms = 50   # 放慢速度
    # ... 慢速操作 ...
    mcu.inter_cmd_delay_ms = 0    # 恢复全速
```

---

## 9. 错误处理

### 9.1 异常层次结构

```
RamgsError (基类)
  +-- ConnectionError      # ramgs.exe 未找到、state.json 缺失、串口故障
  +-- SymbolError          # 变量未找到、符号文件错误
  +-- ValueError           # 类型转换/编码错误
  +-- CommunicationError   # MCU 通信失败、CLI 错误
        +-- TimeoutError   # wait_until() 超时
```

### 9.2 常见异常

#### ConnectionError -- 没有配置

```python
from ramgs.testkit import McuConnection, ConnectionError

try:
    mcu = McuConnection()
except ConnectionError as e:
    print(f"Setup error: {e}")
    print("Run 'ramgs open --name COM3 --baud 115200' first")
```

#### ConnectionError -- ramgs.exe 不在 PATH 中

```python
try:
    with McuConnection() as mcu:
        mcu.get("counter")
except ConnectionError as e:
    print(f"Cannot find ramgs.exe: {e}")
    print("Add the ramgs dist directory to your system PATH")
```

#### SymbolError -- 变量未找到

```python
from ramgs.testkit import McuConnection, SymbolError

with McuConnection() as mcu:
    try:
        mcu.get("nonexistent_var")
    except SymbolError as e:
        print(f"Symbol error: {e}")
```

#### CommunicationError -- MCU 未响应

```python
from ramgs.testkit import McuConnection, CommunicationError

with McuConnection() as mcu:
    try:
        mcu.get("counter")
    except CommunicationError as e:
        print(f"MCU error: {e}")
        # 检查物理连接、MCU 供电、固件是否在运行
```

### 9.3 捕获所有 testkit 错误

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

## 10. pytest 集成

### 10.1 会话级 Fixture

在整个测试会话中共享一个连接：

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

### 10.2 函数级 Fixture（隔离）

每个测试获得独立的连接：

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

### 10.3 测试示例

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

### 10.4 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 带详细输出运行
pytest tests/ -v -s

# 运行特定测试
pytest tests/test_calibration.py::test_counter_reset -v
```

### 10.5 带重置的 Fixture

在每个测试前重置 MCU 状态：

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

## 11. 实战示例

### 11.1 PID 控制器调参验证

```python
from ramgs.testkit import McuConnection

with McuConnection(inter_cmd_delay_ms=10) as mcu:
    # 设置 PID 参数
    mcu.set_dict({
        "pid.kp": 1.5,
        "pid.ki": 0.1,
        "pid.kd": 0.05,
        "pid.setpoint": 100.0,
    })

    # 使能控制器
    mcu.set("pid.enable", 1)

    # 等待输出到达目标值（允许 5% 误差）
    mcu.wait_until(
        "pid.output",
        lambda v: 95.0 <= v <= 105.0,
        timeout_s=10.0,
        poll_interval_ms=200,
    )

    # 检查是否有过冲
    peak = mcu.get("pid.output_peak")
    assert peak < 120.0, f"Excessive overshoot: {peak}"

    print("PID tuning validated!")
```

### 11.2 通信协议压力测试

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

> **注意**: 吞吐量受子进程开销限制（每次调用约 100-300ms）。如需高速数据采集，请直接使用 `ramgs chart` 或 `ramgs image` CLI 命令。

### 11.3 数据记录

```python
import csv
import time
from ramgs.testkit import McuConnection

VARIABLES = ["temp", "pressure", "humidity"]
INTERVAL_S = 1.0  # 1秒（子进程开销使亚秒级不实际）
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

### 11.4 启动序列验证

```python
from ramgs.testkit import McuConnection, TimeoutError

def verify_boot_sequence():
    with McuConnection() as mcu:
        # Step 1: 等待初始化完成
        try:
            mcu.wait_until("init_done", 1, timeout_s=5.0)
        except TimeoutError:
            print("ERROR: MCU did not finish initialization")
            print(f"  init_state = {mcu.get('init_state')}")
            return False

        # Step 2: 验证外设状态
        status = mcu.get_many(
            "uart_ok", "spi_ok", "adc_ok", "timer_ok"
        )
        for name, ok in status.items():
            if not ok:
                print(f"ERROR: {name} failed")
                return False

        # Step 3: 验证固件版本
        version = mcu.get("firmware_version")
        print(f"Firmware version: {version}")

        print("Boot sequence OK")
        return True

verify_boot_sequence()
```

### 11.5 数组填充与验证

```python
from ramgs.testkit import McuConnection

with McuConnection() as mcu:
    # 用已知模式填充数组
    for i in range(16):
        mcu.set(f"buffer[{i}]", i * 10)

    # 验证所有值
    for i in range(16):
        val = mcu.get(f"buffer[{i}]")
        assert val == i * 10, f"buffer[{i}]: expected {i * 10}, got {val}"

    print("Array test passed!")
```

---

## 12. API 参考

### 12.1 McuConnection

#### 构造函数

```python
McuConnection(
    inter_cmd_delay_ms: int = 0,
)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `inter_cmd_delay_ms` | `int` | `0` | 连续 CLI 调用之间的最小间隔（ms） |

**异常**: 若 `state.json` 缺失抛出 `ConnectionError`；若符号文件缺失抛出 `SymbolError`。

#### 连接生命周期

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `open()` | `None` | 验证 `ramgs.exe` 可用（运行 `ramgs status`）。 |
| `close()` | `None` | 标记会话结束。可安全多次调用。 |

| 属性 | 类型 | 说明 |
|------|------|------|
| `is_connected` | `bool` | `open()` 后为 True，`close()` 后为 False |
| `port_name` | `str` | 来自 state.json 的串口名称（如 `"COM3"`） |
| `baud_rate` | `int` | 来自 state.json 的波特率（如 `115200`） |
| `symbols` | `list[str]` | 所有可用变量名（从 symbols.json 读取） |

#### 读取方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `get(var_name)` | `Any` | 通过 `ramgs get` 读取单个变量 |
| `get_many(*var_names)` | `dict` | 在一次 CLI 调用中读取多个变量 |

#### 写入方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `set(var_name, value)` | `None` | 通过 `ramgs set` 写入单个变量 |
| `set_many(**kwargs)` | `None` | 批量写入（关键字参数，仅限简单变量名） |
| `set_dict(assignments)` | `None` | 批量写入（字典，支持任意变量名） |

#### 等待方法

```python
wait_until(
    var_name: str,
    condition,           # 具体值 或 callable(value) -> bool
    timeout_s: float = 5.0,
    poll_interval_ms: int = 100,
) -> Any
```

返回满足条件的值。超时时抛出 `TimeoutError`。

#### 时序属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `inter_cmd_delay_ms` | `int` | 可读写。CLI 调用间最小延迟。 |

### 12.2 异常

| 异常 | 父类 | 触发时机 |
|------|------|----------|
| `RamgsError` | `Exception` | 所有 testkit 错误的基类 |
| `ConnectionError` | `RamgsError` | ramgs.exe 未找到、state.json 缺失、串口故障 |
| `SymbolError` | `RamgsError` | 变量未找到、符号文件错误 |
| `ValueError` | `RamgsError` | 编码/解码类型错误 |
| `CommunicationError` | `RamgsError` | MCU 未响应、CLI 错误 |
| `TimeoutError` | `CommunicationError` | `wait_until()` 超时 |

`TimeoutError` 的额外属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `var_name` | `str` | 正在轮询的变量 |
| `timeout_s` | `float` | 超时时长 |
| `last_value` | `Any` | 超时前最后读到的值 |

---

## 13. 故障排除

### 13.1 "No connection config found"

**错误**: `ConnectionError: No connection config found.`

**原因**: `~/.ramgs/state.json` 不存在或缺少端口信息。

**解决**:
```bash
ramgs open --name COM3 --baud 115200
```

### 13.2 "No symbols file found"

**错误**: `SymbolError: No symbols file found.`

**原因**: `state.json` 中没有符号文件路径，或文件已被删除/移动。

**解决**:
```bash
ramgs create firmware.elf
# 或者已有 symbols.json：
ramgs load path/to/symbols.json
```

### 13.3 "ramgs.exe not found in PATH"

**错误**: `ConnectionError: ramgs.exe not found in PATH.`

**原因**: `ramgs.exe` 不在系统 PATH 中。

**解决**:
```bash
# 添加到 PATH（Windows）
set PATH=%PATH%;F:\works_2026\mcu-terminal\ramgs\dist\ramgs

# 验证
ramgs --version
```

### 13.4 "Failed to open COMx"

**错误**: `ConnectionError: Failed to open COM3: ...`

**可能原因**:
- 串口被其他程序占用（如终端模拟器、另一个 ramgs 实例或 IDE 调试器）。
- COM 端口号变了（如 USB 适配器插到了不同的端口）。
- 设备未连接。

**解决**:
```bash
# 检查可用端口
ramgs ports

# 如果端口变了，更新配置
ramgs open --name COM5 --baud 115200
```

### 13.5 "Variable not found"

**错误**: `SymbolError: Variable not found: my_var`

**可能原因**:
- 变量名拼写错误。
- 变量被编译器优化掉了。
- 符号文件过期（固件重新编译后未重新运行 `ramgs create`）。

**解决**:
```python
# 查找可用符号
mcu = McuConnection()
matching = [s for s in mcu.symbols if "my_var" in s]
print(matching)

# 如需要则重新生成符号
# ramgs create firmware.elf
```

### 13.6 wait_until() 超时

**错误**: `TimeoutError: Timeout waiting for 'cal_done' (last=0, timeout=5.0s)`

**可能原因**:
- MCU 进程比预期慢。
- 条件永远不会满足（MCU 固件逻辑 Bug）。

**解决**:
```python
# 1. 增加超时时间
mcu.wait_until("cal_done", 1, timeout_s=30.0)

# 2. 用回调调试
try:
    mcu.wait_until("cal_done", 1, timeout_s=5.0)
except TimeoutError as e:
    # 检查 MCU 状态以了解原因
    state = mcu.get("cal_state")
    error = mcu.get("cal_error")
    print(f"cal_state={state}, cal_error={error}, last={e.last_value}")
```

### 13.7 性能说明

由于每次 `get()` / `set()` 调用都启动一个子进程（`ramgs.exe`），存在固有开销：

- **典型延迟**: 每次调用约 100-300ms（进程启动 + 串口打开/关闭 + 通信）
- **使用 `get_many()` / `set_dict()`** 将操作合并为单次子进程调用
- **高速数据采集**（< 100ms 间隔），请直接使用 `ramgs chart` 或 `ramgs image` CLI 命令
- **仅在必要时使用 `inter_cmd_delay_ms`** -- 设为 0（默认）可获得最大吞吐量
- **复用连接** -- 使用会话级 pytest fixture 避免重复 `open()` 的开销
