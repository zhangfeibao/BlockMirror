from setuptools import setup

setup(
    name='ramgs',
    version='1.0.0',
    description='RAMViewer - MCU RAM Read/Write Tool',
    package_dir={'ramgs': '.'},
    packages=[
        'ramgs',
        'ramgs.chart',
        'ramgs.designer',
        'ramgs.gui',
        'ramgs.recognizer',
        'ramgs.repl',
    ],
    install_requires=[
        'pyserial',
    ],
    python_requires='>=3.8',
)
