# ConfigFile class - Dynamically parse and edit configuration files.
# Copyright (C) 2011-2014 Dario Giovannetti <dev@dariogiovannetti.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from distutils.core import setup

setup(name='configfile',
      version='1.1.0',
      description='Dynamically parse and edit configuration files with '
                                                    'support for subsections.',
      author='Dario Giovannetti',
      author_email='dev@dariogiovannetti.net',
      url='https://kynikos.github.io/lib.py.configfile',
      license='GPLv3',
      packages=['configfile', ])
