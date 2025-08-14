#!/usr/bin/env python3
"""
HchDB 分布式数据库 - 安装脚本
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="hchdb",
    version="0.1.0",
    author="hch",
    author_email="hch@example.com",
    description="Python分布式数据库 - 类PolarDB-X实现",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hch/hchdb",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Database",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "hchdb=hchdb.main:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)