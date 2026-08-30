# Consulta de procesos judiciales (Rama Judicial / CPNU).
# Migración aditiva: agrega campos con default y una tabla nueva; no toca datos existentes.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consultas', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='busqueda',
            name='judicial_estado',
            field=models.CharField(
                choices=[
                    ('no_consultado', 'No consultado'),
                    ('ok', 'Consultado'),
                    ('no_disponible', 'No disponible'),
                ],
                default='no_consultado',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='busqueda',
            name='judicial_total_reportado',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name='ProcesoJudicial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id_proceso', models.CharField(blank=True, max_length=30, null=True)),
                ('radicado', models.CharField(blank=True, max_length=40, null=True)),
                ('fecha_proceso', models.CharField(blank=True, max_length=40, null=True)),
                ('fecha_ultima_actuacion', models.CharField(blank=True, max_length=40, null=True)),
                ('despacho', models.CharField(blank=True, max_length=255, null=True)),
                ('departamento', models.CharField(blank=True, max_length=120, null=True)),
                ('sujetos_procesales', models.TextField(blank=True, null=True)),
                ('es_privado', models.BooleanField(default=False)),
                ('categoria', models.CharField(default='Otro', max_length=20)),
                ('busqueda', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='procesos_judiciales', to='consultas.busqueda')),
            ],
            options={
                'ordering': ['-fecha_proceso'],
            },
        ),
    ]
