# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build Commands

```bash
npm install                  # Install dependencies
npm run build                # Production build (minified)
npm run devbuild             # Development build
npm run watch                # Watch mode for development
npm run electron:start       # Launch Electron desktop app
```

If you encounter `Error: error:0308010C:digital envelope routines::unsupported`, run first:
```bash
export NODE_OPTIONS=--openssl-legacy-provider
```

Build output goes to `dist/`:
- `dist/block_mirror.js` — main library (BlockMirror + AST handlers, no Blockly/CodeMirror)
- `dist/skulpt_parser.js` — bundled Skulpt Python parser
- `dist/block_mirror.css` — styles

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
  ├── Run/Stop button → editor.getCode() → electronAPI.runPython()
  └── window.electronAPI  ← exposed via contextBridge
         ↕ IPC (contextIsolation: true)
Main Process (electron/main.js)
  ├── python:run  → spawn('python', ['-u', '-c', code])
  ├── python:kill → taskkill (Win32) / SIGTERM
  └── shell:start → spawn('powershell.exe' / 'bash')
```

**`electron/main.js`** — Main process. Manages two child processes (`pythonProcess`, `shellProcess`), streams stdout/stderr back to the renderer via `terminal:output` IPC events, and handles process lifecycle.

**`electron/preload.js`** — Bridges main ↔ renderer via `contextBridge.exposeInMainWorld('electronAPI', ...)`. IPC channels:

| Direction | Channel | Purpose |
|-----------|---------|---------|
| renderer → main (invoke) | `python:run` | Execute Python code string |
| renderer → main (invoke) | `python:kill` | Kill running Python process |
| renderer → main (invoke) | `shell:start` | Start persistent shell |
| renderer → main (send) | `shell:write` | Send keystrokes to shell stdin |
| renderer → main (send) | `terminal:resize` | Reserved for node-pty upgrade |
| main → renderer | `terminal:output` | Streamed stdout/stderr text |
| main → renderer | `process:exit` | Process exit with `{exitCode, source}` |
| main → renderer | `process:start` | Process started with `{source}` |

### Terminal Shell Interaction (no PTY)

The shell is spawned without a PTY (`child_process.spawn`, not `node-pty`) to avoid native compilation. This means:
- The shell does **not** echo characters back to the terminal
- Input must be **line-buffered** in the renderer: characters are locally echoed via `term.write(data)`, accumulated in `shellInputBuffer`, and sent to shell stdin only on `Enter` (`\r`)
- Backspace, Ctrl+C are handled client-side before forwarding

The `terminal:resize` IPC channel is a no-op stub; upgrade to `node-pty` to enable true PTY resize support.

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

## Skulpt Fork

The `src/skulpt/` directory is a vendored copy of a custom Skulpt fork (not the npm package). It adds features like end-line-number tracking and missing AST nodes compared to upstream Skulpt. If you need to update it, changes must come from the [blockpy-edu/skulpt](https://github.com/blockpy-edu/skulpt) fork.
