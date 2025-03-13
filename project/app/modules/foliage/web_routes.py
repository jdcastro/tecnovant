from . import foliage as web
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask import render_template, url_for, request

def get_dashboard_menu():
    return {
        "menu": [
            {"name": "Home", "url": url_for("core.index")},
            {"name": "Logout", "url": url_for("core.logout")},
            {"name": "Profile", "url": url_for("core.profile")},
        ]
    }


@web.route("/nutrientes")
@jwt_required()
def nutrientes():
    """
    Página: Renderiza la vista de nutrientes
    """
    user_id = get_jwt_identity()
    context = {
        "dashboard": True,
        "title": "Gestión de nutrientes",
        "description": "Administración de nutrientes.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }
    # user_view = UserView()
    # response, status_code = user_view._get_user_list()
    # items = response.get_json()
    # assigned_org = get_clients_for_user(user_id)
    # org_dict = {org.name: org.id for org in assigned_org}
    # # logging.error("Items obtenidos: %s, org_dict: %s", items, org_dict) 

    # if status_code != 200:
    #     return render_template("error.j2"), status_code
    items = {}
    org_dict = {}
    
    return (
        render_template(
            "nutrientes.j2", 
            items=items, 
            org_dict=org_dict,
            **context, 
            request=request,
        ),
        200,
    )