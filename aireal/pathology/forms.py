from ..forms import (Form,
                    TextInput,
                    DirectoryInput,
                    SelectInput)
from ..i18n import __ as _



class DirectoryUploadForm(Form):
    def definition(self):
        #self.project_id = SelectInput(_("Project"))
        #self.pathology_site_id = SelectInput(_("Site"))
        self.files = DirectoryInput(_("Select Slide Folder to Upload"), required=False)



class AjaxForm(Form):
    def definition(self):
        self.timestamp = TextInput(required=False)
        self.path = TextInput()
        self.md5 = TextInput()



class CompletionForm(Form):
    def definition(self):
        self.timestamp = TextInput()
        self.directory = TextInput()
        #self.project_id = SelectInput(_("Site"))
        #self.pathology_site_id = SelectInput(_("Site"))



class SlideForm(Form):
    def definition(self):
        self.name = TextInput(_("Name"))
        self.pathologysite_id = SelectInput(_("Site"))
        self.clinical_details = TextInput(_("Clinical Details"))
