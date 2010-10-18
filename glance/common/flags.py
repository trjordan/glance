# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Package-level global flags are defined here, the rest are defined
where they're used.
"""

import getopt
import os
import socket
import sys

import gflags


class FlagValues(gflags.FlagValues):
    """Extension of gflags.FlagValues that allows undefined and runtime flags.

    Unknown flags will be ignored when parsing the command line, but the
    command line will be kept so that it can be replayed if new flags are
    defined after the initial parsing.

    """

    def __init__(self):
        gflags.FlagValues.__init__(self)
        self.__dict__['__dirty'] = []
        self.__dict__['__was_already_parsed'] = False
        self.__dict__['__stored_argv'] = []

    def __call__(self, argv):
        # We're doing some hacky stuff here so that we don't have to copy
        # out all the code of the original verbatim and then tweak a few lines.
        # We're hijacking the output of getopt so we can still return the
        # leftover args at the end
        sneaky_unparsed_args = {"value": None}
        original_argv = list(argv)

        if self.IsGnuGetOpt():
            orig_getopt = getattr(getopt, 'gnu_getopt')
            orig_name = 'gnu_getopt'
        else:
            orig_getopt = getattr(getopt, 'getopt')
            orig_name = 'getopt'

        def _sneaky(*args, **kw):
            optlist, unparsed_args = orig_getopt(*args, **kw)
            sneaky_unparsed_args['value'] = unparsed_args
            return optlist, unparsed_args

        try:
            setattr(getopt, orig_name, _sneaky)
            args = gflags.FlagValues.__call__(self, argv)
        except gflags.UnrecognizedFlagError:
            # Undefined args were found, for now we don't care so just
            # act like everything went well
            # (these three lines are copied pretty much verbatim from the end
            # of the __call__ function we are wrapping)
            unparsed_args = sneaky_unparsed_args['value']
            if unparsed_args:
                if self.IsGnuGetOpt():
                    args = argv[:1] + unparsed_args
                else:
                    args = argv[:1] + original_argv[-len(unparsed_args):]
            else:
                args = argv[:1]
        finally:
            setattr(getopt, orig_name, orig_getopt)

        # Store the arguments for later, we'll need them for new flags
        # added at runtime
        self.__dict__['__stored_argv'] = original_argv
        self.__dict__['__was_already_parsed'] = True
        self.ClearDirty()
        return args

    def SetDirty(self, name):
        """Mark a flag as dirty so that accessing it will case a reparse."""
        self.__dict__['__dirty'].append(name)

    def IsDirty(self, name):
        return name in self.__dict__['__dirty']

    def ClearDirty(self):
        self.__dict__['__is_dirty'] = []

    def WasAlreadyParsed(self):
        return self.__dict__['__was_already_parsed']

    def ParseNewFlags(self):
        if '__stored_argv' not in self.__dict__:
            return
        new_flags = FlagValues()
        for k in self.__dict__['__dirty']:
            new_flags[k] = gflags.FlagValues.__getitem__(self, k)

        new_flags(self.__dict__['__stored_argv'])
        for k in self.__dict__['__dirty']:
            setattr(self, k, getattr(new_flags, k))
        self.ClearDirty()

    def __setitem__(self, name, flag):
        gflags.FlagValues.__setitem__(self, name, flag)
        if self.WasAlreadyParsed():
            self.SetDirty(name)

    def __getitem__(self, name):
        if self.IsDirty(name):
            self.ParseNewFlags()
        return gflags.FlagValues.__getitem__(self, name)

    def __getattr__(self, name):
        if self.IsDirty(name):
            self.ParseNewFlags()
        return gflags.FlagValues.__getattr__(self, name)


FLAGS = FlagValues()


def _wrapper(func):
    def _wrapped(*args, **kw):
        kw.setdefault('flag_values', FLAGS)
        func(*args, **kw)
    _wrapped.func_name = func.func_name
    return _wrapped


DEFINE = _wrapper(gflags.DEFINE)
DEFINE_string = _wrapper(gflags.DEFINE_string)
DEFINE_integer = _wrapper(gflags.DEFINE_integer)
DEFINE_bool = _wrapper(gflags.DEFINE_bool)
DEFINE_boolean = _wrapper(gflags.DEFINE_boolean)
DEFINE_float = _wrapper(gflags.DEFINE_float)
DEFINE_enum = _wrapper(gflags.DEFINE_enum)
DEFINE_list = _wrapper(gflags.DEFINE_list)
DEFINE_spaceseplist = _wrapper(gflags.DEFINE_spaceseplist)
DEFINE_multistring = _wrapper(gflags.DEFINE_multistring)
DEFINE_multi_int = _wrapper(gflags.DEFINE_multi_int)


def DECLARE(name, module_string, flag_values=FLAGS):
    if module_string not in sys.modules:
        __import__(module_string, globals(), locals())
    if name not in flag_values:
        raise gflags.UnrecognizedFlag(
                "%s not defined by %s" % (name, module_string))


# __GLOBAL FLAGS ONLY__
# Define any app-specific flags in their own files, docs at:
# http://code.google.com/p/python-gflags/source/browse/trunk/gflags.py#39

# TODO(sirp): move this out to an application specific setting when we create
# Nova/Glance common library
DEFINE_string('sql_connection',
              'sqlite:///%s/glance.sqlite' % os.path.abspath("./"),
              'connection string for sql database')
DEFINE_bool('verbose', False, 'show debug output')