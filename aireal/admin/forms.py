from ..i18n import i18n_nop as _
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



class UserRoleForm(Form):
    def definition(self):
        self.role = MultiCheckboxInput(_("Roles"), coerce=str, required=False)



class UserProjectForm(Form):
    def definition(self):
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
        self.fastq_s3_path = TextInput(_("S3 path to fastqs"))
        self.fastq_command_line = TextInput(_("Command line for fastq analysis"))
        #self.subject_attr = TextInput(_("Subject Attributes"), required=False)
        #self.collection_attr = TextInput(_("Sample Attributes"), required=False)
        #self.pipeline_id = SelectInput(_("Default Pipeline"), required=False)
        #self.default_pipeline_options = TextInput(_("Default Pipeline Options"), required=False)



class ProjectIdentifierForm(Form):
    def definition(self):
        self.identifiertype_id = SelectInput(_("Identifier Type"), _class="get-dynamic-fields")
        self.required = BooleanInput(_("Required"), required=False)
        self.regex = TextInput(_("Regular Expression"), required=False)



class LocationModelForm(Form):
    def definition(self):
        self.name = TextInput(_("Name"))
        self.locationtype = SelectInput(_("Type"), coerce=str, _class="get-dynamic-fields")
        
        self.temperature = IntegerInput(_("Temperature"), units="temperature-celsius")
        
        self.shelves = IntegerInput(_("Shelves"), min_val=1)
        self.trays = IntegerInput(_("Trays"), min_val=1)
        self.rows = IntegerInput(_("Rows"), min_val=1)
        self.columns = IntegerInput(_("Columns"), min_val=1)

        self.volume = FloatInput(_("Volume"), units="volume-milliliter", frac_prec=1)



class NameBarcodeForm(Form):
    def definition(self):
        self.name = TextInput(_("Name"))
        self.barcode = Input(_("Barcode"), required=False)



    
    
    
    
    
    
    
    
    
    
    
    
    
