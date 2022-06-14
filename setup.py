#!/usr/bin/env python3

import setuptools

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setuptools.setup(name="nola-tools",
                 version="0.1.1",
                 author="CoXlab Inc.",
                 author_email="support@coxlab.kr",
                 description="Nol.A SDK Command Line Interface for IoT Device Firmware Development",
                 long_description=long_description,
                 long_description_content_type="text/markdown",
                 url="https://github.com/CoXlabInc/Nol.A-Tools",
                 project_urls={
                     "Bug Tracker": "https://github.com/CoXlabInc/Nol.A-Tools/issues",
                 },
                 classifiers=[
                     "Programming Language :: Python :: 3",
                     "License :: OSI Approved :: MIT License",
                     "Operating System :: OS Independent",
                 ],
                 packages=['nola_tools'],
                 python_requires=">=3.6",
                 install_requires=["setuptools>=42"],
                 entry_points = {
                     'console_scripts': ['nolja=nola_tools.nolja:main'],
                 },
)
