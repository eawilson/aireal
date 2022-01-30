from ...forms import (Form,
                    SelectInput)
from ...i18n import __ as _



#class SelectSamplesForm(Form):
    #def definition(self):
        #self.bssample_ids = MultiCheckboxInput("", required=_("No samples selected."), coerce=int)



class ServerForm(Form):
    def definition(self):
        self.bsserver_id = SelectInput(_("BaseSpace Region"))
