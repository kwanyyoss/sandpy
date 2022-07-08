import types
import re, json

import traceback


from sys import modules as sysmodules
__main__ = sysmodules['__main__']

# To make classes read-only, we need metaclasses.  To make the metaclasses
# read-only, we need to block access to the most fundamental metaclass(es).
# To do that, we need to audit/filter the "type()" keyword/function.
class ReadOnly_meta(type):
    def __setattr__(cls, attr, val):
        raise TypeError(f"'{cls.__name__}' class is read-only.")
    def __delattr__(cls, attr):
        raise TypeError(f"'{cls.__name__}' class is read-only.")

    @property
    def __class__(cls):
        return cls                      # ground type (see def Rtype)
    def __init__(cls, name, bases, dict):
        super().__init__(name, bases, dict)
class ReadOnly2_meta(type, metaclass=ReadOnly_meta):
    def __new__(cls, name, bases, dict, *_, **kwargs):
        ret = super().__new__(cls, name, bases, dict)
        ret.__locked__ = None
        tmp = list(bases)
        try:
            tmp.remove(type)
        except ValueError:
            pass
        if len(tmp) == 0:
            tmp.append(object)
        ret.__Rbases__ = tuple(tmp)
        return ret

    def __setattr__(cls, attr, val):
        if getattr(cls, '__locked__', None) != cls:
            return super().__setattr__(attr, val)
        raise RuntimeError(f"Cannot modify - class '{cls.__name__}' is locked.")
    def __delattr__(cls, attr):
        if getattr(cls, '__locked__', None) != cls:
            return super().__delattr__(attr)
        raise RuntimeError(f"Cannot modify - class '{cls.__name__}' is locked.")

    def metalock(cls):
        if getattr(cls, '__locked__', None) != cls:
            cls.__locked__ = cls
        return cls

    def mro(cls):
        orig = type.mro(cls)
        tmp = orig.copy()
        try:
            tmp.remove(type)
        except ValueError:
            pass
        cls.__Rmro__ = tuple(tmp)
        return orig

    @property
    def __mro__(cls):
        return cls.__Rmro__
    @property
    def __base__(cls):
        return cls.__Rbases__[0]
    @property
    def __bases__(cls):
        return cls.__Rbases__

    @property
    def __class__(cls):
        return cls                      # ground type (see def Rtype)
    def __init__(cls, name, bases, dict, *_, **kwargs):
        super().__init__(name, bases, dict)

class Final(metaclass=ReadOnly_meta):
    __repr__ = object.__repr__


class Freeze_meta(type, metaclass=ReadOnly2_meta):
    def __init__(cls, *argv, **kwargs):
        super().__init__(*argv)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()
        # "__init_subclass__" implementations could interfere with the setup 
        # processing required in this class
        if isinstance(cls.__init_subclass__, types.MethodType) and\
           cls.__init_subclass__.__func__ !=\
             __class__.__init_subclass__.__func__:
            raise TypeError("'__init_subclass__' forbidden in subclass of " +
                            f"'{__class__}'");

    def __new__(cls, *argv, **kwargs):
        ret = super().__new__(cls, *argv, **kwargs)
        if getattr(ret, '__locked__', None) != ret:
            ret.__locked__ = None
        return ret

    def __setattr__(cls, attr, val):
        if getattr(cls, '__locked__', None) != cls:
            return super().__setattr__(attr, val)
        raise RuntimeError(f"Cannot modify - class '{cls.__name__}' is locked.")
    def __delattr__(cls, attr):
        if getattr(cls, '__locked__', None) != cls:
            return super().__delattr__(attr)
        raise RuntimeError(f"Cannot modify - class '{cls.__name__}' is locked.")

    def lock(cls):
        if getattr(cls, '__locked__', None) != cls:
            if hasattr(cls, '__Rsupermap__'):
                cls.__Rsupermap__ = Dict(cls.__Rsupermap__).lock()
                cls.__Rsupermap__ = cls.__Rsupermap__.as_dict(__main__.makeapi)
            cls.__locked__ = cls
Freeze_meta.metalock()

