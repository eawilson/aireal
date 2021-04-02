from ..forms import (Form,
                    TextInput,
                    DirectoryInput,
                    SelectInput)
from ..i18n import _



class DirectoryUploadForm(Form):
    def definition(self):
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



class SlideForm(Form):
    def definition(self):
        self.name = TextInput("Name")
        self.site_id = SelectInput("Site")
        self.project_id = SelectInput("Project")

