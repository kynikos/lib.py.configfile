# This file is part of ConfigFile - Parse and edit configuration files.
# Copyright (C) 2011-present Dario Giovannetti <dev@dariogiovannetti.net>
# Licensed under MIT
# https://github.com/kynikos/lib.py.configfile/blob/master/LICENSE


"""
This library provides the :py:class:`ConfigFile` class, whose goal is to
provide an interface for parsing, modifying and writing configuration files.

Main features:

* Support for subsections. Support for sectionless options (root options).
* Read from multiple sources (files, file-like objects, dictionaries or special
  compatible objects) and compose them in a single :py:class:`ConfigFile`
  object.
* When importing and exporting it is possible to choose what to do with
  options only existing in the source, only existing in the destination, or
  existing in both with different values.
* Import a configuration source into a particular subsection of an existing
  object. Export only a particular subsection of an existing object.
* Preserve the order of sections and options when exporting. Try the best to
  preserve any comments too.
* Access sections and options with the
  ``root('Section', 'Subsection')['option']`` syntax or the
  ``root('Section')('Subsection')['option']`` syntax.
* save references to subsections with e.g.
  ``subsection = section('Section', 'Subsection')``.
* Interpolation of option values between sections when importing.

Author: Dario Giovannetti <dev@dariogiovannetti.net>

License: MIT

GitHub: https://www.github.com/kynikos/lib.py.configfile

Issue tracker: https://www.github.com/kynikos/lib.py.configfile/issues

**Note:** as it is clear by reading this page, the documentation is still in a
poor state. If you manage to understand how this library works and want to help
documenting it, you are welcome to fork the GitHub repository and request to
pull your improvements. Everything is written in docstrings in the only
python module of the package.

Also, if you have any questions, do not hesitate to ask in the issue tracker,
or write the author an email!

Examples
========

Basic usage
-----------

Suppose you have these two files:

``/path/to/file``:

.. code-block:: cfg

    root_option = demo

    [Section1]
    test = ok
    retest = no
    test3 = yes

    [Section2.Section2A]
    foo = fooo

    [Section3]
    bar = yay

``/path/to/other_file``:

.. code-block:: cfg

    [Section2C]
    an_option = 2

Now run this script:

::

    from configfile import ConfigFile

    conf = ConfigFile("/path/to/file")

    conf("Section2").upgrade("path/to/other_file")

    option = conf("Section2", "Section2C")["an_option"]
    print(option, type(option))  # 2 <class 'str'>

    option = conf("Section2")("Section2C").get_int("an_option")
    print(option, type(option))  # 2 <class 'int'>

    conf.export_add("/path/to/file")

    conf["root_option"] = "value"

    conf("Section3").export_reset("/path/to/another_file")

You will end up with these files (``/path/to/other_file`` is left
untouched):

``/path/to/file``:

.. code-block:: cfg

    root_option = demo

    [Section1]
    test = ok
    retest = no
    test3 = yes

    [Section2.Section2A]
    foo = fooo

    [Section2.Section2C]
    an_option = 2

    [Section3]
    bar = yay

``/path/to/another_file``:

.. code-block:: cfg

    bar = yay

Interpolation
-------------

Suppose you have this file:

``/path/to/file``:

.. code-block:: cfg

    [Section1]
    option = foo ${$:Section2$:optionA$}

    [Section1.Section2]
    optionA = some value
    optionB = ${optionA$} test
    optionC = test ${$:optionA$}

    [Section3]
    option = ${Section1$:Section2$:optionA$} bar

Now run this script:

::

    from configfile import ConfigFile

    conf = ConfigFile("/path/to/file", interpolation=True)

    print(conf('Section1')['option'])  # foo some value
    print(conf('Section1', 'Section2')['optionA'])  # some value
    print(conf('Section1', 'Section2')['optionB'])  # some value test
    print(conf('Section1', 'Section2')['optionC'])  # test some value
    print(conf('Section3')['option'])  # some value bar

Module contents
===============
"""

import errno
import re as re_
import collections
import io


