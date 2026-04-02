from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.utils.crypto import get_random_string
from django.contrib.auth.admin import UserAdmin
from django import forms
from django.contrib.auth.forms import UserCreationForm

class UserCreationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super(UserCreationForm, self).__init__(*args, **kwargs)
        self.fields['password1'].required = False
        self.fields['password2'].required = False

        self.fields['password1'].widget.attrs['autocomplete'] = 'off'
        self.fields['password2'].widget.attrs['autocomplete'] = 'off'
    
    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = super(UserCreationForm, self).clean_password2()

        if bool(password1) ^ bool(password2):
            raise forms.ValidationError("Fill out both fields")
        
        return password2

User = get_user_model()

class UserAdmin(UserAdmin):
    add_form = UserCreationForm

    add_fieldsets = (
        (None, {
            'description': (
                "Enter the new user's name and email address and click save."
            ),
            'fields': ('email', 'username','first_name', 'last_name'),
        }),
        ('Password', {
            'description': "Optionally, you may set the user's password here.",
            'fields': ('password1', 'password2'),
            'classes': ('collapse', 'collapse-closed'),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change and (not form.cleaned_data['password1'] or not obj.has_usable_password()):
            obj.set_password(get_random_string(8))

        super(UserAdmin, self).save_model(request, obj, form, change)

admin.site.unregister(User)
admin.site.register(User, UserAdmin)