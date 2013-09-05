# ConfigFile class - Dynamically parse and edit configuration files.
# Copyright (C) 2011-2013 Dario Giovannetti <dev@dariogiovannetti.net>
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

"""
ConfigFile class - Dynamically parse and edit configuration files.

@author: Dario Giovannetti
@copyright: Copyright (C) 2011-2013 Dario Giovannetti <dev@dariogiovannetti.net>
@license: GPLv3
@version: 1.0.0
@date: 2013-09-05
"""

import re as _re
import collections as _collections


class Section():
    """
    The class for a section in the configuration file.
    
    Possible options at the beginning of the file, before any section, are
    considered to be in the "root" section.
    """
    def __init__(self, name=None, parent=None, subsections=True,
                                       inherit_options=True, ignore_case=True):
        """
        Constructor.
        
        name (string): the name of the section
        parent (Section instance): a reference to the parent section object
        subsections (boolean): if True, subsections are enabled; otherwise they
        are disabled
        ignore_case (boolean): if True, section and option names will be
        compared ignoring case differences; regular expressions will use re.I
        flag
        """
        # Store section name
        self._NAME = name
        
        # Store parent reference
        self._PARENT = parent
        
        # Enable/Disable subsections
        self._ENABLE_SUBS = subsections
        
        # Enable option inheritance
        self._INHERIT_OPTIONS = inherit_options
        
        # Enable/Disable ignore case
        self._IGNORE_CASE = ignore_case
        if self._IGNORE_CASE:
            self._RE_I = _re.I
        else:
            self._RE_I = 0
        
        # Define regular expressions
        self._PARSE_SECTION = '^\s*\[(.+)\]\s*$'
        self._PARSE_OPTION = '^\s*([^\=]+?)\s*\=\s*(.*?)\s*$'
        self._PARSE_COMMENT = '^\s*[#;]{1}\s*(.*?)\s*$'
        self._PARSE_IGNORE = '^\s*$'
        if self._ENABLE_SUBS:
            self._SECTION = '^[a-zA-Z_]+(?:\.?[a-zA-Z0-9_]+)*$'
        else:
            self._SECTION = '^[a-zA-Z_]+[a-zA-Z0-9_]*$'
        self._OPTION = '^[a-zA-Z_]+[a-zA-Z0-9_]*$'
        self._VALUE = '^.*$'
        
        # Separators
        self._SECTION_SEP = '.'
        self._OPTION_SEP = ' = '
        # This will be used with str.format(): section name will be written in
        # place of {}
        self._SECTION_MARKERS = '[{}]'
        self._COMMENT_MARKER = '# '
        
        # get_bool tuples and default
        self._GET_BOOLEAN_TRUE = ('true', '1', 'yes', 'on')
        self._GET_BOOLEAN_FALSE = ('false', '0', 'no', 'off')
        self._GET_BOOLEAN_DEFAULT = None
        
        # Store subsections
        self._subsections = _collections.OrderedDict()
        
        # Store options
        self._options = _collections.OrderedDict()
    
    ### DATA MODEL ###
    
    def __call__(self, key):
        """
        Enables calling directly the object with a string, returning the
        corresponding subsection object, if existent.
        
        key (string): the name of the subsection
        """
        if isinstance(key, str):
            for k in self._subsections:
                if (self._IGNORE_CASE and key.lower() == k.lower()) or \
                                          (not self._IGNORE_CASE and key == k):
                    return self._subsections[k]
            else:
                raise KeyError('Section not found: ' + key)
        else:
            raise TypeError(str(key) + ' section name must be a string')
    
    def __getitem__(self, opt):
        """
        Returns the value for the option specified.
        
        opt (string): the name of the option whose value must be returned
        """
        item = self.get(opt, fallback=None,
                                         inherit_options=self._INHERIT_OPTIONS)
        # self.get returns None as a fallback value if opt is not found:
        # however, for compatibility with usual dictionary operations,
        # __getitem__ should better raise KeyError in this case
        if item == None:
            raise KeyError('Option not found: ' + opt)
        else:
            return(item)
    
    def __setitem__(self, opt, val):
        """
        Stores the provided value in the specified option.
        
        Both the option name and the value must be strings.
        
        opt (string): the name of the option
        val (string): the new value for the option
        """
        if isinstance(opt, str):
            if isinstance(val, str):
                if self._IGNORE_CASE:
                    for o in self._options:
                        if opt.lower() == o.lower():
                            self._options[o] = str(val)
                            break
                    else:
                        self._options[opt] = str(val)
                else:
                    self._options[opt] = str(val)
            else:
                raise TypeError(str(val) + ': value must be a string')
        else:
            raise TypeError(str(opt) + ': option name must be a string')
    
    def __delitem__(self, opt):
        """
        Deletes the specified option.
        
        opt (string): the name of the option that must be deleted
        """
        if isinstance(opt, str):
            for o in self._options:
                if (self._IGNORE_CASE and opt.lower() == o.lower()) or \
                                          (not self._IGNORE_CASE and opt == o):
                    del self._options[o]
                    break
            else:
                raise KeyError('Option not found: ' + opt)
        else:
            raise TypeError(str(opt) + ': option name must be a string')
    
    def __iter__(self):
        """
        Lets iterate over the options of the section (for example with a for
        loop).
        """
        return(iter(self._options))
    
    def __contains__(self, item):
        """
        If item is a Section object, this method returns True if item (the
        object, not its name) is a subsection of self; otherwise this returns
        True if item is the name of an option in self.
        
        item: a Section object or the name of an option
        """
        if isinstance(item, Section):
            if item in self._subsections.values():
                return(True)
            else:
                return(False)
        else:
            if self._IGNORE_CASE:
                for o in self._options:
                    if item.lower() == o.lower():
                        return(True)
                else:
                    return(False)
            else:
                if item in self._options:
                    return(True)
                else:
                    return(False)
    
    ### IMPORTING DATA ###
    
    def set(self, opt, val):
        """
        This is an alias for __setitem__().
        """
        self[opt] = val
    
    def make_subsection(self, name):
        """
        Create an empty subsection under the current section if it doesn't
        exist.
        
        name (string): the name of the new subsection
        """
        self._import_dict({0: {name: {0: {}}}}, mode='add')
    
    def delete(self):
        """
        Delete the current section.
        """
        del self._PARENT._subsections[self._NAME]
    
    def upgrade(self, *sources, **kwargs):
        """
        Import sections and options from a file or compatible dictionary with
        upgrade mode.
        
        See _import_dict for a description of available modes and dictionary
        compatibility.
        
        sources: a sequence of files and/or dictionaries.
        interpolation (boolean): enable/disable value interpolation.
        """
        # Necessary for Python 2 compatibility
        # The Python 3 definition was:
        #def upgrade(self, *sources, interpolation=False):
        if 'interpolation' in kwargs:
            interpolation = kwargs['interpolation']
        else:
            interpolation = False
        
        self._import(sources, mode='upgrade', interpolation=interpolation)
    
    def update(self, *sources, **kwargs):
        """
        Import sections and options from a file or compatible dictionary with
        update mode.
        
        See _import_dict for a description of available modes and dictionary
        compatibility.
        
        sources: a sequence of files and/or dictionaries.
        interpolation (boolean): enable/disable value interpolation.
        """
        # Necessary for Python 2 compatibility
        # The Python 3 definition was:
        #def upgrade(self, *sources, interpolation=False):
        if 'interpolation' in kwargs:
            interpolation = kwargs['interpolation']
        else:
            interpolation = False
        
        self._import(sources, mode='update', interpolation=interpolation)
    
    def reset(self, *sources, **kwargs):
        """
        Import sections and options from a file or compatible dictionary with
        reset mode.
        
        See _import_dict for a description of available modes and dictionary
        compatibility.
        
        sources: a sequence of files and/or dictionaries.
        interpolation (boolean): enable/disable value interpolation.
        """
        # Necessary for Python 2 compatibility
        # The Python 3 definition was:
        #def upgrade(self, *sources, interpolation=False):
        if 'interpolation' in kwargs:
            interpolation = kwargs['interpolation']
        else:
            interpolation = False
        
        self._import(sources, mode='reset', interpolation=interpolation)
    
    def add(self, *sources, **kwargs):
        """
        Import sections and options from a file or compatible dictionary with
        add mode.
        
        See _import_dict for a description of available modes and dictionary
        compatibility.
        
        sources: a sequence of files and/or dictionaries.
        interpolation (boolean): enable/disable value interpolation.
        """
        # Necessary for Python 2 compatibility
        # The Python 3 definition was:
        #def upgrade(self, *sources, interpolation=False):
        if 'interpolation' in kwargs:
            interpolation = kwargs['interpolation']
        else:
            interpolation = False
        
        self._import(sources, mode='add', interpolation=interpolation)

    def _import(self, sources, mode='upgrade', interpolation=False):
        """
        Parse some files or dictionaries and add their configuration to the
        existing one.
        
        Distinction between files and dictionaries is done automatically.
        
        sources: a sequence of all the files or dictionaries to be parsed.
        mode (string): this sets if and how the next file or dictionary in the
        chain overwrites already imported sections and options; available
        choices are 'upgrade', 'update', 'reset' and 'add' (see _import_dict()
        for more details)
        interpolation (boolean): if True, option values will be interpolated
        using values from other options through the special syntax
        ${section$:section$:option$}. Options will be interpolated only once at
        importing: all links among options will be lost after importing.
        """
        if mode in ('upgrade', 'update', 'reset', 'add'):
            for f in sources:
                if not isinstance(f, dict):
                    f = self._parse_file(f)
                self._import_dict(f, mode=mode)
                if interpolation:
                    self._interpolate(root=self)
        else:
            raise ValueError('Unrecognized importing mode: ' + mode)
    
    def _parse_file(self, cfile):
        """
        Parse a text file and translate it into a compatible dictionary, thus
        making it possible to import it.
        
        cfile (string): the name of the file to be parsed
        """
        try:
            stream = open(cfile, 'r')
        except EnvironmentError as e:
            raise InvalidFileError('Cannot import configuration from {} ({})'
                                             ''.format(e.filename, e.strerror))
        else:
            with stream:
                cdict = _collections.OrderedDict()
                cdict[0] = _collections.OrderedDict()
                lastsect = cdict
                for lno, line in enumerate(stream):
                    # Note that the order the various types are evaluated
                    # matters!
                    if _re.match(self._PARSE_IGNORE, line, self._RE_I):
                        pass
                    elif _re.match(self._PARSE_COMMENT, line, self._RE_I):
                        pass
                    else:
                        re_option = _re.match(self._PARSE_OPTION, line,
                                              self._RE_I)
                        if re_option:
                            lastsect[re_option.group(1)] = re_option.group(2)
                        else:
                            re_section = _re.match(self._PARSE_SECTION, line,
                                                   self._RE_I)
                            if re_section:
                                subs = self._parse_subsections(re_section)
                                d = cdict
                                for s in subs:
                                    if s not in d[0]:
                                        d[0][s] = _collections.OrderedDict()
                                        d[0][s][0] = _collections.OrderedDict()
                                    d = d[0][s]
                                lastsect = d
                            
                            else:
                                # Invalid lines
                                raise ParsingError('Invalid line in ' + cfile +
                                                   ': ' + line + ' (line ' +
                                                   str(lno + 1) + ')')
            
            return(cdict)
    
    def _parse_subsections(self, re):
        """
        Parse the sections hierarchy in a section line of a text file and
        return them in a list.
        
        re: regexp object
        """
        if self._ENABLE_SUBS:
            subs = re.group(1).split(self._SECTION_SEP)
        else:
            subs = (re.group(1),)
        return subs
    
    def _import_dict(self, cdict, mode='upgrade'):
        """
        Import sections and options from a compatible dictionary.
        
        cdict (mapping object): a dictionary (or compatible mapping object) to
        be imported; it represents a section, and the keys which are strings
        will be considered option names (and their values the option values),
        while a special key 0 (integer) will be considered as the container for
        subsections, like in this example:
        cdict = {
            0: {
                'sectionA': {
                    0: {
                        'sectionC': {
                            0: {},
                            'optionC1': 'value',
                            'optionC2': 'value'
                        }
                    },
                    'optionA1': 'value',
                    'optionA2': 'value'
                },
                'sectionB': {
                    0: {},
                    'optionB1': 'value',
                    'optionB2': 'value'
                }
            },
            'option1': 'value',
            'option2': 'value'
        }
        
        mode (string): this is the mode of data import; available choices are
        'upgrade', 'update', 'reset' and 'add', here descripted:
        
        upgrade mode:
        if an option already exists, change its value; if it doesn't exist,
        create it and store its value:
        (A:a,B:b,C:c) upgrade (A:d,D:e) => (A:d,B:b,C:c,D:e)
        
        update mode:
        if an option already exists, change its value; if it doesn't exist,
        don't do anything:
        (A:a,B:b,C:c) update (A:d,D:e) => (A:d,B:b,C:c)
        
        reset mode:
        delete all options and subsections and recreate everything from the
        importing dictionary:
        (A:a,B:b,C:c) reset (A:d,D:e) => (A:d,D:e)
        
        add mode:
        if an option already exists, don't do anything; if it doesn't exist,
        create it and store its value:
        (A:a,B:b,C:c) add (A:d,D:e) => (A:a,B:b,C:c,D:e)
        """
        if mode == 'reset':
            self._subsections = _collections.OrderedDict()
            self._options = _collections.OrderedDict()
        
        for e in cdict:
            if e == 0 and isinstance(cdict[0], dict):
                for s in cdict[0]:
                    if isinstance(s, str):
                        if _re.match(self._SECTION, s, self._RE_I):
                            self._import_dict_subsection(mode, s, cdict[0][s])
                        else:
                            raise InvalidDictionaryError('Invalid section '
                                                         'name: ' + s)
                    else:
                        raise InvalidDictionaryError('The dictionary to be '
                                                     'imported has invalid '
                                                     'keys or values')
            elif isinstance(e, str) and isinstance(cdict[e], str):
                if _re.match(self._OPTION, e, self._RE_I) and \
                                  _re.match(self._VALUE, cdict[e], self._RE_I):
                    self._import_dict_option(mode, e, cdict[e])
                else:
                    raise InvalidDictionaryError('Invalid option or value: ' +
                                                 e + ': ' + cdict[e])
            else:
                raise InvalidDictionaryError('The dictionary to be imported '
                                             'has invalid keys or values')
    
    def _import_dict_subsection(self, mode, sec, secd):
        """
        Auxiliary method for _import_dict().
        
        Import the currently-examined subsection.
        """
        if mode == 'reset':
            self._import_dict_subsection_create(mode, sec, secd)
        elif self._IGNORE_CASE:
            for ss in self._subsections:
                if sec.lower() == ss.lower():
                    # Do not use "if sec.lower() == ss.lower() and mode in
                    # ('upgrade', 'update')" because if mode is not in
                    # ('upgrade', 'update') the loop never breaks, not even if
                    # sec.lower() == ss.lower()
                    if mode in ('upgrade', 'update'):
                        self._subsections[ss]._import_dict(secd, mode=mode)
                    break
            else:
                if mode in ('upgrade', 'add'):
                    self._import_dict_subsection_create(mode, sec, secd)
        else:
            if sec in self._subsections and mode in ('upgrade', 'update'):
                self._subsections[sec]._import_dict(secd, mode=mode)
            elif sec not in self._subsections and mode in ('upgrade', 'add'):
                self._import_dict_subsection_create(mode, sec, secd)
    
    def _import_dict_subsection_create(self, mode, sec, secd):
        """
        Auxiliary method for _import_dict_subsection().
        
        Import the currently-examined subsection.
        """
        subsection = Section(name=sec, parent=self,
                             subsections=self._ENABLE_SUBS,
                             inherit_options=self._INHERIT_OPTIONS,
                             ignore_case=self._IGNORE_CASE)
        subsection._import_dict(secd, mode=mode)
        self._subsections[sec] = subsection
    
    def _import_dict_option(self, mode, opt, val):
        """
        Auxiliary method for _import_dict().
        
        Import the currently-examined option.
        """
        if mode == 'reset':
            self._options[opt] = val
        elif self._IGNORE_CASE:
            for o in self._options:
                if opt.lower() == o.lower():
                    # Do not use "if opt.lower() == o.lower() and mode in
                    # ('upgrade', 'update')" because if mode is not in
                    # ('upgrade', 'update') the loop never breaks, not even if
                    # opt.lower() == o.lower()
                    if mode in ('upgrade', 'update'):
                        self._options[o] = val
                    break
            else:
                if mode in ('upgrade', 'add'):
                    self._options[opt] = val
        elif (opt in self._options and mode in ('upgrade', 'update')) or \
                     (opt not in self._options and mode in ('upgrade', 'add')):
            self._options[opt] = val
    
    def _interpolate(self, root=None):
        """
        Interpolate values among different options.
        
        root: the root section from which resolve interpolations.
        
        The '$' sign is a special character: a '$' not followed by '$', '{',
        ':' or '}' will be left '$'; '$$' will be translated as '$' both inside
        or outside an interpolation path; '${' will be considered as the
        beginning of an interpolation path, unless it's found inside another
        interpolation path, and in the latter case it will be left '${'; '$:'
        will be considered as a separator between sections of an interpolation
        path, unless it's found outside of an interpolation path, and in the
        latter case it will be left '$:'; '$}' will be considered as the end of
        an interpolation path, unless it's found outside of an interpolation
        path, and in the latter case it will be left '$}'.
        Normally all paths will be resolved based on the root section of the
        file; anyway, if the interpolation path has only one item, it will be
        resolved as an option relative to the current section; otherwise, if
        the path starts with '$:', the first item will be considered as a
        section (or an option, if last in the list) relative to the current
        section.
        """
        for o, v in self._options:
            L = _re.split('(\$\$|\$\{|\$\:|\$\})', v)
            resolve = []
            for i in L:
                if i == '$$':
                    i = '$'
                
                if i == '${' and not resolve:
                    resolve.append('')
                    continue
                elif i == '$:' and resolve:
                    resolve.append('')
                    continue
                elif i == '$}' and resolve:
                    option = resolve.pop(-1)
                    if len(resolve) == 0 or resolve[0] == '':
                        section = self
                    else:
                        section = root._subsections[resolve[0]]
                    for r in resolve[1:]:
                        section = section._subsections[r]
                    i = section._options[option]
                    resolve = []
                    continue
                elif resolve:
                    resolve[-1][-1:] = i
            v = ''.join(L)
        for s, ss in self._subsections:
            ss._interpolate(root=root)
    
    ### EXPORTING DATA ###
    
    def get(self, opt, fallback=None, inherit_options=None):
        """
        Returns the value for the option specified.
        
        opt (string): the name of the option whose value must be returned
        fallback (string, None): if set to a string, and the option is not
        found, this method returns that string; if set to None (default) it
        returns KeyError
        inherit_options (boolean): if True, if the option is not found in the
        current section, it's searched in the parent sections; note that this
        can be set as a default for the object, but this setting overwrites it
        only for this call
        """
        if inherit_options not in (True, False):
            inherit_options = self._INHERIT_OPTIONS
        
        if isinstance(opt, str):
            if inherit_options:
                slist = self._get_ancestors()
            else:
                slist = [self, ]
            
            for s in slist:
                for o in s._options:
                    if (self._IGNORE_CASE and opt.lower() == o.lower()) or \
                                          (not self._IGNORE_CASE and opt == o):
                        return s._options[o]
            else:
                # Note that if fallback is not specified, this returns None
                # which is not a string as expected
                return(fallback)
        else:
            raise TypeError(str(opt) + ': option name must be a string')
    
    def get_str(self, opt, fallback=None, inherit_options=None):
        """
        This is an alias for get().
        
        This will always return a string.
        
        opt (string): the name of the option whose value must be returned
        fallback (string, None): if set to a string, and the option is not
        found, this method returns that string; if set to None (default) it
        returns KeyError
        inherit_options (boolean): if True, if the option is not found in the
        current section, it's searched in the parent sections; note that this
        can be set as a default for the object, but this setting overwrites it
        only for this call
        """
        if inherit_options not in (True, False):
            inherit_options = self._INHERIT_OPTIONS
        return(self.get(opt, fallback=fallback,
                                              inherit_options=inherit_options))
    
    def get_int(self, opt, fallback=None, inherit_options=None):
        """
        This method tries to return an integer from the value of an option.
        
        opt (string): the name of the option whose value must be returned
        fallback (string, None): if set to a string, and the option is not
        found, this method returns that string; if set to None (default) it
        returns KeyError
        inherit_options (boolean): if True, if the option is not found in the
        current section, it's searched in the parent sections; note that this
        can be set as a default for the object, but this setting overwrites it
        only for this call
        """
        if inherit_options not in (True, False):
            inherit_options = self._INHERIT_OPTIONS
        return(int(self.get(opt, fallback=fallback,
                                             inherit_options=inherit_options)))
    
    def get_float(self, opt, fallback=None, inherit_options=None):
        """
        This method tries to return a float from the value of an option.
        
        opt (string): the name of the option whose value must be returned
        fallback (string, None): if set to a string, and the option is not
        found, this method returns that string; if set to None (default) it
        returns KeyError
        inherit_options (boolean): if True, if the option is not found in the
        current section, it's searched in the parent sections; note that this
        can be set as a default for the object, but this setting overwrites it
        only for this call
        """
        if inherit_options not in (True, False):
            inherit_options = self._INHERIT_OPTIONS
        return(float(self.get(opt, fallback=fallback,
                                             inherit_options=inherit_options)))
    
    def get_bool(self, opt, true=(), false=(), default=None, fallback=None,
                                                         inherit_options=None):
        """
        This method tries to return a boolean status (True or False) from the
        value of an option.
        
        opt (string): the name of the option whose value must be returned
        true (tuple): a tuple with the strings to be recognized as True
        false (tuple): a tuple with the strings to be recognized as False
        default: if the value is neither in true nor in false tuples, return
        this boolean status; if set to None, it raises a ValueError exception
        fallback: if set to None (default), and the option is not found, it
        raises KeyError; otherwise this value is evaluated with the true and
        false tuples, or the default value
        inherit_options (boolean): if True, if the option is not found in the
        current section, it's searched in the parent sections; note that this
        can be set as a default for the object, but this setting overwrites it
        only for this call
        
        Note that the characters in the strings are compared in lowercase, so
        there's no need to specify all casing variations of a string
        """
        if true == ():
            true = self._GET_BOOLEAN_TRUE
        if false == ():
            false = self._GET_BOOLEAN_FALSE
        if default not in (True, False):
            default = self._GET_BOOLEAN_DEFAULT
        if inherit_options not in (True, False):
            inherit_options = self._INHERIT_OPTIONS
        v = str(self.get(opt, fallback=fallback,
                                      inherit_options=inherit_options)).lower()
        if v in true:
            return(True)
        elif v in false:
            return(False)
        elif default in (True, False):
            return(default)
        else:
            raise ValueError('Unrecognized boolean status: ' + self[opt])
    
    def _get_ancestors(self):
        """
        Return a list with the current section and its ancestors.
        """
        slist = [self, ]
        p = self._PARENT
        while p:
            slist.append(p)
            p = p._PARENT
        return slist
    
    def get_options(self, ordered=True, inherit_options=None):
        """
        Return a dictionary with a copy of option names as keys and their
        values as values.
        
        ordered (boolean): if True, return an ordered dictionary; otherwise
        return a normal dictionary
        inherit_options (boolean): if True, options are searched also in the
        parent sections; note that this can be set as a default for the object,
        but this setting overwrites it only for this call
        """
        if inherit_options not in (True, False):
            inherit_options = self._INHERIT_OPTIONS
        
        if ordered:
            d = _collections.OrderedDict()
        else:
            d = {}
        
        if inherit_options:
            slist = self._get_ancestors()
        else:
            slist = [self, ]
        
        for s in slist:
            for o in s._options:
                d[o] = s._options[o][:]
                # There should be no need to check _IGNORE_CASE, in fact it has
                # already been done at importing time
        
        return(d)
    
    def get_sections(self):
        """
        Return a list with a copy of the names of the child sections.
        """
        d = []
        for s in self._subsections:
            d.append(s)
        return(d)
    
    def get_tree(self, ordered=True, path=False):
        """
        Return a compatible dictionary with options and subsections.
        
        ordered (boolean): if True, return an ordered dictionary; otherwise
        return a normal dictionary
        path (boolean): if True, return the current section as a subsection
        of the parent sections.
        """
        d = self._recurse_tree(ordered=ordered)
        
        if path:
            p = self._PARENT
            n = self._NAME
            while p:
                if ordered:
                    e = _collections.OrderedDict()
                    e[0] = _collections.OrderedDict()
                else:
                    e = {}
                    e[0] = {}
                e[0][n] = d
                d = e
                n = p._NAME
                p = p._PARENT
        
        return(d)
    
    def _recurse_tree(self, ordered=True):
        """
        Auxiliary recursor for tree().
        """
        d = self.get_options(ordered=ordered, inherit_options=False)
        
        if ordered:
            d[0] = _collections.OrderedDict()
        else:
            d[0] = {}
        
        subs = self._subsections
        for s in subs:
            d[0][s] = subs[s]._recurse_tree(ordered=ordered)
        
        return(d)
    
    def _export(self, targets, mode='upgrade', path=True):
        """
        Export the configuration to one or more files.
        
        targets: a sequence with the target file names
        mode (string): this sets if and how sections and options already
        existing in the file are overwritten; available choices are 'upgrade',
        'update', 'reset' and 'add' (see _export_dict() for more details)
        path (boolean): if True, section names are exported with their full
        path
        """
        if mode in ('upgrade', 'update', 'reset', 'add'):
            for f in targets:
                self._export_dict(f, mode=mode, path=path)
        else:
            raise ValueError('Unrecognized exporting mode: ' + mode)
    
    def export_upgrade(self, *targets, **kwargs):
        """
        Export sections and options to one or more files with upgrade mode.
        
        See _export_dict for a description of available modes and dictionary
        compatibility.
        
        targets: a sequence with the target file names
        path (boolean): if True, section names are exported with their full
        path
        """
        # Necessary for Python 2 compatibility
        # The Python 3 definition was:
        #def export_upgrade(self, *targets, path=True):
        if 'path' in kwargs:
            path = kwargs['path']
        else:
            path = True
        
        self._export(targets, mode='upgrade', path=path)
    
    def export_update(self, *targets, **kwargs):
        """
        Export sections and options to one or more files with update mode.
        
        See _export_dict for a description of available modes and dictionary
        compatibility.
        
        targets: a sequence with the target file names
        path (boolean): if True, section names are exported with their full
        path
        """
        # Necessary for Python 2 compatibility
        # The Python 3 definition was:
        #def export_upgrade(self, *targets, path=True):
        if 'path' in kwargs:
            path = kwargs['path']
        else:
            path = True
        
        self._export(targets, mode='update', path=path)
    
    def export_reset(self, *targets, **kwargs):
        """
        Export sections and options to one or more files with reset mode.
        
        See _export_dict for a description of available modes and dictionary
        compatibility.
        
        targets: a sequence with the target file names
        path (boolean): if True, section names are exported with their full
        path
        """
        # Necessary for Python 2 compatibility
        # The Python 3 definition was:
        #def export_upgrade(self, *targets, path=True):
        if 'path' in kwargs:
            path = kwargs['path']
        else:
            path = True
        
        self._export(targets, mode='reset', path=path)
    
    def export_add(self, *targets, **kwargs):
        """
        Export sections and options to one or more files with add mode.
        
        See _export_dict for a description of available modes and dictionary
        compatibility.
        
        targets: a sequence with the target file names
        path (boolean): if True, section names are exported with their full
        path
        """
        # Necessary for Python 2 compatibility
        # The Python 3 definition was:
        #def export_upgrade(self, *targets, path=True):
        if 'path' in kwargs:
            path = kwargs['path']
        else:
            path = True
        
        self._export(targets, mode='add', path=path)
    
    def _export_dict(self, cfile, mode='upgrade', path=True):
        """
        Export the sections tree to a file.
        
        efile (string): the target file name.
        mode (string): this sets if and how sections and options already
        existing in the file are overwritten; available choices are 'upgrade',
        'update', 'reset' and 'add':
        
        upgrade mode:
        if an option already exists, change its value; if it doesn't exist,
        create it and store its value:
        (A:d,D:e) upgrade (A:a,B:b,C:c) => (A:d,B:b,C:c,D:e)
        
        update mode:
        if an option already exists, change its value; if it doesn't exist,
        don't do anything:
        (A:d,D:e) update (A:a,B:b,C:c) => (A:d,B:b,C:c)
        
        reset mode:
        delete all options and subsections and recreate everything from the
        importing dictionary:
        (A:d,D:e) reset (A:a,B:b,C:c) => (A:d,D:e)
        
        add mode:
        if an option already exists, don't do anything; if it doesn't exist,
        create it and store its value:
        (A:d,D:e) add (A:a,B:b,C:c) => (A:a,B:b,C:c,D:e)
        
        path (boolean): if True, section names are exported with their full
        path, otherwise they are left
        """
        try:
            with open(cfile, 'r') as stream:
                lines = stream.readlines()
        except:
            lines = ()
        
        with open(cfile, 'w') as stream:
            tree = self.get_tree(path=path)
            # Don't just do tree.copy(), as that would just copy the root
            # level, and then make normal references for the other levels
            striptree = self.get_tree(path=path)
            
            tp = tree
            stp = striptree
            
            ancestry = [s._NAME for s in self._get_ancestors()][:-1]
            if self._IGNORE_CASE:
                ancestry = [a.lower() for a in ancestry]
            ancestry.reverse()
            
            if mode == 'reset' and self._NAME is None:
                reset = True
            else:
                reset = False
            
            for line in lines:
                # Note that the order the various types are evaluated matters!
                if _re.match(self._PARSE_IGNORE, line, self._RE_I) and \
                                                                     not reset:
                    stream.write(line)
                elif _re.match(self._PARSE_COMMENT, line, self._RE_I) and \
                                                                     not reset:
                    stream.write(line)
                else:
                    re_option = _re.match(self._PARSE_OPTION, line, self._RE_I)
                    if re_option:
                        stp = self._export_dict_option(mode, reset, stream, tp,
                                                       stp, line, re_option)
                    else:
                        re_section = _re.match(self._PARSE_SECTION, line,
                                               self._RE_I)
                        if re_section:
                            stp = self._export_dict_remaining_options(mode,
                                                                      reset,
                                                                      stream,
                                                                      stp)
                            tp, stp, reset = self._export_dict_update_pointers(
                                                         mode, tree, striptree,
                                                          ancestry, re_section)
                            self._export_dict_section(reset, stream, tp, line)
                        elif not reset:
                            # Invalid lines
                            stream.write(line)
            
            # Export the remaining options for the last section in the original
            # file
            stp = self._export_dict_remaining_options(mode, reset, stream, stp,
                                                      end=True)
            
            if mode != 'update':
                self._export_dict_recurse_remaining_sections(stream, striptree)
    
    def _export_dict_update_pointers(self, mode, tree, striptree, ancestry,
                                     re_section):
        """
        Auxiliary method for _export_dict().
        
        Update the tree pointers according to the currently-examined section.
        """
        subs = self._parse_subsections(re_section)
        
        # Reset pointers
        tp = tree
        stp = striptree
                    
        if self._IGNORE_CASE:
            for s in subs:
                # Loop tp instead of stp, so if there are more occurrences of
                # this section, all will be updated
                for ss in tp[0]:
                    if s.lower() == ss.lower():
                        tp = tp[0][ss]
                        stp = stp[0][ss]
                        break
                else:
                    # Section is not in object
                    tp = None
                    stp = None
                    break
            
            if mode == 'reset' and ancestry == [s.lower() for s in
                                                         subs[:len(ancestry)]]:
                reset = True
            else:
                reset = False
        else:
            for s in subs:
                # Loop tp instead of stp, so if there are more occurrences of
                # this section, all will be updated
                if s in tp[0]:
                    tp = tp[0][ss]
                    stp = stp[0][ss]
                else:
                    # Section is not in object
                    tp = None
                    stp = None
                    break
            
            if mode == 'reset' and ancestry == subs[:len(ancestry)]:
                reset = True
            else:
                reset = False
        
        return (tp, stp, reset)
                    
    def _export_dict_section(self, reset, stream, tp, line):
        """
        Auxiliary method for _export_dict().
        
        Write the section currently examined from the destination file.
        """
        if not reset or (reset and tp):
            stream.write(line)
                    
    def _export_dict_option(self, mode, reset, stream, tp, stp, line,
                            re_option):
        """
        Auxiliary method for _export_dict().
        
        Write the option currently examined from the destination file.
        """
        if tp:
            # Section is in object
            if self._IGNORE_CASE:
                for o in tp:
                    if o != 0 and re_option.group(1).lower() == o.lower():
                        if o in stp:
                            del stp[o]
                        
                        if mode != 'add' and re_option.group(2) != tp[o]:
                            stream.write(''.join((o, self._OPTION_SEP,
                                                  tp[o], '\n')))
                        else:
                            stream.write(line)
                        # There shouldn't be more occurrences of this
                        # option (though with different casing) in tree
                        break
                else:
                    if not reset:
                        # Section is in object, but option is not
                        stream.write(line)
            else:
                if re_option.group(1) in tp:
                    del stp[re_option.group(1)]
                    if mode != 'add' and tp[re_option.group(1)] != \
                                                        re_option.group(2):
                        stream.write(''.join((re_option.group(1),
                                              self._OPTION_SEP,
                                              tp[re_option.group(1)],
                                              '\n')))
                    else:
                        stream.write(line)
                elif not reset:
                    # Section is in object, but option is not
                    stream.write(line)
        elif not reset:
            # Section is not in object
            stream.write(line)
        
        return stp
    
    def _export_dict_remaining_options(self, mode, reset, stream, stp,
                                       end=False):
        """
        Auxiliary method for _export_dict().
        
        Write the options from the origin dictionary that were not found in the
        destination file.
        """
        if mode != 'update' and stp is not None:
            # Prevent writing '\n' if there aren't options, unless the section
            # is being reset (normally '\n' is written because it was already
            # there)
            # Note that the if statement must include also the for loop, since
            # it may delete stp[o]
            if len(stp) > 1 or reset:
                for o in stp:
                    if o != 0:
                        stream.write(''.join((o, self._OPTION_SEP, stp[o],
                                              '\n')))
                        del stp[o]
                if not end:
                    stream.write('\n')
        
        return stp
    
    def _export_dict_recurse_remaining_sections(self, stream, dict_, pathl=[]):
        """
        Auxiliary method for _export_dict().
        
        Write the sections and their options from the origin dictionary that
        were not found in the destination file.
        """
        for o in dict_:
            if o != 0:
                stream.write(''.join((o, self._OPTION_SEP, dict_[o], '\n')))
        
        for s in dict_[0]:
            pathl.append(s)
            if len(dict_[0][s]) > 1:
                stream.write('\n')
                stream.write(''.join((self._SECTION_MARKERS, '\n')).format(
                                                self._SECTION_SEP.join(pathl)))
            self._export_dict_recurse_remaining_sections(stream, dict_[0][s],
                                                         pathl)
        else:
            pathl[-1:] = []


