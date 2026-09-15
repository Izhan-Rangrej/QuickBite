from django import forms
from django.core.validators import RegexValidator


class ContactForm(forms.Form):
    """Contact Us page form — emails the team via the configured backend."""

    name = forms.CharField(max_length=80, label='Your name')
    email = forms.EmailField(label='Email address')
    phone = forms.CharField(
        max_length=15, required=False, label='Phone (optional)',
        validators=[RegexValidator(r'^[6-9]\d{9}$',
                                   'Enter a valid 10-digit Indian mobile number.')])
    subject = forms.ChoiceField(choices=[
        ('order', 'Order issue'),
        ('restaurant', 'Partner with us / restaurant onboarding'),
        ('feedback', 'Feedback'),
        ('other', 'Something else'),
    ])
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 5}), max_length=2000)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'qb-input')
