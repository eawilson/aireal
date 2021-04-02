from limscore.forms import (Form,
                            HiddenInput,
                            TextInput,
                            DirectoryInput)
from limscore.i18n import _



class SelectSamplesForm(Form):
    def definition(self):
        self.files = DirectoryInput(_("Select Run Folder to Upload"))
        self.sizes = HiddenInput("")
