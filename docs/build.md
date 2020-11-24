# Build and publish 
Building and publishing `chives-exchange` onto PyPI consist of three steps:

## Installation/packaging instruction 
Package metadata like package name on PyPI, author, etc. is specified in 
`setup.py` and `MANIFEST.in`. There is nothing worth noting in `setup.py`, but 
I would like to point out that `MANIFEST.in` is used to copy non-python source 
code into the package. With this project, this includes everything under 
`chives/templates` (HTMLs) and `chives/static` (CSS and static images).

## Build distribution package 
Run `python setup.py sdist bdist_wheel` to build the source distribution (a tar ball) and a wheel distribution (a `.whl` file) under the `dist` directory.

## Upload to PyPI
Run `python -m twine upload --repository pypi dist/*` to upload the source and wheel distribution onto PyPI. You will be asked to enter credentials: for username enter `__token__`, and for password, use the API token obtained from PyPI that starts with `pypi-`.

