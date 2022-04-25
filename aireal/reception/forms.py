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



class SubjectForm(Form):
    def definition(self):
        self.project_id = SelectInput(_("Project"), _class="get-dynamic-fields")
        self.surname = TextInput(_("Surname"))
        self.forename = TextInput(_("Forename"))
        self.date_of_birth = TextInput(_("Date of Birth"))
        self.medical_records_number = TextInput(_("Medical Record Number"))
        self.nhs_number = TextInput(_("NHS Number"))
        self.study_id = TextInput(_("Study ID"))
        self.screening_id = TextInput(_("Screening ID"))
        self.pre_screening_id = TextInput(_("Pre-screening ID"))
        self.initials = TextInput(_("Initials"))









