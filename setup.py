import pathlib
from setuptools import setup, find_packages

HERE = pathlib.Path(__file__).parent 
README = (HERE / "README.md").read_text()

setup(
    name="chives-exchange",
    version="0.1.1",
    description="Stock exchange with a matching engine and webserver",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/xuganyu96/chives-exchange",
    author='Ganyu "Bruce" Xu',
    author_email="xuganyu96@gmail.com",
    packages=find_packages(include=('chives', 'chives.*')),
    install_requires=[
        "Flask==1.1.2",
        "flask-login==0.5.0",
        "flask-wtf==0.14.3",
        "pytest==6.1.2",
        "pika==1.1.0",
        "requests==2.24.0",
        "SQLAlchemy==1.3.20"
    ],
    entry_points={
        'console_scripts': ['chives=chives.__main__:main']
    },
    include_package_data=True
)
