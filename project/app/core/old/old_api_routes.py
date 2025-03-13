# Third party imports
from flask import jsonify, request, current_app, views
from flask_jwt_extended import (
    jwt_required,
    create_access_token,
    create_refresh_token,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
    get_jwt_identity,
    get_csrf_token,
    get_jwt,
)
from werkzeug.security import check_password_hash

# Local application imports
from .models import User, ResellerPackage
from .schemas import (
    UserSchema,
    ClientSchema,
    ResellerPackageSchema,
)
from app.extensions import db, jwt, cache
from . import core_api as api
from .controller import (
    login_required,
    RoleEnum,
)

__doc__ = """
Set up the API routes for the core module
"""

__doc__ = """
Login, refresh and logout routes
"""


@api.route("/login", methods=["POST"])
def login():
    """Inicio de sesión
    :param str username: Nombre de usuario
    :param str password: Contraseña
    :status 200: Inicio de sesión exitoso
    :status 400: Datos de inicio de sesión no válidos
    :status 401: Nombre de usuario o contraseña incorrectos
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"msg": "No data provided"}), 400

        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"msg": "Username and password are required"}), 400

        user = User.get_by_username(username)

        if not user or not user.check_password(password) or not user.active:
            return jsonify({"msg": "Bad username or password"}), 401

        identity_str = str(user.id)
        additional_claims = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "client": {
                "id": user.client_id,
                "name": user.client.name if user.client else "No client",
            },
            "rol": user.role.value if hasattr(user.role, "value") else user.role,  #
        }

        # Si el usuario es reseller, agregar información de sus clientes
        if user.role == RoleEnum.RESELLER and hasattr(user, "reseller_info"):
            additional_claims["reseller_clients"] = [
                {"id": client.id, "name": client.name}
                for client in user.reseller_info.clients
            ]

        access_token = create_access_token(
            identity=identity_str, additional_claims=additional_claims
        )
        refresh_token = create_refresh_token(
            identity=identity_str, additional_claims=additional_claims
        )

        response = jsonify(
            {
                "access_csrf": get_csrf_token(access_token),
                "refresh_csrf": get_csrf_token(refresh_token),
                "additional_claims": additional_claims,
                "msg": "Login successful",
            }
        )
        set_access_cookies(response, access_token)
        set_refresh_cookies(response, refresh_token)
        return response

    except Exception as e:
        print(f"Error en api_login: {e}")
        return jsonify({"msg": "Bad login data"}), 400


@api.route("/logout")
@login_required
def logout():
    """Cerrar sesión
    :status 200: Sesión cerrada correctamente
    """
    response = jsonify({"msg": "Logout successful"})
    unset_jwt_cookies(response)
    return response, 200


@api.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """Refresh the access token using the refresh token.
    :status 200: Token refreshed successfully
    :status 401: Invalid token
    :status 403: Token has been revoked
    """
    current_user = get_jwt_identity()
    user = User.query.get(current_user)

    if not user:
        return jsonify({"msg": "Usuario no encontrado"}), 404

    if not user.active:
        unset_jwt_cookies()
        return jsonify({"msg": "Sesión invalidada"}), 401

    identity_str = str(user.id)
    additional_claims = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "client": {
            "id": user.client_id,
            "name": user.client.name if user.client else "No client",
        },
        "rol": user.role.value if hasattr(user.role, "value") else user.role,  #
    }

    # Si el usuario es reseller, agregar información de sus clientes
    if user.role == RoleEnum.RESELLER and hasattr(user, "reseller_info"):
        additional_claims["reseller_clients"] = [
            {"id": client.id, "name": client.name}
            for client in user.reseller_info.clients
        ]

    access_token = create_access_token(
        identity=identity_str, additional_claims=additional_claims
    )
    response = jsonify({"access_token": access_token})

    set_access_cookies(response, access_token)
    return response, 200


"""
Endpoints for the User model
"""

from .controller import UserView

user_view = UserView.as_view("user_api")

# Rutas para manejar las operaciones con user_id
api.add_url_rule("/users/", view_func=user_view, methods=["GET", "POST", "DELETE"])
api.add_url_rule(
    "/users/<int:user_id>", view_func=user_view, methods=["GET", "PUT", "DELETE"]
)


# @api.route("/user/<int:user_id>", methods=["GET"])

# def get_user(user_id):
#     # Obtener datos del token
#     aut_user_id = get_jwt_identity()
#     claims = get_jwt()
#     aut_roles = [role["name"] for role in claims["roles"]]
#     aut_client_id = claims["client"]["id"] if claims.get("client") else None

#     user = User.query.get_or_404(user_id)

#     # Verificar permisos para ver este usuario
#     if "administrator" in aut_roles:
#         # Administradores pueden ver cualquier usuario
#         pass
#     elif "reseller" in aut_roles:
#         # Resellers solo pueden ver usuarios de sus clientes
#         current_user = User.query.get(aut_user_id)
#         if not hasattr(current_user, 'reseller_info') or not current_user.reseller_info.is_reseller_client(user.client_id):
#             return jsonify({"error": "Permission denied"}), 403
#     elif user.client_id != aut_client_id:
#         # Otros roles solo pueden ver usuarios de su mismo cliente
#         return jsonify({"error": "Permission denied"}), 403

#     return jsonify(UserSchema().dump(user))
