from django import forms
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy


class PasswordViewRestrictionForm(forms.Form):
    password = forms.CharField(label=gettext_lazy("Password"), widget=forms.PasswordInput)
    return_url = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        self.restriction = kwargs.pop('instance')
        super().__init__(*args, **kwargs)

    def clean_password(self):
        data = self.cleaned_data['password']
        if data != self.restriction.password:
            raise forms.ValidationError(_("The password you have entered is not correct. Please try again."))

        return data
