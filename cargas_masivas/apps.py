from django.apps import AppConfig


class CargasMasivasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cargas_masivas'


    def ready(self):
        import cargas_masivas.signals
