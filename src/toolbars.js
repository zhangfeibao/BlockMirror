let ZERO_BLOCK = BlockMirrorTextToBlocks.create_block('ast_Num', null, {'NUM': 0});

BlockMirrorBlockEditor.EXTRA_TOOLS = {};

const TOOLBOX_CATEGORY = {};

TOOLBOX_CATEGORY.VARIABLES = {name: '变量', colour: 'VARIABLES', custom: 'VARIABLE'};
TOOLBOX_CATEGORY.DECISIONS = {name: "判断", colour: "LOGIC", blocks: [
    'if ___: pass',
    'if ___: pass\nelse: pass',
    '___ < ___',
    '___ and ___',
    'not ___'
]};
TOOLBOX_CATEGORY.CALCULATIONS = {name: "计算", colour: "MATH", blocks: [
    "___ + ___",
    "round(___)"
]};
TOOLBOX_CATEGORY.OUTPUT_WITH_PLOTTING = {name: "输出", colour: "PLOTTING", blocks: [
    "print(___)",
    "plt.plot(___)",
    "plt.scatter(___, ___)",
    "plt.hist(___)",
    "plt.bar(___, ___, tick_label=___)",
    "plt.boxplot(___)",
    "plt.show()",
    "plt.title(___)",
    "plt.xlabel(___)",
    "plt.ylabel(___)",
    "plt.hlines(___, ___, ___)",
    "plt.vlines(___, ___, ___)",
]};
TOOLBOX_CATEGORY.TURTLES = {name: "画图", colour: "PLOTTING", blocks: [
    "turtle.mainloop()",
    "turtle.forward(50)",
    "turtle.backward(50)",
    "turtle.right(90)",
    "turtle.left(90)",
    "turtle.goto(0, 0)",
    "turtle.setx(100)",
    "turtle.sety(100)",
    "turtle.setheading(270)",
    "turtle.pendown()",
    "turtle.penup()",
    "turtle.pencolor('blue')"
]};
TOOLBOX_CATEGORY.INPUT = {name: "输入", colour: "TEXT", blocks: [
    "input('')",
]};
TOOLBOX_CATEGORY.VALUES = {name: "字面值", colour: "TEXT", blocks: [
    '""',
    "0",
    "True"
]};
TOOLBOX_CATEGORY.SEP = "<sep></sep>";

TOOLBOX_CATEGORY.CONVERSIONS = {name: "类型转换", colour: "TEXT", blocks: [
    "int(___)",
    "float(___)",
    "str(___)",
    "bool(___)"
]};

TOOLBOX_CATEGORY.DICTIONARIES = {name: "字典", colour: "DICTIONARY", blocks: [
    "{'1st key': ___, '2nd key': ___, '3rd key': ___}",
    "{}",
    "___['key']"
]};

TOOLBOX_CATEGORY.AUGMENTED_ASSIGN = {name: "复合赋值", colour: "VARIABLES", blocks: [
    "___ += 1",
    "___ -= 1",
    "___ *= ___",
]};

TOOLBOX_CATEGORY.MATH_MODULE = {name: "数学模块", colour: "MATH", blocks: [
    "import math",
    "math.sqrt(___)",
    "math.floor(___)",
    "math.ceil(___)",
    "math.log(___)",
    "math.sin(___)",
    "math.cos(___)",
    "math.pi",
]};

TOOLBOX_CATEGORY.RANDOM_MODULE = {name: "随机模块", colour: "MATH", blocks: [
    "import random",
    "random.randint(0, 10)",
    "random.random()",
    "random.choice(___)",
]};

TOOLBOX_CATEGORY.LIST_METHODS = {name: "列表方法", colour: "LIST", blocks: [
    "___.append(___)",
    "___.insert(___, ___)",
    "___.remove(___)",
    "___.pop()",
    "___.index(___)",
    "___.count(___)",
    "___.sort()",
    "___.reverse()",
    "___.copy()",
    "___.extend(___)",
]};

TOOLBOX_CATEGORY.DICT_METHODS = {name: "字典方法", colour: "DICTIONARY", blocks: [
    "___.keys()",
    "___.values()",
    "___.items()",
    "___.get(___)",
    "___.update(___)",
    "___.pop(___)",
]};

TOOLBOX_CATEGORY.SETS = {name: "集合", colour: "SET", blocks: [
    "{___, ___, ___}",
    "set(___)",
    "___.add(___)",
    "___.remove(___)",
    "___.discard(___)",
]};

TOOLBOX_CATEGORY.STRING_METHODS = {name: "字符串方法", colour: "TEXT", blocks: [
    "len(___)",
    "___.find(___)",
    "___.upper()",
    "___.lower()",
    "___.strip()",
    "___.split()",
    "''.join(___)",
    "___.replace('', '')",
    "___.startswith('')",
    "___.endswith('')",
    "___.isdigit()",
    "___.isalpha()",
]};