class ConfigFile(Section):
    """
    A configuration file object.
    
    One or more text files or compatible dictionaries can be initially parsed
    with configfile.ConfigFile(file1, dict1, file2, ...).
    This will instantiate a ConfigFile object with sections, subsections,
    options and values.
    Even if you parse more files or dictionaries, this will instantiate a
    unified object.
    
    A default set of values can be set by assigning a dictionary as the first
    argument.
    
    By default, sections are allowed to contain both options or other sections
    (subsections): this behaviour can be disabled by instantiating ConfigFile
    with sub=False.
    """
    def __init__(self, *sources, **kwargs):
        """
        Constructor: instantiate a ConfigFile object.
        
        sources (string or dict): a sequence of all the files and dictionaries
        to be parsed
        mode (string): this sets if and how the next file or dictionary in the
        chain overwrites already imported sections and options; available
        choices are 'upgrade', 'update', 'reset' and 'add' (see _import_dict()
        for more details)
        subsections (boolean): if True (default) subsections are allowed
        ignore_case (boolean): if True, section and option names will be
        compared ignoring case differences; regular expressions will use re.I
        flag
        interpolation (boolean): if True, option values will be interpolated
        using values from other options through the special syntax
        ${section$:section$:option$}. Options will be interpolated only once at
        importing: all links among options will be lost after importing.
        """
        # The Python 3 definition was:
        #def __init__(self,
        #             *sources,
        #             mode='upgrade',
        #             subsections=True,
        #             inherit_options=True,
        #             ignore_case=True,
        #             interpolation=False):
        # But to keep compatibility with Python 2 it has been changed to the
        # current
        
        # Necessary for Python 2 compatibility
        if 'mode' in kwargs:
            mode = kwargs['mode']
        else:
            mode = 'upgrade'
            
        # Necessary for Python 2 compatibility
        if 'subsections' in kwargs:
            subsections = kwargs['subsections']
        else:
            subsections = True
        
        # Necessary for Python 2 compatibility
        if 'inherit_options' in kwargs:
            inherit_options = kwargs['inherit_options']
        else:
            inherit_options = True
        
        # Necessary for Python 2 compatibility
        if 'ignore_case' in kwargs:
            ignore_case = kwargs['ignore_case']
        else:
            ignore_case = True
        
        # Necessary for Python 2 compatibility
        if 'interpolation' in kwargs:
            interpolation = kwargs['interpolation']
        else:
            interpolation = False
        
        # Construct the root section
        Section.__init__(self, name=None, parent=None, subsections=subsections,
                      inherit_options=inherit_options, ignore_case=ignore_case)
        
        # Parse the files or dictionaries
        self._import(sources, mode=mode, interpolation=interpolation)


### EXCEPTIONS ###

class ConfigFileError(Exception):
    """
    The root exception, useful for catching generic errors from this module.
    """
    pass


class ParsingError(ConfigFileError):
    """
    An error, overcome at parse time, due to bad file formatting.
    """
    pass


class InvalidFileError(ConfigFileError):
    """
    An invalid or non-existent configuration file.
    """
    pass


class InvalidDictionaryError(ConfigFileError):
    """
    An invalid key found in an importing dictionary.
    """
    pass
