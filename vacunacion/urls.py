from django.urls import path

from . import views

urlpatterns = [
    path("recordatorios/", views.RecordatorioPanelView.as_view(), name="recordatorio_panel"),
    path("vacunacion/catalogo/", views.VacunaListaView.as_view(), name="vacuna_lista"),
    path("vacunacion/catalogo/nueva/", views.VacunaCrearView.as_view(), name="vacuna_crear"),
    path("vacunacion/catalogo/<int:pk>/editar/", views.VacunaEditarView.as_view(), name="vacuna_editar"),
    path("vacunacion/catalogo/<int:pk>/eliminar/", views.VacunaEliminarView.as_view(), name="vacuna_eliminar"),
    path("vacunacion/aplicadas/", views.RegistroVacunaListaView.as_view(), name="registro_vacuna_lista"),
    path("vacunacion/aplicadas/nueva/", views.RegistroVacunaCrearView.as_view(), name="registro_vacuna_crear"),
    path("vacunacion/controles/", views.ControlListaView.as_view(), name="control_lista"),
    path("vacunacion/controles/nuevo/", views.ControlCrearView.as_view(), name="control_crear"),
    path("vacunacion/controles/<int:pk>/editar/", views.ControlEditarView.as_view(), name="control_editar"),
    path("vacunacion/controles/<int:pk>/realizado/", views.ControlRealizadoView.as_view(), name="control_realizado"),
]
