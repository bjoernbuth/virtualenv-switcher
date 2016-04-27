.PHONY: clean devinstall

venv:
	pyvenv venv
	venv/bin/pip install flake8 tox pytest mock

devinstall: venv
	venv/bin/python setup.py develop

test: devinstall
	venv/bin/py.test test_virtualenv_switcher.py

tox: venv
	venv/bin/tox

clean:
	rm -Rf build dist venv virtualenv_switcher.egg-info __pycache__
