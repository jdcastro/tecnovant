# Third party imports
from flask import jsonify, request, current_app, views
from flask_jwt_extended import unset_jwt_cookies

# Local application imports
from . import core_api as api
from .controller import (
    login_required,
    LoginView,
    RefreshView,
    UserView,
    OrgView,
)

#############################################
# Set up the API routes for the core module #
#############################################

####################################
# Login, logout and refresh routes #
####################################
api.add_url_rule("/login", view_func=LoginView.as_view("login"), methods=["POST"])


@api.route("/logout")
@login_required
def logout():
    """Cerrar sesión
    :status 200: Sesión cerrada correctamente
    """
    response = jsonify({"msg": "Logout successful"})
    unset_jwt_cookies(response)
    return response, 200


api.add_url_rule("/refresh", view_func=RefreshView.as_view("refresh"), methods=["POST"])

################################
# Endpoints for the User model #
################################
user_view = UserView.as_view("user_view")

api.add_url_rule("/users/", view_func=user_view, methods=["GET", "POST", "DELETE"])
api.add_url_rule(
    "/users/<string:user_id>", view_func=user_view, methods=["GET", "PUT", "DELETE"]
)

########################################
# Endpoints for the Organization model #
########################################

org_view = OrgView.as_view("org_view")
api.add_url_rule("/org/", view_func=org_view, methods=["GET", "POST", "DELETE"])
api.add_url_rule(
    "/org/<int:org_id>", view_func=org_view, methods=["GET", "PUT", "DELETE"]
)


# # Registro de rutas
# def register_routes(api):
#     """Registra las rutas para las vistas UserView y OrgView."""


#     api.add_url_rule("/users/", view_func=user_view, methods=["GET", "POST"])
#     api.add_url_rule(
#         "/users/<string:user_id>", view_func=user_view, methods=["GET", "PUT", "DELETE"]
#     )
#     api.add_url_rule("/organizations/", view_func=org_view, methods=["GET", "POST"])
#     api.add_url_rule(
#         "/organizations/<int:org_id>",
#         view_func=org_view,
#         methods=["GET", "PUT", "DELETE"],
#     )


# # def get_user(user_id):
# #     # Obtener datos del token
# #     aut_user_id = get_jwt_identity()
# #     claims = get_jwt()
# #     aut_roles = [role["name"] for role in claims["roles"]]
# #     aut_client_id = claims["client"]["id"] if claims.get("client") else None

# #     user = User.query.get_or_404(user_id)

# #     # Verificar permisos para ver este usuario
# #     if "administrator" in aut_roles:
# #         # Administradores pueden ver cualquier usuario
# #         pass
# #     elif "reseller" in aut_roles:
# #         # Resellers solo pueden ver usuarios de sus clientes
# #         current_user = User.query.get(aut_user_id)
# #         if not hasattr(current_user, 'reseller_info') or not current_user.reseller_info.is_reseller_client(user.client_id):
# #             return jsonify({"error": "Permission denied"}), 403
# #     elif user.client_id != aut_client_id:
# #         # Otros roles solo pueden ver usuarios de su mismo cliente
# #         return jsonify({"error": "Permission denied"}), 403

# #     return jsonify(UserSchema().dump(user))
