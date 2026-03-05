from setuptools import setup, find_packages

setup(
    name="benchmark_llm",
    version="1.0.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "bcllm=src.main:main",
        ],
    },
    install_requires=[
        "httpx>=0.25.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "Pillow>=10.0.0",
        "python-dotenv>=1.0.0",
        "rich>=13.0.0",
    ],
    python_requires=">=3.10",
)
