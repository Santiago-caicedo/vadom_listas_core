# archivo: usuarios/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario

class CustomUserAdmin(UserAdmin):
    # ... (tu configuración de fieldsets, list_display, etc.) ...
    fieldsets = UserAdmin.fieldsets + (
        ('Información de la Empresa', {'fields': ('empresa',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información de la Empresa', {'fields': ('empresa',)}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'empresa')
    list_filter = UserAdmin.list_filter + ('empresa',)

admin.site.register(Usuario, CustomUserAdmin)