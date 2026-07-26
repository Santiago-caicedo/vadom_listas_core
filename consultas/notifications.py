# archivo: consultas/notifications.py

import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from usuarios.models import Usuario

logger = logging.getLogger(__name__)


def notificar_superiores_hallazgo(busqueda):
    """
    Envía email a los superiores de la empresa cuando una búsqueda encuentra resultados.
    No lanza excepciones para no interrumpir el flujo de la búsqueda.
    """
    try:
        empresa = busqueda.usuario.empresa
        if not empresa:
            return

        # Obtener superiores de la empresa con email
        superiores = Usuario.objects.filter(
            empresa=empresa,
            es_superior=True,
            is_active=True,
        ).exclude(email='')

        emails_destino = list(superiores.values_list('email', flat=True))
        if not emails_destino:
            return

        # Estadísticas de los resultados
        resultados = busqueda.resultados.all()
        total = resultados.count()
        restrictivas = resultados.filter(es_restrictiva=True).count()
        boletines = resultados.filter(es_boletin=True).count()

        clasificaciones = []
        if resultados.filter(clasificacion='Rojo').exists():
            clasificaciones.append('Rojo')
        if resultados.filter(clasificacion='Amarillo').exists():
            clasificaciones.append('Amarillo')
        if resultados.filter(clasificacion="PEP's").exists():
            clasificaciones.append("PEP's")

        nombre_usuario = busqueda.usuario.get_full_name() or busqueda.usuario.username
        link_expediente = f"{settings.MI_DOMINIO}/gestion/consultas/{busqueda.id}/"

        context = {
            'busqueda': busqueda,
            'nombre_usuario': nombre_usuario,
            'total_resultados': total,
            'restrictivas': restrictivas,
            'boletines': boletines,
            'clasificaciones': clasificaciones,
            'link_expediente': link_expediente,
            'empresa': empresa,
        }

        asunto = (
            f"[Alerta LAFT] Hallazgo en consulta de "
            f"{nombre_usuario} - {busqueda.termino_buscado}"
        )

        html_content = render_to_string('consultas/email_hallazgo.html', context)
        text_content = strip_tags(html_content)

        email = EmailMultiAlternatives(
            subject=asunto,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=emails_destino,
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)

        logger.info(
            "Email de hallazgo enviado a %d superiores de %s (búsqueda #%d)",
            len(emails_destino), empresa.nombre, busqueda.id,
        )

    except Exception:
        logger.exception(
            "Error al enviar notificación de hallazgo (búsqueda #%s)",
            getattr(busqueda, 'id', '?'),
        )


def notificar_exceso_cupo(empresa, consultas_hechas):
    """
    Avisa por email (al correo configurado en .env) que una empresa superó su
    cupo mensual. Best-effort: nunca interrumpe la búsqueda.
    """
    try:
        if not getattr(settings, 'NOTIFICAR_EXCESO_CUPO', True):
            return
        destino = getattr(settings, 'EMAIL_ALERTA_CUPO', '') or getattr(settings, 'ADMIN_EMAIL', '')
        if not destino:
            return
        from django.core.mail import send_mail
        asunto = f"[Cupo excedido] {empresa.nombre} superó su cupo de consultas"
        cuerpo = (
            f"La empresa '{empresa.nombre}' superó su cupo mensual de consultas.\n\n"
            f"Cupo contratado: {empresa.limite_consultas_mensual}\n"
            f"Consultas realizadas este mes: {consultas_hechas}\n"
            f"Sistema: {getattr(settings, 'MI_DOMINIO', '')}\n"
        )
        send_mail(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, [destino], fail_silently=False)
        logger.info("Aviso de exceso de cupo enviado a %s (empresa %s, %s consultas)",
                    destino, empresa.nombre, consultas_hechas)
    except Exception:
        logger.exception("Error enviando aviso de exceso de cupo (empresa %s)",
                         getattr(empresa, 'nombre', '?'))
