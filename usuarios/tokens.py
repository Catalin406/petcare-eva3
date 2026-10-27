# ============================================================
# USUARIOS/TOKENS.PY / JWT CON EL ROL DENTRO DEL TOKEN
# El cliente de la API puede saber qué menú mostrar sin otra consulta.
# El servidor NUNCA confía en este dato: los permisos se evalúan con el
# usuario real de la base de datos en cada petición.
# ============================================================
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class TokenConRolSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, usuario):
        token = super().get_token(usuario)
        token["rol"] = usuario.rol
        token["nombre"] = usuario.nombre_visible
        return token
