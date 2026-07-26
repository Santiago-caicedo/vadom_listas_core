from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0002_empresa_cupo'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='empresa',
            name='mes_alerta_cupo',
        ),
    ]
