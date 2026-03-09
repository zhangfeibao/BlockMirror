# ELF Symbol Extractor (elfsym)

A command-line tool for extracting symbol information from ELF files and exporting to JSON format.

## Features

- Parse ELF files with DWARF debug information (*.elf, *.axf, *.abs, *.out)
- Extract global variables with memory addresses
- Support for complex types: structs, unions, arrays, enums, pointers
- Export to JSON format for easy integration with other tools

## Build

Requires .NET 8.0 SDK.

```bash
cd ElfSymbolExtractor
dotnet build -c Release
```

Output: `bin/Release/net8.0/elfsym.exe`

## Usage

```
elfsym <input-file> [options]

Arguments:
  <input-file>          ELF file to parse

Options:
  -o, --output <file>   Output JSON file path (default: <input>.symbols.json)
  --compact             Output compact JSON without indentation
  -v, --verbose         Show detailed progress information
  --version             Show version information
  -h, --help            Show help message
```

### Examples

```bash
# Basic usage - output to firmware.symbols.json
elfsym firmware.elf

# Specify output file
elfsym firmware.elf -o symbols.json

# Verbose mode with compact output
elfsym firmware.axf -v --compact

# Show help
elfsym --help
```

### Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Input file not found |
| 2 | Invalid ELF format |
| 3 | readelf.exe not found |
| 4 | Parse error |
| 5 | Output write error |
| 6 | Invalid arguments |

---

## JSON Output Format

### Schema Overview

```json
{
  "schemaVersion": "1.0",
  "toolVersion": "1.0.0.0",
  "exportTime": "2026-01-04T10:19:05Z",
  "sourceElfFile": "C:\\path\\to\\firmware.elf",
  "totalSymbols": 750,
  "symbols": [ ... ]
}
```

### Root Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `schemaVersion` | string | JSON schema version for compatibility checking |
| `toolVersion` | string | Version of elfsym tool that generated this file |
| `exportTime` | string | ISO 8601 timestamp of export |
| `sourceElfFile` | string | Absolute path to source ELF file |
| `totalSymbols` | integer | Total number of symbols in the `symbols` array |
| `symbols` | array | Array of symbol objects |

### Symbol Object Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Symbol name (variable name) |
| `dataType` | string | Yes | Data type name (e.g., "uint32_t", "float", "MyStruct") |
| `baseDataType` | string | No | Underlying base type (e.g., "unsigned int" for typedef) |
| `sizeInBytes` | integer | Yes | Size of the symbol in bytes |
| `memoryAddress` | string | Yes | Memory address in hex format (e.g., "0x20001000") |
| `sourceFile` | string | Yes | Source file name where symbol is defined |
| `isPointer` | boolean | No | `true` if symbol is a pointer type |
| `isArray` | boolean | No | `true` if symbol is an array type |
| `isStruct` | boolean | No | `true` if symbol is a struct/union/class type |
| `isEnum` | boolean | No | `true` if symbol is an enumeration type |
| `arrayDimensions` | integer[] | No | Array dimensions (e.g., `[10, 20]` for `arr[10][20]`) |
| `members` | SymbolObject[] | No | Structure/union members (only when `isStruct` is true) |
| `enumValues` | object | No | Enum name-value mapping (only when `isEnum` is true) |
| `memberOffset` | integer | No | Offset from parent struct base address (for members) |
| `bitSize` | integer | No | Bit field size (0 if not a bit field) |
| `bitOffset` | integer | No | Bit field offset within the byte |

**Note:** Fields with `No` in Required column are omitted when not applicable (null/false/0).

---

## Symbol Type Examples

### Basic Type

```json
{
  "name": "g_counter",
  "dataType": "uint32_t",
  "baseDataType": "unsigned int",
  "sizeInBytes": 4,
  "memoryAddress": "0x20001000",
  "sourceFile": "main.c"
}
```

### Pointer Type

```json
{
  "name": "data_ptr",
  "dataType": "uint8_t *",
  "baseDataType": "unsigned char",
  "sizeInBytes": 4,
  "memoryAddress": "0x20001004",
  "sourceFile": "main.c",
  "isPointer": true
}
```

### Array Type

