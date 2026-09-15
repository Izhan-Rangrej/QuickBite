from django import forms

from core.models import Category, Coupon, Dish, Restaurant

INPUT = 'qb-input'


class _StyledForm(forms.ModelForm):
    """Give every widget the dashboard's form styling."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect)):
                field.widget.attrs['class'] = (css + ' qb-check').strip()
            else:
                field.widget.attrs['class'] = (css + f' {INPUT}').strip()


class RestaurantForm(_StyledForm):
    class Meta:
        model = Restaurant
        fields = ['name', 'image', 'description', 'address', 'phone', 'cuisine_type',
                  'rating', 'delivery_time', 'min_order', 'offer_text',
                  'opening_time', 'closing_time', 'latitude', 'longitude',
                  'owner', 'is_promoted', 'is_active']
        widgets = {
            'opening_time': forms.TimeInput(attrs={'type': 'time'}),
            'closing_time': forms.TimeInput(attrs={'type': 'time'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class DishForm(_StyledForm):
    class Meta:
        model = Dish
        fields = ['name', 'image', 'description', 'price', 'discount_price',
                  'restaurant', 'category', 'preparation_time', 'rating',
                  'is_veg', 'is_bestseller', 'is_new', 'is_available']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['restaurant'].queryset = Restaurant.objects.all().order_by('name')
        self.fields['category'].queryset = Category.objects.all().order_by('name')


class CategoryForm(_StyledForm):
    class Meta:
        model = Category
        fields = ['name', 'image', 'description', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}


class CouponForm(_StyledForm):
    class Meta:
        model = Coupon
        fields = ['code', 'title', 'description', 'discount_percentage',
                  'discount_amount', 'min_order_amount', 'max_discount',
                  'usage_limit', 'valid_from', 'valid_until', 'is_active']
        widgets = {
            'valid_from': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'valid_until': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('discount_percentage') and not cleaned.get('discount_amount'):
            raise forms.ValidationError('Set either a percentage or a flat discount amount.')
        return cleaned
