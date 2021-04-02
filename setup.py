from setuptools import setup

setup(name="aireal",
    version= "0.1",
    description="LIMS.",
    url="",
    author="Ed Wilson",
    author_email="edwardadrianwilson@yahoo.co.uk",
    license="MIT",
    packages=["aireal"],
    install_requires=["sqlalchemy",
                      "alembic",
                      "flask",
                      "passlib",
                      "itsdangerous",
                      "pytz",
                      "Babel",
                      "pyqrcode",
                      "bcrypt"],
    entry_points = { "console_scripts":
        ["waitress_serve=aireal.scripts.waitress_serve:main",
         "aireal_babel=aireal.scripts.aireal_babel:run_pybabel",
         "aireal_alembic=aireal.scripts.aireal_alembic:run_alembic"]},
    message_extractors = {"aireal":
        [("**.py", "python", None),
         ("**/templates/**.html", "jinja2.ext.autoescape,jinja2.ext.with_", None)]},
    include_package_data=True,
    zip_safe=True,
    )

