from ..i18n import _
from ..forms import (Form,
                        Input,
                        TextInput,
                        TextAreaInput,
                        HiddenInput,
                        PasswordInput,
                        NameInput,
                        TextNumberInput,
                        LowerCaseInput,
                        EmailInput,
                        IntegerInput,
                        DecimalInput,
                        NHSNumberInput,
                        DateInput,
                        PastDateInput,
                        BooleanInput,
                        SelectInput,
                        MultiSelectInput,
                        MultiCheckboxInput,
                        FileInput,
                        DirectoryInput)



class UserForm(Form):
    def definition(self):
        self.surname = TextInput(_("Surname"))
        self.forename = TextInput(_("Forename"))        
        self.email = EmailInput(_("Email"))
        self.groups = MultiCheckboxInput(_("Groups"), required=False)
        self.sites = MultiCheckboxInput(_("Sites"), required=False)
        self.restricted = BooleanInput(_("Restrict Projects"), details=_("Only allow access to selected projects."), required=False)        
        self.projects = MultiCheckboxInput(_("Projects"), required=False)



class SiteForm(Form):
    def definition(self):
        self.name = TextInput(_("Name"))



class ProjectForm(Form):
    def definition(self):
        self.name = TextInput(_("Name"))
        #self.subject_attr = TextInput(_("Subject Attributes"), required=False)
        #self.collection_attr = TextInput(_("Sample Attributes"), required=False)
        #self.pipeline_id = SelectInput(_("Default Pipeline"), required=False)
        #self.default_pipeline_options = TextInput(_("Default Pipeline Options"), required=False)



