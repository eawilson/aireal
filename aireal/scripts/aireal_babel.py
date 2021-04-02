import os
import subprocess

import aireal



def run_pybabel():
    package_path = os.path.dirname(aireal.__file__)
    locales_dir = os.path.join(package_path, "locales")
    
    if not(os.path.exists(locales_dir)):
        os.mkdir(locales_dir)
    
    pot_path = os.path.join(locales_dir, "aireal.pot")
    command = ["pybabel", "extract", "-o", pot_path, package_path]
    subprocess.run(command)
    
    for locale in os.listdir(locales_dir):
        locale_dir = os.path.join(locales_dir, locale)
        if os.path.isdir(locale_dir):
            po_path = os.path.join(locale_dir, "LC_MESSAGES", f"{locale}.po")
            command = ["pybabel",
                       "update" if os.path.exists(po_path) else "init", 
                       "-i", pot_path,
                       "-o", po_path,
                       "-l", locale]
            subprocess.run(command)



if _name__ == "__main__":
    run_pybabel()
