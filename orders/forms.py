from django import forms

from .models import Address


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ('full_name', 'phone', 'address_line1', 'address_line2',
                  'landmark', 'city', 'state', 'pincode',
                  'address_type', 'is_default')
        widgets = {
            'address_type': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'full_name': 'Full name',
            'phone': '+91 98765 43210',
            'address_line1': 'Flat / house no. / street',
            'address_line2': 'Area / sector (optional)',
            'landmark': 'Nearby landmark (optional)',
            'city': 'City',
            'state': 'State',
            'pincode': '6-digit PIN',
        }
        for name, field in self.fields.items():
            field.widget.attrs.setdefault('class', 'qb-input')
            if name not in ('address_type', 'is_default'):
                field.widget.attrs['placeholder'] = placeholders.get(name, '')

    def clean_pincode(self):
        pincode = self.cleaned_data['pincode'].strip()
        if not (pincode.isdigit() and len(pincode) == 6):
            raise forms.ValidationError('PIN code must be exactly 6 digits.')
        return pincode

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        digits = ''.join(ch for ch in phone if ch.isdigit())
        if len(digits) < 10:
            raise forms.ValidationError('Enter a valid phone number (10+ digits).')
        return phone
