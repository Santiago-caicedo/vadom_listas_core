# archivo: cargas_masivas/forms.py

from django import forms
from .models import LoteConsultaMasiva

class LoteForm(forms.ModelForm):
    class Meta:
        model = LoteConsultaMasiva
        fields = ['archivo_subido']
        widgets = {
            'archivo_subido': forms.FileInput(attrs={'class': 'form-control', 'required': True})
        }