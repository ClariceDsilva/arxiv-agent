from setuptools import setup, find_packages

setup(
    name="arxiv-agent",
    version="0.1.0",
    description="Autonomous arXiv paper digest & QA agent",
    author="Your Name",
    author_email="your.email@example.com",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "requests>=2.31.0",
        "pymupdf>=1.24.0",
        "chromadb>=0.4.0",
        "sentence-transformers>=2.2.0",
        "google-genai>=0.3.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "black>=23.0",
            "mypy>=1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "arxiv-agent=main:main",
        ],
    },
)
