from ..i18n import __ as _
from ..forms import (Form,
                     Input,
                     TextInput,
                     EmailInput,
                     MultiCheckboxInput,
                     SelectInput,
                     IntegerInput,
                     FloatInput,
                     BooleanInput,
                     ActionForm,
                     NameForm)



class UserForm(Form):
    def definition(self):
        self.surname = TextInput(_("Surname"))
        self.forename = TextInput(_("Forename"))        
        self.email = EmailInput(_("Email"))
        self.role = MultiCheckboxInput(_("Roles"), coerce=str, required=False)
        self.project = MultiCheckboxInput(_("Projects"), required=False)



class LocationForm(Form):
    def definition(self):
        self.name = TextInput(_("Name"))
        self.barcode = Input(_("Barcode"), required=False)
        self.locationtype = SelectInput(_("Type"), coerce=str, _class="get-dynamic-fields")
        self.locationmodel_id = SelectInput(_("Model"))



class ProjectForm(Form):
    def definition(self):
        self.name = TextInput(_("Name"))
        #self.subject_attr = TextInput(_("Subject Attributes"), required=False)
        #self.collection_attr = TextInput(_("Sample Attributes"), required=False)
        #self.pipeline_id = SelectInput(_("Default Pipeline"), required=False)
        #self.default_pipeline_options = TextInput(_("Default Pipeline Options"), required=False)



class LocationModelForm(Form):
    def definition(self):
        self.name = TextInput(_("Name"))
        self.locationtype = SelectInput(_("Type"), coerce=str, _class="get-dynamic-fields")
        
        self.temperature = IntegerInput(_("Temperature (°C)"))

        self.shelves = IntegerInput(_("Shelves"))
        self.shelf_width = IntegerInput(_("Shelf Width (cm)"))
        self.shelf_depth = IntegerInput(_("Shelf Depth (cm)"))

        self.trays = IntegerInput(_("Trays"))
        self.boxes = IntegerInput(_("Boxes per Tray"))
 
        
        self.rows = IntegerInput(_("Rows"))
        self.columns = IntegerInput(_("Columns"))
        
        self.width = IntegerInput(_("Width (cm)"))
        self.depth = IntegerInput(_("Depth (cm)"))
        
        self.material = SelectInput(_("Material"))
        self.volume = FloatInput(_("Volume (ml)"))



class NameBarcodeForm(Form):
    def definition(self):
        self.name = TextInput(_("Name"))
        self.barcode = Input(_("Barcode"), required=False)



    
    
    
    
    
    
    
    
    
    
    
    
    
