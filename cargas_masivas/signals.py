# archivo: cargas_masivas/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import LoteConsultaMasiva

# Nuevas importaciones
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags


@receiver(post_save, sender=LoteConsultaMasiva)
def notificar_cambio_lote(sender, instance, created, **kwargs):
    
    domain = settings.MI_DOMINIO
    logo_url = f'{settings.STATIC_URL}images/logo_vadom.png'

    if created:
        # ----- INICIO: Notificación al ADMIN (Esto ya lo teníamos) -----
        subject_admin = f'Nueva Solicitud de Carga Masiva - {instance.empresa.nombre}'
        context_admin = {'instance': instance, 'domain': domain, 'logo_url': logo_url}
        
        html_message_admin = render_to_string('cargas_masivas/emails/admin_notificacion.html', context_admin)
        plain_message_admin = strip_tags(html_message_admin)

        try:
            msg_admin = EmailMultiAlternatives(
                subject=subject_admin,
                body=plain_message_admin,
                from_email=settings.EMAIL_HOST_USER,
                to=[settings.ADMIN_EMAIL]
            )
            msg_admin.attach_alternative(html_message_admin, "text/html")
            msg_admin.send()
            print(f"Correo HTML de notificación enviado al admin por lote {instance.id}")
        except Exception as e:
            print(f"Error al enviar correo HTML al admin: {e}")
        # ----- FIN: Notificación al ADMIN -----


        # ----- INICIO: NUEVA Notificación al USUARIO (Confirmación) -----
        subject_user = f'Hemos recibido tu solicitud de Carga Masiva (ID: {instance.id})'
        context_user = {'instance': instance, 'domain': domain, 'logo_url': logo_url}

        html_message_user = render_to_string('cargas_masivas/emails/usuario_confirmacion.html', context_user)
        plain_message_user = strip_tags(html_message_user)

        try:
            msg_user = EmailMultiAlternatives(
                subject=subject_user,
                body=plain_message_user,
                from_email=settings.EMAIL_HOST_USER,
                to=[instance.usuario_solicitante.email] # Al usuario
            )
            msg_user.attach_alternative(html_message_user, "text/html")
            msg_user.send()
            print(f"Correo HTML de confirmación enviado al usuario {instance.usuario_solicitante.email}")
        except Exception as e:
            print(f"Error al enviar correo HTML de confirmación al usuario: {e}")
        # ----- FIN: NUEVA Notificación al USUARIO -----


    elif instance.estado == 'PROCESADO' and instance.archivo_resultado:
        # Notificar al USUARIO que su lote está listo (Esto ya lo teníamos)
        subject = f'Tu Reporte de Consulta Masiva (ID: {instance.id}) está Listo'
        
        context = {'instance': instance, 'domain': domain, 'logo_url': logo_url}
        
        html_message = render_to_string('cargas_masivas/emails/usuario_notificacion.html', context)
        plain_message = strip_tags(html_message)

        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=plain_message,
                from_email=settings.EMAIL_HOST_USER,
                to=[instance.usuario_solicitante.email]
            )
            msg.attach_alternative(html_message, "text/html")
            msg.send()
            print(f"Correo HTML de reporte listo enviado al usuario {instance.usuario_solicitante.email}")
        
        except Exception as e:
            print(f"Error al enviar correo HTML de reporte listo al usuario: {e}")