class Object(metaclass=Freeze_meta):
    def __init__(self, *argv, **kwargs):
        if getattr(self, '__locked__', False) == True:
            raise RuntimeError('Cannot modify - object is locked.')
        super().__init__(*argv, **kwargs)
        super().__setattr__('__locked__', False)
        super().__setattr__('__proxydict__', Dict())

    def __getattribute__(self, attr):
        try:
            return super().__getattribute__(attr)
        except AttributeError:
            pass
        return self.__getattr__(attr)
    def __setattr__(self, attr, val):
        if attr in [ '__locked__', '__proxydict__' ]:
            raise AttributeError(f"Protected attribute '{attr}'")
        if hasattr(self, attr) and not attr in self.__proxydict__:
            if getattr(self, '__locked__', False):
                raise RuntimeError('Cannot modify - object is locked.')
            super().__setattr__(attr, val)
            return self
        # write-only (attribute forwarding) property - allow
        if type(getattr(self.__class__, attr, None)) == property:
            super().__setattr__(attr, val)
            return self
        self.__proxydict__[attr] = val
        return self
    def __delattr__(self, attr):
        if attr in [ '__locked__', '__proxydict__' ]:
            raise AttributeError(f"Protected attribute '{attr}'")
        if hasattr(self, attr) and not attr in self.__proxydict__:
            if getattr(self, '__locked__', False):
                raise RuntimeError('Cannot modify - object is locked.')
            super().__delattr__(attr)
            return self
        del self.__proxydict__[attr]
        return self
    def __getattr__(self, attr):
        if attr == '__proxydict__':
            raise AttributeError(attr)
        try:
            return self.__proxydict__[attr]
        except KeyError:
            raise AttributeError(attr)
    @property
    def __dict__(self):
        return None
    def __dir__(self):
        return [ *self.__proxydict__.keys() ]
    def __repr__(self):
        jsonstr = json.dumps(self.__proxydict__, indent=2,
                             default=Object.jsondefault)
        # remove the first and last newlines to mimic Python REPL
        return '{' + re.subn('\n[ \t]+}', ' }', jsonstr[3:-2])[0] + ' }'

    def lock(self):
        if not self.__locked__:
            super().__setattr__('__locked__', True)
            self.__proxydict__.lock()
        return self
    def lockdown(self, mkapi):
        if isinstance(self.__proxydict__, Dict):
            if self.__locked__ == True:
                raise RuntimeError(f"{__class__.__name__} - 'lock()' called " +
                                   "before 'lockdown()'!")
            p = self.__proxydict__
            super().__delattr__('__proxydict__')
            super().__setattr__('__proxydict__',
                                p.lockdown(mkapi).as_dict(mkapi))
            super().__setattr__('__locked__', True)
        return self
    @classmethod
    def lockclass(cls):
        Freeze_meta.lock(cls)

    @staticmethod
    def jsondefault(obj):
        if isinstance(obj, __class__):
            if obj.__repr__.__func__ == __class__.__repr__:
                return obj.__proxydict__
        
        try:
            return dict(obj)
        except TypeError:
            pass
        return repr(obj)

    def wrap(self):
        self.lock()
        entries = self.__dir__()

        class wrapper(metaclass=Freeze_meta):
            def __init__(self, i: Object):
                for attr in entries:
                    self.__setattr__(attr, i.__getattr__(attr))
                entries.clear()		# prevent re-initialization

            def __repr__(self2):
                try:
                    jsonstr = json.dumps(dict(self2), indent=2,
                                         default=Object.jsondefault)
                    # remove the first and last newlines to mimic Python REPL
                    return '{' + re.subn('\n[ \t]+}', ' }',
                                         jsonstr[3:-2])[0] + ' }'
                except TypeError:
                    return self.__repr__()

            @property
            def __dict__(self):
                return None
        for attr in entries.copy():
            entry = self.__getattr__(attr)
            if isinstance(entry, types.MethodType):
                # add a method to the class
                wrapper.__class__.__setattr__(wrapper, attr, entry.__func__)
                entries.remove(attr)

        return wrapper(self)
Object.lockclass()

