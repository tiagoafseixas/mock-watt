from setuptools import setup, find_packages

setup(
    name="mock-watt",
    version="0.1.0",
    description="Local Simulator for European Energy Market Communications (IEC 62325)",
    packages=find_packages(),
    py_modules=["cli"],
    install_requires=[
        "fastapi",
        "uvicorn",
        "lxml",
        "signxml",
        "spyne",
        "zeep",
        "requests",
        "sqlalchemy"
    ],
    entry_points={
        "console_scripts": [
            # This maps the terminal command 'mock-watt' to the main() function in cli.py
            "mock-watt=cli:main",
        ],
    },
)