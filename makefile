.PHONY: clean devinstall

venv:
	pyvenv venv

devinstall: venv
	venv/bin/python setup.py develop

clean:
	rm -Rf build dist venv virtualenv_switcher.egg-info __pycache__