class Section(object):
    """
    The class for a section in the configuration file, including the root
    section. You should never need to instantiate this class directly, use
    :py:class:`ConfigFile` instead.
    """
    # TODO: Compile only once (bug #20)
    _PARSE_SECTION = r'^\s*\[(.+)\]\s*$'
    _PARSE_OPTION = r'^\s*([^\=]+?)\s*\=\s*(.*?)\s*$'
    _PARSE_COMMENT = r'^\s*[#;]{1}\s*(.*?)\s*$'
    _PARSE_IGNORE = r'^\s*$'

    _SECTION_SUB = r'^[a-zA-Z_]+(?:\.?[a-zA-Z0-9_]+)*$'
    _SECTION_PLAIN = r'^[a-zA-Z_]+[a-zA-Z0-9_]*$'

    _OPTION = r'^[a-zA-Z_]+[a-zA-Z0-9_]*$'
    _VALUE = r'^.*$'

    _SECTION_SEP = r'.'
    _OPTION_SEP = r' = '
    # "{}" will be replaced with the section name by str.format
    _SECTION_MARKERS = r'[{}]'
    _COMMENT_MARKER = r'# '

    _INTERPOLATION_SPECIAL = '$'
    _INTERPOLATION_SPECIAL_ESC = _INTERPOLATION_SPECIAL * 2
    _INTERPOLATION_START = _INTERPOLATION_SPECIAL + '{'
    _INTERPOLATION_SEP = _INTERPOLATION_SPECIAL + ':'
    _INTERPOLATION_END = _INTERPOLATION_SPECIAL + '}'
    _INTERPOLATION_SPLIT = (r'(' + r'|'.join(re_.escape(mark) for mark in (
                            _INTERPOLATION_SPECIAL_ESC, _INTERPOLATION_START,
                            _INTERPOLATION_SEP, _INTERPOLATION_END)) + r')')

    _GET_BOOLEAN_TRUE = ('true', '1', 'yes', 'on', 'enabled')
    _GET_BOOLEAN_FALSE = ('false', '0', 'no', 'off', 'disabled')
    _GET_BOOLEAN_DEFAULT = None

    _DICT_CLASS = collections.OrderedDict

    # Use lambda to create a new object every time
    _EMPTY_SECTION = lambda self: (self._DICT_CLASS(), self._DICT_CLASS())

    def __init__(self, name=None, parent=None, safe_calls=False,
                 inherit_options=False, subsections=True, ignore_case=True):
        """
        Constructor.

        :param str name: The name of the section.
        :param Section parent: A reference to the parent section object.
        :param bool safe_calls: If True, when calling a non-existent
            subsection, its closest existing ancestor is returned.
        :param bool inherit_options: Whether the section will inherit the
            options from its ancestors.
        :param bool subsections: If True, subsections are enabled; otherwise
            they are disabled.
        :param bool ignore_case: If True, section and option names will be
            compared ignoring case differences; regular expressions will use
            ``re.I`` flag.
        """
        self._NAME = name
        self._PARENT = parent
        # TODO: Move constant settings to a Settings class (bug #19)
        self._SAFE_CALLS = safe_calls
        self._INHERIT_OPTIONS = inherit_options
        self._ENABLE_SUBSECTIONS = subsections
        self._IGNORE_CASE = ignore_case
        self._RE_I = re_.I if self._IGNORE_CASE else 0

        self._SECTION = self._SECTION_SUB if self._ENABLE_SUBSECTIONS else \
                        self._SECTION_PLAIN

        self._options = self._DICT_CLASS()
        self._subsections = self._DICT_CLASS()

    ### DATA MODEL ###

    def __call__(self, *path, **kwargs):
        """
        Enables calling directly the object with a string or sequence of
        strings, returning the corresponding subsection object, if existent.

        :param path: A sequence of strings, representing a relative path of
            section names to the target descendant subsection, whose name is
            the last item.
        :type path: str
        :param bool safe: If True, when calling a non-existent subsection, its
            closest existing ancestor is returned.
        """
        # The Python 3 definition was:
        #def __call__(self, *path, safe=None):
        # But to keep compatibility with Python 2 it has been changed to the
        # current
        safe = kwargs.get('safe')

        section = self

        for sname in path:
            try:
                lsname = sname.lower()
            except AttributeError:
                raise TypeError('Section name must be a string: {}'.format(
                                                                        sname))

            if self._IGNORE_CASE:
                for subname in section._subsections:
                    if lsname == subname.lower():
                        section = section._subsections[subname]
                        break
                else:
                    self._finalize_call(safe, sname)
                    break
            else:
                try:
                    section = section._subsections[sname]
                except KeyError:
                    self._finalize_call(safe, sname)
                    break

        return section

    def _finalize_call(self, safe, sname):
        """
        Auxiliary method for :py:meth:`__call__`.

        Process a not-found section name.
        """
        if safe not in (True, False):
            if self._SAFE_CALLS:
                return
        elif safe:
            return
        raise KeyError('Section not found: {}'.format(sname))

    def __getitem__(self, opt):
        """
        Returns the value for the option specified.

        :param str opt: The name of the option whose value must be returned.
        """
        item = self.get(opt, fallback=None,
                                         inherit_options=self._INHERIT_OPTIONS)
        # self.get returns None as a fallback value if opt is not found:
        # however, for compatibility with usual dictionary operations,
        # __getitem__ should better raise KeyError in this case
        if item is None:
            raise KeyError('Option not found: {}'.format(opt))
        else:
            return item

    def __setitem__(self, opt, val):
        """
        Stores the provided value in the specified option.

        :param str opt: The name of the option.
        :param str val: The new value for the option.
        """
        if isinstance(opt, str):
            if isinstance(val, str):
                if self._IGNORE_CASE:
                    for o in self._options:
                        if opt.lower() == o.lower():
                            self._options[o] = val
                            break
                    else:
                        self._options[opt] = val
                else:
                    self._options[opt] = val
            else:
                raise TypeError('Value must be a string: {}'.format(val))
        else:
            raise TypeError('Option name must be a string: {}'.format(opt))

    def __delitem__(self, opt):
        """
        Deletes the specified option.

        :param str opt: The name of the option that must be deleted.
        """
        try:
            lopt = opt.lower()
        except AttributeError:
            raise TypeError('Option name must be a string: {}'.format(opt))
        else:
            if self._IGNORE_CASE:
                for o in self._options:
                    if opt.lower() == o.lower():
                        del self._options[o]
                        break
                else:
                    raise KeyError('Option not found: {}'.format(opt))
            else:
                try:
                    del self._options[opt]
                except KeyError:
                    raise KeyError('Option not found: {}'.format(opt))

    def __iter__(self):
        """
        Lets iterate over the options of the section (for example with a for
        loop).
        """
        return iter(self._options)

    def __contains__(self, item):
        """
        If item is a :py:class:`Section` object, this method returns True if
        item (the object, not its name) is a subsection of self; otherwise this
        returns True if item is the name of an option in self.

        :param item: A :py:class:`Section` object or the name of an option.
        :type item: Section or str
        """
        if isinstance(item, Section):
            return item in self._subsections.values()
        elif self._IGNORE_CASE:
            for o in self._options:
                if item.lower() == o.lower():
                    return True
            else:
                return False
        else:
            return item in self._options

    ### IMPORTING DATA ###

    def set(self, opt, val):
        """
        This is an alias for :py:meth:`__setitem__`.
        """
        self[opt] = val

    def make_subsection(self, name):
        """
        Create an empty subsection under the current section if it does not
        exist.

        :param str name: The name of the new subsection.
        """
        # TODO: Use this method, where possible, when creating new sections in
        #       the other methods
        sub = self._EMPTY_SECTION()
        sub[1][name] = self._EMPTY_SECTION()
        self._import_object(sub, overwrite=False)

    def delete(self):
        """
        Delete the current section.
        """
        del self._PARENT._subsections[self._NAME]

    def upgrade(self, *sources, **kwargs):
        """
        Import sections and options from a file, file-like object, dictionary
        or special object with upgrade mode.

        If an option already exists, change its value; if it does not exist,
        create it and store its value. For example:

        *{A:a,B:b,C:c} upgrade {A:d,D:e} => {A:d,B:b,C:c,D:e}*

        See :py:meth:`_import_object` for object compatibility.

        :param sources: A sequence of files, file-like objects, dictionaries
            and/or special objects.
        :param bool interpolation: Enable/disable value interpolation.
        """
        # Necessary for Python 2 compatibility
        # The Python 3 definition was:
        #def upgrade(self, *sources, interpolation=False):
        interpolation = kwargs.get('interpolation', False)

        self._import(sources, interpolation=interpolation)

    def update(self, *sources, **kwargs):
        """
        Import sections and options from a file, file-like object, dictionary
        or special object with update mode.

        If an option already exists, change its value; if it does not exist,
        do not do anything. For example:

        *{A:a,B:b,C:c} update {A:d,D:e} => {A:d,B:b,C:c}*

        See :py:meth:`_import_object` for object compatibility.

        :param sources: A sequence of files, file-like objects, dictionaries
            and/or special objects.
        :param bool interpolation: Enable/disable value interpolation.
        """
        # Necessary for Python 2 compatibility
        # The Python 3 definition was:
        #def upgrade(self, *sources, interpolation=False):
        interpolation = kwargs.get('interpolation', False)

        self._import(sources, add=False, interpolation=interpolation)

    def reset(self, *sources, **kwargs):
        """
        Import sections and options from a file, file-like object, dictionary
        or special object with reset mode.

        Delete all options and subsections and recreate everything from the
        importing object. For example:

        *{A:a,B:b,C:c} reset {A:d,D:e} => {A:d,D:e}*

        See :py:meth:`_import_object` for object compatibility.

        :param sources: A sequence of files, file-like objects, dictionaries
            and/or special objects.
        :param bool interpolation: Enable/disable value interpolation.
        """
        # Necessary for Python 2 compatibility
        # The Python 3 definition was:
        #def upgrade(self, *sources, interpolation=False):
        interpolation = kwargs.get('interpolation', False)

        self._import(sources, reset=True, interpolation=interpolation)

    def add(self, *sources, **kwargs):
        """
        Import sections and options from a file, file-like object, dictionary
        or special object with add mode.

        If an option already exists, do not do anything; if it does not exist,
        create it and store its value. For example:

        *{A:a,B:b,C:c} add {A:d,D:e} => {A:a,B:b,C:c,D:e}*

        See :py:meth:`_import_object` for object compatibility.

        :param sources: A sequence of files, file-like objects, dictionaries
            and/or special objects.
        :param bool interpolation: Enable/disable value interpolation.
        """
        # Necessary for Python 2 compatibility
        # The Python 3 definition was:
        #def upgrade(self, *sources, interpolation=False):
        interpolation = kwargs.get('interpolation', False)

        self._import(sources, overwrite=False, interpolation=interpolation)

    def _import(self, sources, overwrite=True, add=True, reset=False,
                                                        interpolation=False):
        """
        Parse some files, file-like objects, dictionaries or special objects
        and add their configuration to the existing one.

        Distinction between the various source types is done automatically.

        :param sources: A sequence of all the file names, file-like objects,
            dictionaries or special objects to be parsed; a value of None will
            be ignored (useful for creating empty objects that will be
            populated programmatically).
        :param bool overwrite: This sets whether the next source in the chain
            overwrites already imported sections and options; see
            :py:meth:`_import_object` for more details.
        :param bool add: This sets whether the next source in the chain adds
            non-pre-existing sections and options; see _import_object for more
            details.
        :param bool reset: This sets whether the next source in the chain
            removes all the data added by the previous sources.
        :param bool interpolation: If True, option values will be interpolated
            using values from other options through the special syntax
            ``${section$:section$:option$}``. Options will be interpolated only
            once at importing: all links among options will be lost after
            importing.
        """
        for source in sources:
            if source is None:
                continue
            elif isinstance(source, str):
                obj = self._parse_file(self._open_file(source))
            elif isinstance(source, io.IOBase):
                obj = self._parse_file(source)
            elif isinstance(source, dict):
                obj = (source, {})
            else:
                obj = source

            self._import_object(obj, overwrite=overwrite, add=add, reset=reset)

            if interpolation:
                self._interpolate()

    def _open_file(self, cfile):
        """
        Open config file for reading.

        :param str cfile: The name of the file to be parsed.
        """
        try:
            return open(cfile, 'r')
        except EnvironmentError as e:
            if e.errno == errno.ENOENT:
                raise NonExistentFileError('Cannot find {} ({})'.format(
                                                    e.filename, e.strerror))
            else:
                raise InvalidFileError('Cannot import configuration from {} '
                                        '({})'.format(e.filename, e.strerror))

    def _parse_file(self, stream):
        """
        Parse a text file and translate it into a compatible object, thus
        making it possible to import it.

        :param stream: a file-like object to be read from.
        """
        with stream:
            cdict = self._EMPTY_SECTION()
            lastsect = cdict

            for lno, line in enumerate(stream):
                # Note that the order the various types are evaluated
                # matters!
                # TODO: Really? What about sorting the tests according
                #       to their likelihood to pass?

                if re_.match(self._PARSE_IGNORE, line, self._RE_I):
                    continue

                if re_.match(self._PARSE_COMMENT, line, self._RE_I):
                    continue

                re_option = re_.match(self._PARSE_OPTION, line, self._RE_I)

                if re_option:
                    lastsect[0][re_option.group(1)] = re_option.group(2)
                    continue

                re_section = re_.match(self._PARSE_SECTION, line,
                                                                self._RE_I)
                if re_section:
                    subs = self._parse_subsections(re_section)
                    d = cdict

                    for s in subs:
                        if s not in d[1]:
                            d[1][s] = self._EMPTY_SECTION()

                        d = d[1][s]

                    lastsect = d
                    continue

                raise ParsingError('Invalid line in {}: {} (line {})'
                                        ''.format(cfile, line, lno + 1))

        return cdict

    def _parse_subsections(self, re):
        """
        Parse the sections hierarchy in a section line of a text file and
        return them in a list.

        :param re: regular expression object.
        """
        if self._ENABLE_SUBSECTIONS:
            return re.group(1).split(self._SECTION_SEP)
        else:
            return (re.group(1), )

    def _import_object(self, cobj, overwrite=True, add=True, reset=False):
        """
        Import sections and options from a compatible object.

        :param cobj: A special object composed of dictionaries (or compatible
            mapping object) and tuples to be imported; a section is represented
            by a 2-tuple: its first value is a mapping object that associates
            the names of options to their values; its second value is a mapping
            object that associates the names of subsections to their 2-tuples.
            For example::

                cobj = (
                    {
                        'option1': 'value',
                        'option2': 'value'
                    },
                    {
                        'sectionA': (
                            {
                                'optionA1': 'value',
                                'optionA2': 'value',
                            },
                            {
                                'sectionC': (
                                    {
                                        'optionC1': 'value',
                                        'optionC2': 'value',
                                    },
                                    {},
                                ),
                            },
                        ),
                        'sectionB': (
                            {
                                'optionB1': 'value',
                                'optionB2': 'value'
                            },
                            {},
                        ),
                    },
                )

        :param bool overwrite: Whether imported data will overwrite
            pre-existing data.
        :param bool add: Whether non-pre-existing data will be imported.
        :param bool reset: Whether pre-existing data will be cleared.
        """
        # TODO: Change "reset" mode to "remove" (complementing "overwrite" and
        #       "add") (bug #25)
        if reset:
            self._options = self._DICT_CLASS()
            self._subsections = self._DICT_CLASS()

        for o in cobj[0]:
            if isinstance(o, str) and isinstance(cobj[0][o], str) and \
                                re_.match(self._OPTION, o, self._RE_I) and \
                                re_.match(self._VALUE, cobj[0][o], self._RE_I):
                self._import_object_option(overwrite, add, reset, o,
                                                                    cobj[0][o])
            else:
                raise InvalidObjectError('Invalid option or value: {}: {}'
                                                    ''.format(o, cobj[0][o]))

        for s in cobj[1]:
            if isinstance(s, str) and re_.match(self._SECTION, s, self._RE_I):
                self._import_object_subsection(overwrite, add, reset, s,
                                                                    cobj[1][s])
            else:
                raise InvalidObjectError('Invalid section name: {}'.format(s))

    def _import_object_option(self, overwrite, add, reset, opt, val):
        """
        Auxiliary method for :py:meth:`_import_object`.

        Import the currently-examined option.
        """
        if reset:
            self._options[opt] = val
            return True

        if self._IGNORE_CASE:
            for o in self._options:
                if opt.lower() == o.lower():
                    # Don't even think of merging these two tests
                    if overwrite:
                        self._options[o] = val
                        return True

                    break

            else:
                # Going through the loop above makes sure the option is not yet
                #  in the section
                if add:
                    self._options[opt] = val
                    return True

        elif opt in self._options:
            # Don't even think of merging these two tests
            if overwrite:
                self._options[opt] = val
                return True

        elif add:
            self._options[opt] = val
            return True

        return False

    def _import_object_subsection(self, overwrite, add, reset, sec, secd):
        """
        Auxiliary method for :py:meth:`_import_object`.

        Import the currently-examined subsection.
        """
        if reset:
            self._import_object_subsection_create(overwrite, add, sec, secd)
            return True

        if self._IGNORE_CASE:
            for ss in self._subsections:
                if sec.lower() == ss.lower():
                    # Don't test overwrite here
                    self._subsections[ss]._import_object(secd,
                                                overwrite=overwrite, add=add)
                    return True

            else:
                # Going through the loop above makes sure the section is not
                #  yet a subsection of the visited section
                if add:
                    self._import_object_subsection_create(overwrite, add, sec,
                                                                        secd)
                    return True

        elif sec in self._subsections:
            # Don't test overwrite here
            self._subsections[sec]._import_object(secd, overwrite=overwrite,
                                                                    add=add)
            return True

        elif add:
            self._import_object_subsection_create(overwrite, add, sec, secd)
            return True

        return False

    def _import_object_subsection_create(self, overwrite, add, sec, secd):
        """
        Auxiliary method for :py:meth:`_import_object_subsection`.

        Import the currently-examined subsection.
        """
        subsection = Section(name=sec, parent=self,
                             safe_calls=self._SAFE_CALLS,
                             inherit_options=self._INHERIT_OPTIONS,
                             subsections=self._ENABLE_SUBSECTIONS,
                             ignore_case=self._IGNORE_CASE)
        subsection._import_object(secd, overwrite=overwrite, add=add)
        self._subsections[sec] = subsection

    def _interpolate(self):
        """
        Interpolate values among different options.

        The ``$`` sign is a special character: a ``$`` not followed by ``$``,
        ``{``, ``:`` or ``}`` will be left ``$``; ``$$`` will be translated as
        ``$`` both inside or outside an interpolation path; ``${`` will be
        considered as the beginning of an interpolation path, unless it is
        found inside another interpolation path, and in the latter case it will
        be left ``${``; ``$:`` will be considered as a separator between
        sections of an interpolation path, unless it is found outside of an
        interpolation path, and in the latter case it will be left
        ``$:``; ``$}`` will be considered as the end of an interpolation path,
        unless it is found outside of an interpolation path, and in the latter
        case it will be left ``$}``.

        Normally all paths will be resolved based on the root section of the
        file; anyway, if the interpolation path has only one item, it will be
        resolved as an option relative to the current section; otherwise, if
        the path starts with ``$:``, the first item will be considered as a
        section (or an option, if last in the list) relative to the current
        section.
        """
        try:
            root = self._get_ancestors()[-1]
        except IndexError:
            root = self

        for optname in self._options:
            split = re_.split(self._INTERPOLATION_SPLIT,
                              self._options[optname])
            value = ''
            resolve = None

            for chunk in split:
                if resolve is None:
                    if chunk == self._INTERPOLATION_SPECIAL_ESC:
                        value += self._INTERPOLATION_SPECIAL
                    elif chunk == self._INTERPOLATION_START:
                        resolve = ['']
                    else:
                        value += chunk
                else:
                    if chunk == self._INTERPOLATION_SPECIAL_ESC:
                        resolve[-1] += self._INTERPOLATION_SPECIAL
                    elif chunk == self._INTERPOLATION_SEP:
                        resolve.append('')
                    elif chunk == self._INTERPOLATION_END:
                        intoptname = resolve.pop()

                        if len(resolve) == 0:
                            # TODO: It's currently not possible to write a
                            #       reference to a root option?!?
                            intsection = self
                        else:
                            if resolve[0] == '':
                                intsection = self
                                resolve.pop(0)
                            else:
                                intsection = root
                            for s in resolve:
                                intsection = intsection._subsections[s]

                        # Use get(intoptname) instead of _options[intoptname]
                        # so that options are properly inherited if the object
                        # is configured to do so
                        value += intsection.get(intoptname)
                        resolve = None
                    else:
                        resolve[-1] += chunk

            if resolve is not None:
                # The last interpolation wasn't closed, so interpret it as a
                # normal string
                value += self._INTERPOLATION_START + \
                         self._INTERPOLATION_SEP.join(resolve)

            self._options[optname] = value

        for secname in self._subsections:
            self._subsections[secname]._interpolate()

    ### EXPORTING DATA ###

    def get(self, opt, fallback=None, inherit_options=None):
        """
        Returns the value for the option specified.

        :param str opt: The name of the option whose value must be returned.
        :param fallback: If set to a string, and the option is not found, this
            method returns that string; if set to None (default) it returns
            KeyError.
        :type fallback: str or None
        :param bool inherit_options: If True, if the option is not found in the
            current section, it is searched in the parent sections; note that
            this can be set as a default for the object, but this setting
            overwrites it only for this call.
        """
        if inherit_options not in (True, False):
            inherit_options = self._INHERIT_OPTIONS

        if isinstance(opt, str):
            slist = [self, ]

            if inherit_options:
                slist.extend(self._get_ancestors())

            for s in slist:
                for o in s._options:
                    if (self._IGNORE_CASE and opt.lower() == o.lower()) or \
                                          (not self._IGNORE_CASE and opt == o):
                        return s._options[o]

            else:
                # Note that if fallback is not specified, this returns None
                # which is not a string as expected
                return fallback

        else:
            raise TypeError('Option name must be a string: {}'.format(opt))

    def get_str(self, opt, fallback=None, inherit_options=None):
        """
        This is an alias for :py:meth:`get`.

        This will always return a string.

        :param str opt: The name of the option whose value must be returned.
        :param fallback: If set to a string, and the option is not found, this
            method returns that string; if set to None (default) it returns
            KeyError.
        :type fallback: str or None
        :param bool inherit_options: If True, if the option is not found in the
            current section, it is searched in the parent sections; note that
            this can be set as a default for the object, but this setting
            overwrites it only for this call.
        """
        if inherit_options not in (True, False):
            inherit_options = self._INHERIT_OPTIONS

        return self.get(opt, fallback=fallback,
                                              inherit_options=inherit_options)

    def get_int(self, opt, fallback=None, inherit_options=None):
        """
        This method tries to return an integer from the value of an option.

        :param str opt: The name of the option whose value must be returned.
        :param fallback: If set to a string, and the option is not found, this
            method returns that string; if set to None (default) it returns
            KeyError.
        :type fallback: str or None
        :param bool inherit_options: If True, if the option is not found in the
            current section, it is searched in the parent sections; note that
            this can be set as a default for the object, but this setting
            overwrites it only for this call.
        """
        if inherit_options not in (True, False):
            inherit_options = self._INHERIT_OPTIONS

        return int(self.get(opt, fallback=fallback,
                                             inherit_options=inherit_options))

    def get_float(self, opt, fallback=None, inherit_options=None):
        """
        This method tries to return a float from the value of an option.

        :param str opt: The name of the option whose value must be returned.
        :param fallback: If set to a string, and the option is not found, this
            method returns that string; if set to None (default) it returns
            KeyError.
        :type fallback: str or None
        :param bool inherit_options: If True, if the option is not found in the
            current section, it is searched in the parent sections; note that
            this can be set as a default for the object, but this setting
            overwrites it only for this call.
        """
        if inherit_options not in (True, False):
            inherit_options = self._INHERIT_OPTIONS

        return float(self.get(opt, fallback=fallback,
                                             inherit_options=inherit_options))

    def get_bool(self, opt, true=(), false=(), default=None, fallback=None,
                                                         inherit_options=None):
        """
        This method tries to return a boolean status (True or False) from the
        value of an option.

        :param str opt: The name of the option whose value must be returned.
        :param tuple true: A tuple with the strings to be recognized as True.
        :param tuple false: A tuple with the strings to be recognized as False.
        :param default: If the value is neither in true nor in false tuples,
            return this boolean status; if set to None, it raises a ValueError
            exception.
        :param fallback: If set to None (default), and the option is not found,
            it raises KeyError; otherwise this value is evaluated with the true
            and false tuples, or the default value.
        :param bool inherit_options: If True, if the option is not found in the
            current section, it is searched in the parent sections; note that
            this can be set as a default for the object, but this setting
            overwrites it only for this call.

        Note that the characters in the strings are compared in lowercase, so
        there is no need to specify all casing variations of a string.
        """
        # TODO: Use default values in definition with Settings class (bug #19)
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
            return True
        elif v in false:
            return False
        elif default in (True, False):
            return default
        else:
            raise ValueError('Unrecognized boolean status: {}'.format(
                                                                    self[opt]))

    def _get_ancestors(self):
        """
        Return a list with the ancestors of the current section, but not the
        current section itself.
        """
        slist = []
        p = self._PARENT

        while p:
            slist.append(p)
            p = p._PARENT

        return slist

    def _get_descendants(self):
        """
        Return a list with the descendants of the current section, but not the
        current section itself.
        """
        # Don't do `slist = self._subsections.values()` because the descendants
        #  for each subsection must be appended after the proper subsection,
        #  not at the end of the list
        slist = []

        for section in self._subsections.values():
            slist.append(section)
            slist.extend(section._get_descendants())

        return slist

    def get_options(self, ordered=True, inherit_options=None):
        """
        Return a dictionary with a copy of option names as keys and their
        values as values.

        :param bool ordered: If True, return an ordered dictionary; otherwise
            return a normal dictionary.
        :param bool inherit_options: If True, options are searched also in the
            parent sections; note that this can be set as a default for the
            object, but this setting overwrites it only for this call.
        """
        if inherit_options not in (True, False):
            inherit_options = self._INHERIT_OPTIONS

        if ordered:
            d = self._DICT_CLASS()
        else:
            d = {}

        slist = [self, ]

        if inherit_options:
            slist.extend(self._get_ancestors())

        for s in slist:
            for o in s._options:
                d.setdefault(o, s._options[o][:])
                # There should be no need to check _IGNORE_CASE, in fact it has
                # already been done at importing time

        return d

    def get_sections(self):
        """
        Return a view of the names of the child sections.
        """
        return self._subsections.keys()

    def get_tree(self, ordered=True, path=False):
        """
        Return a compatible object with options and subsections.

        :param bool ordered: If True, the object uses ordered dictionaries;
            otherwise it uses normal dictionaries.
        :param bool path: If True, return the current section as a subsection
            of the parent sections.
        """
        d = self._recurse_tree(ordered=ordered)

        if path:
            p = self._PARENT
            n = self._NAME

            while p:
                if ordered:
                    e = self._EMPTY_SECTION()
                else:
                    e = ({}, {})

                e[1][n] = d
                d = e
                n = p._NAME
                p = p._PARENT

        return d

    def _recurse_tree(self, ordered=True):
        """
        Auxiliary recursor for :py:meth:`get_tree`.
        """
        options = self.get_options(ordered=ordered, inherit_options=False)

        if ordered:
            d = (options, self._DICT_CLASS())
        else:
            d = (options, {})

        for s in self._subsections:
            d[1][s] = self._subsections[s]._recurse_tree(ordered=ordered)

        return d

    def _export(self, targets, overwrite=True, add=True, reset=False,
                                                                    path=True):
        """
        Export the configuration to one or more files.

        :param targets: A sequence with the target file names.
        :param bool overwrite: This sets whether sections and options in the
            file are overwritten; see _import_object for more details.
        :param bool add: This sets whether non-pre-existing sections and option
            are added; see _import_object for more details.
        :param  bool path: If True, section names are exported with their full
            path.
        """
        # TODO: Change "reset" mode to "remove" (complementing "overwrite" and
        #       "add") (bug #25)
        for f in targets:
            self._export_file(f, overwrite=overwrite, add=add, reset=reset,
                                                                    path=path)

    def export_upgrade(self, *targets, **kwargs):
        """
        Export sections and options to one or more files with upgrade mode.

        If an option already exists, change its value; if it does not exist,
        create it and store its value. For example:

        *{A:d,D:e} upgrade {A:a,B:b,C:c} => {A:d,B:b,C:c,D:e}*

        See :py:meth:`_export_file` for object compatibility.

        :param targets: A sequence with the target file names.
        :param bool path: If True, section names are exported with their full
            path.
        """
        # Necessary for Python 2 compatibility
        # The Python 3 definition was:
        #def export_upgrade(self, *targets, path=True):
        path = kwargs.get('path', True)

        self._export(targets, path=path)

    def export_update(self, *targets, **kwargs):
        """
        Export sections and options to one or more files with update mode.

        If an option already exists, change its value; if it does not exist,
        do not do anything. For example:

        *{A:d,D:e} update {A:a,B:b,C:c} => {A:d,B:b,C:c}*

        See :py:meth:`_export_file` for object compatibility.

        :param targets: A sequence with the target file names.
        :param bool path: If True, section names are exported with their full
            path.
        """
        # Necessary for Python 2 compatibility
        # The Python 3 definition was:
        #def export_upgrade(self, *targets, path=True):
        path = kwargs.get('path', True)

        self._export(targets, add=False, path=path)

    def export_reset(self, *targets, **kwargs):
        """
        Export sections and options to one or more files with reset mode.

        Delete all options and subsections and recreate everything from the
        importing object. For example:

        *{A:d,D:e} reset {A:a,B:b,C:c} => {A:d,D:e}*

        See :py:meth:`_export_file` for object compatibility.

        :param targets: A sequence with the target file names.
        :param bool path: If True, section names are exported with their full
            path.
        """
        # Necessary for Python 2 compatibility
        # The Python 3 definition was:
        #def export_upgrade(self, *targets, path=True):
        path = kwargs.get('path', True)

        self._export(targets, reset=True, path=path)

    def export_add(self, *targets, **kwargs):
        """
        Export sections and options to one or more files with add mode.

        If an option already exists, do not do anything; if it does not exist,
        create it and store its value. For example:

        *{A:d,D:e} add {A:a,B:b,C:c} => {A:a,B:b,C:c,D:e}*

        See :py:meth:`_export_file` for object compatibility.

        :param targets: A sequence with the target file names.
        :param bool path: If True, section names are exported with their full
            path.
        """
        # Necessary for Python 2 compatibility
        # The Python 3 definition was:
        #def export_upgrade(self, *targets, path=True):
        path = kwargs.get('path', True)

        self._export(targets, overwrite=False, path=path)

    def _export_file(self, cfile, overwrite=True, add=True, reset=False,
                                                                    path=True):
        """
        Export the sections tree to a file.

        :param str efile: The target file name.
        :param bool overwrite: Whether sections and options already existing in
            the file are overwritten.
        :param bool add: Whether non-pre-existing data will be exported.
        :param bool path: If True, section names are exported with their full
            path.
        """
        try:
            with open(cfile, 'r') as stream:
                lines = stream.readlines()
        except IOError:
            lines = []
        else:
            # Exclude leading blank lines
            for lineN, line in enumerate(lines):
                if not re_.match(self._PARSE_IGNORE, line, self._RE_I):
                    lines = lines[lineN:]
                    break
            else:
                lines = []

        with open(cfile, 'w') as stream:
            BASE_SECTION = self

            try:
                ROOT_SECTION = self._get_ancestors()[-1]
            except IndexError:
                ROOT_SECTION = self
                readonly_section = False
                remaining_descendants = []
            else:
                if path:
                    readonly_section = True
                    remaining_descendants = [BASE_SECTION, ]
                else:
                    # The options without a section (i.e. at the top of the
                    #  file) must be considered part of the current section if
                    #  path is False
                    readonly_section = False
                    remaining_descendants = []

            remaining_options = BASE_SECTION.get_options(inherit_options=False)
            remaining_descendants.extend(BASE_SECTION._get_descendants())
            other_lines = []

            for line in lines:
                re_option = re_.match(self._PARSE_OPTION, line, self._RE_I)

                if re_option:
                    # This also changes other_lines in place
                    self._export_other_lines(stream, other_lines,
                                                    readonly_section, reset)

                    self._export_file_existing_option(stream, line, re_option,
                                        readonly_section, remaining_options,
                                        overwrite, reset)
                    continue

                re_section = re_.match(self._PARSE_SECTION, line, self._RE_I)

                if re_section:
                    if add:
                        self._export_file_remaining_options(stream,
                                        readonly_section, remaining_options)

                    # This also changes other_lines in place
                    self._export_other_lines_before_existing_section(stream,
                                        other_lines, readonly_section, reset)

                    # This also changes remaining_descendants in place
                    (readonly_section, remaining_options) = \
                                            self._export_file_existing_section(
                                            stream, line, re_section,
                                            ROOT_SECTION, BASE_SECTION,
                                            remaining_descendants, path)
                    continue

                # Comments, ignored/invalid lines
                other_lines.append(line)

            if add:
                self._export_file_remaining_options(stream, readonly_section,
                                                            remaining_options)

            # Don't use _export_other_lines_before_existing_section here
            #  because any pre-existing unrecognized lines must be restored in
            #  any case, and since they're at the end of the original file,
            #  they weren't meant to separate any further sections, so let
            #  _export_file_remaining_sections handle the addition of a blank
            #  line
            # This also changes other_lines in place
            self._export_other_lines(stream, other_lines, readonly_section,
                                                                        reset)

            if add:
                self._export_file_remaining_sections(stream, BASE_SECTION,
                                                remaining_descendants, path)

    def _export_file_existing_option(self, stream, line, re_option,
                        readonly_section, remaining_options, overwrite, reset):
        """
        Auxiliary method for :py:meth:`_export_file`.

        Write the option currently examined from the destination file.
        """
        if readonly_section:
            stream.write(line)
            return True

        if self._IGNORE_CASE:
            for option in remaining_options:
                fkey = re_option.group(1)
                fvalue = re_option.group(2)

                if fkey.lower() == option.lower():
                    if overwrite and fvalue != remaining_options[option]:
                        stream.write(''.join((fkey, self._OPTION_SEP,
                                            remaining_options[option], '\n')))
                    else:
                        stream.write(line)

                    del remaining_options[option]

                    # There shouldn't be more occurrences of this option (even
                    #  with different casing)
                    return True

        else:
            fkey = re_option.group(1)
            fvalue = re_option.group(2)

            if fkey in remaining_options:
                if overwrite and remaining_options[fkey] != fvalue:
                    stream.write(''.join((fkey, self._OPTION_SEP,
                                            remaining_options[fkey], '\n')))

                else:
                    stream.write(line)

                del remaining_options[fkey]
                return True

        if not reset:
            stream.write(line)
            return True

        return False

    def _export_file_remaining_options(self, stream, readonly_section,
                                                            remaining_options):
        """
        Auxiliary method for :py:meth:`_export_file`.

        Write the options from the origin object that were not found in the
        destination file.
        """
        if not readonly_section:
            for option in remaining_options:
                stream.write(''.join((option, self._OPTION_SEP,
                                            remaining_options[option], '\n')))

    def _export_file_existing_section(self, stream, line, re_section,
                    ROOT_SECTION, BASE_SECTION, remaining_descendants, path):
        """
        Auxiliary method for :py:meth:`_export_file`.

        Write the section currently examined from the destination file.
        """
        if self._ENABLE_SUBSECTIONS:
            names = re_section.group(1).split(self._SECTION_SEP)
        else:
            names = (re_section.group(1), )

        current_section = ROOT_SECTION if path else BASE_SECTION

        for name in names:
            try:
                current_section = current_section(name)
            except KeyError:
                # The currently parsed section is not in the configuration
                #  object
                readonly_section = True
                remaining_options = self._DICT_CLASS()
                break
        else:
            alist = [current_section, ]
            alist.extend(current_section._get_ancestors())

            if BASE_SECTION in alist:
                readonly_section = False
                remaining_options = current_section.get_options(
                                                        inherit_options=False)
                remaining_descendants.remove(current_section)
            else:
                readonly_section = True
                remaining_options = self._DICT_CLASS()

        # TODO: If reset (which for all the other modes by default is "deep",
        #       i.e. it must affect the subsections too) this section and all
        #       the other "old" subsections must be removed from the file
        #       (bug #22)
        stream.write(line)

        return (readonly_section, remaining_options)

    def _export_file_remaining_sections(self, stream, BASE_SECTION,
                                                remaining_descendants, path):
        """
        Auxiliary method for :py:meth:`_export_file`.

        Write the sections and their options from the origin object that
        were not found in the destination file.
        """
        # Do not add an empty line if at the start of the file
        BR = "\n" if stream.tell() > 0 else ""

        for section in remaining_descendants:
            if len(section._options) > 0:
                ancestors = [section._NAME, ]

                for ancestor in section._get_ancestors()[:-1]:
                    if not path and ancestor is BASE_SECTION:
                        break

                    ancestors.append(ancestor._NAME)

                ancestors.reverse()

                stream.write("".join((BR, self._SECTION_MARKERS, "\n")
                                ).format(self._SECTION_SEP.join(ancestors)))

                for option in section._options:
                    stream.write("".join((option, self._OPTION_SEP,
                                                    section[option], "\n")))

                # All the subsequent sections will need a blank line in any
                #  case (do not add a double line break after the last option
                #  because the last option of the last section must have only
                #  one break)
                BR = "\n"

    def _export_other_lines(self, stream, other_lines, readonly_section,
                                                                        reset):
        """
        Auxiliary method for :py:meth:`_export_file`.
        """
        if readonly_section or not reset:
            stream.writelines(other_lines)

        other_lines[:] = []

    def _export_other_lines_before_existing_section(self, stream, other_lines,
                                                    readonly_section, reset):
        """
        Auxiliary method for :py:meth:`_export_file`.
        """
        if readonly_section or not reset:
            stream.writelines(other_lines)
        elif stream.tell() > 0:
            stream.write("\n")

        other_lines[:] = []


