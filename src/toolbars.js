let ZERO_BLOCK = BlockMirrorTextToBlocks.create_block('ast_Num', null, {'NUM': 0});

BlockMirrorBlockEditor.EXTRA_TOOLS = {};

const TOOLBOX_CATEGORY = {};

TOOLBOX_CATEGORY.VARIABLES = {name: 'Variables', colour: 'VARIABLES', custom: 'VARIABLE'};
TOOLBOX_CATEGORY.DECISIONS = {name: "Decisions", colour: "LOGIC", blocks: [
    'if ___: pass',
    'if ___: pass\nelse: pass',
    '___ < ___',
    '___ and ___',
    'not ___'
]};
TOOLBOX_CATEGORY.CALCULATIONS = {name: "Calculation", colour: "MATH", blocks: [
    "___ + ___",
    "round(___)"
]};
TOOLBOX_CATEGORY.OUTPUT_WITH_PLOTTING = {name: "Output", colour: "PLOTTING", blocks: [
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
TOOLBOX_CATEGORY.TURTLES = {name: "Turtles", colour: "PLOTTING", blocks: [
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
TOOLBOX_CATEGORY.INPUT = {name: "Input", colour: "TEXT", blocks: [
    "input('')",
]};
TOOLBOX_CATEGORY.VALUES = {name: "Values", colour: "TEXT", blocks: [
    '""',
    "0",
    "True"
]};
TOOLBOX_CATEGORY.SEP = "<sep></sep>";

TOOLBOX_CATEGORY.CONVERSIONS = {name: "Conversion", colour: "TEXT", blocks: [
    "int(___)",
    "float(___)",
    "str(___)",
    "bool(___)"
]};

TOOLBOX_CATEGORY.DICTIONARIES = {name: "Dictionaries", colour: "DICTIONARY", blocks: [
    "{'1st key': ___, '2nd key': ___, '3rd key': ___}",
    "{}",
    "___['key']"
]};

TOOLBOX_CATEGORY.AUGMENTED_ASSIGN = {name: "Augmented Assignment", colour: "VARIABLES", blocks: [
    "___ += 1",
    "___ -= 1",
    "___ *= ___",
]};

TOOLBOX_CATEGORY.MATH_MODULE = {name: "Math Module", colour: "MATH", blocks: [
    "import math",
    "math.sqrt(___)",
    "math.floor(___)",
    "math.ceil(___)",
    "math.log(___)",
    "math.sin(___)",
    "math.cos(___)",
    "math.pi",
]};

TOOLBOX_CATEGORY.RANDOM_MODULE = {name: "Random Module", colour: "MATH", blocks: [
    "import random",
    "random.randint(0, 10)",
    "random.random()",
    "random.choice(___)",
]};

TOOLBOX_CATEGORY.LIST_METHODS = {name: "List Methods", colour: "LIST", blocks: [
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

TOOLBOX_CATEGORY.DICT_METHODS = {name: "Dict Methods", colour: "DICTIONARY", blocks: [
    "___.keys()",
    "___.values()",
    "___.items()",
    "___.get(___)",
    "___.update(___)",
    "___.pop(___)",
]};

TOOLBOX_CATEGORY.SETS = {name: "Sets", colour: "SET", blocks: [
    "{___, ___, ___}",
    "set(___)",
    "___.add(___)",
    "___.remove(___)",
    "___.discard(___)",
]};

TOOLBOX_CATEGORY.STRING_METHODS = {name: "String Methods", colour: "TEXT", blocks: [
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
        {"name": "Empty Toolbox", "colour": "PYTHON", "blocks": []}
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
        {name: "Iteration", colour: "CONTROL", blocks: [
            'for ___ in ___: pass',
            'for ___ in range(0, 10): pass',
            'while ___: pass',
            'break',
            'continue',
        ]},
        {name: "Functions", colour: "FUNCTIONS", blocks: [
            "def ___(___): pass",
            "def ___(___: int)->str: pass",
            "return ___",
        ]},
        TOOLBOX_CATEGORY.SEP,
        {name: "Calculation", colour: "MATH", blocks: [
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
        {name: "Lists", colour: "LIST", blocks: [
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
    ],
    //******************************************************
    'ct': [
        TOOLBOX_CATEGORY.VARIABLES,
        TOOLBOX_CATEGORY.DECISIONS,
        {name: "Iteration", colour: "CONTROL", blocks: [
            'for ___ in ___: pass',
        ]},
        TOOLBOX_CATEGORY.SEP,
        TOOLBOX_CATEGORY.CALCULATIONS,
        TOOLBOX_CATEGORY.OUTPUT_WITH_PLOTTING,
        TOOLBOX_CATEGORY.INPUT,
        TOOLBOX_CATEGORY.SEP,
        TOOLBOX_CATEGORY.VALUES,
        TOOLBOX_CATEGORY.CONVERSIONS,
        {name: "Lists", colour: "LIST", blocks: [
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
        {name: "Literal Values", colour: "LIST", blocks: [
            "0",
            "''",
            "True",
            "None",
            "[___, ___, ___]",
            "(___, ___, ___)",
            "{___, ___, ___}",
            "{___: ___, ___: ___, ___: ___}",
            ]},
        {name: "Calculations", colour: "MATH", blocks: [
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
        {name: "Logic", colour: "LOGIC", blocks: [
            '___ if ___ else ___',
            '___ == ___',
            '___ < ___',
            '___ in ___',
            '___ and ___',
            'not ___'
        ]},
        TOOLBOX_CATEGORY.SEP,
        {name: "Classes", colour: "OO", blocks: [
            "class ___: pass",
            "class ___(___): pass",
            "___.___",
            "___: ___",
            "super()"
        ]},
        {name: "Functions", colour: "FUNCTIONS", blocks: [
            "def ___(___): pass",
            "def ___(___: int)->str: pass",
            "return ___",
            "yield ___",
            "lambda ___: ___"
        ]},
        {name: "Imports", colour: "PYTHON", blocks: [
            "import ___",
            "from ___ import ___",
            "import ___ as ___",
            "from ___ import ___ as ___"
        ]},
        TOOLBOX_CATEGORY.SEP,
        {name: "Control Flow", colour: "CONTROL", blocks: [
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
        {name: "Files", colour: "FILE", blocks: [
            "with open('', 'r') as ___: pass",
            "___.read()",
            "___.readlines()",
            "___.write(___)",
            "___.writelines(___)"
        ]},
        TOOLBOX_CATEGORY.SEP,
        {name: "Conversion", colour: "TEXT", blocks: [
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
        {name: "Builtin Functions", colour: "SEQUENCES", blocks: [
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
        {name: "Subscripting", colour: "SEQUENCES", blocks: [
            "___[___]",
            "___[___:___]",
            "___[___:___:___]"
        ]},
        {name: "Generators", colour: "SEQUENCES", blocks: [
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
        {name: "Comments", colour: "PYTHON", blocks: [
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
        {name: 'Memory', colour: 'VARIABLES', custom: 'VARIABLE', hideGettersSetters: true},
        TOOLBOX_CATEGORY.SEP,

        '<category name="Expressions" expanded="true">',
        {name: "Constants", colour: "TEXT", blocks: [
                '""',
                "0",
                "True",
                "[0, 0, 0]",
                "[___, ___, ___]",
                "[]",
            ]},
        {name: "Variables", colour: "VARIABLES", blocks: [
                "VARIABLE",
            ]},
        TOOLBOX_CATEGORY.CALCULATIONS,
        TOOLBOX_CATEGORY.CONVERSIONS,
        {name: "Conditions", colour: "LOGIC", blocks: [
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
