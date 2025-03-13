"""📃 Rutas de páginas de la aplicación (jinja2)"""

# Third party imports
from flask import render_template, redirect, url_for, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, jwt_required, get_jwt
# from sqlalchemy.orm import joinedload

# Local application imports
from . import core as web
from .controller import InstallationView, login_required
from .models import User, get_clients_for_user

# from .models import User, get_clients_for_user

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
            **context,
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


from .controller import UserView, OrgView
from .models import get_clients_for_user, RoleEnum

import logging

@web.route("/dashboard/users")
@jwt_required()
def amd_users():
    """
    Página: Renderiza la vista de usuarios
    """
    user_id = get_jwt_identity()
    context = {
        "dashboard": True,
        "title": "Gestión de clientes",
        "description": "Administración de clientes.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }
    user_view = UserView()
    response, status_code = user_view._get_user_list()
    items = response.get_json()
    assigned_org = get_clients_for_user(user_id)
    org_dict = {org.name: org.id for org in assigned_org}
    # logging.error("Items obtenidos: %s, org_dict: %s", items, org_dict) 

    if status_code != 200:
        return render_template("error.j2"), status_code
    return (
        render_template(
            "dashboard/users.j2", 
            items=items, 
            org_dict=org_dict,
            **context, 
            request=request,
        ),
        200,
    )

@web.route("/dashboard/clients")
@jwt_required()
def amd_clients():
    """
    Página: Renderiza la vista de clientes
    """
    claims = get_jwt()
    user_role = claims.get("rol")
    user_id = claims.get("id")
    context = {
        "dashboard": True,
        "title": "Gestión de clientes",
        "description": "Administración de clientes.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }
    org_view = OrgView()
    response, status_code = org_view._get_org_list()
    if status_code != 200:
        return render_template("error.j2"), status_code
    items = response.get_json()
    if user_role == 'administrator':
    # Obtener todos los usuarios con rol reseller
        resellers = User.query.filter_by(role=RoleEnum.RESELLER).all()
        reseller_dict = {
            "Sin Reseller": None
        }
        for user in resellers:
            reseller_dict[user.full_name] = user.id
    elif user_role == 'reseller':
        # Obtener el usuario actual
        user = User.query.get(user_id)
        reseller_dict = {
            user.full_name: user.username
        }
    return (
        render_template(
            "dashboard/clients.j2", items=items, reseller_dict=reseller_dict, **context,  request=request
        ),200,
    )

@web.route("/dashboard/profile")
@jwt_required()
def profile():
    """
    Página: Renderiza la vista de perfil de usuario
    """
    context = {}
    return render_template("dashboard/profile.j2", **context)

web.add_url_rule('/install', view_func=InstallationView.as_view('install'))