class ConfigFile(Section):
    """
    The main configuration object.
    """
    def __init__(self, *sources, **kwargs):
        """
        Constructor.

        :param sources: A sequence of all the files, file-like objects,
            dictionaries and special objects to be parsed.
        :type sources: str, dict or special object (see
            :py:meth:`Section._import_object`)
        :param str mode: This sets if and how the next source in the chain
            overwrites already imported sections and options; available choices
            are ``'upgrade'``, ``'update'``, ``'reset'`` and ``'add'`` (see the
            respective methods for more details).
        :param bool safe_calls: If True, when calling a non-existent
            subsection, its closest existing ancestor is returned.
        :param bool inherit_options: If True, if an option is not found in a
            section, it is searched in the parent sections.
        :param bool ignore_case: If True, section and option names will be
            compared ignoring case differences; regular expressions will use
            ``re.I`` flag.
        :param bool subsections: If True (default) subsections are allowed.
        :param bool interpolation: If True, option values will be interpolated
            using values from other options through the special syntax
            ``${section$:section$:option$}``. Options will be interpolated only
            once at importing: all links among options will be lost after
            importing.
        """
        # The Python 3 definition was:
        #def __init__(self,
        #             *sources,
        #             mode='upgrade',
        #             safe_calls=False,
        #             inherit_options=False,
        #             subsections=True,
        #             ignore_case=True,
        #             interpolation=False):
        # But to keep compatibility with Python 2 it has been changed to the
        # current
        mode = kwargs.get('mode', 'upgrade')
        safe_calls = kwargs.get('safe_calls', False)
        inherit_options = kwargs.get('inherit_options', False)
        subsections = kwargs.get('subsections', True)
        ignore_case = kwargs.get('ignore_case', True)
        interpolation = kwargs.get('interpolation', False)

        # Root section
        Section.__init__(self, name=None, parent=None,
                                            safe_calls=safe_calls,
                                            inherit_options=inherit_options,
                                            subsections=subsections,
                                            ignore_case=ignore_case)

        try:
            overwrite, add, reset = {
                "upgrade": (True, True, False),
                "update": (True, False, False),
                "reset": (True, True, True),
                "add": (False, True, False),
            }[mode]
        except KeyError:
            raise ValueError('Unrecognized importing mode: {}'.format(mode))

        self._import(sources, overwrite=overwrite, add=add, reset=reset,
                                                interpolation=interpolation)


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


class NonExistentFileError(ConfigFileError):
    """
    A non-existent configuration file.
    """
    pass


class InvalidFileError(ConfigFileError):
    """
    An invalid configuration file.
    """
    pass


class InvalidObjectError(ConfigFileError):
    """
    An invalid key found in an importing object.
    """
    pass
