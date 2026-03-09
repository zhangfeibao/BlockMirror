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

`ramgs.testkit` 是一个用于编写 MCU 自动化测试脚本的 Python 库。它提供了 `McuConnection` 类，维持与 MCU 的持久串口连接，允许你以编程方式读写 RAM 变量。

与 CLI 命令（`ramgs get`、`ramgs set`）每次调用都打开/关闭串口不同，`McuConnection` 在整个测试会话期间保持串口打开，从而获得更高的通信吞吐量。

### 1.2 设计理念

- **零参数构造函数**: `McuConnection()` 从 `~/.ramgs/state.json` 读取所有配置 -- 无需传入任何参数。
- **持久连接**: 串口保持打开，直到你显式调用 `close()`。
- **非侵入性**: 测试库绝不写入 `state.json` -- 它只读取由 `ramgs open` 和 `ramgs create` 设置的配置。
- **异常驱动**: 所有错误通过清晰的异常层次结构报告，天然适配 pytest 等测试框架。

### 1.3 工作流程

```
   CLI (一次性配置)                        Python 测试脚本
   ==================                    ====================

1. ramgs open --name COM3 --baud 115200  -->  state.json 已创建
2. ramgs create firmware.elf             -->  symbols.json 已生成
                                              state.json 已更新
                                                    |
                                                    v
                                         3. McuConnection() 读取 state.json
                                         4. mcu.open() 打开串口
                                         5. mcu.get() / mcu.set() / ...
                                         6. mcu.close() 关闭串口
```

---

## 2. 前置条件

### 2.1 安装

testkit 模块是 `ramgs` 包的一部分。如果你已经安装了 ramgs，无需额外安装。

```bash
# 安装 ramgs（如尚未安装）
cd ramgs
pip install -e .
```

### 2.2 MCU 准备

使用 testkit 前，请确保：

1. 你的 MCU 固件已集成 RAMViewer 库（`ramviewer.h` / `ramviewer.c`）。
2. MCU 已通过串口物理连接到 PC。
3. MCU 固件已带调试符号编译（ELF 文件可用）。

### 2.3 CLI 配置（仅需一次）

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

1. `McuConnection()` 读取 `~/.ramgs/state.json` 获取串口、波特率、字节序、符号文件路径。
2. 加载 `symbols.json` 并构建符号查找表。
3. `with ... as mcu:` 调用 `mcu.open()`，打开串口。
4. `mcu.get("counter")` 解析变量名，解析为内存地址，通过协议发送 READ 请求，接收响应，将原始字节解码为 Python 值。
5. `with` 块退出时，`mcu.close()` 关闭串口。

---

## 4. 连接生命周期

### 4.1 上下文管理器（推荐）

使用 `McuConnection` 最安全的方式是作为上下文管理器。即使发生异常，也能保证串口被关闭。

```python
from ramgs.testkit import McuConnection

with McuConnection() as mcu:
    print(f"Connected to {mcu.port_name} at {mcu.baud_rate} baud")
    print(f"MCU alive: {mcu.ping()}")
    # ... 你的测试代码 ...
# 串口在此自动关闭
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

### 4.4 Ping

使用 `ping()` 验证 MCU 是否响应：

```python
with McuConnection() as mcu:
    if mcu.ping():
        print("MCU is alive")
    else:
        print("MCU not responding")
```

### 4.5 连接信息

```python
mcu = McuConnection()
print(f"Port: {mcu.port_name}")       # 如 "COM3"
print(f"Baud: {mcu.baud_rate}")       # 如 115200
print(f"Symbols: {len(mcu.symbols)}") # 如 750
```

---

## 5. 读取变量

### 5.1 单个变量

```python
with McuConnection() as mcu:
    temp = mcu.get("cal_temp")
    speed = mcu.get("motor_speed")
    flag = mcu.get("status_flags.bit0")
```

### 5.2 批量读取（单次事务）

`get_many()` 在一个协议包中读取所有变量，比多次调用 `get()` 更快。

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

### 5.4 原始字节

如果你需要未经类型解码的原始字节：

```python
with McuConnection() as mcu:
    raw = mcu.get_raw("counter")
    print(f"Raw bytes: {raw.hex()}")  # 如 "2a000000"
```

### 5.5 列出可用变量

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

默认轮询间隔为 100ms。可以根据需要调快或调慢：

```python
with McuConnection() as mcu:
    # 每10ms轮询一次，用于快速变化的变量
    mcu.wait_until("fast_signal", 1, timeout_s=2.0, poll_interval_ms=10)

    # 每500ms轮询一次，用于慢速过程
    mcu.wait_until("boot_done", 1, timeout_s=60.0, poll_interval_ms=500)
```

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
    timeout_ms=1000,        # 每次 MCU 响应最多等待1秒
    retries=5,              # 失败时最多重试5次
    inter_cmd_delay_ms=50,  # 连续命令之间至少间隔50ms
)
```

### 8.2 运行时调整超时

```python
with McuConnection() as mcu:
    # 默认超时
    val = mcu.get("fast_var")

    # 为慢操作增加超时
    mcu.timeout_ms = 2000
    mcu.set("start_long_process", 1)

    # 恢复默认
    mcu.timeout_ms = 500
```

### 8.3 命令间延迟

