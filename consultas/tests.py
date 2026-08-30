"""
Tests de la lógica anti-falso-negativo del webservice de listas (ConsultaListasPeps)
y de la consulta de procesos judiciales (Rama Judicial / CPNU).

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

from consultas import services, services_judicial
from consultas.models import Busqueda, ProcesoJudicial
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


@override_settings(CONSULTAR_PROCESOS_JUDICIALES=False)
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


@override_settings(CONSULTAR_PROCESOS_JUDICIALES=False)
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

    @patch('consultas.views.notificar_exceso_cupo')
    @patch('consultas.views.consultar_api_por_nombre', return_value=[])
    def test_avisa_en_cada_consulta_excedida(self, _mock_api, mock_avisar):
        # Debe avisar en CADA consulta que exceda (no solo una vez al mes).
        self.empresa.limite_consultas_mensual = 1
        self.empresa.save()
        Busqueda.objects.create(usuario=self.user, termino_buscado='previa')  # base = 1 (en el límite)
        self.client.post(self.url, {'nombres': 'A'})   # consumo 2 -> excede -> aviso 1
        self.client.post(self.url, {'nombres': 'B'})   # consumo 3 -> excede -> aviso 2
        self.assertEqual(mock_avisar.call_count, 2)
def _respuesta_cpnu(payload, status=200, json_ok=True):
    """Arma un mock de respuesta de la Rama Judicial."""
    from unittest.mock import MagicMock
    resp = MagicMock()
    resp.status_code = status
    resp.headers = {'Content-Type': 'application/json' if json_ok else 'text/html'}
    resp.json.return_value = payload
    return resp


def _pagina(procesos, cantidad_paginas=1, cantidad_registros=None):
    return {
        'procesos': procesos,
        'paginacion': {
            'cantidadPaginas': cantidad_paginas,
            'cantidadRegistros': (len(procesos) if cantidad_registros is None
                                  else cantidad_registros),
        },
    }


class ServiciosJudicialesTests(TestCase):
    """La consulta a la Rama Judicial debe distinguir 'no se pudo consultar' (None)
    de 'no hay procesos' ([]), igual que el webservice de listas."""

    def setUp(self):
        # Sin esperas de backoff: los tests no deben tardar segundos.
        parche = patch('consultas.services_judicial.time.sleep')
        parche.start()
        self.addCleanup(parche.stop)

    @patch('consultas.services_judicial.requests.get')
    def test_respuesta_ok_devuelve_procesos_y_total(self, mock_get):
        mock_get.return_value = _respuesta_cpnu(
            _pagina([{'idProceso': 1, 'llaveProceso': '11001'}])
        )
        procesos, total = services_judicial.consultar_procesos_judiciales('JUAN PEREZ')
        self.assertEqual(len(procesos), 1)
        self.assertEqual(total, 1)

    @patch('consultas.services_judicial.requests.get')
    def test_sin_procesos_devuelve_lista_vacia(self, mock_get):
        # [] NO es None: sí se consultó, simplemente no hay procesos.
        mock_get.return_value = _respuesta_cpnu(_pagina([]))
        procesos, total = services_judicial.consultar_procesos_judiciales('JUAN PEREZ')
        self.assertEqual(procesos, [])
        self.assertEqual(total, 0)

    @patch('consultas.services_judicial.requests.get')
    def test_rama_caida_devuelve_none(self, mock_get):
        # 503 en la primera página -> None (no se pudo consultar).
        mock_get.return_value = _respuesta_cpnu(None, status=503)
        procesos, total = services_judicial.consultar_procesos_judiciales('JUAN PEREZ')
        self.assertIsNone(procesos)
        self.assertEqual(total, 0)

    @patch('consultas.services_judicial.requests.get')
    def test_error_de_conexion_devuelve_none(self, mock_get):
        mock_get.side_effect = services_judicial.requests.exceptions.RequestException('caído')
        procesos, _ = services_judicial.consultar_procesos_judiciales('JUAN PEREZ')
        self.assertIsNone(procesos)

    @patch('consultas.services_judicial.requests.get')
    def test_respuesta_no_json_devuelve_none(self, mock_get):
        # 200 pero el portal devolvió HTML (mantenimiento) -> no es un "sin procesos".
        mock_get.return_value = _respuesta_cpnu('<html>', json_ok=False)
        procesos, _ = services_judicial.consultar_procesos_judiciales('JUAN PEREZ')
        self.assertIsNone(procesos)

    def test_nombre_muy_corto_no_consulta(self):
        # La API exige mínimo 3 caracteres; no vale la pena molestarla.
        self.assertEqual(
            services_judicial.consultar_procesos_judiciales('AB'), (None, 0)
        )

    @patch('consultas.services_judicial.requests.get')
    def test_recorre_todas_las_paginas(self, mock_get):
        mock_get.side_effect = [
            _respuesta_cpnu(_pagina([{'idProceso': 1}], cantidad_paginas=2, cantidad_registros=2)),
            _respuesta_cpnu(_pagina([{'idProceso': 2}], cantidad_paginas=2, cantidad_registros=2)),
        ]
        procesos, total = services_judicial.consultar_procesos_judiciales('JUAN PEREZ')
        self.assertEqual(len(procesos), 2)
        self.assertEqual(total, 2)

    @patch('consultas.services_judicial.CPNU_MAX_PAGINAS', 1)
    @patch('consultas.services_judicial.requests.get')
    def test_trunca_pero_reporta_el_total_real(self, mock_get):
        # Con el tope de páginas solo traemos una parte: el total de la Rama se
        # conserva para poder avisar "mostrando X de Y" en vez de truncar callado.
        mock_get.return_value = _respuesta_cpnu(
            _pagina([{'idProceso': 1}], cantidad_paginas=9, cantidad_registros=180)
        )
        procesos, total = services_judicial.consultar_procesos_judiciales('JUAN PEREZ')
        self.assertEqual(len(procesos), 1)
        self.assertEqual(total, 180)

    def test_clasificacion_por_despacho(self):
        clasificar = services_judicial.clasificar_proceso
        self.assertEqual(clasificar('JUZGADO 3 PENAL DEL CIRCUITO DE BOGOTA'), 'Penal')
        self.assertEqual(clasificar('SALA DISCIPLINARIA'), 'Disciplinario')
        self.assertEqual(clasificar('TRIBUNAL ADMINISTRATIVO DE SANTANDER'), 'Administrativo')
        self.assertEqual(clasificar('JUZGADO LABORAL DEL CIRCUITO'), 'Laboral')
        self.assertEqual(clasificar(''), 'Otro')
        self.assertEqual(clasificar(None), 'Otro')


@override_settings(NOTIFICAR_HALLAZGOS=False, CONSULTAR_PROCESOS_JUDICIALES=True)
class ProcesosJudicialesEnLaBusquedaTests(TestCase):
    """La consulta judicial acompaña a la búsqueda LAFT, pero nunca la estorba."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='clave-larga-123')
        self.client.force_login(self.user)
        self.url = reverse('pagina_busqueda')

    @patch('consultas.views.consultar_procesos_judiciales')
    @patch('consultas.views.consultar_api_por_nombre', return_value=[])
    def test_guarda_los_procesos_encontrados(self, _mock_api, mock_judicial):
        mock_judicial.return_value = ([{
            'idProceso': 12345,
            'llaveProceso': '11001310300120240001',
            'fechaProceso': '2024-03-15T00:00:00',
            'despacho': 'JUZGADO 1 PENAL DEL CIRCUITO DE BOGOTA',
            'departamento': 'BOGOTA',
            'sujetosProcesales': 'Demandante: X | Demandado: JUAN PEREZ',
        }], 1)
        self.client.post(self.url, {'nombres': 'JUAN PEREZ'})

        b = Busqueda.objects.get()
        self.assertEqual(b.judicial_estado, 'ok')
        self.assertEqual(b.judicial_total_reportado, 1)
        proceso = b.procesos_judiciales.get()
        self.assertEqual(proceso.radicado, '11001310300120240001')
        self.assertEqual(proceso.categoria, 'Penal')

    @patch('consultas.views.consultar_procesos_judiciales', return_value=(None, 0))
    @patch('consultas.views.consultar_api_por_nombre', return_value=[])
    def test_rama_caida_no_se_muestra_como_sin_procesos(self, _mock_api, _mock_judicial):
        # Clave: 'no_disponible' != 'sin procesos'. Y la búsqueda LAFT se conserva.
        self.client.post(self.url, {'nombres': 'JUAN PEREZ'})
        b = Busqueda.objects.get()
        self.assertEqual(b.judicial_estado, 'no_disponible')
        self.assertEqual(b.procesos_judiciales.count(), 0)

    @patch('consultas.views.consultar_procesos_judiciales', side_effect=Exception('boom'))
    @patch('consultas.views.consultar_api_por_nombre', return_value=[])
    def test_un_fallo_inesperado_no_tumba_la_busqueda_laft(self, _mock_api, _mock_judicial):
        resp = self.client.post(self.url, {'nombres': 'JUAN PEREZ'})
        self.assertEqual(resp.status_code, 200)
        b = Busqueda.objects.get()          # la consulta de listas sí quedó registrada
        self.assertEqual(b.judicial_estado, 'no_disponible')

    @patch('consultas.views.consultar_procesos_judiciales')
    @patch('consultas.views.consultar_api_por_id', return_value=[])
    def test_busqueda_solo_por_documento_no_consulta_la_rama(self, _mock_api, mock_judicial):
        # La API de la Rama solo busca por nombre: sin nombre no hay nada que preguntar.
        self.client.post(self.url, {'identificacion': '79149126'})
        mock_judicial.assert_not_called()
        self.assertEqual(Busqueda.objects.get().judicial_estado, 'no_consultado')

    @override_settings(CONSULTAR_PROCESOS_JUDICIALES=False)
    @patch('consultas.views.consultar_procesos_judiciales')
    @patch('consultas.views.consultar_api_por_nombre', return_value=[])
    def test_flag_apagado_no_consulta_la_rama(self, _mock_api, mock_judicial):
        self.client.post(self.url, {'nombres': 'JUAN PEREZ'})
        mock_judicial.assert_not_called()
        self.assertEqual(Busqueda.objects.get().judicial_estado, 'no_consultado')

    @patch('consultas.views.consultar_procesos_judiciales')
    @patch('consultas.views.consultar_api_por_nombre', return_value=None)
    def test_si_falla_el_webservice_de_listas_no_se_consulta_la_rama(self, _mock_api, mock_judicial):
        # No hay Busqueda que colgarle los procesos, y la consulta no ocurrió.
        self.client.post(self.url, {'nombres': 'JUAN PEREZ'})
        mock_judicial.assert_not_called()
        self.assertEqual(Busqueda.objects.count(), 0)
        self.assertEqual(ProcesoJudicial.objects.count(), 0)
