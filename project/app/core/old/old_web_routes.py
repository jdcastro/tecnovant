"""📃 Rutas de páginas de la aplicación (jinja2)"""

# Third party imports
from flask import render_template, redirect, url_for, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, jwt_required
from sqlalchemy.orm import joinedload

# Local application imports
from . import core as web
from .controller import login_required, UserView
from .models import User, get_clients_for_user

__doc__ = """
paginas de bienvenida y contenido general
"""


def get_dashboard_menu():
    return {
        "menu": [
            {"name": "Home", "url": url_for("core.index")},
            {"name": "Logout", "url": url_for("core.logout")},
            {"name": "Profile", "url": url_for("core.profile")},
        ]
    }


@web.route("/")
def index():
    """Página: Inicio de la aplicación "Welcome Page"
    :param None: No requiere parámetros, opcional obtiene el ID del usuario autenticado
    :status 200: Retorna la página principal
    """
    user_authenticated = False
    claims = None  # Initialize claims variable here
    context = {
        "has_login_button": True,
        "is_full_width": True,
        "title": "Welcome",
        "description": "Bienvenido a TecnoAgro.",
        "keywords": "gestión foliar, manejo de suelos y cultivos",
        "author": "Johnny De Castro",
        "site_title": "Software para gestión de  datos de foliar",
        "og_image": "/img/og-image.jpg",
        "twitter_image": "/img/twitter-image.jpg",
    }
    try:
        verify_jwt_in_request()
        claims = get_jwt_identity()
        if claims is not None:
            user_authenticated = True
        else:
            user_authenticated = False
    except Exception as e:
        # Si hay un error al obtener el token, asume que no está autenticado
        user_authenticated = False
    return (
        render_template(
            "home.j2",
            is_user_authenticated=user_authenticated,
            **context,
            request=request,
        ),
        200,
    )


__doc__ = """
Paginas de autenticacion y autorizacion
"""


@web.route("/login")
def login():
    """Página: Inicio de sesión. Implementa core_api.login"""
    context = {
        "has_login_button": False,
        "is_full_width": True,
        "title": "Bienvenido a App TecnoAgro",
        "description": "Acceso a la aplicación.",
        "author": "Johnny De Castro",
        "site_title": "Login",
        "og_image": "/img/og-image.jpg",
        "twitter_image": "/img/twitter-image.jpg",
    }
    try:
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        if user_id:
            return redirect(url_for("core.dashboard"))
    except:
        pass
    return render_template(
        "login.j2", login_status="not_authenticated", **context, request=request
    )


@web.route("/logout")
def logout():
    """Página de cierre de sesión. Implementa core_api.logout"""
    return render_template("logout.j2")


__doc__ = """
Paginas de dashboard y administracion
"""


@web.route("/dashboard")
@login_required
def dashboard():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    user_name = user.username
    rol = user.role.value
    context = {
        "dashboard": True,
        "title": "Dashboard TecnoAgro",
        "description": "Panel de control.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "og_image": "/img/og-image.jpg",
        "twitter_image": "/img/twitter-image.jpg",
        "data_menu": get_dashboard_menu(),
    }

    return (
        render_template(
            "dashboard/welcome.j2",
            username=user_name,
            **context,
            rol=rol,
            request=request,
        ),
        200,
    )


@web.route("/home/not-authorized")
def not_authorized():
    """
    Página de error para usuarios no autorizados
    """
    return render_template("dashboard/not_authorized.j2")


@web.route("/dashboard/users")
@jwt_required()
def amd_users():
    user_id = get_jwt_identity()
    user_view = UserView()  # instanciar la vista de usuarios
    # obtener el listado de clientes asignados a este usuario

    assigned_org = get_clients_for_user(user_id)
    context = {
        "dashboard": True,
        "title": "Gestión de usuarios",
        "description": "Administración de usuarios.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }
    org_dict = {org.name: org.id for org in assigned_org}

    if isinstance(user_view._get_user_list(), tuple):
        response, status_code = user_view._get_user_list()
        items = response.get_json()
    else:
        response = user_view._get_user_list()
        items = response.get_json()
        status_code = response.status_code
    if status_code != 200:
        # Manejar errores
        return render_template("error.j2"), status_code
    return (
        render_template(
            "dashboard/users.j2", items=items, client_dict=org_dict, **context
        ),
        200,
    )


# @web.route("/dashboard/clients")
# @jwt_required()
# def amd_clients():
#     user_id = get_jwt_identity()
#     context = {
#         "dashboard": True,
#         "title": "Gestión de clientes",
#         "description": "Administración de clientes.",
#         "author": "Johnny De Castro",
#         "site_title": "Panel de Control",
#         "data_menu": get_dashboard_menu(),
#     }
#     reseller_dict = {
#         user.full_name: user.username
#         for user in User.query.join(Client, User.client_id == Client.id)
#         .filter(Client.name == "Reseller ORG")
#         .all()
#     }

#     client_view = ClientView()
#     if isinstance(client_view.get(), tuple):
#         response, status_code = client_view.get()
#         items = response.get_json()
#     else:
#         response = client_view.get()
#         items = response.get_json()
#         status_code = response.status_code
#     if status_code != 200:
#         # Manejar errores
#         return render_template("error.j2"), status_code
#     return (
#         render_template(
#             "dashboard/clients.j2", items=items, reseller_dict=reseller_dict, **context
#         ),
#         200,
#     )


@web.route("/dashboard/profile")
@login_required
def profile():
    """
    Página: Renderiza la vista de perfil de usuario
    """
    # user_id = get_jwt_identity()

    # user = (
    #     User.query.options(joinedload(User.client)).filter(User.id == user_id).first()
    # )
    # context = {
    #     "user": user,
    #     "title": "User Profile",
    #     "username": user.username,
    #     "full_name": user.full_name,
    #     "role": user.role_name(),
    #     "email": user.email,
    #     "client": user.client.name if user.client else None,
    # }
    context = {}
    return render_template("dashboard/profile.j2", **context)
