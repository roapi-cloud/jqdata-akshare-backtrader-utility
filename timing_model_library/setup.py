from setuptools import setup, find_packages

setup(
    name="timing_model_library",
    version="1.0.0",
    description="统一择时模型库 - 聚合所有大盘择时与个股择时模型",
    author="Timing Model Library",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.20",
        "pandas>=1.3",
        "scipy>=1.7",
        "akshare>=1.8",
        "scikit-learn>=1.0",
    ],
    python_requires=">=3.8",
)