class InterruptorJudicialTests(TestCase):
    """CONSULTAR_PROCESOS_JUDICIALES=False debe apagar la feature EN TODO NIVEL:
    no se consulta la Rama (probado arriba), la URL de detalle no existe y la
    sección desaparece de la ficha y del contexto aunque haya datos guardados."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='clave-larga-123')
        self.client.force_login(self.user)
        # Búsqueda con procesos guardados de cuando la feature estuvo activa.
        self.busqueda = Busqueda.objects.create(
            usuario=self.user, termino_buscado='Nombre: JUAN PEREZ',
            judicial_estado='ok', judicial_total_reportado=1,
        )
        ProcesoJudicial.objects.create(
            busqueda=self.busqueda, id_proceso='12345',
            radicado='11001310300120240001', despacho='JUZGADO 1 PENAL',
            categoria='Penal',
        )

    @override_settings(CONSULTAR_PROCESOS_JUDICIALES=False)
    def test_url_de_detalle_da_404_con_el_flag_apagado(self):
        # El 404 ocurre ANTES de tocar la red: no hace falta mockear la Rama.
        resp = self.client.get(reverse('detalle_proceso_judicial', args=['12345']))
        self.assertEqual(resp.status_code, 404)

    @override_settings(CONSULTAR_PROCESOS_JUDICIALES=False)
    def test_ficha_oculta_la_seccion_aunque_haya_datos(self):
        resp = self.client.get(reverse('detalle_busqueda', args=[self.busqueda.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['procesos_judiciales_activos'])
        self.assertNotContains(resp, 'Procesos Judiciales')
        self.assertNotContains(resp, '11001310300120240001')

    @override_settings(CONSULTAR_PROCESOS_JUDICIALES=True)
    def test_ficha_muestra_la_seccion_con_el_flag_encendido(self):
        resp = self.client.get(reverse('detalle_busqueda', args=[self.busqueda.id]))
        self.assertContains(resp, 'Procesos Judiciales')
        self.assertContains(resp, '11001310300120240001')
