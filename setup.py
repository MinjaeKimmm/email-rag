from setuptools import setup, find_packages

setup(
    name="email-rag",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "streamlit>=1.42.0",
        "langchain>=0.3.17",
        "langchain-core>=0.3.33",
        "langchain-community>=0.3.16",
        "langchain-openai>=0.3.3",
        "elasticsearch>=8.17.1",
        "openai>=1.61.0",
        "pydantic>=2.10.6",
        "python-dotenv>=1.0.1",
        "tiktoken>=0.8.0"
    ],
)
