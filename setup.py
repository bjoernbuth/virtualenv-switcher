from setuptools import setup

setup(
    name='virtualenv-switcher',
    version='0.1.1',
    description='Virtualenv switcher.',
    long_description='Facilitate switching between python virtualenvs.',
    url='https://github.com/kvas-it/virtualenv-switcher/',
    py_modules=['virtualenv_switcher'],
    entry_points={
        'console_scripts': [
            'vs-bash-hook=virtualenv_switcher:vs_bash_hook',
            'vs-bash-complete=virtualenv_switcher:vs_bash_complete',
            'vs-add=virtualenv_switcher:vs_add',
            'vs-del=virtualenv_switcher:vs_del',
            'vs-list=virtualenv_switcher:vs_list',
            'vs-expose=virtualenv_switcher:vs_expose',
            'vs-path=virtualenv_switcher:vs_path',
            'vs-install=virtualenv_switcher:vs_install'
        ]
    },
    include_package_data=True,
    license='MIT',
    keywords='virtualenv',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
    ]
)
