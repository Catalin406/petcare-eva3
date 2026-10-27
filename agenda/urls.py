from django.urls import path

from . import views

urlpatterns = [
    path("agenda/calendario/", views.CalendarioView.as_view(), name="calendario"),
    path("agenda/citas/", views.CitaListaView.as_view(), name="cita_lista"),
    path("agenda/citas/nueva/", views.CitaCrearView.as_view(), name="cita_crear"),
    path("agenda/citas/<int:pk>/", views.CitaDetalleView.as_view(), name="cita_detalle"),
    path("agenda/citas/<int:pk>/reprogramar/", views.CitaEditarView.as_view(), name="cita_editar"),
    path("agenda/citas/<int:pk>/estado/", views.CitaCambiarEstadoView.as_view(), name="cita_cambiar_estado"),
    path("agenda/citas/<int:pk>/eliminar/", views.CitaEliminarView.as_view(), name="cita_eliminar"),
    path("agenda/disponibilidad/", views.DisponibilidadListaView.as_view(), name="disponibilidad_lista"),
    path("agenda/disponibilidad/nueva/", views.DisponibilidadCrearView.as_view(), name="disponibilidad_crear"),
    path("agenda/disponibilidad/<int:pk>/editar/", views.DisponibilidadEditarView.as_view(), name="disponibilidad_editar"),
    path("agenda/disponibilidad/<int:pk>/eliminar/", views.DisponibilidadEliminarView.as_view(), name="disponibilidad_eliminar"),
    path("agenda/bloqueos/nuevo/", views.BloqueoCrearView.as_view(), name="bloqueo_crear"),
    path("agenda/bloqueos/<int:pk>/editar/", views.BloqueoEditarView.as_view(), name="bloqueo_editar"),
    path("agenda/bloqueos/<int:pk>/eliminar/", views.BloqueoEliminarView.as_view(), name="bloqueo_eliminar"),
]
