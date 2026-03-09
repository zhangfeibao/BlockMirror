from setuptools import setup, find_packages

setup(
    name="ramgs",
    version="1.0.0",
    description="RAMViewer - MCU RAM Read/Write CLI Tool",
    author="RAMViewer Team",
    packages=find_packages(),
    install_requires=[
        "click>=8.0.0",
        "pyserial>=3.5",
        "matplotlib>=3.5.0",
    ],
    entry_points={
        "console_scripts": [
            "ramgs=ramgs.cli:main",
        ],
    },
    python_requires=">=3.8",
)
