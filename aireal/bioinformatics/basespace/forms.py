from limscore.forms import (Form,
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
                            MultiCheckboxInput)
from limscore.i18n import _

class SelectSamplesForm(Form):
    def definition(self):
        self.bssample_ids = MultiCheckboxInput("", required=_("No samples selected."), coerce=int)
