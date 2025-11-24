from django import forms
from .models import Store, PropaneTank
from .models import SellerApplication

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
            'email'
        ]
        widgets = {
            'business_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your business name'
            }),
            'business_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter complete business address'
            }),
            'business_permit': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png'
            }),
            'dti_certificate': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png'
            }),
            'mayors_permit': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png'
            }),
            'valid_id': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png'
            }),
            'tin_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'XXX-XXX-XXX-XXX'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+63 XXX XXX XXXX'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'your.email@example.com'
            }),
        }
        labels = {
            'business_name': 'Business Name *',
            'business_address': 'Complete Business Address *',
            'business_permit': 'Business Permit (PDF/Image) *',
            'dti_certificate': 'DTI Certificate (Optional)',
            'mayors_permit': "Mayor's Permit (Optional)",
            'valid_id': 'Valid Government ID *',
            'tin_number': 'TIN Number (Optional)',
            'phone': 'Contact Number *',
            'email': 'Email Address *',
        }
        help_texts = {
            'business_permit': 'Upload your business permit from the city/municipality',
            'dti_certificate': 'Department of Trade and Industry registration',
            'mayors_permit': 'Business permit from your local government',
            'valid_id': 'Any valid government-issued ID',
        }

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        # Basic Philippine phone number validation
        if phone and not (phone.startswith('+63') or phone.startswith('09')):
            raise forms.ValidationError('Please enter a valid Philippine phone number')
        return phone

    def clean_business_permit(self):
        permit = self.cleaned_data.get('business_permit')
        if permit:
            if permit.size > 5 * 1024 * 1024:  # 5MB limit
                raise forms.ValidationError('File size must not exceed 5MB')
        return permit


class ApplicationReviewForm(forms.ModelForm):
    """Form for admin to review applications"""
    class Meta:
        model = SellerApplication
        fields = ['status', 'rejection_reason']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'rejection_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Provide reason for rejection (if applicable)'
            }),
        }

class StoreCreationForm(forms.ModelForm):
    # Tank selection
    tanks_to_sell = forms.MultipleChoiceField(
        choices=PropaneTank.TANK_TYPES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Select tanks to sell"
    )
    
    # Initial prices and stock for each tank type
    as_valve_price = forms.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        required=False,
        initial=950,
        label="A/S Valve Gasul Price (₱)"
    )
    as_valve_stock = forms.IntegerField(
        min_value=0, 
        required=False,
        initial=10,
        label="A/S Valve Gasul Initial Stock"
    )
    
    pol_valve_price = forms.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        required=False,
        initial=920,
        label="POL Valve Gasul Price (₱)"
    )
    pol_valve_stock = forms.IntegerField(
        min_value=0, 
        required=False,
        initial=10,
        label="POL Valve Gasul Initial Stock"
    )
    
    price_gas_price = forms.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        required=False,
        initial=880,
        label="Price Gas Price (₱)"
    )
    price_gas_stock = forms.IntegerField(
        min_value=0, 
        required=False,
        initial=10,
        label="Price Gas Initial Stock"
    )
    
    class Meta:
        model = Store
        fields = ['name', 'description', 'owner_photo', 'latitude', 'longitude']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'owner_photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
        
    def clean_owner_photo(self):
        photo = self.cleaned_data.get('owner_photo')
        if not photo:
            raise forms.ValidationError("Owner photo is required. Please upload your photo.")
        
        # Check file size (limit to 5MB)
        if photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Image file too large ( > 5MB )")
        
        return photo
        
    def clean(self):
        cleaned_data = super().clean()
        tanks_to_sell = cleaned_data.get('tanks_to_sell', [])
        
        # Validate that prices and stock are provided for selected tanks
        for tank_type, _ in self.fields['tanks_to_sell'].choices:
            if tank_type in tanks_to_sell:
                if tank_type == 'A/S Valve Gasul':
                    if not cleaned_data.get('as_valve_price'):
                        self.add_error('as_valve_price', 'Price required for selected tank')
                    if cleaned_data.get('as_valve_stock') is None:
                        self.add_error('as_valve_stock', 'Stock required for selected tank')
                elif tank_type == 'POL Valve Gasul':
                    if not cleaned_data.get('pol_valve_price'):
                        self.add_error('pol_valve_price', 'Price required for selected tank')
                    if cleaned_data.get('pol_valve_stock') is None:
                        self.add_error('pol_valve_stock', 'Stock required for selected tank')
                elif tank_type == 'Price Gas':
                    if not cleaned_data.get('price_gas_price'):
                        self.add_error('price_gas_price', 'Price required for selected tank')
                    if cleaned_data.get('price_gas_stock') is None:
                        self.add_error('price_gas_stock', 'Stock required for selected tank')
        
        return cleaned_data


class TankUpdateForm(forms.ModelForm):
    class Meta:
        model = PropaneTank
        fields = ['stock', 'price', 'is_active']
        labels = {
            'is_active': 'Available for sale',
        }