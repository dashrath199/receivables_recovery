# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
from receivables_recovery import __version__ as version

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="receivables_recovery",
    version=version,
    description="Multi-channel collections automation for ERPNext",
    author="Receivables Recovery",
    author_email="support@example.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
