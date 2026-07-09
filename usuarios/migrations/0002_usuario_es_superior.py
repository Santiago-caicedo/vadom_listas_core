# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='es_superior',
            field=models.BooleanField(
                default=False,
                help_text='Permite ver métricas y consultas de todos los usuarios de la empresa.',
                verbose_name='Superior de empresa'
            ),
        ),
    ]
