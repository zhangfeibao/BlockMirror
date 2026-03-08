# 添加自定义 Blockly 积木块指南

本文档详细说明如何在 BlockMirror 中添加新的自定义积木块，实现 Python 代码与 Blockly 可视化积木之间的双向转换。

---

## 目录

1. [工作原理概述](#1-工作原理概述)
2. [创建积木块文件](#2-创建积木块文件)
3. [第一层：积木块 UI 定义](#3-第一层积木块-ui-定义)
4. [第二层：Python 代码生成器](#4-第二层python-代码生成器)
5. [第三层：AST → 积木块转换器](#5-第三层ast--积木块转换器)
6. [注册到构建系统](#6-注册到构建系统)
7. [加入工具箱（Toolbox）](#7-加入工具箱toolbox)
8. [create_block 参数详解](#8-create_block-参数详解)
9. [表达式块 vs 语句块](#9-表达式块-vs-语句块)
10. [可变形积木（Mutations）](#10-可变形积木mutations)
11. [添加内置函数签名](#11-添加内置函数签名)
12. [完整示例：`repeat N times` 块](#12-完整示例repeat-n-times-块)
13. [调试技巧](#13-调试技巧)

---

## 1. 工作原理概述

BlockMirror 中，每种积木块都需要实现 **三层转换**，才能在块视图和文本视图之间双向同步：

```
Python 文本
    │
    ▼  (Skulpt 解析)
AST 节点 (如 ast_For, ast_Assign)
    │
    ▼  (第三层: AST → 积木 XML)
Blockly XML
    │
    ▼  (Blockly 渲染)
可视化积木块
    │
    ▼  (第二层: 积木 → Python)
Python 文本
```

**三层结构总览：**

| 层次 | 作用 | API |
|------|------|-----|
| 第一层 | 定义积木块的外观（形状、字段、颜色）| `BlockMirrorTextToBlocks.BLOCKS.push()` 或 `Blockly.Blocks['xxx'] = { init() }` |
| 第二层 | 从积木块生成 Python 代码 | `python.pythonGenerator.forBlock['xxx'] = function(block)` |
| 第三层 | 把 Skulpt AST 节点转换成积木块 XML | `BlockMirrorTextToBlocks.prototype['ast_xxx'] = function(node, parent)` |

---

## 2. 创建积木块文件

在 `src/ast/` 目录下创建新文件，命名规范为 `ast_<NodeType>.js`，例如 `ast_While.js`。

> **注意**：文件名中的 `NodeType` 必须与 Skulpt 解析出的 AST 节点名称对应（`ast_` 前缀 + Skulpt AST 节点的 `_astname` 字段值）。如果是全新的自定义块而非对应某个 Python AST 节点，可以任意命名，但需要手动触发，而不是自动从 AST 派发。

---

## 3. 第一层：积木块 UI 定义

积木块 UI 定义有两种写法：**JSON 格式**（简单块）和 **命令式 `init()`**（复杂/可变形块）。

### 3.1 JSON 格式定义（推荐用于固定形状的块）

```javascript
BlockMirrorTextToBlocks.BLOCKS.push({
    "type": "ast_MyBlock",          // 块类型，全局唯一
    "message0": "repeat %1 times %2 %3",  // 显示文本，%N 是占位符
    "args0": [
        // %1 - 内联值输入（嵌入一个表达式块）
        { "type": "input_value", "name": "TIMES" },
        // %2 - 换行占位符
        { "type": "input_dummy" },
        // %3 - 语句输入（嵌入一段代码块序列）
        { "type": "input_statement", "name": "BODY" }
    ],
    "inputsInline": true,           // 输入是否内联显示
    "previousStatement": null,      // 是否可接在其他语句块后面（null 表示可以）
    "nextStatement": null,          // 是否可接其他语句块（null 表示可以）
    "colour": BlockMirrorTextToBlocks.COLOR.CONTROL,  // 颜色
});
```

**`message0` 占位符与 `args0` 的对应关系：**

- `%1`、`%2`... 按顺序对应 `args0` 数组中的每个元素
- 字符串中可以包含普通文本（如 `"repeat"`）

**常见 `args0` 类型：**

| 类型 | 作用 | 示例 |
|------|------|------|
| `input_value` | 嵌入另一个表达式块（有输出的块） | 变量名、数字、表达式 |
| `input_statement` | 嵌入一段语句块序列 | 循环体、函数体 |
| `input_dummy` | 换行/分组，不接受连接 | 用于布局 |
| `field_input` | 文本输入框（可编辑文字） | `{"type": "field_input", "name": "NAME", "text": "default"}` |
| `field_number` | 数字输入框 | `{"type": "field_number", "name": "NUM", "value": 0}` |
| `field_dropdown` | 下拉菜单 | 见下方示例 |
| `field_variable` | 变量选择器 | `{"type": "field_variable", "name": "VAR"}` |
| `field_checkbox` | 复选框 | `{"type": "field_checkbox", "name": "FLAG", "checked": true}` |

**下拉菜单示例：**

```javascript
{
    "type": "field_dropdown",
    "name": "OP",
    "options": [
        ["+", "ADD"],
        ["-", "SUB"],
        ["*", "MUL"],
        ["/", "DIV"]
    ]
}
```

**颜色常量（`BlockMirrorTextToBlocks.COLOR`）：**

```javascript
VARIABLES: 225,   // 蓝色      - 变量赋值、名称
FUNCTIONS:  210,  // 青蓝色    - 函数定义、调用
OO:         240,  // 深蓝色    - 类、对象
CONTROL:    270,  // 紫色      - 控制流（for/while/if）
MATH:       190,  // 蓝绿色    - 数学运算
TEXT:       120,  // 绿色      - 字符串
FILE:       170,  // 中绿色    - 输入输出、文件
LOGIC:      345,  // 棕红色    - 逻辑运算（and/or/not）
SEQUENCES:   15,  // 橙色      - 序列、迭代器
LIST:        30,  // 橙色      - 列表
DICTIONARY:   0,  // 红色      - 字典
EXCEPTIONS: 300,  // 粉紫色    - 异常处理
PYTHON:      60,  // 黄色      - 通用 Python 语法
```

### 3.2 命令式 `init()` 定义（用于动态/可变形的块）

当积木块的形状需要根据内容动态变化时（如 `if/elif/else`、多目标赋值），使用命令式写法：

```javascript
Blockly.Blocks['ast_MyMutableBlock'] = {
    init: function () {
        // 初始化内部状态
        this.itemCount_ = 1;

        // 设置基本属性
        this.setInputsInline(true);
        this.setPreviousStatement(true, null);
        this.setNextStatement(true, null);
        this.setColour(BlockMirrorTextToBlocks.COLOR.LIST);

        // 构建初始形状
        this.updateShape_();
    },

    // 根据状态重建输入
    updateShape_: function () {
        // 移除旧输入
        let i = 0;
        while (this.getInput('ITEM' + i)) {
            this.removeInput('ITEM' + i);
            i++;
        }
        // 添加新输入
        for (let j = 0; j < this.itemCount_; j++) {
            this.appendValueInput('ITEM' + j)
                .appendField(j === 0 ? '[' : ',');
        }
        this.appendDummyInput('TAIL').appendField(']');
    },

    // 把内部状态序列化成 XML（用于保存/粘贴）
    mutationToDom: function () {
        let container = document.createElement('mutation');
        container.setAttribute('items', this.itemCount_);
        return container;
    },

    // 从 XML 恢复内部状态（加载时调用）
    domToMutation: function (xmlElement) {
        this.itemCount_ = parseInt(xmlElement.getAttribute('items'), 10);
        this.updateShape_();
    }
};
```

---

## 4. 第二层：Python 代码生成器

这一层将积木块转换成 Python 代码字符串。

```javascript
python.pythonGenerator.forBlock['ast_MyBlock'] = function(block, generator) {
    // 读取嵌入的值输入（表达式）
    let times = python.pythonGenerator.valueToCode(
        block,
        'TIMES',                               // 对应 args0 中的 name
        python.pythonGenerator.ORDER_NONE      // 运算符优先级
    ) || python.pythonGenerator.blank;         // 空时用 ___ 占位

    // 读取语句输入（代码块序列），空时用 pass
    let body = python.pythonGenerator.statementToCode(block, 'BODY')
        || python.pythonGenerator.PASS;

    // 读取字段值（文本/数字/下拉/变量）
    let varName = python.pythonGenerator.getVariableName(
        block.getFieldValue('VAR'),
        Blockly.Variables.NAME_TYPE
    );
    let opValue = block.getFieldValue('OP');   // 下拉菜单的值
    let numValue = block.getFieldValue('NUM'); // 数字字段的值

    // 拼接并返回 Python 代码
    // - 语句块返回字符串（末尾加 \n）
    // - 表达式块返回 [代码, 优先级] 数组
    return 'for ___ in range(' + times + '):\n' + body;
};
```

**`valueToCode` 的 ORDER 参数（运算符优先级）：**

当子表达式可能被加括号时，需要传入当前操作的优先级，让生成器决定是否加括号。常用优先级：

```javascript
python.pythonGenerator.ORDER_ATOMIC          // 最高，原子值（数字、字符串、变量）
python.pythonGenerator.ORDER_FUNCTION_CALL   // 函数调用
python.pythonGenerator.ORDER_UNARY_SIGN      // 一元运算 (-x)
python.pythonGenerator.ORDER_MULTIPLICATIVE  // * / //
python.pythonGenerator.ORDER_ADDITIVE        // + -
python.pythonGenerator.ORDER_RELATIONAL      // < > <= >=
python.pythonGenerator.ORDER_EQUALITY        // == !=
python.pythonGenerator.ORDER_LOGICAL_NOT     // not
python.pythonGenerator.ORDER_LOGICAL_AND     // and
python.pythonGenerator.ORDER_LOGICAL_OR      // or
python.pythonGenerator.ORDER_NONE            // 最低，不加括号
```

**表达式块返回格式：**

如果你的块是表达式块（有 `output` 字段），必须返回 `[代码字符串, 优先级]` 数组：

```javascript
python.pythonGenerator.forBlock['ast_Num'] = function(block) {
    var code = parseFloat(block.getFieldValue('NUM'));
    return [code, python.pythonGenerator.ORDER_ATOMIC];
};
```

---

## 5. 第三层：AST → 积木块转换器

这一层将 Skulpt 解析出的 Python AST 节点转换成 Blockly XML 元素。函数命名必须与 Skulpt AST 节点类型匹配：`BlockMirrorTextToBlocks.prototype['ast_' + node._astname]`。

```javascript
BlockMirrorTextToBlocks.prototype['ast_While'] = function (node, parent) {
    // AST 节点的属性直接访问，名称与 Python AST 规范一致
    let test = node.test;      // 条件表达式节点
    let body = node.body;      // 循环体语句列表
    let orelse = node.orelse;  // else 子句语句列表

    // 递归转换子节点
    let testBlock = this.convert(test, node);          // 转换表达式节点
    let bodyBlocks = this.convertBody(body, node);     // 转换语句列表

    // 用 create_block 生成 XML 元素
    return BlockMirrorTextToBlocks.create_block(
        "ast_While",       // 块类型
        node.lineno,       // 行号（用于布局排序）
        {},                // fields: { 字段名: 值 }
        {                  // values: { 输入名: 子块XML }
            "TEST": testBlock
        },
        {},                // settings: XML 属性 { 属性名: 值 }
        {},                // mutations: 变形数据
        {                  // statements: { 语句输入名: 子块XML列表 }
            "BODY": bodyBlocks
        }
    );
};
```

### 5.1 如何查找 Skulpt AST 节点属性

在 `src/skulpt/astnodes.js` 中定义了所有 AST 节点的字段。也可以参考 [Python 官方 AST 文档](https://docs.python.org/3/library/ast.html)，字段名基本一致。

常见 AST 节点属性：

```
Module:     body (语句列表)
For:        target, iter, body, orelse
While:      test, body, orelse
If:         test, body, orelse
Assign:     targets (列表), value
AugAssign:  target, op, value
FunctionDef:name, args, body, decorator_list, returns
ClassDef:   name, bases, body
Call:       func, args, keywords
BinOp:      left, op, right
Compare:    left, ops (列表), comparators (列表)
Name:       id (Skulpt 字符串对象，需用 Sk.ffi.remapToJs() 转换)
Num:        n  (Skulpt 数字对象，需用 Sk.ffi.remapToJs() 转换)
Str:        s  (Skulpt 字符串对象，需用 Sk.ffi.remapToJs() 转换)
```

**读取 Skulpt 封装的 Python 值：**

```javascript
// Skulpt 字符串/数字需要转换
let name = Sk.ffi.remapToJs(node.id);   // str
let num  = Sk.ffi.remapToJs(node.n);    // number
let str  = Sk.ffi.remapToJs(node.s);    // string

// 枚举值（如运算符）通常是对象，取其 name 属性
let op = node.op.name;   // 'Add', 'Sub', 'Mult', 'Div', 'Mod' ...
```

### 5.2 可用的辅助方法

| 方法 | 用途 |
|------|------|
| `this.convert(node, parent)` | 递归转换单个 AST 节点（表达式/语句均可）|
| `this.convertBody(nodeList, parent)` | 转换语句列表，返回 XML 元素数组 |
| `this.convertElements(prefix, nodeList, parent)` | 将节点列表转换为 `{ prefix0: xml, prefix1: xml, ... }` |
| `BlockMirrorTextToBlocks.create_block(...)` | 创建积木 XML 元素（见[第 8 节](#8-create_block-参数详解)）|
| `BlockMirrorTextToBlocks.raw_block(text)` | 创建原始代码块（兜底降级用） |

---

## 6. 注册到构建系统

完成以上三层后，必须在 `webpack.config.js` 的 `JS_BLOCKMIRROR_FILES` 数组中注册新文件，否则构建时不会打包：

```javascript
// webpack.config.js
const JS_BLOCKMIRROR_FILES = [
    // ... 其他文件 ...
    path.resolve(__dirname, 'src/ast/ast_While.js'),
    path.resolve(__dirname, 'src/ast/ast_MyBlock.js'),  // ← 添加这行
    // ...
];
```

**文件顺序有意义：** 所有文件共享同一个全局作用域（Blockly、python、BlockMirrorTextToBlocks），`ast_functions.js` 和 `toolbars.js` 必须在 AST 处理器之后。不要改动 `src/block_mirror.js`、`src/text_to_blocks.js` 等核心文件的顺序。

---

## 7. 加入工具箱（Toolbox）

工具箱定义在 `src/toolbars.js` 中。BlockMirror 使用 **Python 代码片段**来描述工具箱中的积木，系统会自动将代码片段转换成对应的积木块。

### 7.1 在现有工具箱中添加积木

找到 `BlockMirrorBlockEditor.prototype.TOOLBOXES` 中的目标工具箱（`'normal'`、`'full'` 等），在对应的 `blocks` 数组中添加 Python 代码片段：

```javascript
'normal': [
    TOOLBOX_CATEGORY.VARIABLES,
    {name: "Iteration", colour: "CONTROL", blocks: [
        'for ___ in ___: pass',
        'while ___: pass',
        'repeat 10 times: pass',   // ← 添加你的积木（对应的 Python 语法）
        'break',
    ]},
    // ...
]
```

代码片段中 `___` 是空输入插槽的占位符，系统会自动解析这些 Python 片段生成对应积木。

### 7.2 定义可复用的工具箱分类

```javascript
TOOLBOX_CATEGORY.MY_CATEGORY = {
    name: "My Category",    // 显示名称
    colour: "CONTROL",      // 颜色（对应 BlockMirrorTextToBlocks.COLOR 的键名）
    blocks: [
        "repeat 10 times: pass",
        "my_func(___)",
    ]
};
```

### 7.3 在运行时动态添加工具类别

如果你需要在运行时（初始化之后）向工具箱添加内容，可以使用 `BlockMirrorBlockEditor.EXTRA_TOOLS`：

```javascript
// 在页面初始化或模块加载时执行
BlockMirrorBlockEditor.EXTRA_TOOLS['myCategory'] =
    `<category name="My Tools" colour="210">
        <block type="ast_MyBlock"></block>
    </category>`;

// 初始化 BlockMirror 后调用 remakeToolbox 使更改生效
editor.blockEditor.remakeToolbox();
```

---

## 8. `create_block` 参数详解

`BlockMirrorTextToBlocks.create_block` 是生成积木 XML 的核心工具函数：

```javascript
BlockMirrorTextToBlocks.create_block(
    type,        // string   - 块类型（对应第一层定义的 type）
    lineNumber,  // number   - Python 源码行号
    fields,      // object   - 字段值 { 字段名: 字符串值 }
    values,      // object   - 值输入 { 输入名: 子块XML元素 }
    settings,    // object   - XML 属性 { 属性名: 值 }（一般为空 {}）
    mutations,   // object   - 变形数据（见下方说明）
    statements   // object   - 语句输入 { 输入名: 子块XML数组 }
)
```

**`fields` - 字段值（文本、数字、下拉等）：**

```javascript
fields: {
    "VAR": "my_variable",   // field_variable 的变量名
    "NUM": 42,              // field_number 的数值
    "OP":  "ADD",           // field_dropdown 的选项值
    "TEXT": "hello",        // field_input 的文本
}
```

**`values` - 嵌入的子表达式块：**

```javascript
values: {
    "TIMES": this.convert(timesNode, node),  // 单个子块 XML 元素
    "ITEM0": this.convert(items[0], node),
    "ITEM1": this.convert(items[1], node),
}
```

**`mutations` - 变形数据，有两种写法：**

```javascript
// 1. "@属性名" 形式 -> 直接在 <mutation> 上设置 XML 属性（供 domToMutation 读取）
mutations: {
    "@items": 3,
    "@simple": true,
}
// 生成: <mutation items="3" simple="true"/>

// 2. 普通键名 -> 在 <mutation> 内生成子元素
mutations: {
    "arg": subBlockXmlElement,  // 生成 <arg name="keyName">...</arg>
}
```

**`statements` - 嵌入的语句块序列（值为数组，`convertBody` 的返回值）：**

```javascript
statements: {
    "BODY": this.convertBody(node.body, node),    // 循环体
    "ELSE": this.convertBody(node.orelse, node),  // else 子句
}
```

---

## 9. 表达式块 vs 语句块

这是最重要的区分之一，决定了块的连接方式和代码生成返回格式。

### 语句块（Statement Block）

- 可以堆叠连接（上下相连）
- 定义时设置 `previousStatement: null` 和 `nextStatement: null`
- Python 生成器返回**字符串**（末尾要加 `\n`）

```javascript
// 第一层（JSON）
{
    "type": "ast_MyStatement",
    "previousStatement": null,
    "nextStatement": null,
    // ...
}

// 第二层
python.pythonGenerator.forBlock['ast_MyStatement'] = function(block) {
    return 'do_something()\n';  // 返回字符串
};
```

### 表达式块（Value Block / Expression Block）

- 可以插入到其他块的值输入插槽中
- 定义时设置 `"output": 类型` 或 `"output": null`（null 表示接受任意类型）
- Python 生成器返回 `[代码, 优先级]` **数组**

```javascript
// 第一层（JSON）
{
    "type": "ast_MyExpression",
    "output": null,   // 或 "Number", "String", "Boolean"
    // 没有 previousStatement / nextStatement
    // ...
}

// 第二层
python.pythonGenerator.forBlock['ast_MyExpression'] = function(block) {
    let code = 'my_value()';
    return [code, python.pythonGenerator.ORDER_FUNCTION_CALL];  // 返回数组
};
```

---

## 10. 可变形积木（Mutations）

当积木块的输入数量需要动态变化时（如列表元素个数不固定），必须实现 Mutations 机制。

### 完整实现模板

**第一层（命令式）：**

```javascript
Blockly.Blocks['ast_MyList'] = {
    init: function () {
        this.itemCount_ = 3;   // 默认元素数量
        this.setColour(BlockMirrorTextToBlocks.COLOR.LIST);
        this.setOutput(true, null);
        this.setInputsInline(true);
        this.updateShape_();
    },
    updateShape_: function () {
        // 添加缺少的输入
        for (let i = 0; i < this.itemCount_; i++) {
            if (!this.getInput('ITEM' + i)) {
                let input = this.appendValueInput('ITEM' + i);
                if (i === 0) input.appendField('[');
                else         input.appendField(',');
            }
        }
        // 删除多余的输入
        let j = this.itemCount_;
        while (this.getInput('ITEM' + j)) {
            this.removeInput('ITEM' + j);
            j++;
        }
        // 确保有结尾标记
        if (!this.getInput('TAIL')) {
            this.appendDummyInput('TAIL').appendField(']');
        }
    },
    mutationToDom: function () {
        let container = document.createElement('mutation');
        container.setAttribute('items', this.itemCount_);
        return container;
    },
    domToMutation: function (xmlElement) {
        this.itemCount_ = parseInt(xmlElement.getAttribute('items'), 10);
        this.updateShape_();
    }
};
```

**第二层（代码生成）：**

```javascript
python.pythonGenerator.forBlock['ast_MyList'] = function(block, generator) {
    let items = [];
    for (let i = 0; i < block.itemCount_; i++) {
        items.push(
            python.pythonGenerator.valueToCode(block, 'ITEM' + i,
                python.pythonGenerator.ORDER_NONE)
            || python.pythonGenerator.blank
        );
    }
    return ['[' + items.join(', ') + ']', python.pythonGenerator.ORDER_ATOMIC];
};
```

**第三层（AST 转换）：**

```javascript
BlockMirrorTextToBlocks.prototype['ast_List'] = function (node, parent) {
    let elts = node.elts;  // 元素列表
    let items = this.convertElements('ITEM', elts, node);

    return BlockMirrorTextToBlocks.create_block('ast_MyList', node.lineno,
        {},      // fields
        items,   // values: { ITEM0: xml, ITEM1: xml, ... }
        {},      // settings
        { "@items": elts.length },  // mutations: 告诉 domToMutation 元素数量
        {}       // statements
    );
};
```

---

## 11. 添加内置函数签名

如果你的自定义块对应 Python 内置函数（如 `my_func(x, y)`），可以在 `src/ast/ast_functions.js` 的 `FUNCTION_SIGNATURES` 中注册，这样调用该函数时会自动使用 `ast_Call` 块的专用渲染：

```javascript
BlockMirrorTextToBlocks.prototype.FUNCTION_SIGNATURES['my_func'] = {
    returns: true,              // 是否有返回值（决定块是表达式块还是语句块）
    colour: BlockMirrorTextToBlocks.COLOR.MATH,  // 颜色
    // 简单参数签名（只传几个常用参数时使用）
    simple: ['x', 'y'],
    // 完整参数签名（含可选参数、*args、**kwargs）
    full: ['x', 'y', 'z=0'],
};
```

**参数名前缀的含义：**

| 前缀 | 含义 | 例子 |
|------|------|------|
| 无前缀 | 普通参数 | `'x'` |
| `*` | 可变位置参数（接收多个值） | `'*messages'` |
| `**` | 关键字参数 | `'**key'` |
| `*`（单独） | 分隔符（之后为关键字专属参数） | `'*'` |

注册后，不需要写额外的 AST 转换器——当 Python 中出现 `my_func(...)` 的调用时，`ast_Call` 处理器会自动查询签名并生成对应的调用块。

---

## 12. 完整示例：`repeat N times` 块

下面是一个完整的示例，添加一个 `repeat N times:` 积木块，对应 Python 的 `for _ in range(N):` 语法。

**新建文件 `src/ast/ast_RepeatN.js`：**

```javascript
// ============================================================
// 第一层：积木块 UI 定义
// ============================================================
BlockMirrorTextToBlocks.BLOCKS.push({
    "type": "ast_RepeatN",
    "message0": "repeat %1 times %2 %3",
    "args0": [
        { "type": "input_value", "name": "TIMES" },
        { "type": "input_dummy" },
        { "type": "input_statement", "name": "BODY" }
    ],
    "inputsInline": true,
    "previousStatement": null,
    "nextStatement": null,
    "colour": BlockMirrorTextToBlocks.COLOR.CONTROL,
});

// ============================================================
// 第二层：积木块 → Python 代码
// ============================================================
python.pythonGenerator.forBlock['ast_RepeatN'] = function(block, generator) {
    let times = python.pythonGenerator.valueToCode(
        block, 'TIMES', python.pythonGenerator.ORDER_NONE
    ) || python.pythonGenerator.blank;

    let body = python.pythonGenerator.statementToCode(block, 'BODY')
        || python.pythonGenerator.PASS;

    return 'for _ in range(' + times + '):\n' + body;
};

// ============================================================
// 第三层：Python AST → 积木块
// 注意：此块没有对应的独立 AST 节点，它是 ast_For 的特例。
// 需要在 ast_For.js 的处理器中检测模式并分发到此块。
// 这里提供一个辅助函数，由 ast_For.js 调用。
// ============================================================
BlockMirrorTextToBlocks.prototype['ast_RepeatN'] = function (node, parent) {
    // node 是 For 节点，但已知是 for _ in range(N) 模式
    let timesNode = node.iter.args[0];  // range 的第一个参数

    return BlockMirrorTextToBlocks.create_block('ast_RepeatN', node.lineno,
        {},
        { "TIMES": this.convert(timesNode, node) },
        {},
        {},
        { "BODY": this.convertBody(node.body, node) }
    );
};
```

**在 `src/ast/ast_For.js` 中检测并分发（在现有 `ast_For` 处理器中添加模式匹配）：**

```javascript
// 在 ast_For 处理器开头添加特例检测
BlockMirrorTextToBlocks.prototype['ast_For'] = function (node, parent) {
    // 检测是否为 for _ in range(N) 模式
    let isRepeatN = (
        node.target._astname === 'Name' &&
        Sk.ffi.remapToJs(node.target.id) === '_' &&
        node.iter._astname === 'Call' &&
        node.iter.func._astname === 'Name' &&
        Sk.ffi.remapToJs(node.iter.func.id) === 'range' &&
        node.iter.args.length === 1 &&
        node.orelse.length === 0
    );

    if (isRepeatN) {
        return this['ast_RepeatN'](node, parent);
    }

    // 原有 ast_For 逻辑...
};
```

**在 `webpack.config.js` 中注册：**

```javascript
const JS_BLOCKMIRROR_FILES = [
    // ...现有文件...
    path.resolve(__dirname, 'src/ast/ast_For.js'),
    path.resolve(__dirname, 'src/ast/ast_RepeatN.js'),  // ← 添加
    // ...
];
```

**在 `src/toolbars.js` 中加入工具箱：**

```javascript
{name: "Iteration", colour: "CONTROL", blocks: [
    'for ___ in ___: pass',
    'while ___: pass',
    'for _ in range(10): pass',   // ← 工具箱中显示此代码片段对应的积木
    'break',
]},
```

---

## 13. 调试技巧

### 不用完整构建直接测试

使用 `test/simple_dev.html` 可以直接加载源文件，修改后刷新浏览器即可，无需 `npm run build`：

```html
<!-- 在 test/simple_dev.html 中添加你的文件 -->
<script src="../src/ast/ast_RepeatN.js"></script>
```

### 查看转换结果

打开浏览器控制台，手动调用转换器查看 XML：

```javascript
// 查看 Python 代码转换出的 XML
let result = editor.textToBlocks.convertSource('test.py', 'for _ in range(10):\n    pass');
console.log(result.xml);

// 查看当前工作区的代码
console.log(editor.getCode());
```

### AST 节点结构检查

在转换器函数中临时打印 AST 节点：

```javascript
BlockMirrorTextToBlocks.prototype['ast_MyNode'] = function (node, parent) {
    console.log('AST node:', JSON.stringify(node, null, 2));  // 查看结构
    // ...
};
```

### 常见错误排查

| 症状 | 可能原因 |
|------|----------|
| 代码变成灰色 Raw 块 | 第三层转换器抛出了异常（打开控制台查看 Error）|
| 修改积木后文本不更新 | 第二层生成器语法错误或未返回值 |
| 工具箱中看不到积木 | `toolbars.js` 中的 Python 片段无法被正确解析 |
| 积木形状加载后错误 | `domToMutation` 中属性读取失败，检查 `mutationToDom` 写入的属性名 |
| `Could not find function: ast_XXX` | 第三层函数名拼写错误，或文件未在 `webpack.config.js` 中注册 |
