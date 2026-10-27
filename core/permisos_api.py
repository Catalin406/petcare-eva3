# ============================================================
# CORE/PERMISOS_API.PY / PERMISOS POR ROL PARA LA API
# Cada ViewSet declara qué roles pueden leer y cuáles escribir.
# El acceso a nivel de OBJETO se logra filtrando el queryset por
# usuario (un objeto ajeno responde 404, como si no existiera).
# ============================================================
from rest_framework.permissions import SAFE_METHODS, BasePermission

from usuarios.models import Rol

TODOS = (Rol.ADMINISTRADOR, Rol.RECEPCIONISTA, Rol.VETERINARIO, Rol.TUTOR)
STAFF = (Rol.ADMINISTRADOR, Rol.RECEPCIONISTA)


class PorRol(BasePermission):
    """
    La vista define:
      roles_lectura:   roles que pueden hacer GET/HEAD/OPTIONS
      roles_escritura: roles que pueden POST/PUT/PATCH/DELETE
      roles_acciones:  {"nombre_accion": (roles...)} para @action personalizadas
    """

    def has_permission(self, request, view):
        usuario = request.user
        if not usuario or not usuario.is_authenticated:
            return False
        accion = getattr(view, "action", None)
        especificos = getattr(view, "roles_acciones", {})
        if accion in especificos:
            return usuario.rol in especificos[accion]
        if request.method in SAFE_METHODS:
            return usuario.rol in view.roles_lectura
        return usuario.rol in view.roles_escritura
