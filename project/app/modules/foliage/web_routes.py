# Third party imports
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask import render_template, url_for, request

# Local application imports
from . import foliage as web
from .controller import NutrientView, FarmView, LotView, CropView, ObjectiveView
from .models import Farm, Crop, Nutrient
from app.core.models import get_clients_for_user

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
    nutrient_view = NutrientView()
    response = nutrient_view._get_nutrient_list()
    items = response.get_json()
    status_code = response.status_code
    assigned_org = get_clients_for_user(user_id)
    org_dict = {org.name: org.id for org in assigned_org}
    if status_code != 200:
        return render_template("error.j2"), status_code
    return (
        render_template(
            "nutrients.j2", 
            items=items, 
            org_dict=org_dict,
            **context, 
            request=request,
        ),
        200,
    )
    
@web.route("/dashboard/farms")
@jwt_required()
def amd_farms():
    """
    Página: Renderiza la vista de Fincas
    """
    user_id = get_jwt_identity()
    context = {
        "dashboard": True,
        "title": "Gestión de Fincas",
        "description": "Administración de Fincas.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }
    farm_view = FarmView()
    response = farm_view._get_farm_list()
    items = response.get_json()
    status_code = response.status_code
    assigned_org = get_clients_for_user(user_id)
    org_dict = {org.name: org.id for org in assigned_org}
    if status_code != 200:
        return render_template("error.j2"), status_code
    return (
        render_template(
            "farms.j2", 
            items=items, 
            org_dict=org_dict,
            **context, 
            request=request,
        ),
        200,
    )


@web.route("/dashboard/lots")
@jwt_required()
def amd_lots(filter_value=None):
    """
    Página: Renderiza la vista de lotes
    """
    user_id = get_jwt_identity()
    context = {
        "dashboard": True,
        "title": "Gestión de lotes",
        "description": "Administración de lotes.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }
    lot_view = LotView()
    filter_value = request.args.get('filter_value')
    if filter_value:
        filter_value = int(filter_value)  
        response = lot_view._get_lot_list(filter_by=filter_value)
    else:
        response = lot_view._get_lot_list()

    items = response.get_json()
    status_code = response.status_code
    filter_field = 'farm_id'
    farms = Farm.query.all() 
    filter_options = farms
    select_url = url_for('foliage.amd_lots')
    farms_dic = {farm.name: farm.id for farm in farms}
    if status_code != 200:
        return render_template("error.j2"), status_code
    return (
        render_template(
            "lots.j2", 
            items=items, 
            farms_dic=farms_dic,
            **context, 
            request=request,
            filter_field=filter_field, filter_options=filter_options,
            filter_value=filter_value, select_url=select_url
        ),
        200,
    )
    

@web.route("/dashboard/crops")
@jwt_required()
def amd_crops():
    """
    Página: Renderiza la vista de cultivos
    """
    user_id = get_jwt_identity()
    context = {
        "dashboard": True,
        "title": "Gestión de cultivos",
        "description": "Administración de cultivos.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }
    crop_view = CropView()
    response = crop_view._get_crop_list()
    items = response.get_json()
    status_code = response.status_code
    
    if status_code != 200:
        return render_template("error.j2"), status_code
    return (
        render_template(
            "crops.j2", 
            items=items, 
            **context, 
            request=request,
        ),
        200,
    )

@web.route("/dashboard/objectives")
@jwt_required()
def amd_objectives():
    """
    Página: Renderiza la vista de objetivos
    """
    user_id = get_jwt_identity()
    context = {
        "dashboard": True,
        "title": "Gestión de objetivos",
        "description": "Administración de objetivos.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }

    # Instantiate the view and get objectives
    objective_view = ObjectiveView()
    response = objective_view._get_objective_list()
    items = response.get_json()
    status_code = response.status_code

    # Get organizations and crops for the dropdown
    assigned_org = get_clients_for_user(user_id)
    org_dict = {org.name: org.id for org in assigned_org}
    crops = Crop.query.all()
    crop_options = {crop.name: crop.id for crop in crops}

    # Define form fields
    nutrient_ids = Nutrient.query.all()
    form_fields = {
        "crop_id": {
            "type": "select",
            "label": "Cultivo",
            "options": crop_options,
            "required": True,
        },
        "target_value": {
            "type": "number",
            "label": "Valor objetivo general",
            "required": True,
            "placeholder": "Ej: 100.0",
        },
        "protein": {
            "type": "number",
            "label": "Proteína",
            "required": False,
            "placeholder": "Ej: 20.5",
        },
        "rest": {
            "type": "number",
            "label": "Descanso",
            "required": False,
            "placeholder": "Ej: 15.0",
        },
    }

    # Add nutrient fields dynamically
    for nutrient in nutrient_ids:
        form_fields[f"nutrient_{nutrient.id}"] = {
            "type": "number",
            "label": f"Valor objetivo de {nutrient.name} ({nutrient.symbol})",
            "required": False,  # Optional, as not all nutrients may be set
            "placeholder": f"Ej: 10.5 ({nutrient.unit})",
        }


    # base_headers = ["ID", "Cultivo", "Valor Objetivo", "Proteína", "Descanso", "Fecha de Creación", "Fecha de Actualización"]
    # nutrient_headers = [f"{nutrient.name} ({nutrient.symbol})" for nutrient in nutrient_ids]
    # table_headers = base_headers + nutrient_headers
    # base_fields = ["id", "crop_name", "target_value", "protein", "rest", "created_at", "updated_at"]
    # nutrient_fields = [f"nutrient_{nutrient.id}" for nutrient in nutrient_ids]
    # item_fields = base_fields + nutrient_fields
    
    if status_code != 200:
        return render_template("error.j2"), status_code

    return (
        render_template(
            "objectives.j2",
            items=items,
            org_dict=org_dict,
            crops=crops,  # Pass crops for reference if needed
            nutrient_ids=nutrient_ids,  # Pass nutrients for reference
            form_fields=form_fields,
            request=request,
            **context,
        ),
        200,
    )