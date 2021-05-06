import os
import glob
import csv
import pdb
import importlib

from flask import current_app, session, request
from babel.messages.pofile import read_po



class AnnotatedStr(str):
    pass



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
    
    

# TODO once tested enclose in a big try except as we can't trust anyone
def locale_from_headers():
    # eg en-GB,en-US;q=0.9,en;q=0.8
    locales = current_app.extensions["locales"]
    accept_header = request.headers.get("Accept-Language", "")
    weighted_lang = [token.strip().split(";q=") for token in accept_header.split(",")]
    sorted_lang = sorted(weighted_lang, key=lambda x:float(x[1]) if len(x)>1 else 1.0, reverse=True)
    for lang_q in sorted_lang:
        lang = lang_q[0]
        locale = "_".join(lang.split("-")[:2])
        if locale in locales:
            return locale
    return "en_GB"
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
