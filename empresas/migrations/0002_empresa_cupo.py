from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='limite_consultas_mensual',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='empresa',
            name='bloqueado',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='empresa',
            name='mes_alerta_cupo',
            field=models.CharField(blank=True, default='', max_length=7),
        ),
    ]
