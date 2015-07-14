#!/usr/bin/env python

from distutils.core import setup

setup(name='interfaces',
      version='1.0',
      description="An index of interface: relation stubs and layers for the Juju Project",
      author='Juju Solutions Team',
      author_email='benjamin.saller@canonical.com',
      url='https://github.com/bcsaller/juju-interfaces',
      packages=['juju_interfaces'],
      entry_points={
          'console_scripts': [
          ]
      }
      )
