from .views import app

from ..logic import loggable, joins


loggable["pathology_locations"] = ["name"]
loggable["slides"] = ["site", "status", "name", "project", "attr"]

