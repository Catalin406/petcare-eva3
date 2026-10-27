from django.urls import path

from . import views

urlpatterns = [
    path("clinica/fichas/<int:mascota_pk>/", views.FichaDetalleView.as_view(), name="ficha_detalle"),
    path("clinica/fichas/<int:mascota_pk>/editar/", views.FichaEditarView.as_view(), name="ficha_editar"),
    path("clinica/atenciones/nueva/", views.AtencionCrearView.as_view(), name="atencion_crear"),
    path("clinica/atenciones/<int:pk>/", views.AtencionDetalleView.as_view(), name="atencion_detalle"),
    path("clinica/atenciones/<int:pk>/editar/", views.AtencionEditarView.as_view(), name="atencion_editar"),
    path("clinica/examenes/<int:pk>/archivo/", views.ExamenArchivoView.as_view(), name="examen_archivo"),
]
