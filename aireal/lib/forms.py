import re, pdb
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from collections import OrderedDict
from collections.abc import MutableMapping
from itertools import chain

from html import escape
from jinja2 import Markup
from flask import session, request


email_regex = re.compile("^[a-zA-Z0-9.!#$%&'*+\/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$")
name_regex = re.compile("[^a-zA-Z-' ]")
number_regex = re.compile("^[0-9]+$")


__all__ = ["Form",
           "Input",
           "TextInput",
           "TextAreaInput",
           "HiddenInput",
           "PasswordInput",
           "NameInput",
           "TextNumberInput",
           "LowerCaseInput",
           "EmailInput",
           "IntegerInput",
           "DecimalInput",
           "NHSNumberInput",
           "DateInput",
           "PastDateInput",
           "BooleanInput",
           "SelectInput",
           "MultiSelectInput",
           "MultiCheckboxInput"]


def is_valid_nhs_number(data):
    if len(data) == 10 and data.isnumeric():
        val = 11 - (sum(int(x)*y for x, y in zip(data[:9], range(10, 1, -1))) % 11)
        if val == 11:
            val = 0
        if val == int(data[9]):
            return data



class HTMLAttr(MutableMapping):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.attr = {}
        for d in args + (kwargs,):
            for k, v in d.items():
                self[k] = v
                

    def __setitem__(self, k, v):
        if k.startswith("_"):
            k = k[1:]
        if k == "class" and "class" in self:
            v = "{} {}".format(self["class"], v)
        self.attr.__setitem__(k, v)
    
    
    def __repr__(self):
        return "{}({})".format(type(self).__name__, repr(self.attr))


    def __str__(self):
        attr = []
        for k, v in sorted(self.items()):
            if v is True:
                attr.append(k)
            elif v is not False and v is not None and v != "":
                if escape(k) != k:
                    raise ValueError("'{k}' is not a valid html attribute.")
                attr.append('{}="{}"'.format(k, escape(str(v))))
        return " ".join(attr)
    
    
    def __html__(self):
        return str(self)
    
    
    def __getitem__(self, k):
        return self.attr.__getitem__(k)
    
    
    def __delitem__(self, k):
        return self.attr.__delitem__(k)
    
    
    def __iter__(self):
        return self.attr.__iter__()
    
    
    def __len__(self):
        return self.attr.__len__()
    
    
    def combined(self, *args, **kwargs):
        return HTMLAttr(self.attr, *args, kwargs, id=self.attr["id"]) if args or kwargs else self
    

    def __call__(self, **kwargs):
        return Markup(self.combined(kwargs).__html__())



class Fields(MutableMapping):
    """ Ordered collection of form fields that can be accessed by name, either
        as an attribute or a key. Each field added will have
        its name and id html attributes set to its name.
    """
    def __init__(self):
        self._fields = OrderedDict()
        
    
    def __repr__(self):
        return "{}({})".format(type(self).__name__, repr(self._fields))
        
        
    def __getitem__(self, key):
        return self._fields[key]
        
        
    def __setitem__(self, key, val):
        if not isinstance(val, Input):
            raise TypeError(f'"{key}" is not of type Input.')
        return self.__setattr__(key, val)
    
    
    def __delitem__(self, key):
        return self.__delattr__(key)
        
    
    def __iter__(self):
        yield from self._fields
        
        
    def __len__(self):
        return len(self._fields)
    
    
    def __setattr__(self, attr, val):
        if isinstance(val, Input):
            if hasattr(self, attr):
                previous = getattr(self, attr, None)
                if previous is not None and not isinstance(previous, Inupt):
                    raise AttributeError(f"Cannot overwrite attribute '{attr}'.")
            self._fields[attr] = val
            if "name" not in val.attr:
                val.attr["name"] = attr
            if "id" not in val.attr:
                val.attr["id"] = attr
        return super().__setattr__(attr, val)
    
    
    def __delattr__(self, attr):
        self._fields.pop(attr, None)
        return super().__delattr__(attr)
    


