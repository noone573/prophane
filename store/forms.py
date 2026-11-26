import re
from decimal import Decimal

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import PropaneTank, SellerApplication, Store
from .validators import validate_document_upload, validate_image_upload

PHONE_RE = re.compile(r'^(\+639|09)\d{9}$')
TIN_RE = re.compile(r'^\d{3}-?\d{3}-?\d{3}(-?\d{3,5})?$')

MAX_PRICE = Decimal('100000')
MAX_STOCK = 10000


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=False, help_text='Optional. Used for order updates.')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


class SellerApplicationForm(forms.ModelForm):
    class Meta:
        model = SellerApplication
        fields = [
            'business_name',
            'business_address',
            'business_permit',
            'dti_certificate',
            'mayors_permit',
            'valid_id',
            'tin_number',
            'phone',
            'email',
        ]
        doc_attrs = {'accept': '.pdf,.jpg,.jpeg,.png'}
        widgets = {
            'business_name': forms.TextInput(attrs={'placeholder': 'e.g. Bayan Gas Supply', 'maxlength': 200}),
            'business_address': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Street, barangay, municipality'}),
            'business_permit': forms.FileInput(attrs=doc_attrs),
            'dti_certificate': forms.FileInput(attrs=doc_attrs),
            'mayors_permit': forms.FileInput(attrs=doc_attrs),
            'valid_id': forms.FileInput(attrs=doc_attrs),
            'tin_number': forms.TextInput(attrs={'placeholder': '000-000-000-000'}),
            'phone': forms.TextInput(attrs={'placeholder': '09XX XXX XXXX', 'inputmode': 'tel'}),
            'email': forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
        }
        labels = {
            'business_name': 'Business name',
            'business_address': 'Business address',
            'business_permit': 'Business permit',
            'dti_certificate': 'DTI certificate',
            'mayors_permit': "Mayor's permit",
            'valid_id': 'Government-issued ID',
            'tin_number': 'TIN',
            'phone': 'Contact number',
            'email': 'Email address',
        }
        help_texts = {
            'business_permit': 'Issued by your city or municipality.',
            'dti_certificate': 'Department of Trade and Industry registration, if you have one.',
            'mayors_permit': 'Optional.',
            'valid_id': 'Any valid government ID. Only reviewers can see it.',
        }

    def clean_business_name(self):
        return self.cleaned_data['business_name'].strip()

    def clean_phone(self):
        phone = re.sub(r'[\s-]', '', self.cleaned_data.get('phone') or '')
        if not PHONE_RE.match(phone):
            raise forms.ValidationError('Enter a Philippine mobile number, e.g. 09171234567 or +639171234567.')
        return phone

    def clean_tin_number(self):
        tin = (self.cleaned_data.get('tin_number') or '').strip()
        if tin and not TIN_RE.match(tin):
            raise forms.ValidationError('TIN should look like 000-000-000 or 000-000-000-000.')
        return tin or None

    def _clean_doc(self, field):
        upload = self.cleaned_data.get(field)
        if upload:
            validate_document_upload(upload)
        return upload

    def clean_business_permit(self):
        return self._clean_doc('business_permit')

    def clean_dti_certificate(self):
        return self._clean_doc('dti_certificate')

    def clean_mayors_permit(self):
        return self._clean_doc('mayors_permit')

    def clean_valid_id(self):
        return self._clean_doc('valid_id')


# Form field prefix for each tank type on the create-store form
TANK_FIELD_PREFIX = {
    'A/S Valve Gasul': 'as_valve',
    'POL Valve Gasul': 'pol_valve',
    'Price Gas': 'price_gas',
}


def _price_field(initial, label):
    return forms.DecimalField(
        max_digits=8, decimal_places=2, required=False, initial=initial,
        min_value=Decimal('1'), max_value=MAX_PRICE, label=label,
    )


def _stock_field(label):
    return forms.IntegerField(
        min_value=0, max_value=MAX_STOCK, required=False, initial=10, label=label,
    )


class StoreCreationForm(forms.ModelForm):
    tanks_to_sell = forms.MultipleChoiceField(
        choices=PropaneTank.TANK_TYPES,
        widget=forms.CheckboxSelectMultiple,
        label='Tanks you sell',
    )

    as_valve_price = _price_field(950, 'Price (₱)')
    as_valve_stock = _stock_field('Stock')
    pol_valve_price = _price_field(920, 'Price (₱)')
    pol_valve_stock = _stock_field('Stock')
    price_gas_price = _price_field(880, 'Price (₱)')
    price_gas_stock = _stock_field('Stock')

    class Meta:
        model = Store
        fields = ['name', 'description', 'owner_photo', 'latitude', 'longitude']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Juan\'s LPG Center'}),
            'description': forms.Textarea(attrs={'rows': 3, 'maxlength': 500}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'owner_photo': forms.FileInput(attrs={'accept': 'image/jpeg,image/png'}),
        }
        labels = {
            'name': 'Store name',
            'owner_photo': 'Your photo',
        }
        help_texts = {
            'owner_photo': 'A clear photo of you, shown to customers. JPG or PNG, up to 5 MB.',
        }

    def clean_name(self):
        return self.cleaned_data['name'].strip()

    def clean_description(self):
        return (self.cleaned_data.get('description') or '').strip()[:500]

    def clean_owner_photo(self):
        photo = self.cleaned_data.get('owner_photo')
        if not photo:
            raise forms.ValidationError('Please upload a photo of yourself.')
        validate_image_upload(photo)
        return photo

    def clean_latitude(self):
        lat = self.cleaned_data.get('latitude')
        if lat is None or not -90 <= lat <= 90:
            raise forms.ValidationError('Pick your store location on the map.')
        return lat

    def clean_longitude(self):
        lng = self.cleaned_data.get('longitude')
        if lng is None or not -180 <= lng <= 180:
            raise forms.ValidationError('Pick your store location on the map.')
        return lng

    def clean(self):
        cleaned = super().clean()
        for tank_type in cleaned.get('tanks_to_sell', []):
            prefix = TANK_FIELD_PREFIX[tank_type]
            if not cleaned.get(f'{prefix}_price'):
                self.add_error(f'{prefix}_price', 'Enter a price for this tank.')
            if cleaned.get(f'{prefix}_stock') is None:
                self.add_error(f'{prefix}_stock', 'Enter the stock for this tank.')
        return cleaned

    def tank_rows(self):
        """Selected tank types with their (price, stock), for the view to save."""
        return [
            (tank_type,
             self.cleaned_data[f'{TANK_FIELD_PREFIX[tank_type]}_price'],
             self.cleaned_data[f'{TANK_FIELD_PREFIX[tank_type]}_stock'])
            for tank_type in self.cleaned_data['tanks_to_sell']
        ]

    def tank_sections(self):
        """(tank type, price field, stock field) for the template."""
        return [
            (tank_type, self[f'{prefix}_price'], self[f'{prefix}_stock'])
            for tank_type, prefix in TANK_FIELD_PREFIX.items()
        ]
