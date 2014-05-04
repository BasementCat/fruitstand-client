#!/usr/bin/env python
import os
from setuptools import setup

def read(filen):
    with open(os.path.join(os.path.dirname(__file__), filen), "r") as fp:
        return fp.read()
 
setup (
    name = "fruitstand-client",
    version = "0.1",
    description = "Client - Web-based digital signage (designed for the RPi + Raspbian)",
    long_description = read("README.md"),
    author = "Alec Elton",
    author_email = "alec.elton@gmail.com",
    url = "https://github.com/BasementCat/fruitstand-client",
    packages = ["fruitstand-client", "tests"],
    test_suite = "nose.collector",
    install_requires = [],
    tests_require = ["nose"]
)