BlockMirrorBlockEditor.prototype.TOOLBOXES = {
    //******************************************************
    'empty': [
        {"name": "空工具箱", "colour": "PYTHON", "blocks": []}
    ],
    //******************************************************
    'minimal': [
        // TODO: What should live in here?
        TOOLBOX_CATEGORY.VARIABLES,
    ],
    //******************************************************
    'normal': [
        TOOLBOX_CATEGORY.VARIABLES,
        TOOLBOX_CATEGORY.AUGMENTED_ASSIGN,
        TOOLBOX_CATEGORY.DECISIONS,
        {name: "迭代循环", colour: "CONTROL", blocks: [
            'for ___ in ___: pass',
            'for ___ in range(0, 10): pass',
            'while ___: pass',
            'break',
            'continue',
        ]},
        {name: "函数", colour: "FUNCTIONS", blocks: [
            "def ___(___): pass",
            "def ___(___: int)->str: pass",
            "return ___",
        ]},
        TOOLBOX_CATEGORY.SEP,
        {name: "计算", colour: "MATH", blocks: [
            "___ + ___",
            "___ - ___",
            "___ * ___",
            "___ / ___",
            "___ // ___",
            "___ % ___",
            "___ ** ___",
            "-___",
            "round(___)",
            "abs(___)",
            "min(___, ___)",
            "max(___, ___)",
            "sum(___)",
        ]},
        TOOLBOX_CATEGORY.OUTPUT_WITH_PLOTTING,
        TOOLBOX_CATEGORY.INPUT,
        TOOLBOX_CATEGORY.TURTLES,
        TOOLBOX_CATEGORY.SEP,
        TOOLBOX_CATEGORY.VALUES,
        TOOLBOX_CATEGORY.CONVERSIONS,
        {name: "列表", colour: "LIST", blocks: [
            "[0, 0, 0]",
            "[___, ___, ___]",
            "[]",
            "range(0, 10)",
            "len(___)",
            "___ in ___",
            "sorted(___)",
        ]},
        TOOLBOX_CATEGORY.LIST_METHODS,
        TOOLBOX_CATEGORY.DICTIONARIES,
        TOOLBOX_CATEGORY.DICT_METHODS,
        TOOLBOX_CATEGORY.STRING_METHODS,
        TOOLBOX_CATEGORY.SEP,
        TOOLBOX_CATEGORY.MATH_MODULE,
        TOOLBOX_CATEGORY.RANDOM_MODULE,
        TOOLBOX_CATEGORY.SETS,
        TOOLBOX_CATEGORY.SEP,
    ],
    //******************************************************
    'ct': [
        TOOLBOX_CATEGORY.VARIABLES,
        TOOLBOX_CATEGORY.DECISIONS,
        {name: "迭代", colour: "CONTROL", blocks: [
            'for ___ in ___: pass',
        ]},
        TOOLBOX_CATEGORY.SEP,
        TOOLBOX_CATEGORY.CALCULATIONS,
        TOOLBOX_CATEGORY.OUTPUT_WITH_PLOTTING,
        TOOLBOX_CATEGORY.INPUT,
        TOOLBOX_CATEGORY.SEP,
        TOOLBOX_CATEGORY.VALUES,
        TOOLBOX_CATEGORY.CONVERSIONS,
        {name: "列表", colour: "LIST", blocks: [
            "[0, 0, 0]",
            "[___, ___, ___]",
            "[]",
            "___.append(___)"
        ]}
    ],
    //******************************************************
    'full': [
        TOOLBOX_CATEGORY.VARIABLES,
        TOOLBOX_CATEGORY.AUGMENTED_ASSIGN,
        {name: "字面值", colour: "LIST", blocks: [
            "0",
            "''",
            "True",
            "None",
            "[___, ___, ___]",
            "(___, ___, ___)",
            "{___, ___, ___}",
            "{___: ___, ___: ___, ___: ___}",
            ]},
        {name: "计算", colour: "MATH", blocks: [
            "-___",
            "___ + ___",
            "___ - ___",
            "___ * ___",
            "___ / ___",
            "___ // ___",
            "___ % ___",
            "___ ** ___",
            "___ >> ___",
            "abs(___)",
            "round(___)",
        ]},
        {name: "逻辑", colour: "LOGIC", blocks: [
            '___ if ___ else ___',
            '___ == ___',
            '___ < ___',
            '___ in ___',
            '___ and ___',
            'not ___'
        ]},
        TOOLBOX_CATEGORY.SEP,
        {name: "类", colour: "OO", blocks: [
            "class ___: pass",
            "class ___(___): pass",
            "___.___",
            "___: ___",
            "super()"
        ]},
        {name: "函数", colour: "FUNCTIONS", blocks: [
            "def ___(___): pass",
            "def ___(___: int)->str: pass",
            "return ___",
            "yield ___",
            "lambda ___: ___"
        ]},
        {name: "导入", colour: "PYTHON", blocks: [
            "import ___",
            "from ___ import ___",
            "import ___ as ___",
            "from ___ import ___ as ___"
        ]},
        TOOLBOX_CATEGORY.SEP,
        {name: "控制流", colour: "CONTROL", blocks: [
            'if ___: pass',
            'if ___: pass\nelse: pass',
            'for ___ in ___: pass',
            'while ___: pass',
            'break',
            'continue',
            'try: pass\nexcept ___ as ___: pass',
            'raise ___',
            'assert ___',
            'with ___ as ___: pass'
        ]},
        TOOLBOX_CATEGORY.SEP,
        TOOLBOX_CATEGORY.OUTPUT_WITH_PLOTTING,
        TOOLBOX_CATEGORY.INPUT,
        {name: "文件", colour: "FILE", blocks: [
            "with open('', 'r') as ___: pass",
            "___.read()",
            "___.readlines()",
            "___.write(___)",
            "___.writelines(___)"
        ]},
        TOOLBOX_CATEGORY.SEP,
        {name: "类型转换", colour: "TEXT", blocks: [
            "int(___)",
            "float(___)",
            "str(___)",
            "chr(___)",
            "bool(___)",
            "list(___)",
            "dict(___)",
            "tuple(___)",
            "set(___)",
            "type(___)",
            "isinstance(___)"
        ]},
        {name: "内置函数", colour: "SEQUENCES", blocks: [
            "len(___)",
            "sorted(___)",
            "enumerate(___)",
            "reversed(___)",
            "range(0, 10)",
            "min(___, ___)",
            "max(___, ___)",
            "sum(___)",
            "all(___)",
            "any(___)",
            "zip(___, ___)",
            "map(___, ___)",
            "filter(___, ___)",
        ]},
        TOOLBOX_CATEGORY.LIST_METHODS,
        TOOLBOX_CATEGORY.STRING_METHODS,
        TOOLBOX_CATEGORY.DICT_METHODS,
        TOOLBOX_CATEGORY.SETS,
        {name: "索引切片", colour: "SEQUENCES", blocks: [
            "___[___]",
            "___[___:___]",
            "___[___:___:___]"
        ]},
        {name: "生成器", colour: "SEQUENCES", blocks: [
            "[___ for ___ in ___]",
            "(___ for ___ in ___)",
            "{___ for ___ in ___}",
            "{___: ___ for ___ in ___ if ___}",
            "[___ for ___ in ___ if ___]",
            "(___ for ___ in ___ if ___)",
            "{___ for ___ in ___ if ___}",
            "{___: ___ for ___ in ___ if ___}"
        ]},
        TOOLBOX_CATEGORY.SEP,
        TOOLBOX_CATEGORY.MATH_MODULE,
        TOOLBOX_CATEGORY.RANDOM_MODULE,
        {name: "注释", colour: "PYTHON", blocks: [
            "# ",
            '"""\n"""'
        ]}/*,
        {name: "Weird Stuff", colour: "PYTHON", blocks: [
            "delete ___",
            "global ___"
        ]}*/
    ],
    //******************************************************
    'ct2': [
        {name: '存储', colour: 'VARIABLES', custom: 'VARIABLE', hideGettersSetters: true},
        TOOLBOX_CATEGORY.SEP,

        '<category name="Expressions" expanded="true">',
        {name: "常量", colour: "TEXT", blocks: [
                '""',
                "0",
                "True",
                "[0, 0, 0]",
                "[___, ___, ___]",
                "[]",
            ]},
        {name: "变量", colour: "VARIABLES", blocks: [
                "VARIABLE",
            ]},
        TOOLBOX_CATEGORY.CALCULATIONS,
        TOOLBOX_CATEGORY.CONVERSIONS,
        {name: "条件", colour: "LOGIC", blocks: [
                '___ == ___',
                '___ and ___',
                'not ___'
            ]},
        TOOLBOX_CATEGORY.INPUT,
        '</category>',
        TOOLBOX_CATEGORY.SEP,

        '<category name="Operations" expanded="true">',
        {name: "Assignment", colour: "VARIABLES", blocks: [
                "VARIABLE = ___",
                "___.append(___)"
            ]},
        TOOLBOX_CATEGORY.OUTPUT_WITH_PLOTTING,
        '</category>',
        TOOLBOX_CATEGORY.SEP,

        '<category name="Control" expanded="true">',
        {name: "Decision", colour: "CONTROL", blocks: [
                'if ___: pass',
                'if ___: pass\nelse: pass',
            ]},
        {name: "Iteration", colour: "CONTROL", blocks: [
                'for ___ in ___: pass',
            ]},
        '</category>',
    ],
};
