# Copyright 2022 Ultimaker BV
#
# This file is part of Telepathy.
#
# Telepathy is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# Telepathy is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for
# more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with Telepathy. If not, see <https://www.gnu.org/licenses/>.

import threading


class LazyLoaded:
    """
    Mixin class to support lazy loading of attributes

    An attribute is set using _setlazy, which registers a callable and
    arguments. Upon first access to the attribute, the value is obtained from
    the callable and stored as an attribute. Subsequent accesses will return
    the stored value.
    """
    def __init__(self):
        self.__lazyattributes = {}
        self.__lock = threading.Lock()

        super().__init__()

    def _setlazy(self, name, callable, *args, **kwargs):
        self.__lazyattributes[name] = (callable, args, kwargs)

    def __dir__(self):
        return super().__dir__() + list(self.__lazyattributes.keys())

    def __getattr__(self, name):
        assert '_LazyLoaded__lock' in self.__dict__, '__init__() not called before attribute access'
        
        # Use a lock to ensure callable is never called twice, even if the same attribute is accessed
        # simultaneously from two threads
        with self.__lock:
            try:
                callable, args, kwargs = self.__lazyattributes[name]
            except KeyError:
                raise AttributeError(f'{self.__class__.__name__!r} object has no attribute {name!r}')

            value = callable(*args, **kwargs)

            self.__lazyattributes.pop(name) # Remove the attribute after successfully retrieving value

            setattr(self, name, value)

        return value


if __name__ == '__main__':
    a = LazyLoaded()


    class OnceTest:
        def __init__(self, value):
            self.wascalled = False
            self.value = value

        def __call__(self, value):
            assert not self.wascalled
            self.wascalled = True
            return self.value + value

    a._setlazy('b', OnceTest(10), 5)
    a._setlazy('a', OnceTest(20), 2)
    dir1 = dir(a)
    assert a.a == 22
    dir2 = dir(a)
    assert a.b == 15
    dir3 = dir(a)
    assert a.a == 22
    assert a.b == 15
    assert dir1 == dir2 == dir3  # check dir() stays equal
