"""
Tests de la lógica anti-falso-negativo del webservice de listas (ConsultaListasPeps).

Regla de negocio crítica (LAFT):
  - Si el servicio FALLA (de la forma que sea) -> NO se debe guardar la búsqueda
    ni mostrar "sin coincidencias". Se avisa "servicio no disponible".
  - Solo si el servicio RESPONDE (aunque sea vacío) se guarda la consulta.

Ejecutar:  python manage.py test consultas
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from consultas import services
from consultas.models import Busqueda
from empresas.models import Empresa

User = get_user_model()


class RealizarPeticionTests(TestCase):
    """La capa de servicios debe devolver None ante CUALQUIER falla,
    y una lista (posiblemente vacía) solo cuando el API respondió bien."""

    @patch('consultas.services.requests.get')
    def test_200_con_resultados_devuelve_lista(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            'MensajeError': '', 'Resultados': [{'NombreCompleto': 'X'}]
        }
        self.assertEqual(
            services._realizar_peticion('http://x'),
            [{'NombreCompleto': 'X'}],
        )

    @patch('consultas.services.requests.get')
    def test_200_sin_coincidencias_devuelve_lista_vacia(self, mock_get):
        # [] NO es None: sí se consultó, simplemente sin hallazgos.
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {'MensajeError': '', 'Resultados': []}
        self.assertEqual(services._realizar_peticion('http://x'), [])

    @patch('consultas.services.requests.get')
    def test_http_error_devuelve_none(self, mock_get):
        mock_get.return_value.status_code = 500
        mock_get.return_value.text = 'Internal Server Error'
        self.assertIsNone(services._realizar_peticion('http://x'))

    @patch('consultas.services.requests.get')
    def test_error_de_conexion_devuelve_none(self, mock_get):
        mock_get.side_effect = services.requests.exceptions.RequestException('caído')
        self.assertIsNone(services._realizar_peticion('http://x'))

    @patch('consultas.services.requests.get')
    def test_mensaje_error_del_api_devuelve_none(self, mock_get):
        # 200 OK pero con error de aplicación en 'MensajeError' -> falla, no falso negativo.
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            'MensajeError': 'Token inválido', 'Resultados': []
        }
        self.assertIsNone(services._realizar_peticion('http://x'))

    @patch('consultas.services.requests.get')
    def test_respuesta_no_json_devuelve_none(self, mock_get):
        # 200 pero el cuerpo no es JSON (mantenimiento/proxy) -> falla.
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.side_effect = ValueError('no es json')
        self.assertIsNone(services._realizar_peticion('http://x'))


class PaginaBusquedaFalloTests(TestCase):
    """La vista pagina_busqueda NO debe registrar un falso negativo si el servicio falla."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='clave-larga-123')
        self.client.force_login(self.user)
        self.url = reverse('pagina_busqueda')

    @patch('consultas.views.consultar_api_por_nombre', return_value=None)
    def test_servicio_caido_no_crea_busqueda(self, _mock):
        resp = self.client.post(self.url, {'nombres': 'JUAN PEREZ'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['servicio_no_disponible'])
        self.assertIsNone(resp.context['busqueda_obj'])
        self.assertEqual(Busqueda.objects.count(), 0)   # <- clave: NO se guardó nada

    @patch('consultas.views.consultar_api_por_nombre', return_value=[])
    def test_servicio_ok_sin_coincidencias_si_crea_busqueda(self, _mock):
        resp = self.client.post(self.url, {'nombres': 'JUAN PEREZ'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['servicio_no_disponible'])
        self.assertEqual(Busqueda.objects.count(), 1)
        self.assertFalse(Busqueda.objects.first().encontro_resultados)

    @override_settings(NOTIFICAR_HALLAZGOS=False)
    @patch('consultas.views.consultar_api_por_nombre')
    def test_servicio_ok_con_hallazgos_crea_busqueda_y_resultado(self, mock_api):
        mock_api.return_value = [{
            'NombreCompleto': 'JUAN PEREZ', 'Id': '123', 'Tipo_Lista': 'OFAC',
            'Restrictiva': True, 'CoincidenciaID': 100, 'CoincidenciaNombre': 90,
        }]
        resp = self.client.post(self.url, {'nombres': 'JUAN PEREZ'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['servicio_no_disponible'])
        self.assertEqual(Busqueda.objects.count(), 1)
        b = Busqueda.objects.first()
        self.assertTrue(b.encontro_resultados)
        self.assertTrue(b.genero_alerta)                 # Restrictiva=True
        self.assertEqual(b.resultados.count(), 1)
        self.assertEqual(b.resultados.first().clasificacion, 'Rojo')  # OFAC -> Rojo

    def test_requiere_login(self):
        self.client.logout()
        resp = self.client.post(self.url, {'nombres': 'JUAN PEREZ'})
        self.assertNotEqual(resp.status_code, 200)       # redirige al login
        self.assertEqual(Busqueda.objects.count(), 0)


class CupoYBloqueoTests(TestCase):
    """Cupo mensual por empresa: bloqueo manual corta; exceder solo avisa."""

    def setUp(self):
        self.empresa = Empresa.objects.create(nombre='ACME')
        self.user = User.objects.create_user(username='u1', password='clave-larga-123')
        self.user.empresa = self.empresa
        self.user.save()
        self.client.force_login(self.user)
        self.url = reverse('pagina_busqueda')

    @patch('consultas.views.consultar_api_por_nombre')
    def test_empresa_bloqueada_no_consulta_ni_guarda(self, mock_api):
        self.empresa.bloqueado = True
        self.empresa.save()
        resp = self.client.post(self.url, {'nombres': 'JUAN PEREZ'})
        self.assertTrue(resp.context['consultas_bloqueadas'])
        self.assertEqual(Busqueda.objects.count(), 0)
        mock_api.assert_not_called()   # ni siquiera consulta el API externo

    @patch('consultas.views.notificar_exceso_cupo')
    @patch('consultas.views.consultar_api_por_nombre', return_value=[])
    def test_cupo_excedido_avisa_pero_no_bloquea(self, _mock_api, mock_avisar):
        self.empresa.limite_consultas_mensual = 1
        self.empresa.save()
        # Ya hay 1 búsqueda este mes -> la nueva es la 2da y excede el cupo de 1.
        Busqueda.objects.create(usuario=self.user, termino_buscado='previa')
        resp = self.client.post(self.url, {'nombres': 'JUAN PEREZ'})
        self.assertTrue(resp.context['cupo_excedido'])
        self.assertEqual(Busqueda.objects.count(), 2)   # sí se guardó (solo avisa)
        mock_avisar.assert_called_once()                 # se envió el aviso por email

    @patch('consultas.views.notificar_exceso_cupo')
    @patch('consultas.views.consultar_api_por_nombre', return_value=[])
    def test_dentro_del_cupo_no_avisa(self, _mock_api, mock_avisar):
        self.empresa.limite_consultas_mensual = 5
        self.empresa.save()
        resp = self.client.post(self.url, {'nombres': 'JUAN PEREZ'})
        self.assertFalse(resp.context['cupo_excedido'])
        mock_avisar.assert_not_called()

    @patch('consultas.views.notificar_exceso_cupo')
    @patch('consultas.views.consultar_api_por_nombre', return_value=[])
    def test_cupo_cero_es_ilimitado(self, _mock_api, mock_avisar):
        self.empresa.limite_consultas_mensual = 0   # 0 = ilimitado
        self.empresa.save()
        for _ in range(3):
            self.client.post(self.url, {'nombres': 'JUAN PEREZ'})
        mock_avisar.assert_not_called()