class Dict(metaclass=ReadOnly_meta):
    def __init__(self, *argv, **kwargs):
        if getattr(self, '__locked__', False):
            raise RuntimeError('Cannot modify - object is locked.')
        self.__locked__ = False
        self.store = dict(*argv, **kwargs)

    def __repr__(self):
        return repr(self.store)

    def lock(self):
        if not self.__locked__:
            self.__locked__ = True
            for i in self.store:
                if issubclass(type(self.store[i]), __class__):
                    self.store[i].lock()
        return self
    def lockdown(self, mkapi):
        for i in self.store:
            if issubclass(type(self.store[i]), __class__):
                self.store[i] = self.store[i].lockdown(mkapi).as_dict(mkapi)
            elif issubclass(type(self.store[i]), Object):
                self.store[i].lockdown(mkapi)
        if not self.__locked__:
            self.__locked__ = True
        return self


    def __getitem__(self, item):
        return self.store[item]

    def __setitem__(self, item, val):
        if not getattr(self, '__locked__', False):
            self.store[item] = val
            return None
        raise RuntimeError('Cannot modify - object is locked.')

    def __delitem__(self, item):
        if not getattr(self, '__locked__', False):
            del self.store[item]
            return None
        raise RuntimeError('Cannot modify - object is locked.')

    def __setattr__(self, attr, val):
        if not getattr(self, '__locked__', False):
            return super().__setattr__(attr, val)
        raise RuntimeError('Cannot modify - object is locked.')

    def __delattr__(self, attr):
        if not getattr(self, '__locked__', False):
            return super().__delattr__(attr)
        raise RuntimeError('Cannot modify - object is locked.')

    @property
    def __dict__(self):
        return None

    def __contains__(self, key):
        return key in self.store
    def len(self):
        return len(self.store)
    def iter(self):
        return self.store.iter()
    def clear(self):
        if not getattr(self, '__locked__', False):
            return self.store.clear()
        raise RuntimeError('Cannot modify - object is locked.')
    def copy(self):
        return __class__(self.store.copy())
    def get(self, key, *argv):
        return self.store.get(key, *argv)
    def items(self):
        return self.store.items();
    def keys(self):
        return self.store.keys();
    def pop(self, key, *argv):
        if getattr(self, '__locked__', False) and key in self.store:
            raise RuntimeError('Cannot modify - object is locked.')
        return self.store.pop(key, *argv)
    def popitem(self):
        if not getattr(self, '__locked__', False):
            return self.store.popitem()
        raise RuntimeError('Cannot modify - object is locked.')
    def setdefault(self, key, *argv):
        if key in self.store:
            return self.store[key]
        if not getattr(self, '__locked__', False):
            return self.store.setfault(key, *argv)
        raise RuntimeError('Cannot modify - object is locked.')
    def update(self, *argv, **kwargs):
        if not getattr(self, '__locked__', False):
            return self.store.update(*argv, **kwargs)
        raise RuntimeError('Cannot modify - object is locked.')
    def values(self):
        return self.store.values()

    def make_interface(self, mkapi):
        "Returns an Object instance containing only the interface (methods)"
        intf = Object()
        intf.__repr__ = lambda : self.__repr__()
        intf.__contains__ = mkapi('fn = lambda self, k: contains(k)',
                                  contains=self.__contains__).__get__(intf)
        intf.__getitem__ = mkapi('fn = lambda self, i: getitem(i)',
                                 getitem=self.__getitem__).__get__(intf)
        intf.__setitem__ = mkapi('fn = lambda self, i, v: setitem(i, v)',
                                 setitem=self.__setitem__).__get__(intf)
        intf.__delitem__ = mkapi('fn = lambda self, i: delitem(i)',
                                 delitem=self.__delitem__).__get__(intf)
        intf.iter = mkapi('fn = lambda self: i()', i=self.iter).__get__(intf)
        intf.clear = mkapi('fn = lambda self: clear()',
                           clear=self.clear).__get__(intf)
        intf.len = mkapi('fn = lambda self: l()', l=self.len).__get__(intf)
        intf.copy = mkapi('fn = lambda self: copy()',
                          copy=self.copy).__get__(intf)
        intf.get = mkapi("""
def fn(self, key, *argv):
  return get(key, *argv)
""",                     get=self.get).__get__(intf)
        intf.items = mkapi('fn = lambda self: items()',
                           items=self.items).__get__(intf)
        intf.keys = mkapi('fn = lambda self: keys()', keys=self.keys).__get__(intf)
        intf.pop = mkapi("""
def fn(self, key, *argv):
  return pop(key, *argv)
""",                     pop=self.pop).__get__(intf)
        intf.popitem = mkapi('fn = lambda self: popi()',
                             popi=self.popitem).__get__(intf)
        intf.setdefault = mkapi("""
def fn(self, key, *argv):
  return setdefault(key, *argv)
""",                            setdefault=self.setdefault).__get__(intf)
        intf.update = mkapi("""
def fn(self, key, *argv, **kwargs):
  return update(key, *argv, **kwargs)
""",                        update=self.update).__get__(intf)
        intf.values = mkapi('fn = lambda self: values()',
                            values=self.values).__get__(intf)
        intf.lock()
        return intf

    def as_dict(self, mkapi):
        def blocked(a):
            raise AttributeError("'dict' object has no attribute '" + a + "'")
        w = self.make_interface(mkapi).wrap()
        w.__class__.__getattr__ = mkapi("fn = lambda attr: b(attr)",
                                        b=blocked)._c
        w.__class__.__setattr__ = mkapi("fn = lambda self, attr, v: b(attr)",
                                        b=blocked)
        w.__class__.__delattr__ = mkapi("fn = lambda self, attr: b(attr)",
                                        b=blocked)
        w.__class__.lock()
        return w

