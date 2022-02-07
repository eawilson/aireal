#!/usr/bin/env python3

from setuptools import setup
import os

with open(os.path.join(os.path.dirname(__file__), "aireal", "version.py")) as f_in:
    exec(f_in.read())

setup(name="aireal",
    version= __version__,
    description="LIMS.",
    url="",
    author="Ed Wilson",
    author_email="edwardadrianwilson@yahoo.co.uk",
    license="MIT",
    packages=["aireal"],
    install_requires=["flask",
                      "passlib",
                      "itsdangerous",
                      "pytz",
                      "babel",
                      "pyqrcode",
                      "bcrypt",
                      "requests>=2.27.0",
                      "cryptography",
                      "boto3",
                      "psycopg2",
                      "pyvips",
                      "waitress",
                      "boto3"],
    entry_points = { "console_scripts":
        ["waitress_serve=aireal.scripts.waitress_serve:main",
         "bsauth=aireal.bioinformatics.basespace.bsauth:main"]},
    message_extractors = {"aireal":
        [("**.py", "python", None),
         ("**/templates/**.html", "jinja2.ext.autoescape,jinja2.ext.with_", None)]},
    include_package_data=True,
    zip_safe=True,
    )

