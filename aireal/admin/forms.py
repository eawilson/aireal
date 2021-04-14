from ..i18n import _
from ..forms import (Form,
                     Input,
                     TextInput,
                     EmailInput,
                     MultiCheckboxInput,
                     SelectInput,
                     IntegerInput,
                     BooleanInput,
                     ActionForm,
                     NameForm)



class UserForm(Form):
    def definition(self):
        self.surname = TextInput(_("Surname"))
        self.forename = TextInput(_("Forename"))        
        self.email = EmailInput(_("Email"))
        self.groups = MultiCheckboxInput(_("Groups"), required=False)
        self.restricted = BooleanInput(_("Restrict Projects"), details=_("Only allow access to selected projects."), required=False)        
        self.projects = MultiCheckboxInput(_("Projects"), required=False)



class LocationForm(Form):
    def definition(self):
        self.locationmodel_id = SelectInput(_("Type"))
        self.name = TextInput(_("Name"))
        self.barcode = Input(_("Barcode"), required=False)



class ProjectForm(Form):
    def definition(self):
        self.name = TextInput(_("Name"))
        #self.subject_attr = TextInput(_("Subject Attributes"), required=False)
        #self.collection_attr = TextInput(_("Sample Attributes"), required=False)
        #self.pipeline_id = SelectInput(_("Default Pipeline"), required=False)
        #self.default_pipeline_options = TextInput(_("Default Pipeline Options"), required=False)



class LocationModelForm(Form):
    def definition(self):
        self.locationtype = SelectInput(_("Type"), coerce=str)
        self.name = TextInput(_("Name"))
        self.rows = IntegerInput(_("Rows"))
        self.columns = IntegerInput(_("Columns"))
        self.width = IntegerInput(_("Width (cm)"))
        self.length = IntegerInput(_("Length (cm)"))
        self.shelf_model_id = SelectInput(_("Shelf Model"))
        self.shelf_number = IntegerInput(_("Number of Shelves"))
        self.tray_model_id = SelectInput(_("Tray Model"))
        self.tray_number = IntegerInput(_("Number of Trays"))
        self.temperature = IntegerInput(_("Temperature (°C)"))



class NameBarcodeForm(Form):
    def definition(self):
        self.name = TextInput(_("Name"))
        self.barcode = Input(_("Barcode"), required=False)



