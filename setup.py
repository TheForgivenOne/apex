from setuptools import setup, find_packages

setup(
    name="apex-web",
    version="0.1.0",
    description="A modern Python web framework with file-based routing",
    long_description=open("README.md").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    author="Apex Team",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "uvicorn>=0.20.0",
    ],
    extras_require={
        "dev": ["watchfiles>=1.0.0"],
    },
    entry_points={
        "console_scripts": [
            "apex=apex.cli:main",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Framework :: Apex",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Server",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
)
