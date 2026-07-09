# core_admin/forms.py
from django import forms
from cargas_masivas.models import LoteConsultaMasiva
from usuarios.models import Usuario
from empresas.models import Empresa


class UsuarioCreateForm(forms.ModelForm):
    """
    Formulario para crear un nuevo usuario desde el panel de admin.
    """
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='Mínimo 8 caracteres.'
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Usuario
        fields = ['username', 'email', 'first_name', 'last_name', 'empresa', 'es_superior', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'empresa': forms.Select(attrs={'class': 'form-select'}),
            'es_superior': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'username': 'Nombre de usuario',
            'email': 'Correo electrónico',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'empresa': 'Empresa',
            'es_superior': 'Superior de empresa',
            'is_active': 'Usuario activo',
        }

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        if password1 and len(password1) < 8:
            raise forms.ValidationError('La contraseña debe tener al menos 8 caracteres.')
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class UsuarioEditForm(forms.ModelForm):
    """
    Formulario para editar un usuario existente.
    La contraseña es opcional (solo se cambia si se llena).
    """
    password1 = forms.CharField(
        label='Nueva contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        help_text='Dejar en blanco para mantener la contraseña actual.'
    )
    password2 = forms.CharField(
        label='Confirmar nueva contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = Usuario
        fields = ['username', 'email', 'first_name', 'last_name', 'empresa', 'es_superior', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'empresa': forms.Select(attrs={'class': 'form-select'}),
            'es_superior': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'username': 'Nombre de usuario',
            'email': 'Correo electrónico',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'empresa': 'Empresa',
            'es_superior': 'Superior de empresa',
            'is_active': 'Usuario activo',
        }

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 or password2:
            if password1 != password2:
                raise forms.ValidationError('Las contraseñas no coinciden.')
            if len(password1) < 8:
                raise forms.ValidationError('La contraseña debe tener al menos 8 caracteres.')
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        password1 = self.cleaned_data.get('password1')
        if password1:
            user.set_password(password1)
        if commit:
            user.save()
        return user


class ProcesarLoteForm(forms.ModelForm):
    """
    Formulario para que el SuperAdmin procese un lote pendiente.
    Solo permite cambiar el estado y subir el archivo de resultado.
    """
    class Meta:
        model = LoteConsultaMasiva
        fields = ['estado', 'archivo_resultado']
        widgets = {
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'archivo_resultado': forms.FileInput(attrs={'class': 'form-control'}),
        }