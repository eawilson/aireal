from pytz import timezone
from babel.dates import format_datetime
from flask import session

from .i18n import _
import pdb


class Local(object):
    """ Wrapper around a datetime object thar will print in local time with
        the specified format. Also has a value property which is used
        to provide a data-sort value to sortable tables.
    """
    def __init__(self, val, format="medium"):
        self._val = val
        self._format = format
        
    def __repr__(self):
        return "{}({}, format={})".format(type(self).__name__,
                                          repr(self._val),
                                          repr(self._format))
    
    def __html__(self):
        if self._val is None:
            return ""
        tz = timezone(session["timezone"])
        dt = self._val.astimezone(tz)
        ret = format_datetime(dt, 
                              format=self._format,
                              locale=session["locale"])
        if self._format != "long":
            ret = "{} {}".format(ret, dt.strftime("%Z"))
        return ret
    
    def __str__(self):
        return self.__html__()
    
    @property
    def value(self):
        if self._val is None:
            return ""
        return self._val.timestamp() 



class Attr(object):
    """ Wrapper around any object passed to a template that will allow the
        the optional addition of additional attributes to control
        formatting and sorting.
    """
    def __init__(self, val, **kwargs):
        self._val = val
        self._kwargs = kwargs
     
    def __repr__(self):
        items = [(k, repr(v)) for k, v in sorted(self._kwargs.items())]
        kwargs = [f"{k}={v}" for k, v in items]
        if kwargs:
            kwargs = [""] + kwargs
        return "{}({}{})".format(type(self).__name__,
                                   repr(self._val),
                                   ", ".join(kwargs))
           
    def __str__(self): 
        return str(self._val)
    
    def __getattr__(self, attr):
        try:
            return self._kwargs[attr]
        except KeyError:
            return getattr(self._val, attr)



#class Number(object):
    #""" Wrapper around any object passed to a template that will allow the
        #the optional addition of additional attributes to control
        #formatting and sorting.
    #"""
    #def __init__(self, val):
        #self._val = val
     
    #def __repr__(self):
        #return "{}({})".format(type(self).__name__, str(self._val))
           
    #def __str__(self): 
        #return str(self._val)
    
    #def __getattr__(self, attr):
        #try:
            #return self._kwargs[attr]
        #except KeyError:
            #msg = "'{}' object has no attribute '{}'"
            #raise AttributeError(msg.format(type(self).__name__, attr))
