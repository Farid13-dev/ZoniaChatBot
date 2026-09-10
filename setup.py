from setuptools import setup, find_packages

setup(
    name="rag",
    version="0.1.1",
    packages=find_packages(include=["rag", "rag.*"]),
)
