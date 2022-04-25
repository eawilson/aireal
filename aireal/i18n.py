import os
import importlib
import pdb

from pytz import timezone

from babel.dates import format_datetime
from babel.numbers import parse_pattern, LC_NUMERIC, format_percent
from babel.messages.pofile import read_po
from babel.units import UnknownUnitError, _find_unit_pattern, get_unit_name
from babel.core import Locale

from flask import current_app, session, request



def format_unit(value, measurement_unit, length="short", locale=LC_NUMERIC, frac_prec=None):
    locale = Locale.parse(locale)

    q_unit = _find_unit_pattern(measurement_unit, locale=locale)
    if not q_unit:
        raise UnknownUnitError(unit=measurement_unit, locale=locale)
    unit_patterns = locale._data["unit_patterns"][q_unit].get(length, {})

    if isinstance(value, str):  # Assume the value is a preformatted singular.
        formattedvalue = value
        plural_form = "one"
    else:
        formattedvalue = format_decimal(value, locale, frac_prec)
        plural_form = locale.plural_form(value)

    if plural_form not in unit_patterns:
        # The current CLDR has no way for this to happen.
        raise NotImplementedError
    
    return unit_patterns[plural_form].format(formattedvalue)



def format_decimal(value, locale=LC_NUMERIC, decimal_quantization=True, group_separator=True, frac_prec=None):
    locale = Locale.parse(locale)
    
    format = locale.decimal_formats.get(None)
    pattern = parse_pattern(format)
    if frac_prec is not None:
        pattern.frac_prec = (0, frac_prec)
    return pattern.apply(value, locale, decimal_quantization=decimal_quantization, group_separator=group_separator)



class AnnotatedStr(str):
    pass



def i18n_nop(text):
    """ NOP function used to mark strings for inclusion in message catalog.
    
    Imported as _ or gettext to mark strings for inclusion in message
    catalog. These strings must be explicitily translated later when they
    are displayed.
    """
    return text



def _(text):
    try:
        return current_app.extensions["locales"][session["locale"]][text]
    except KeyError:
        return text
    
    

def __(text):
    try:
        translated = AnnotatedStr(current_app.extensions["locales"][session["locale"]][text])
    except KeyError:
        translated = AnnotatedStr(text)
    translated.unlocalised = text
    return translated
    
    

def i18n_init(app):
    package = importlib.import_module(app.import_name)
    root_dir = os.path.dirname(package.__file__)
    locales_dir = os.path.join(root_dir, "locales")
    if not os.path.exists(locales_dir):
        return
    
    translations = {}
    app.extensions["locales"] = translations
    for locale in os.listdir(locales_dir):        
        po_file = os.path.join(locales_dir, locale, "LC_MESSAGES", f"{locale}.po")
        if os.path.exists(po_file):
            # TODO fix warning
            with open(po_file) as f:
                catalog = read_po(f)
                
            translations[locale] = {}
            for message in catalog:
                if message.id and message.string:
                    translations[locale][message.id] = message.string
                                
    if "en_GB" not in translations:
        translations["en_GB"] = {}
    
    app.jinja_env.globals.update(_=_)
    
    

def locale_from_headers():
    """ Parse the browser Acept-Language header and return the supported locale 
        that has the highest q score. Default to en_GB if none of the requested
        locales are supported. Header format = en-GB,en-US;q=0.9,en;q=0.8
    """
    try: # We cannot trust any browser input therefore catch everything
        locales = current_app.extensions["locales"]
        accept_header = request.headers.get("Accept-Language", "")
        weighted_lang = [token.strip().split(";q=") for token in accept_header.split(",")]
        sorted_lang = sorted(weighted_lang, key=lambda x:float(x[1]) if len(x)>1 else 1.0, reverse=True)
        for lang_q in sorted_lang:
            lang = lang_q[0]
            locale = "_".join(lang.split("-")[:2])
            if locale in locales:
                return locale
    except Exception:
        pass
    return "en_GB"



class Wrapper(object):
    def __str__(self):
        return self.__html__()
    
    @property
    def value(self):
        if self.val is None:
            return ""
        return self.val



class Date(Wrapper):
    """ Wrapper around a datetime object thar will print in local time with
        the specified format. Also has a value property which is used
        to provide a data-sort value to sortable tables.
    """
    def __init__(self, val, format="medium"):
        self.val = val
        self.format = format
        
    def __repr__(self):
        return "{}({}, format={})".format(type(self).__name__,
                                          repr(self.val),
                                          repr(self.format))
    
    def __html__(self):
        if self.val is None:
            return ""
        tz = timezone(session["timezone"])
        dt = self.val.astimezone(tz)
        ret = format_datetime(dt, 
                              format=self.format,
                              locale=session["locale"])
        if self.format != "long":
            ret = "{} {}".format(ret, dt.strftime("%Z"))
        return ret
    
    @property
    def value(self):
        if self.val is None:
            return ""
        return self.val.timestamp() 



class Number(Wrapper):
    """ Wrapper around a number that will print wih local formating.
        Also has a value property which is used to provide a data-sort
        value to sortable tables.
    """
    def __init__(self, val, frac_prec=None, units=None):
        if frac_prec is None or val is None:
            self.val = val
        else:
            fmt = f"{{:.{frac_prec}f}}"
            self.val = fmt.format(float(val))
        self.units = units
        
    def __repr__(self):
        return "{}({}, units={})".format(type(self).__name__, repr(self.val), repr(self.units))
    
    def __html__(self):
        if self.val is None:
            return ""
        elif self.units is None:
            return format_decimal(self.val, locale=session["locale"])
        else:
            return format_unit(self.val, self.units, locale=session["locale"])



class Percent(Wrapper):
    """ Wrapper around a percentage that will print wih local formating.
        Also has a value property which is used to provide a data-sort
        value to sortable tables.
    """
    def __init__(self, val, frac_prec=None):
        if frac_prec is None or val is None:
            self.val = val
        else:
            frac_prec = frac_prec + 2
            fmt = f"{{:.{frac_prec}f}}"
            self.val = float(fmt.format(float(val)))
        
    def __repr__(self):
        return "{}({})".format(type(self).__name__, repr(self.val))
        
    def __html__(self):
        if self.val is None:
            return ""
        return format_percent(self.val, locale=session["locale"], decimal_quantization=False)



def Unit(unit):
    return get_unit_name(unit, locale=session["locale"], length="narrow")


