from django.urls import path

from . import views

urlpatterns = [
    path("tutores/", views.TutorListaView.as_view(), name="tutor_lista"),
    path("tutores/nuevo/", views.TutorCrearView.as_view(), name="tutor_crear"),
    path("tutores/<int:pk>/", views.TutorDetalleView.as_view(), name="tutor_detalle"),
    path("tutores/<int:pk>/editar/", views.TutorEditarView.as_view(), name="tutor_editar"),
    path("tutores/<int:pk>/eliminar/", views.TutorEliminarView.as_view(), name="tutor_eliminar"),
    path("mascotas/", views.MascotaListaView.as_view(), name="mascota_lista"),
    path("mascotas/nueva/", views.MascotaCrearView.as_view(), name="mascota_crear"),
    path("mascotas/<int:pk>/", views.MascotaDetalleView.as_view(), name="mascota_detalle"),
    path("mascotas/<int:pk>/editar/", views.MascotaEditarView.as_view(), name="mascota_editar"),
    path("mascotas/<int:pk>/eliminar/", views.MascotaEliminarView.as_view(), name="mascota_eliminar"),
    path("mascotas/<int:pk>/foto/", views.MascotaFotoView.as_view(), name="mascota_foto"),
]