```json
{
  "name": "buffer",
  "dataType": "uint8_t[64]",
  "baseDataType": "unsigned char",
  "sizeInBytes": 1,
  "memoryAddress": "0x20001008",
  "sourceFile": "comm.c",
  "isArray": true,
  "arrayDimensions": [64]
}
```

### Multi-dimensional Array

```json
{
  "name": "matrix",
  "dataType": "int16_t[10, 20]",
  "baseDataType": "signed short",
  "sizeInBytes": 2,
  "memoryAddress": "0x20001048",
  "sourceFile": "math.c",
  "isArray": true,
  "arrayDimensions": [10, 20]
}
```

### Struct Type with Members

```json
{
  "name": "sensor_data",
  "dataType": "SensorData",
  "baseDataType": "<struct>",
  "sizeInBytes": 12,
  "memoryAddress": "0x20002000",
  "sourceFile": "sensors.c",
  "isStruct": true,
  "members": [
    {
      "name": "temperature",
      "dataType": "int16_t",
      "baseDataType": "signed short",
      "sizeInBytes": 2,
      "memoryAddress": "0x20002000",
      "sourceFile": "sensors.c",
      "memberOffset": 0
    },
    {
      "name": "humidity",
      "dataType": "int16_t",
      "baseDataType": "signed short",
      "sizeInBytes": 2,
      "memoryAddress": "0x20002002",
      "sourceFile": "sensors.c",
      "memberOffset": 2
    },
    {
      "name": "pressure",
      "dataType": "float",
      "baseDataType": "float",
      "sizeInBytes": 4,
      "memoryAddress": "0x20002004",
      "sourceFile": "sensors.c",
      "memberOffset": 4
    }
  ]
}
```

### Enum Type

```json
{
  "name": "current_state",
  "dataType": "SystemState",
  "baseDataType": "<enum>",
  "sizeInBytes": 1,
  "memoryAddress": "0x20003000",
  "sourceFile": "state.c",
  "isEnum": true,
  "enumValues": {
    "STATE_IDLE": 0,
    "STATE_RUNNING": 1,
    "STATE_ERROR": 2,
    "STATE_SHUTDOWN": 3
  }
}
```

---

## Parsing Guidelines for Other Tools

### Reading the JSON File

```python
# Python example
import json

with open('firmware.symbols.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Access metadata
print(f"Schema version: {data['schemaVersion']}")
print(f"Total symbols: {data['totalSymbols']}")

# Iterate symbols
for symbol in data['symbols']:
    print(f"{symbol['name']}: {symbol['dataType']} @ {symbol['memoryAddress']}")
```

```csharp
// C# example
using System.Text.Json;

var json = File.ReadAllText("firmware.symbols.json");
var data = JsonSerializer.Deserialize<ExportResult>(json);

foreach (var symbol in data.Symbols)
{
    Console.WriteLine($"{symbol.Name}: {symbol.DataType} @ {symbol.MemoryAddress}");
}
```

### Calculating Member Addresses

For struct members, the absolute memory address can be calculated as:

```
member_address = parent_address + memberOffset
```

The `memoryAddress` field in members already contains the calculated absolute address.

### Handling Type Flags

Use type flags to determine how to interpret the symbol:

```python
def get_symbol_category(symbol):
    if symbol.get('isPointer'):
        return 'pointer'
    elif symbol.get('isArray'):
        return 'array'
    elif symbol.get('isStruct'):
        return 'struct'
    elif symbol.get('isEnum'):
        return 'enum'
    else:
        return 'primitive'
```

### Memory Address Parsing

Memory addresses are always in hexadecimal format with "0x" prefix:

```python
def parse_address(addr_str):
    return int(addr_str, 16)

address = parse_address("0x20001000")  # Returns 536875008
```

---

## Special Type Markers

| Marker | Description |
|--------|-------------|
| `<struct>` | Anonymous or unnamed structure type |
| `<union>` | Anonymous or unnamed union type |
| `<class>` | C++ class type |
| `<enum>` | Anonymous or unnamed enumeration type |
| `<function pointer>` | Function pointer type |

---

## Limitations

- Only extracts global/static variables with memory addresses (DW_OP_addr)
- Local variables and function parameters are not included
- Requires ELF file with DWARF debug information
- Uses GNU readelf for DWARF parsing

## Dependencies

- readelf.exe (included in Util/ELF directory)
- .NET 8.0 Runtime

## License

Internal tool for ucProbe project.
