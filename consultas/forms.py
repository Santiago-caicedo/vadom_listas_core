# archivo: consultas/forms.py
from django import forms

class BusquedaForm(forms.Form):
    identificacion = forms.CharField(
        label='Número de Identificación',
        max_length=50,
        required=False, # Hacemos que no sea estrictamente requerido
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg', 
            'placeholder': 'Buscar por identificación...'
        })
    )
    nombres = forms.CharField(
        label='Nombres o Razón Social',
        max_length=150,
        required=False, # También opcional
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg', 
            'placeholder': 'Buscar por nombres...'
        })
    )

    # Añadimos una validación personalizada
    def clean(self):
        cleaned_data = super().clean()
        identificacion = cleaned_data.get("identificacion")
        nombres = cleaned_data.get("nombres")

        if not identificacion and not nombres:
            raise forms.ValidationError(
                "Debe proporcionar al menos un criterio de búsqueda: Identificación o Nombres.",
                code='required'
            )