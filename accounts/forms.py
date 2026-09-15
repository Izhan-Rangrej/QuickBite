from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User

INPUT_ATTRS = {'class': 'qb-input', 'placeholder': ''}


class SignupForm(UserCreationForm):
    """Username, email, phone + the two passwords. Styled widgets for the theme."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
    )
    phone_number = forms.CharField(
        max_length=20, required=True,
        widget=forms.TextInput(attrs={'placeholder': '+91 98765 43210'}),
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'phone_number', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'username': 'e.g. foodlover99',
            'password1': 'Create a password',
            'password2': 'Repeat your password',
        }
        for name, field in self.fields.items():
            field.widget.attrs.setdefault('class', 'qb-input')
            field.widget.attrs['placeholder'] = placeholders.get(name, '')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.phone_number = self.cleaned_data['phone_number']
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """AuthenticationForm + 'Remember me' checkbox."""

    remember_me = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update(
            {'class': 'qb-input', 'placeholder': 'Username'})
        self.fields['password'].widget.attrs.update(
            {'class': 'qb-input', 'placeholder': 'Password'})


class ProfileForm(forms.ModelForm):
    """Edit profile + delivery address + avatar."""

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone_number',
                  'date_of_birth', 'profile_picture',
                  'address', 'city', 'pincode')
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'first_name': 'First name', 'last_name': 'Last name',
            'email': 'you@example.com', 'phone_number': '+91 98765 43210',
            'address': 'Flat / street / landmark', 'city': 'City',
            'pincode': '6-digit PIN code',
        }
        for name, field in self.fields.items():
            field.widget.attrs.setdefault('class', 'qb-input')
            if name != 'profile_picture':
                field.widget.attrs['placeholder'] = placeholders.get(name, '')

    def clean_pincode(self):
        pincode = self.cleaned_data.get('pincode', '').strip()
        if pincode and not (pincode.isdigit() and len(pincode) == 6):
            raise forms.ValidationError('PIN code must be exactly 6 digits.')
        return pincode
