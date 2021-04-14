from .i18n import _
from .lib.forms import (Form,
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



class TwoFactorForm(Form):
    def definition(self):
        self.secret = HiddenInput()



class LoginForm(Form):
    def definition(self):
        self.email = EmailInput(_("Email"))
        self.password = PasswordInput(_("Password"))
        self.authenticator = IntegerInput(_("Authenticator Code"))
        self.timezone = HiddenInput("", required=False)



class ChangePasswordForm(Form):
    def definition(self):        
        self.old_password = PasswordInput(_("Old Password"), autocomplete="new-password")
        self.password1 = PasswordInput(_("New Password"), autocomplete="new-password")
        self.password2 = PasswordInput(_("New Password"), autocomplete="new-password")

    def validate(self):
        if super().validate() and self.password1.data != self.password2.data:
            self.password1.errors = _("Passwords must match.")
        return not self.errors



class ReorderForm(Form):
    def definition(self):
        self.order = HiddenInput(required=False)



class ActionForm(Form):
    def definition(self):
        self.action = HiddenInput(required=True)



class NameForm(Form):
    def definition(self):
        self.name = TextInput(_("Name"))