def HideBases(to_hide: tuple, *bases):
    if type(to_hide) != tuple or not all(isinstance(i, type) for i in to_hide):
        raise TypeError("'to_hide' must be a tuple of types")
    if bases:
        if not all(isinstance(i, type) for i in bases):
            raise TypeError("'bases' must be a tuple of types")
    else:
        bases = (Freeze_meta,)

    class hbcls(*bases, metaclass=ReadOnly2_meta):
        def __new__(cls, name, bases, dict, *argv, **kwargs):
            ret = super().__new__(cls, name, bases, dict, *argv, **kwargs)
            tmp = list(bases)
            for k in to_hide:
                try:
                    while True:
                        tmp.remove(k)
                except ValueError:
                    pass
            if len(tmp) == 0:
                tmp.append(object)
            ret.__Rbases__ = tuple(tmp)
            return ret

        def mro(cls, **kwargs):
            orig = type.mro(cls)
            tmp = orig.copy()
            tmp2 = {}
            ordered_rem = [ orig.index(k) for k in orig if k in to_hide ]
            ordered_rem.reverse()
            for k in ordered_rem:
                if orig[k] in tmp:
                    fr = cls if k == 0 else orig[k - 1]
                    if orig[k] in tmp2:
                        tmp2[fr] = tmp2[orig[k]]
                        del tmp2[orig[k]]
                    else:
                        tmp2[fr] = lambda s: super(orig[k], s)
                    try:
                        while True:
                            tmp.remove(orig[k])
                    except ValueError:
                        pass
            cls.__Rmro__ = tuple(tmp)
            cls.__Rsupermap__ = tmp2
            return orig

        @property
        def __mro__(cls):
            return cls.__Rmro__
        @property
        def __base__(cls):
            return cls.__Rbases__[0]
        @property
        def __bases__(cls):
            return cls.__Rbases__

        def __init__(cls, *argv, **kwargs):
            super().__init__(*argv, **kwargs)
            # finished creating class

    return hbcls

class RException(BaseException,
                 metaclass=HideBases((BaseException,)).metalock()):
    "Exception replacement that does not leak the global scope"
    def __init__(self, *argv, **kwargs):
        super().__init__(*argv, **kwargs)
        self.access_verify = None

    def with_traceback(self, tb):
        self.access_verify = __main__.Interact.prog
        ret = super().with_traceback(tb)
        self.access_verify = None
        return ret

    @property
    def __traceback__(self):
        if self.access_verify == __main__.Interact.prog:
            return super().__traceback__
        return traceback.format_tb(super().__traceback__)
#RException.lock()