class Form(Fields):
    def __init__(self, data=None, method="post", autocomplete="off", **kwargs):
        super().__init__()
        self.attr = HTMLAttr(method=method, autocomplete=autocomplete, **kwargs)
        self.definition()
        self.fill(data)
        self._error = ""
    
    
    def __repr__(self):
        return "{}({})".format(type(self).__name__, ", ".join([repr(field) for field in self.values()]))
    
    
    def fill(self, data=None, **kwargs):
        if data:
            for name, field in self.items():
                if field.empty == list and hasattr(data, "getlist"):
                    field.data = data.getlist(name)
                elif name in data:
                    field.data = data.get(name)
            self.csrf = data.get("csrf", "")
            self.back = data.get("back", "")
                    
        for k, v in kwargs.items():
            if k.endswith("_choices") and k[:-8] in self:
                self[k[:-8]].choices = v
            else:
                raise TypeError("Unknown keyword argument {}.".format(k))


    @property
    def fields(self):
        return self.values()
    
    
    def definition(self):
        return
        
        
    def validate(self):
        if "csrf" in session and self.csrf != session["csrf"]:
            return False
        return all(field.validate() for field in self.values())
    
    
    @property
    def errors(self):
        return any(field.errors for field in self.values())
    
    
    @property
    def error(self):
        return self._error
            #", ".join(field.errors for field in self.values() if field.errors)
    
    
    @error.setter
    def error(self, msg):
        self._error = msg
    
    
    @property
    def data(self):
        return {name: field.data for name, field in self.items()}


    def __html__(self):
        if any(isinstance(field, FileInput) for field in self.fields):
            self.attr["enctype"] = "multipart/form-data"
        template = '<form {}><input type="hidden" name="csrf" value="{}"><input type="hidden" id="back" name="back" value="">'
        return template.format(self.attr, session.get("csrf", ""))



class Input(object):
    empty = type(None)
    
    def __init__(self, label="", required="Data required", **kwargs):
        self.attr = HTMLAttr(**kwargs)
        self._label = label
        if required is True:
            # Hard habit to break
            required = "Data required"
        self.required = required
        self.data = self.empty()
        self.errors = ""
    
    
    def __repr__(self):
        return "{}({}, value={})".format(type(self).__name__, ", ".join("{}={}".format(k, v) for k, v in self.attr.items()), repr(self.data)) 
    
    
    @property
    def data(self):
        return self._data
            
            
    @data.setter
    def data(self, val):
        if hasattr(val, "strip"):
            val = val.strip()
        self._data = self.empty() if val in (None, "") else self.convert(val)
    
    
    def convert(self, val):
        return str(val)
    
    
    def validate(self):
        if (self.data == self.empty()) and self.required:
            self.errors = self.required
        return not self.errors
   
    
    def label(self, **kwargs):
        return Markup('<label {}>{}</label>'.format(HTMLAttr(kwargs, _for=self.attr["id"]), escape(self._label)))
    
    
    @property
    def element(self):
        return self.attr.get("type", "text")
        
    
    def __call__(self, **kwargs):
        return Markup('<input {}>'.format(self.attr.combined(kwargs, value=self.data)))
    
    
    def __html__(self):
        return self()



class TextInput(Input):
    empty = str
        
        
        
class HiddenInput(TextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, _type="hidden", **kwargs)



class FileInput(Input):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, _type="file", **kwargs)

    #@property
    #def data(self):
        #return self._data
                        
    #@data.setter
    #def data(self, val):
        #raise NotImplementedError()
    
    #def validate(self):
        #if (self.data == self.empty()) and self.required:
            #self.errors = self.required
        #return not self.errors



class DirectoryInput(FileInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, webkitdirectory=True, **kwargs)



class TextAreaInput(TextInput):
    def __init__(self, *args, rows="1", **kwargs):
        super().__init__(*args, rows=rows, **kwargs)
        
    def __call__(self, **kwargs):
        return Markup('<textarea {}>{}</textarea>'.format(self.attr.combined(kwargs), escape(self.data if self.data is not None else "")))

    @property
    def element(self):
        return "textarea"



class PasswordInput(Input):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, _type="password", **kwargs)
    
    def __call__(self, **kwargs):
        return Markup('<input {}>'.format(self.attr.combined(kwargs)))
        
        

class NameInput(Input):
    def validate(self):
        if super().validate() and self.data:
            invalid_chars = "".join(name_regex.findall(self.data))
            if invalid_chars:
                self.errors = "Invalid character{} {} in name.".format("s" if len(invalid_chars)>1 else "", repr(invalid_chars))
        return not self.errors



class TextNumberInput(Input):
    def validate(self):
        if super().validate() and self.data and not number_regex.match(self.data):
            self.errors = "Must be a number."
        return not self.errors



class LowerCaseInput(Input):
    def convert(self, val):
        return val.lower()



class NHSNumberInput(Input):
    def validate(self):
        if super().validate() and self.data and not is_valid_nhs_number(self.data):
            self.errors = "Not a valid NHS number."
        return not self.errors
    
    def convert(self, val):
        self._data = "".join(val.split())



class EmailInput(LowerCaseInput):
    def validate(self):
        if super().validate() and self.data and not email_regex.match(self.data):
            self.errors = "Invalid email address."
        return not self.errors



