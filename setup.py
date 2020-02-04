import os
import sys

from setuptools import setup, find_packages

assert sys.version_info >= (3, 7, 0), "pyembc requires Python 3.7+"

with open("README.md", 'r') as f:
    long_description = f.read()


here = os.path.abspath(os.path.dirname(__file__))


setup(
    name="pyembc",
    version="0.0.1",
    description="pyembc - declarative c datatypes",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    url="https://github.com/waszil/pyembc",
    use_scm_version={
        "write_to": "_pyembc_version.py",
        "write_to_template": 'version = "{version}"\n',
    },
    author="csaba.nemes",
    author_email="waszil.waszil@gmail.com",
    packages=find_packages(exclude=["test"]),
    tests_require=[
        "pytest",
        "construct"
    ],
    install_requires=[],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)
