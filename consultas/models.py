# archivo: consultas/models.py

from django.db import models
from usuarios.models import Usuario

class Busqueda(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='busquedas')
    termino_buscado = models.CharField(max_length=100)
    fecha_busqueda = models.DateTimeField(auto_now_add=True)
    encontro_resultados = models.BooleanField(default=False)
    genero_alerta = models.BooleanField(default=False)

    # --- Consulta de procesos judiciales (Rama Judicial / CPNU) ---
    # Estado de esa consulta, que es independiente de la de listas restrictivas:
    #   'no_consultado' -> no se intentó (no se dio nombre, o el cliente la tiene apagada)
    #   'ok'            -> se consultó bien (ver procesos_judiciales; puede ser 0)
    #   'no_disponible' -> la Rama estaba caída / no se pudo consultar
    # Igual que con el webservice de listas, "no disponible" NUNCA se muestra como
    # "sin procesos": son cosas distintas y confundirlas es un falso negativo.
    JUDICIAL_ESTADOS = [
        ('no_consultado', 'No consultado'),
        ('ok', 'Consultado'),
        ('no_disponible', 'No disponible'),
    ]
    judicial_estado = models.CharField(
        max_length=20, choices=JUDICIAL_ESTADOS, default='no_consultado'
    )
    # Cuántos procesos dijo la Rama que existen para ese nombre. Puede ser mayor
    # que los guardados, porque solo traemos las primeras CPNU_MAX_PAGINAS páginas.
    # Se guarda para poder avisar "mostrando X de Y" en vez de truncar en silencio.
    judicial_total_reportado = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Búsqueda de '{self.termino_buscado}' por {self.usuario.username}"

class TextoSaneadoMixin:
    """
    Blindaje contra datos malformados de los servicios externos.

    Dos problemas reales vistos en producción:
      - Caracteres NUL (0x00) en el texto: PostgreSQL los rechaza y el
        INSERT tumba la consulta entera con un error 500.
      - Textos más largos que la columna: mismo efecto.

    Antes que perder la consulta del analista, se guarda el dato saneado.
    Lo usan los modelos que guardan datos que vienen de un tercero
    (el webservice de listas y la API de la Rama Judicial).
    """

    def save(self, *args, **kwargs):
        for campo in self._meta.fields:
            if not isinstance(campo, (models.CharField, models.TextField)):
                continue
            valor = getattr(self, campo.attname, None)
            if not isinstance(valor, str):
                continue
            limpio = valor.replace('\x00', '')
            if campo.max_length:
                limpio = limpio[:campo.max_length]
            if limpio != valor:
                setattr(self, campo.attname, limpio)
        super().save(*args, **kwargs)


class Resultado(TextoSaneadoMixin, models.Model):
    # Relación con la búsqueda a la que pertenece
    busqueda = models.ForeignKey(Busqueda, related_name='resultados', on_delete=models.CASCADE)
    
    # Campos originales del API
    nombre_completo = models.CharField(max_length=255, null=True, blank=True)
    identificacion = models.CharField(max_length=50, null=True, blank=True) # Mapeado desde 'Id' del API
    tipo_lista = models.CharField(max_length=100, null=True, blank=True)
    origen_lista = models.CharField(max_length=100, null=True, blank=True)
    relacionado_con = models.TextField(null=True, blank=True) # Descripción principal
    fuente = models.CharField(max_length=255, null=True, blank=True)
    es_restrictiva = models.BooleanField(default=False) # Campo 'Restrictiva' del API
    
    # Campos adicionales identificados en los PDFs
    es_boletin = models.BooleanField(default=False) # Campo 'Boletin' del API
    alias = models.CharField(max_length=255, null=True, blank=True) # Campo 'Aka' del API
    coincidencia_nombre = models.IntegerField(default=0) # Campo 'CoincidenciaNombre' del API
    coincidencia_id = models.IntegerField(default=0) # Campo 'CoincidenciaID' del API
    tipo_persona = models.CharField(max_length=50, null=True, blank=True) # Campo 'Tipo_Persona' del API
    
    # Campos de la guía SIDIF (Página 41) - Opcionales pero útiles
    fecha_update = models.CharField(max_length=100, null=True, blank=True) # Formato /Date(...)/
    estado = models.CharField(max_length=100, null=True, blank=True) # Ej: INGRESA LISTA: 20160801
    llaveimagen = models.CharField(max_length=255, null=True, blank=True) # Sub-clasificación
    
    # Campo para nuestra clasificación interna
    clasificacion = models.CharField(max_length=20, default='No Clasificado') # Opciones: Rojo, Amarillo, PEP's

    def __str__(self):
        return f"Resultado para {self.nombre_completo or 'Desconocido'} ({self.identificacion or 'N/A'})"
class ProcesoJudicial(TextoSaneadoMixin, models.Model):
    """
    Proceso judicial encontrado en la Rama Judicial (CPNU) para una búsqueda.
    La API busca por NOMBRE (no por cédula) y no devuelve documento, por lo que
    estos resultados son INFORMATIVOS y pueden incluir homónimos.
    """
    busqueda = models.ForeignKey(
        Busqueda, related_name='procesos_judiciales', on_delete=models.CASCADE
    )

    # Campos que devuelve la búsqueda por nombre (endpoint NombreRazonSocial)
    id_proceso = models.CharField(max_length=30, null=True, blank=True)       # idProceso
    radicado = models.CharField(max_length=40, null=True, blank=True)         # llaveProceso
    fecha_proceso = models.CharField(max_length=40, null=True, blank=True)    # fechaProceso (ISO)
    fecha_ultima_actuacion = models.CharField(max_length=40, null=True, blank=True)
    despacho = models.CharField(max_length=255, null=True, blank=True)
    departamento = models.CharField(max_length=120, null=True, blank=True)
    sujetos_procesales = models.TextField(null=True, blank=True)              # Demandante/Demandado…
    es_privado = models.BooleanField(default=False)

    # Categoría deducida del despacho (Penal, Administrativo, Civil, …).
    # 'Penal' es la de mayor relevancia para LAFT.
    categoria = models.CharField(max_length=20, default='Otro')

    class Meta:
        ordering = ['-fecha_proceso']

    def __str__(self):
        return f"Proceso {self.radicado or 'N/A'} (búsqueda #{self.busqueda_id})"