class IntegerInput(Input):
    def __init__(self, *args, minval=None, maxval=None, **kwargs):
        self.minval=minval
        self.maxval = maxval
        super().__init__(*args, **kwargs)
    
    def convert(self, val):
        try:
            return int(val)
        except (ValueError, TypeError):
            self.errors = "Not a valid integer."

    def validate(self):
        if super().validate() and self.data != self.empty():
            if self.minval is not None and self.data < self.minval:
                self.errors = "Cannot be less than {}.".format(self.minval)
            if self.maxval is not None and self.data > self.maxval:
                self.errors = "Cannot be greater than {}.".format(self.maxval)
        return not self.errors
    


class DecimalInput(Input):
    def __init__(self, *args, prec=1, **kwargs):
        self.prec = prec
        super().__init__(*args, **kwargs)
    
    def convert(self, val):
        try:
            return Decimal(val).quantize(Decimal("".join(["1."]+(["0"]*self.prec)))) # looks crazy but is recommended way to round a decimal from python docs.
        except InvalidOperation:
            self.errors = "Not a valid decimal."



class DateInput(Input):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, _type="date", **kwargs)
    
    
    def convert(self, val):
        if not isinstance(val, date):
            try:
                return datetime.strptime(val, "%Y-%m-%d").date()
            except ValueError:
                self.errors = "Not a valid date."


    def __call__(self, **kwargs):
        return Markup('<input {}>'.format(self.attr.combined(kwargs, value=self.data.strftime("%Y-%m-%d") if self.data is not None else "")))



class PastDateInput(DateInput):
    def validate(self):
        if super().validate() and self.data:
            if self.data > datetime.now().date():
                self.errors = "Date cannot be in the future."
        return not self.errors



class BooleanInput(Input):
    empty = bool

    def __init__(self, *args, details="", **kwargs):
        super().__init__(*args, type="checkbox", _class="no-border-focus", **kwargs)
        self.details = details
        
    
    def convert(self, val):
        return bool(val)

    
    def __call__(self, **kwargs):
        return Markup('<input {}>'.format(self.attr.combined(kwargs, checked=self.data)))



class SelectInput(Input):
    def __init__(self, *args, choices=(), coerce=int, empty_choice=True, **kwargs):
        self._empty_choice = empty_choice
        self.choices = choices
        self.coerce = coerce
        super().__init__(*args, **kwargs)


    @property
    def choices(self):
        return self._choices
    
    
    @choices.setter
    def choices(self, choices):
        if self._empty_choice:
            choices = list(chain(((self.empty(), ""),), choices))
        self._choices = choices
    
    
    def convert(self, val):
        try:
            return self.coerce(val)
        except Exception:
            return self.empty()
        
    
    def validate(self):
        if super().validate():
            try:
                index = [choice[0] for choice in self.choices].index(self.data) # will raise ValueError if not a valid option
            except ValueError:
                self.errors = "Invalid choice."
        return not self.errors


    @property
    def element(self):
        return "select"
        
    
    def __call__(self, **kwargs):
        html = ["<select {}>".format(self.attr.combined(kwargs))]
        for choice in self.choices:
            k = choice[0]
            html.append('<option value="{}"{}>{}</option>'.format(escape(str(k) if k is not None else ""), " selected" if self.is_selected(k) else "", escape(str(choice[1]))))
        html.append("</select>")
        return Markup("".join(html))
    
    
    def is_selected(self, option):
        return (option == self.data) or ""



class MultiSelectInput(SelectInput):
    empty = list
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, multiple=True, empty_choice=False, **kwargs)

    
    def validate(self):
        choices = [choice[0] for choice in self.choices]
        try:
            self.data = [self.coerce(data) for data in self.data] # If fails could raise any exception dependent on coerce                
            index = [choices.index(data) for data in self.data] # will raise ValueError if not a valid option
        except Exception:
            self.errors = "Invalid choice."
        if self.required and not self.data:
            self.errors = self.required
        return not self.errors


    def convert(self, val):
        return [self.coerce(item) for item in val]


    def is_selected(self, option):
        return (option in self.data) or ""



class MultiCheckboxInput(MultiSelectInput):
    def __iter__(self):
        for choice in self.choices:
            yield self._single_checkbox(choice)
            
            
    def _single_checkbox(self, choice):
        disabled = len(choice) > 2 and choice[2] == "disabled"
        name = self.attr["name"]
        field = Input(name=name,
                      id="{}-{}".format(self.attr["id"], choice[0]),
                      type="checkbox",
                      checked=self.is_selected(choice[0]),
                      disabled=disabled)
        field.details = choice[1]
        field.data = choice[0]
        return field


    def checkbox(self, choice):
        self.choices = self.choices + (choice,)
        return self._single_checkbox(choice)
        

    def label(self, **kwargs):
        if not len(self.choices):
            return ""
        return super().label(**kwargs)



