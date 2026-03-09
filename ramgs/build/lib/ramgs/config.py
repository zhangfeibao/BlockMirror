"""
RAMViewer Configuration Constants
"""

# Protocol constants
SOF = 0xAA  # Start of frame

# Command types
CMD_READ_VAR = 0x01
CMD_WRITE_VAR = 0x02
CMD_READ_RESP = 0x81
CMD_WRITE_RESP = 0x82
CMD_ERROR = 0xFF
CMD_PING = 0x10
CMD_PONG = 0x90

# Error codes
ERR_OK = 0x00
ERR_CRC = 0x01
ERR_ADDR = 0x02
ERR_SIZE = 0x03
ERR_CMD = 0x04
ERR_TIMEOUT = 0x05

# Error messages
ERROR_MESSAGES = {
    ERR_OK: "OK",
    ERR_CRC: "CRC mismatch",
    ERR_ADDR: "Invalid address",
    ERR_SIZE: "Invalid size",
    ERR_CMD: "Unknown command",
    ERR_TIMEOUT: "Timeout",
}

# Bitfield marker (0xFF means not a bitfield)
NO_BITFIELD = 0xFF

# Communication settings
DEFAULT_TIMEOUT_MS = 500
MAX_RETRIES = 3
MAX_PAYLOAD_SIZE = 256
MAX_VARIABLES = 30

# Frame overhead: SOF(1) + LEN(2) + CMD(1) + SEQ(1) + CRC(2) = 7
FRAME_OVERHEAD = 7

# Default symbols file name
DEFAULT_SYMBOLS_FILE = "symbols.json"

# Version
VERSION = "1.0.0"
