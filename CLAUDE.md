# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build Commands

```bash
npm install                  # Install dependencies
npm run build                # Production build (minified)
npm run devbuild             # Development build
npm run watch                # Watch mode for development
npm run electron:start       # Launch Electron desktop app
npm run pack:win             # Package as Windows app (output: release/win-unpacked/)
```

If you encounter `Error: error:0308010C:digital envelope routines::unsupported`, run first:
```bash
export NODE_OPTIONS=--openssl-legacy-provider
```

Build output goes to `dist/`:
- `dist/block_mirror.js` — main library (BlockMirror + AST handlers, no Blockly/CodeMirror)
- `dist/skulpt_parser.js` — bundled Skulpt Python parser
- `dist/block_mirror.css` — styles

No linting or formatting tools are configured. The only config file is `.babelrc` (`@babel/preset-env`).

## Testing

There is no automated test suite. Testing is done by opening HTML files in a browser:
- `test/simple.html` — loads from `dist/` (production)
- `test/simple_dev.html` — loads source files directly (development, no build needed)
- `test/simple_v2.html` — entry point used by the Electron app (has terminal panel)
- `test/simple_prod.html` — production variant
- `test/minimal_skulpt.html` — minimal test for Skulpt parser only

## Architecture Overview

BlockMirror is a dual block/text Python editor that synchronizes [Blockly](https://developers.google.com/blockly) (visual blocks) and [CodeMirror](https://codemirror.net/) (text editor) in real time. Python text is parsed via a bundled fork of [Skulpt](https://skulpt.org/) into an AST, which is then converted to Blockly XML.

### Core Components

**`src/block_mirror.js`** — Top-level controller. Owns the canonical code model (`block_mirror.code_`) and coordinates between the two editors. Key config options: `container`, `viewMode` (`'split'`/`'block'`/`'text'`), `height`, `readOnly`, `blockDelay`, `renderer` (Blockly renderer, default `'Thrasos'`), `skipSkulpt`, `toolbox` (`'normal'`/`'basic'`/`'advanced'`/`'complete'`), `imageMode`.

**`src/text_editor.js`** — CodeMirror-based text editor. When the user edits text, it calls into `TextToBlocks` to update the block view.

**`src/block_editor.js`** — Blockly-based block editor. When blocks change, it uses Blockly's Python generator to update the text view.

**`src/text_to_blocks.js`** — The core conversion engine. Calls `Sk.parse()` (Skulpt) to produce an AST, then walks the AST dispatching to per-node-type handlers. On parse failure it strips lines one at a time until it finds parseable code; unparseable sections become `ast_Raw` blocks.

**`src/skulpt/`** — A custom fork of the Skulpt Python parser (tokenizer → parser → AST). Not the Skulpt runtime; only the parser is used here. Changes here require rebuilding `dist/skulpt_parser.js`.

**`src/ast/`** — One file per Python AST node type (e.g. `ast_For.js`, `ast_If.js`). Each file defines all three layers needed for a node (see below).

**`src/toolbars.js`** — Defines the Blockly toolbox XML (which blocks appear in the palette).

**`src/blockly_shims.js`** — Patches and extensions to Blockly before it is used.

Note: `src/main.js` is the webpack entry point but contains only comments — the actual file concatenation is handled by `webpack-merge-and-include-globally` plugin in `webpack.config.js`.

### Sync / Loop-prevention

To prevent update cycles between the two editors, the main controller uses two boolean flags: `silenceText` (suppress text→block propagation) and `silenceBlock` (suppress block→text propagation). The `blockDelay` option adds a debounce for expensive block renders on large files.

### Block Color Conventions

Colors are referenced via `BlockMirrorTextToBlocks.COLOR.*` constants:
- Variables: 225 | Functions: 210 | Control flow: 270
- Math: 150 | Text/Strings: 120 | Logic: 345 | Sequences: 15
- Dictionary: 0 | OO (object-oriented): 240 | Python builtins: 60 | File I/O: 180

## Electron App Architecture

The Electron app (`npm run electron:start`) adds Python code execution and an integrated xterm.js terminal to the editor. The entry point is `test/simple_v2.html`.

```
Renderer Process (test/simple_v2.html)
  ├── BlockMirror editor (Blockly + CodeMirror)
  ├── xterm.js terminal panel (resizable, draggable)
  ├── Run/Stop button → editor.getCode() → electronAPI.runPython(filePath)
  ├── ramgs toolbar (生成/加载/连接) + status bar
  └── window.electronAPI  ← exposed via contextBridge
         ↕ IPC (contextIsolation: true)
Main Process (electron/main.js)
  ├── python:run  → spawn('python', ['-u', filePath], {cwd: dirname(filePath)})
  ├── python:kill → taskkill (Win32) / SIGTERM
  ├── shell:start → spawn('powershell.exe' / 'bash')
  ├── file:open/save/saveAs/exportPng/confirmSave → dialog + fs
  ├── window:setTitle / window:forceClose → BrowserWindow control
  ├── blockfactory:open → opens blockfactory/ in a new BrowserWindow
  ├── custom-modules:* → Custom modules CRUD + manager window
  └── ramgs:* → MCU debugging tool (serial connect, symbol management)
```

**`electron/main.js`** — Main process. Manages `pythonProcess`, `shellProcess`, `blockFactoryWindow`, `moduleManagerWindow`, and `customModulesStore`. Streams stdout/stderr via `terminal:output` IPC. Menu items send `menu:command` events to the renderer; the renderer's `initMenuCommands()` dispatches them to handler functions.

**`electron/preload.js`** — Bridges main ↔ renderer via `contextBridge.exposeInMainWorld('electronAPI', ...)`. All `on*` listener methods return a cleanup/unsubscribe function.

### IPC Channels

| Direction | Channel | Purpose |
|-----------|---------|---------|
| renderer → main (invoke) | `python:run` | Execute Python file at path (cwd = file's directory) |
| renderer → main (invoke) | `python:kill` | Kill running Python process |
| renderer → main (invoke) | `shell:start` | Start persistent shell |
| renderer → main (send) | `shell:write` | Send keystrokes to shell stdin |
| renderer → main (send) | `terminal:resize` | Reserved for node-pty upgrade |
| renderer → main (invoke) | `file:open` | Open file dialog → `{canceled, filePath, content}` |
| renderer → main (invoke) | `file:save` | Save `{filePath, content}` |
| renderer → main (invoke) | `file:saveAs` | Save-as dialog → `{canceled, filePath}` |
| renderer → main (invoke) | `file:exportPng` | Export PNG from `{dataUrl}` |
| renderer → main (invoke) | `file:confirmSave` | Show save-before-close dialog → `{response: 0/1/2}` |
| renderer → main (send) | `window:setTitle` | Set main window title string |
| renderer → main (send) | `window:forceClose` | Close window bypassing `close` listener |
| renderer → main (send) | `blockfactory:open` | Open/focus custom blocks editor window |
| renderer → main (send) | `custom-modules:openManager` | Open/focus module manager window |
| renderer → main (invoke) | `custom-modules:getAll` | Get all custom modules data |
| renderer → main (invoke) | `custom-modules:createModule` | Create a new module |
| renderer → main (invoke) | `custom-modules:updateModule` | Update module properties |
| renderer → main (invoke) | `custom-modules:deleteModule` | Delete a module |
| renderer → main (invoke) | `custom-modules:createFunction` | Add function to a module |
| renderer → main (invoke) | `custom-modules:updateFunction` | Update function properties |
| renderer → main (invoke) | `custom-modules:deleteFunction` | Remove function from a module |
| renderer → main (invoke) | `custom-modules:export` | Export module(s) to JSON file |
| renderer → main (invoke) | `custom-modules:import` | Import modules from JSON file |
| renderer → main (send) | `custom-modules:changed` | Notify main window to reload modules |
| renderer → main (invoke) | `ramgs:ports` | Enumerate COM ports → `{success, ports[{name, description}]}` |
| renderer → main (invoke) | `ramgs:status` | Get connection status → `{connected, port, baud, endian, symbols}` |
| renderer → main (invoke) | `ramgs:create` | Generate symbols from ELF → streams to terminal |
| renderer → main (invoke) | `ramgs:load` | Load symbols JSON → streams to terminal |
| renderer → main (invoke) | `ramgs:open` | Connect to device (port/baud/endian validated) → streams to terminal |
| renderer → main (invoke) | `ramgs:close` | Disconnect device → streams to terminal |
| renderer → main (invoke) | `ramgs:selectElf` | File dialog for `.elf/.abs/.axf/.out` |
| renderer → main (invoke) | `ramgs:selectSymbols` | File dialog for `.json` |
| renderer → main (invoke) | `ramgs:selectOutputDir` | Directory selection dialog |
| main → renderer | `terminal:output` | Streamed stdout/stderr text |
| main → renderer | `process:exit` | Process exit with `{exitCode, source}` |
| main → renderer | `process:start` | Process started with `{source}` |
| main → renderer | `menu:command` | Native menu item clicked (e.g. `'file:new'`, `'view:split'`, `'tools:moduleManager'`) |
| main → renderer | `custom-modules:reload` | Push updated modules data to renderer |

### Python Execution

Python code is executed by saving to a temp file (or using the current file path) and running `spawn('python', ['-u', filePath], { cwd: dirname(filePath) })`. The working directory is set to the file's parent directory so relative imports and file paths work correctly. Stderr output is wrapped in ANSI red escape codes for terminal display.

### Terminal Shell Interaction (no PTY)

The shell is spawned without a PTY (`child_process.spawn`, not `node-pty`) to avoid native compilation. This means:
- The shell does **not** echo characters back to the terminal
- Input must be **line-buffered** in the renderer: characters are locally echoed via `term.write(data)`, accumulated in `shellInputBuffer`, and sent to shell stdin only on `Enter` (`\r`)
- Backspace, Ctrl+C are handled client-side before forwarding

The `terminal:resize` IPC channel is a no-op stub; upgrade to `node-pty` to enable true PTY resize support.

### Menu Command Flow

Native menu items (defined in `buildAppMenu()` in `main.js`) send `menu:command` IPC events to the renderer with a string command key. The renderer's `initMenuCommands()` registers an `onMenuCommand` listener that dispatches to handler functions. To add a new menu action:
1. Add a menu item in `buildAppMenu()`: `{ label: '...', click: () => sendToRenderer('menu:command', 'ns:action') }`
2. Add a `case 'ns:action':` in the `switch` inside `initMenuCommands()` in `simple_v2.html`

The toolbar buttons in `simple_v2.html` call the same handler functions directly (no IPC needed).

### BlockFactory Window

`blockfactory/` is a self-contained copy of Google's Blockly Developer Tools for creating custom block definitions. It is opened as a child `BrowserWindow` (no menu bar, `setMenu(null)`) via the `blockfactory:open` IPC channel. The window carries its own copies of Blockly in `blockfactory/dist/` and `blockfactory/build/`. Its `beforeunload` hook is suppressed via `webContents.on('will-prevent-unload', e => e.preventDefault())` so the close button works normally.

### Custom Modules Management System

The custom modules system allows users to define their own Python module/function blocks without writing code. It consists of three layers:

**`electron/custom-modules-store.js`** — Persistent storage. Saves to `app.getPath('userData')/custom-modules.json`. Supports CRUD for modules and functions, import/export to JSON, and atomic file writes (write-to-tmp-then-rename). Corrupted data files are automatically backed up before reset.

**`custom-modules/manager.html` + `manager-preload.js`** — A separate BrowserWindow with a three-column UI (module list → function list → property editor). Opened via `custom-modules:openManager` IPC. Uses its own preload script exposing `moduleManagerAPI`.

**Renderer integration (in `simple_v2.html`)** — `loadCustomModules(data)` registers custom functions into `BlockMirrorTextToBlocks.FUNCTION_SIGNATURES` (for standalone functions) and `BlockMirrorTextToBlocks.MODULE_FUNCTION_SIGNATURES` (for module-prefixed functions like `module.func()`), generates toolbox XML into `BlockMirrorBlockEditor.EXTRA_TOOLS`, then calls `remakeToolbox()` and `forceBlockRefresh()`.

Data model:
```javascript
Module: {
    id: 'mod_TIMESTAMP_RANDOM',
    name: string,
    colour: number,        // HSV hue 0-360
    description: string,
    functions: [Function]
}
Function: {
    id: 'fn_TIMESTAMP_RANDOM',
    name: string,          // Python identifier (e.g. 'my_func')
    displayName: string,   // Block display text
    returns: boolean,      // Affects block shape (expression vs statement)
    colour: number,        // HSV hue 0-360
    params: string[],      // Default parameters shown
    fullParams: string[],  // All parameters (expanded mode)
    module: string,        // Optional module prefix (e.g. 'turtle')
    toolboxSnippet: string
}
```

Lifecycle: app starts → `CustomModulesStore` loads from disk → `did-finish-load` sends `custom-modules:reload` to renderer → `loadCustomModules()` registers blocks → user edits in manager window → `custom-modules:changed` triggers reload in main window.

### AI Assistant Integration

The Electron app includes a built-in AI chat assistant for Python code generation. It supports two LLM backends (GPT-5 and Claude Sonnet) via an enterprise API gateway (`aimpapi.midea.com`).

**`electron/ai-client.js`** — HTTP client for the LLM API. Sends synchronous (non-streaming) requests. GPT-5 uses OpenAI-compatible format; Claude uses AWS Bedrock-compatible format with extended thinking enabled (8K budget tokens).

**`electron/ai-settings-store.js`** — Persistent settings saved to `app.getPath('userData')/ai-settings.json`. Fields: `authToken`, `aigcUser` (required auth headers), `model` (`'gpt-5'` or `'claude'`), `effort` (GPT-5 reasoning effort: `'low'`/`'medium'`/`'high'`), `systemPrompt`.

**`electron/ai-conversations-store.js`** — Conversation history saved to `app.getPath('userData')/ai-conversations.json`. Supports multiple named conversations with full message history. Auto-titles conversations from the first user message.

The AI system prompt is dynamically composed: base system prompt + optional API doc content (loaded from a local file) + current editor code. This allows the AI to reference hardware API documentation and modify the user's existing code in context.

| Direction | Channel | Purpose |
|-----------|---------|---------|
| renderer → main (invoke) | `ai:getSettings` | Get AI settings |
| renderer → main (invoke) | `ai:saveSettings` | Update AI settings |
| renderer → main (invoke) | `ai:getConversations` | List all conversations (summaries) |
| renderer → main (invoke) | `ai:getConversation` | Get full conversation with messages |
| renderer → main (invoke) | `ai:createConversation` | Create new conversation |
| renderer → main (invoke) | `ai:deleteConversation` | Delete a conversation |
| renderer → main (invoke) | `ai:clearConversation` | Clear messages in a conversation |
| renderer → main (invoke) | `ai:selectApiDoc` | Open file dialog to load API doc |
| renderer → main (invoke) | `ai:sendMessage` | Send message with context → LLM response |

### RAMViewer (ramgs) Tool Integration

The Electron app integrates `ramgs` — a serial-port-based MCU RAM debugging tool for reading/writing MCU variables in real-time. The tool binary lives at `ramgs/ramgs.exe`; its `elfsymbol/elfsym.exe` sub-tool extracts symbols from ELF firmware files with DWARF debug info.

**Architecture**: `ensureRamgsInPath()` (called at app startup) appends the `ramgs/` directory to `process.env.PATH`. The `spawnRamgs(args, label)` helper in `main.js` spawns `ramgs.exe` with given args, streams stdout/stderr to the terminal via `terminal:output` IPC, and resolves with `{exitCode}`.

**UI components** (in `simple_v2.html`):
- **Status bar** (`#status-bar`) — fixed at window bottom, shows connection status (dot + text), port, baud rate, and loaded symbols
- **Toolbar buttons** (`#ramgs-toolbar`) — 生成/加载/连接, displayed in Electron mode
- **Three modal dialogs** (`.ramgs-overlay`) — Generate Symbols (ELF file + output dir pickers), Load Symbols (JSON file picker), Connect Device (port dropdown + baud + endian selects)

**Key functions in renderer**:
- `refreshRamgsStatus()` — fetches `ramgs:status` and updates status bar; called at startup and after every action
- `refreshPorts()` — populates the port `<select>` dropdown via `ramgs:ports`
- `doCreateSymbols()` / `doLoadSymbols()` / `doConnect()` / `doDisconnect()` — action handlers that show terminal, call IPC, display result

**Validation**: `ramgs:open` in main.js validates port (regex: `COM\d+` or `/dev/...`), baud (numeric), and endian (`'little'`/`'big'` whitelist) before spawning.

**Menu items** (Tools submenu): 生成符号表... / 加载符号表... / 连接设备... / 断开设备 → dispatched via `menu:command` → `ramgs:create` / `ramgs:load` / `ramgs:connect` / `ramgs:disconnect`.

### BlockMirror Height Sync (`syncEditorHeight`)

`block_editor.js` and `text_editor.js` both read `editor.configuration.height` (default: 500px) to set fixed pixel heights on their internal containers (`blockContainer`, `blockArea`, `textContainer`). This value is set once at construction and never automatically updated.

In `simple_v2.html`, the editor sits in a flex column with a resizable terminal panel below it. Whenever layout changes (drag, window resize, terminal toggle), `syncEditorHeight()` must be called instead of `editor.refresh()`:

```javascript
function syncEditorHeight() {
    var h = document.getElementById('blockmirror-editor').offsetHeight;
    if (h > 0) editor.configuration.height = h;
    editor.textEditor.resizeResponsively(); // editor.refresh() does NOT call this
    editor.refresh();                       // calls blockEditor.resized() + codeMirror.refresh()
}
```

`editor.refresh()` alone only calls `blockEditor.resized()` — it does **not** call `textEditor.resizeResponsively()`, so the CodeMirror container height would not update without the explicit call above.

`#blockmirror-editor` requires `position: relative` so that `blockEditor`'s `position: absolute` children (Blockly toolbox, scrollbars) are clipped by its `overflow: hidden` rather than escaping to the viewport.

## Adding a New AST Node

Each `src/ast/ast_XXX.js` file must define exactly three things:

```javascript
// 1. Blockly block definition (JSON) — describes the UI shape
BlockMirrorTextToBlocks.BLOCKS.push({
    type: "ast_XXX",
    message0: "...",
    // ...
});

// 2. Python code generator — Blockly block → Python string
python.pythonGenerator.forBlock['ast_XXX'] = function(block, generator) {
    // return Python source string
};

// 3. AST → Block converter — Skulpt AST node → Blockly XML element
BlockMirrorTextToBlocks.prototype['ast_XXX'] = function(node, parent) {
    // return a Blockly block XML element
};
```

After creating the file, **register it in `webpack.config.js`** by adding it to `JS_BLOCKMIRROR_FILES` (the ordered list under `// AST Handlers`). Also add a `<script>` tag in the test HTML files if you want to test without a full build.

Note: `src/ast/ast_Nonlocal.js` exists but is intentionally excluded from the webpack build.

## Adding Built-in Functions

Built-in Python functions (e.g. `print`, `range`, `len`) are defined in `src/ast/ast_functions.js` as entries in `BlockMirrorTextToBlocks.FUNCTION_SIGNATURES`. Each entry supports these fields:

```javascript
'funcName': {
    returns: true,          // whether the function returns a value (affects block shape)
    colour: BlockMirrorTextToBlocks.COLOR.MATH,  // block color
    simple: ['x'],          // parameters shown by default
    full: ['x', 'base'],    // all parameters (shown in expanded mode)
    custom: function(node, parent, bmttb) { ... }  // override handler for AST→block conversion
}
```

Module-prefixed functions (e.g. `turtle.forward()`) use `BlockMirrorTextToBlocks.MODULE_FUNCTION_SIGNATURES` with the same structure, keyed by `'module.funcName'`.

## Skulpt Fork

The `src/skulpt/` directory is a vendored copy of a custom Skulpt fork (not the npm package). It adds features like end-line-number tracking and missing AST nodes compared to upstream Skulpt. If you need to update it, changes must come from the [blockpy-edu/skulpt](https://github.com/blockpy-edu/skulpt) fork.

## Packaging (electron-builder)

The app is packaged for Windows using `electron-builder`. Configuration lives in the `"build"` field of `package.json`.

```bash
npm run devbuild   # must build dist/ first
npm run pack:win   # produces release/win-unpacked/MideaBlockly.exe
```

Key design:
- **`files`** — app code packed into asar: `electron/`, `test/simple_v2.html`, `dist/`, `lib/`, `blockfactory/`, `custom-modules/`, and runtime `node_modules` (blockly, @blockly, @xterm)
- **`extraResources`** — large external tools copied outside asar to `resources/`: `python-embedded/`, `ramgs/`, `VSCode/`, `device_api/`
- **`asarUnpack`** — `node_modules/blockly/media/**/*` must be unpacked so Blockly can access media files by filesystem path
- **`target: "dir"`** — outputs unpacked directory; change to `"nsis"` for an installer

## Dev vs Packaged Path Resolution

`electron/main.js` uses a dual-path pattern for all external tools. In development, paths resolve relative to `__dirname/..`; in packaged mode, they resolve via `process.resourcesPath`:

```javascript
// Pattern used by getEmbeddedPythonPath(), getVscodeExePath(), getDeviceApiDir(), ensureRamgsInPath()
const devPath = path.join(__dirname, '..', 'tool-dir', 'executable');
const prodPath = path.join(process.resourcesPath || '', 'tool-dir', 'executable');
if (fs.existsSync(prodPath)) return prodPath;
if (fs.existsSync(devPath)) return devPath;
return 'fallback';
```

When adding new external tools, follow this pattern and add the directory to `extraResources` in `package.json`.

Python execution also calls `buildPythonEnv()` which strips `PYTHONHOME` and `PYTHONPATH` from the environment to prevent system Python from interfering with the embedded runtime.

## VS Code Integration

The `vscode:open` IPC handler launches an embedded portable VS Code (`VSCode/Code.exe`) for Python editing:
- Configures the Python interpreter path in VS Code settings (global + workspace)
- Copies device API templates (`ice.py`, `ice_user.py`) from `device_api/` to the target project directory
- VS Code uses a portable data directory (`VSCode/data/`) so it doesn't conflict with system VS Code

## Device API Templates

`device_api/` contains hardware API modules copied to user projects when opening VS Code:
- `ice_maker/ice.py` — hardware API module for MCU control
- `ice_maker/ice_user.py` — user code template
- `demo.py` — example usage