某些 MCU 在连续命令之间需要间隔。`inter_cmd_delay_ms` 参数确保任意两次操作（get/set/ping）之间保持最小延迟。

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
with McuConnection(inter_cmd_delay_ms=100) as mcu:
    mcu.get("temp")

    # 花了80ms做其他事
    time.sleep(0.08)

    mcu.get("temp")  # 只再等 ~20ms（而非100ms）
```

---

## 9. 错误处理

### 9.1 异常层次结构

```
RamgsError (基类)
  +-- ConnectionError      # 串口问题、state.json 缺失
  +-- SymbolError          # 变量未找到、符号文件错误
  +-- ValueError           # 类型转换/编码错误
  +-- CommunicationError   # MCU 通信失败
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
        poll_interval_ms=50,
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

def test_stress(iterations=1000):
    errors = 0

    with McuConnection(timeout_ms=200, retries=1) as mcu:
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
    print(f"Throughput: {iterations / elapsed:.0f} ops/s")
    print(f"Errors: {errors} ({errors / iterations * 100:.1f}%)")

test_stress()
```

### 11.3 数据记录

```python
import csv
import time
from ramgs.testkit import McuConnection

VARIABLES = ["temp", "pressure", "humidity"]
INTERVAL_S = 0.1
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
    with McuConnection(timeout_ms=1000) as mcu:
        # Step 1: 检查 MCU 是否存活
        assert mcu.ping(), "MCU not responding"

        # Step 2: 等待初始化完成
        try:
            mcu.wait_until("init_done", 1, timeout_s=5.0)
        except TimeoutError:
            print("ERROR: MCU did not finish initialization")
            print(f"  init_state = {mcu.get('init_state')}")
            return False

        # Step 3: 验证外设状态
        status = mcu.get_many(
            "uart_ok", "spi_ok", "adc_ok", "timer_ok"
        )
        for name, ok in status.items():
            if not ok:
                print(f"ERROR: {name} failed")
                return False

        # Step 4: 验证固件版本
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
    timeout_ms: int = 500,
    retries: int = 3,
    inter_cmd_delay_ms: int = 0,
)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `timeout_ms` | `int` | `500` | 每次 MCU 响应超时时间（ms） |
| `retries` | `int` | `3` | 每个请求的最大重试次数 |
| `inter_cmd_delay_ms` | `int` | `0` | 连续命令之间的最小间隔（ms） |

**异常**: 若 `state.json` 缺失抛出 `ConnectionError`；若符号文件缺失抛出 `SymbolError`。

#### 连接生命周期

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `open()` | `None` | 打开串口。失败时抛出 `ConnectionError`。 |
| `close()` | `None` | 关闭串口。可安全多次调用。 |
| `ping()` | `bool` | 发送 PING，若 MCU 响应 PONG 则返回 True。 |

| 属性 | 类型 | 说明 |
|------|------|------|
| `is_connected` | `bool` | 串口是否已打开 |
| `port_name` | `str` | 串口名称（如 `"COM3"`） |
| `baud_rate` | `int` | 波特率（如 `115200`） |
| `symbols` | `list[str]` | 所有可用变量名（已排序） |

#### 读取方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `get(var_name)` | `Any` | 读取单个变量，返回解码后的值 |
| `get_many(*var_names)` | `dict` | 单次事务读取多个变量 |
| `get_raw(var_name)` | `bytes` | 读取原始字节（不解码） |

#### 写入方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `set(var_name, value)` | `None` | 写入单个变量 |
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
| `timeout_ms` | `int` | 可读写。每次响应超时时间。 |
| `inter_cmd_delay_ms` | `int` | 可读写。命令间最小延迟。 |

### 12.2 异常

| 异常 | 父类 | 触发时机 |
|------|------|----------|
| `RamgsError` | `Exception` | 所有 testkit 错误的基类 |
| `ConnectionError` | `RamgsError` | 串口打开失败、state.json 缺失、未连接 |
| `SymbolError` | `RamgsError` | 变量未找到、符号文件错误 |
| `ValueError` | `RamgsError` | 编码/解码类型错误 |
| `CommunicationError` | `RamgsError` | MCU 未响应、协议错误 |
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

### 13.3 "Failed to open COMx"

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

### 13.4 "Timeout: No response from MCU"

**错误**: `CommunicationError: Read 'counter' failed: Timeout: No response from MCU`

**可能原因**:
- MCU 固件未运行（停止、处于调试模式或崩溃）。
- PC 与 MCU 之间波特率不匹配。
- TX/RX 线接反。
- MCU 固件未集成 RAMViewer 库。

**解决**:
```python
# 1. 尝试更长的超时
mcu = McuConnection(timeout_ms=2000, retries=5)

# 2. 用 ping 验证
with mcu:
    print(mcu.ping())  # 应返回 True
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

### 13.7 性能优化建议

1. **使用 `get_many()` 代替多次 `get()` 调用** -- 在单次协议事务中读取所有变量。

2. **快速轮询时减少重试次数**：
   ```python
   mcu = McuConnection(timeout_ms=100, retries=1)
   ```

3. **仅在必要时使用 `inter_cmd_delay_ms`** -- 设为 0（默认）可获得最大吞吐量。

4. **复用连接** -- 使用会话级 pytest fixture 避免每个测试都重新打开串口。
