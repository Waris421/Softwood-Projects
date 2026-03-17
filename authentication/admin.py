from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from django.contrib.auth.admin import UserAdmin
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.shortcuts import render, redirect

class UserCreationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super(UserCreationForm, self).__init__(*args, **kwargs)
        self.fields['password1'].required = False
        self.fields['password2'].required = False

        self.fields['password1'].widget.attrs['autocomplete'] = 'off'
        self.fields['password2'].widget.attrs['autocomplete'] = 'off'
    
    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if bool(password1) ^ bool(password2):
            raise forms.ValidationError("Fill out both fields")
        
        return password2

class AddUsersToGroupForm(forms.Form):
    group = forms.ModelChoiceField(queryset=Group.objects.all(), label="Select Group")

User = get_user_model()

@admin.action(description='Add selected users to a group')
def AddUsersToGroupAction(modeladmin,request, queryset):
    if 'apply' in request.POST:
        form = AddUsersToGroupForm(request.POST)
        if form.is_valid():
            group = form.cleaned_data['group']
            for user in queryset:
                user.groups.add(group)
            modeladmin.message_user(request, f"Successfully added {queryset.count()} users to {group.name}.")
            return redirect(request.get_full_path())
    else:
        form = AddUsersToGroupForm()
        return render(request, 'admin/add_to_group.html', {
            'users': queryset,
            'form': form,
            'title': 'Choose a group'
        })

class UserAdmin(UserAdmin):
    actions = [AddUsersToGroupAction]

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