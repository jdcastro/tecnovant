import json 
from decimal import Decimal


# Third party imports
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask import render_template, url_for, request, jsonify

# Local application imports
from . import foliage as web
from .controller import (
    NutrientView,
    FarmView,
    LotView,
    CropView,
    ObjectiveView,
    ProductView,
    ProductContributionView,
    ProductPriceView,
    CommonAnalysisView, 
    LotCropView,
    LeafAnalysisView, 
    SoilAnalysisView,
    NutrientApplicationView, 
    ProductionView
)
from .models import Farm, Crop, Nutrient, Product, Lot, CommonAnalysis
from app.core.models import get_clients_for_user
from app.core.controller import login_required
from .nutrient_optimizer import calcular_cv_nutriente, determinar_coeficientes_variacion, contribuciones_de_producto, ObjectiveResource, LeafAnalysisResource, NutrientOptimizer

def get_dashboard_menu():
    """Define el menu superior en los templates"""
    return {
        "menu": [
            {"name": "Home", "url": url_for("core.index")},
            {"name": "Logout", "url": url_for("core.logout")},
            {"name": "Profile", "url": url_for("core.profile")},
        ]
    }

# 👌
@web.route("/nutrientes")
@login_required
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

# 👌
@web.route("/farms")
@login_required
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

# 👌
@web.route("/lots")
@login_required
def amd_lots(filter_value=None):
    """
    Página: Renderiza la vista de lotes
    """
    context = {
        "dashboard": True,
        "title": "Gestión de lotes",
        "description": "Administración de lotes.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }
    lot_view = LotView()
    filter_value = request.args.get("filter_value")
    if filter_value:
        filter_value = int(filter_value)
        response = lot_view._get_lot_list(filter_by=filter_value)
    else:
        response = lot_view._get_lot_list()

    items = response.get_json()
    status_code = response.status_code
    filter_field = "farm_id"
    farms = Farm.query.all()
    filter_options = farms
    select_url = url_for("foliage.amd_lots")
    if filter_value:
        filter_value = int(filter_value)
        farms = Farm.query.filter_by(id=filter_value).all()
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
            filter_field=filter_field,
            filter_options=filter_options,
            filter_value=filter_value,
            select_url=select_url,
        ),
        200,
    )

# 👌
@web.route("/crops")
@login_required
def amd_crops():
    """
    Página: Renderiza la vista de cultivos
    """
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

# 👌
@web.route("/lot_crops")
@login_required
def amd_lot_crops():
    """
    Página: Renderiza la vista de lotes de cultivos
    """
    context = {
        "dashboard": True,
        "title": "Gestión de lotes de cultivos",
        "description": "Administración de lotes de cultivos.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }

    # Instanciar la vista de LotCrop
    lot_crop_view = LotCropView()
    
    # Obtener el valor del filtro desde los argumentos de la solicitud
    filter_value = request.args.get("filter_value")
    filter_field = "farm_id"
    farms = Farm.query.all()
    filter_options = farms

    # Obtener las relaciones LotCrop con filtro opcional por farm_id
    if filter_value:
        filter_value = int(filter_value)
        # Modificar LotCropView para aceptar un filtro por farm_id si es necesario
        # Por ahora, filtramos manualmente después de obtener la lista
        response = lot_crop_view._get_lot_crop_list()
        items = response.get_json()
        # Filtrar los items por farm_id
        items = [item for item in items if item["organization_id"] == filter_value]
        status_code = 200  # Simulamos que el filtro manual es exitoso
    else:
        response = lot_crop_view._get_lot_crop_list()
        items = response.get_json()
        status_code = response.status_code

    # Obtener lots y crops para el formulario, aplicando el filtro si existe
    if filter_value:
        lots = Lot.query.join(Farm).filter(Farm.id == filter_value).all()
    else:
        lots = Lot.query.all()
    lots_dic = {lot.name: lot.id for lot in lots}

    crops = Crop.query.all()  # Los cultivos no necesitan filtrarse por farm_id
    crop_dic = {crop.name: crop.id for crop in crops}

    if status_code != 200:
        return render_template("error.j2"), status_code

    return (
        render_template(
            "lot_crops.j2",
            items=items,
            filter_value=filter_value,
            filter_field=filter_field,
            filter_options=filter_options,
            lots_dic=lots_dic,
            crop_dic=crop_dic,
            **context,
            request=request,
        ),
        200,
    )

# 👌
@web.route("/objectives")
@login_required
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

# 👌
@web.route("/products")
@login_required
def amd_products():
    """
    Página: Renderiza la vista de productos
    """
    user_id = get_jwt_identity()
    context = {
        "dashboard": True,
        "title": "Gestión de productos",
        "description": "Administración de productos.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }
    product_view = ProductView()
    response = product_view._get_product_list()
    items = response.get_json()
    status_code = response.status_code
    if status_code != 200:
        return render_template("error.j2"), status_code
    return (
        render_template(
            "products.j2",
            items=items,
            **context,
            request=request,
        ),
        200,
    )

# 👌
@web.route("/product_contributions")
@login_required
def amd_product_contributions():
    """
    Página: Renderiza la vista de contribuciones de productos
    """
    user_id = get_jwt_identity()
    context = {
        "dashboard": True,
        "title": "Gestión de contribuciones de productos",
        "description": "Administración de contribuciones de productos.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }
    # Instantiate the view and get product contributions
    product_contribution_view = ProductContributionView()
    response = product_contribution_view._get_product_contribution_list()
    items = response.get_json()
    status_code = response.status_code
    # Get products for the dropdown
    products = Product.query.all()
    product_options = {product.name: product.id for product in products}
    # Define form fields
    nutrient_ids = Nutrient.query.all()
    form_fields = {
        "product_id": {
            "type": "select",
            "label": "Producto",
            "options": product_options,
            "required": True,
        },
    }
    # Add nutrient fields dynamically
    for nutrient in nutrient_ids:
        form_fields[f"nutrient_{nutrient.id}"] = {
            "type": "number",
            "label": f"Contribución de {nutrient.name} ({nutrient.symbol})",
            "required": False,  # Optional, as not all nutrients may be set
            "placeholder": f"Ej: 10.5 ({nutrient.unit})",
        }
    # base_headers = ["ID", "Producto", "Fecha de Creación", "Fecha de Actualización"]
    # nutrient_headers = [f"{nutrient.name} ({nutrient.symbol})" for nutrient in nutrient_ids]
    # table_headers = base_headers + nutrient_headers
    # base_fields = ["id", "product_name", "created_at", "updated_at"]
    # nutrient_fields = [f"nutrient_{nutrient.id}" for nutrient in nutrient_ids]
    # item_fields = base_fields + nutrient_fields
    if status_code != 200:
        return render_template("error.j2"), status_code
    return (
        render_template(
            "product_contributions.j2",
            items=items,
            products=products,  # Pass products for reference if needed
            nutrient_ids=nutrient_ids,  # Pass nutrients for reference
            form_fields=form_fields,
            request=request,
            **context,
        ),
        200,
    )

# 👌
@web.route("/product_prices")
@login_required
def amd_product_prices():
    """
    Página: Renderiza la vista de precios de productos
    """
    user_id = get_jwt_identity()
    context = {
        "dashboard": True,
        "title": "Gestión de precios de productos",
        "description": "Administración de precios de productos.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }
    product_price_view = ProductPriceView()
    response = product_price_view._get_product_price_list()
    items = response.get_json()
    status_code = response.status_code
    products = Product.query.all()
    product_options = {product.name: product.id for product in products}
    if status_code != 200:
        return render_template("error.j2"), status_code
    return (
        render_template(
            "product_prices.j2",
            items=items,
            product_options=product_options,
            **context,
            request=request,
        ),
        200,
    )

# 👌
@web.route("/common_analyses")
@login_required
def amd_common_analyses():
    """
    Página: Renderiza la vista de análisis comunes
    """
    user_id = get_jwt_identity()
    context = {
        "dashboard": True,
        "title": "Gestión de análisis comunes",
        "description": "Administración de análisis comunes.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }
    common_analysis_view = CommonAnalysisView()
    filter_value = request.args.get("filter_value")
    if filter_value:
        filter_value = int(filter_value)
        response = common_analysis_view._get_common_analysis_list(filter_by=filter_value)
    else:
        response = common_analysis_view._get_common_analysis_list()
        
    items = response.get_json()
    status_code = response.status_code
    if filter_value:
        lots = Lot.query.join(Farm).filter(Farm.id == filter_value).all()
    else:
        lots = Lot.query.all()
    lots_dic = {lot.name: lot.id for lot in lots}
    
    filter_field = "farm_id"
    farms = Farm.query.all()
    filter_options = farms
    
    if status_code != 200:
        return render_template("error.j2"), status_code
    return (
        render_template(
            "common_analyses.j2", 
            items=items, 
            lots_dic=lots_dic, 
            filter_field=filter_field,
            filter_options=filter_options,
            filter_value=filter_value,
            **context, 
            request=request,
        ),
        200,
    )
    


# 👌✍🏼
@web.route("/leaf_analyses")
@jwt_required()
def amd_leaf_analyses():
    """
    Página: Renderiza la vista de análisis de hojas
    """
    user_id = get_jwt_identity()
    context = {
        "dashboard": True,
        "title": "Gestión de análisis foliares",
        "description": "Administración de análisis foliares.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }
    
    # Get data
    leaf_analysis_view = LeafAnalysisView()
    filter_value = request.args.get("filter_value")
    if filter_value:
        filter_value = int(filter_value)
        response = leaf_analysis_view._get_leaf_analysis_list(filter_by=filter_value)
    else:
        response = leaf_analysis_view._get_leaf_analysis_list()
    filter_field = "farm_id"
    farms = Farm.query.all()
    filter_options = farms
    items = response.get_json()
    status_code = response.status_code
    
    # Get CommonAnalysisView
    analisis_comun_id = request.args.get("analisis_comun_id")
    if filter_value:
        common_analyses = CommonAnalysis.query.join(Lot, CommonAnalysis.lot_id == Lot.id).filter(Lot.farm_id == filter_value).all()
    else:
        common_analyses = CommonAnalysis.query.all()

    # Actualizar el diccionario common_analysis_options
    if analisis_comun_id:
        common_analysis_options = {int(analisis_comun_id): int(analisis_comun_id)}
    else:
        common_analysis_options = {common_analysis.id: common_analysis.id for common_analysis in common_analyses}
    
    
    # Define form fields
    nutrient_ids = Nutrient.query.all()
    form_fields = {
        "common_analysis_id": {
            "type": "select",
            "label": "Análisis común",
            "options": common_analysis_options,
            "required": True,
        },
    }
    
    # Add nutrient fields dynamically
    for nutrient in nutrient_ids:
        form_fields[f"nutrient_{nutrient.id}"] = {
            "type": "number",
            "label": f"Valor de {nutrient.name} ({nutrient.symbol})",
            "required": False,
            "placeholder": f"Ej: 10.5 ({nutrient.unit})",
        }
    if status_code != 200:
        return render_template("error.j2"), status_code
        
    return render_template(
        "leaf_analyses.j2",
        items=items,
        nutrient_ids=nutrient_ids,
        form_fields=form_fields,
        filter_field=filter_field,
        filter_options=filter_options,
        filter_value=filter_value,
        **context,
        request=request,
    ), 200
    
# 👌
@web.route("/soil_analyses")
@jwt_required()
def amd_soil_analyses():
    """
    Página: Renderiza la vista de análisis de suelos
    """
    user_id = get_jwt_identity()
    context = {
        "dashboard": True,
        "title": "Gestión de análisis de suelos",
        "description": "Administración de análisis de suelos.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }
    soil_analysis_view = SoilAnalysisView()
    filter_value = request.args.get("filter_value")
    if filter_value:
        filter_value = int(filter_value)
        response = soil_analysis_view._get_soil_analysis_list(filter_by=filter_value)
    else:
        response = soil_analysis_view._get_soil_analysis_list()

    items = response.get_json()
    status_code = response.status_code
    
    filter_field = "farm_id"
    farms = Farm.query.all()
    filter_options = farms
    
    # Get CommonAnalysisView
    analisis_comun_id = request.args.get("analisis_comun_id")
    if filter_value:
        common_analyses = CommonAnalysis.query.join(Lot, CommonAnalysis.lot_id == Lot.id).filter(Lot.farm_id == filter_value).all()
    else:
        common_analyses = CommonAnalysis.query.all()

    # Actualizar el diccionario common_analysis_options
    if analisis_comun_id:
        common_analysis_options = {int(analisis_comun_id): int(analisis_comun_id)}
    else:
        common_analysis_options = {common_analysis.id: common_analysis.id for common_analysis in common_analyses}

    if status_code != 200:
        return render_template("error.j2"), status_code
    return (
        render_template(
            "soil_analyses.j2", 
            items=items, 
            filter_field=filter_field,
            filter_options=filter_options,
            filter_value=filter_value,
            common_analysis_options=common_analysis_options,
            **context, 
            request=request,
        ),
        200,
    )

# 👌
@web.route("/nutrient_applications")
@jwt_required()
def amd_nutrient_applications():
    """
    Página: Renderiza la vista de aplicaciones de nutrientes
    """
    filter_value = request.args.get("filter_value")
    context = {
        "dashboard": True,
        "title": "Gestión de aplicaciones de nutrientes",
        "description": "Administración de aplicaciones de nutrientes.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }

    nutrient_application_view = NutrientApplicationView()
    if filter_value:
        filter_value = int(filter_value)
        response = nutrient_application_view._get_nutrient_application_list(filter_by=filter_value)
    else:
        response = nutrient_application_view._get_nutrient_application_list()

    status_code = response.status_code
    items = response.get_json()

    if status_code != 200:
        return render_template("error.j2"), status_code

    lots = Lot.query.join(Farm).filter(Farm.org_id == filter_value).all() if filter_value else Lot.query.all()
    lots_dic = {lot.name: lot.id for lot in lots}

    filter_field = "farm_id"
    farms = Farm.query.all()
    filter_options = farms

    # Define form fields
    nutrient_ids = Nutrient.query.all()
    form_fields = {
        'date': {
            'type': 'date', 
            'label': 'Fecha de aplicación', 
            'required': True
        },
        'lot_id': {
            'type': 'select', 
            'label': 'Lote', 
            'options': lots_dic, 
            'required': True, 
            'new_value': False
        },
    }

    # Add nutrient fields dynamically
    for nutrient in nutrient_ids:
        form_fields[f"nutrient_{nutrient.id}"] = {
            "type": "number",
            "label": f"Valor de {nutrient.name} ({nutrient.symbol})",
            "required": False,
            "placeholder": f"Ej: 10.5 ({nutrient.unit})",
        }

    return (
        render_template(
            "nutrient_applications.j2", 
            items=items, 
            lots_dic=lots_dic,
            filter_field=filter_field,
            filter_options=filter_options,
            filter_value=filter_value,
            form_fields=form_fields,
            **context, 
            request=request,
        ),
        status_code,
    )
    
@web.route("/productions")
@jwt_required()
def amd_productions():
    """
    Página: Renderiza la vista de producciones
    """
    user_id = get_jwt_identity()
    context = {
        "dashboard": True,
        "title": "Gestión de producciones",
        "description": "Administración de producciones.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "data_menu": get_dashboard_menu(),
    }
    production_view = ProductionView()
    response = production_view._get_production_list()
    items = response.get_json()
    status_code = response.status_code

    if status_code != 200:
        return render_template("error.j2"), status_code
    return (
        render_template(
            "productions.j2",
            items=items, 
            **context, 
            request=request,
        ),
        200,
    )

@web.route("/vista_reporte")
def vista_reporte():
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

    analysisData = {
        "common": {
            "id": 3,
            "fechaAnalisis": "2025-03-26",
            "finca": "El nuevo rocío",
            "lote": "Lote 1",
            "proteinas": 6.0,
            "descanso": 5.0,
            "diasDescanso": 5,
            "mes": 5,
        },
        "foliar": {
            "id": 1,
            "nitrogeno": 2.5,
            "fosforo": 0.3,
            "potasio": 1.8,
            "calcio": 1.2,
            "magnesio": 0.4,
            "azufre": 0.2,
            "hierro": 85,
            "manganeso": 45,
            "zinc": 18,
            "cobre": 6,
            "boro": 25,
        },
        "soil": {
            "id": 1,
            "ph": 6.5,
            "materiaOrganica": 3.2,
            "nitrogeno": 0.15,
            "fosforo": 12,
            "potasio": 180,
            "calcio": 1200,
            "magnesio": 180,
            "azufre": 15,
            "textura": "Franco-arcillosa",
            "cic": 15.2,
        },
    }
    
    optimalLevels = {
        "foliar": {
            "nitrogeno": {"min": 2.8, "max": 3.5},
            "fosforo": {"min": 0.2, "max": 0.4},
            "potasio": {"min": 2.0, "max": 3.0},
            "calcio": {"min": 1.0, "max": 2.0},
            "magnesio": {"min": 0.3, "max": 0.6},
            "azufre": {"min": 0.2, "max": 0.4},
            "hierro": {"min": 50, "max": 150},
            "manganeso": {"min": 25, "max": 100},
            "zinc": {"min": 20, "max": 50},
            "cobre": {"min": 5, "max": 15},
            "boro": {"min": 20, "max": 50},
        },
        "soil": {
            "ph": {"min": 6.0, "max": 7.0},
            "materiaOrganica": {"min": 3.0, "max": 5.0},
            "nitrogeno": {"min": 0.15, "max": 0.25},
            "fosforo": {"min": 15, "max": 30},
            "potasio": {"min": 150, "max": 250},
            "calcio": {"min": 1000, "max": 2000},
            "magnesio": {"min": 150, "max": 300},
            "azufre": {"min": 10, "max": 20},
            "cic": {"min": 12, "max": 25},
        },
    }

    foliarChartData = [
        {"name": "N", "actual": analysisData["foliar"]["nitrogeno"], "min": optimalLevels["foliar"]["nitrogeno"]["min"], "max": optimalLevels["foliar"]["nitrogeno"]["max"]},
        {"name": "P", "actual": analysisData["foliar"]["fosforo"], "min": optimalLevels["foliar"]["fosforo"]["min"], "max": optimalLevels["foliar"]["fosforo"]["max"]},
        {"name": "K", "actual": analysisData["foliar"]["potasio"], "min": optimalLevels["foliar"]["potasio"]["min"], "max": optimalLevels["foliar"]["potasio"]["max"]},
        {"name": "Ca", "actual": analysisData["foliar"]["calcio"], "min": optimalLevels["foliar"]["calcio"]["min"], "max": optimalLevels["foliar"]["calcio"]["max"]},
        {"name": "Mg", "actual": analysisData["foliar"]["magnesio"], "min": optimalLevels["foliar"]["magnesio"]["min"], "max": optimalLevels["foliar"]["magnesio"]["max"]},
        {"name": "S", "actual": analysisData["foliar"]["azufre"], "min": optimalLevels["foliar"]["azufre"]["min"], "max": optimalLevels["foliar"]["azufre"]["max"]},
    ]

    soilChartData = [
        {"name": "pH", "actual": analysisData["soil"]["ph"], "min": optimalLevels["soil"]["ph"]["min"], "max": optimalLevels["soil"]["ph"]["max"], "unit": ""},
        {"name": "M.O.", "actual": analysisData["soil"]["materiaOrganica"], "min": optimalLevels["soil"]["materiaOrganica"]["min"], "max": optimalLevels["soil"]["materiaOrganica"]["max"], "unit": "%"},
        {"name": "N", "actual": analysisData["soil"]["nitrogeno"], "min": optimalLevels["soil"]["nitrogeno"]["min"], "max": optimalLevels["soil"]["nitrogeno"]["max"], "unit": "%"},
        {"name": "P", "actual": analysisData["soil"]["fosforo"], "min": optimalLevels["soil"]["fosforo"]["min"], "max": optimalLevels["soil"]["fosforo"]["max"], "unit": "ppm"},
        {"name": "K", "actual": analysisData["soil"]["potasio"], "min": optimalLevels["soil"]["potasio"]["min"], "max": optimalLevels["soil"]["potasio"]["max"], "unit": "ppm"},
        {"name": "CIC", "actual": analysisData["soil"]["cic"], "min": optimalLevels["soil"]["cic"]["min"], "max": optimalLevels["soil"]["cic"]["max"], "unit": "meq/100g"},
    ]

    historicalData = [
        {"fecha": "Ene 2025", "nitrogeno": 2.3, "fosforo": 0.25, "potasio": 1.5},
        {"fecha": "Feb 2025", "nitrogeno": 2.4, "fosforo": 0.28, "potasio": 1.6},
        {"fecha": "Mar 2025", "nitrogeno": 2.5, "fosforo": 0.3, "potasio": 1.8},
    ]

    nutrientNames = {
        "nitrogeno": "Nitrógeno",
        "fosforo": "Fósforo",
        "potasio": "Potasio",
        "calcio": "Calcio",
        "magnesio": "Magnesio",
        "azufre": "Azufre",
        "hierro": "Hierro",
        "manganeso": "Manganeso",
        "zinc": "Zinc",
        "cobre": "Cobre",
        "boro": "Boro",
        "ph": "pH",
        "materiaOrganica": "Materia Orgánica",
        "cic": "CIC",
    }

    def getNutrientStatus(actual, min, max):
        if actual < min:
            return "deficiente"
        if actual > max:
            return "excesivo"
        return "óptimo"

    def getStatusColor(status):
        match status:
            case "deficiente":
                return "text-red-500"
            case "excesivo":
                return "text-yellow-500"
            case "óptimo":
                return "text-green-500"
            case _:
                return ""

    def getStatusIcon(status):
        match status:
            case "deficiente":
                return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4 text-red-500"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"></polygon><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>'
            case "excesivo":
                return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4 text-yellow-500"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"></polygon><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>'
            case "óptimo":
                return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4 text-green-500"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="12 2 2 7.86 12 12"></polyline><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>'
            case _:
                return ""

    def findLimitingNutrient():
        limitingNutrient = None
        lowestPercentage = 100

        for nutrient, value in analysisData["foliar"].items():
            if nutrient in optimalLevels["foliar"]:
                min_value = optimalLevels["foliar"][nutrient]["min"]
                max_value = optimalLevels["foliar"][nutrient]["max"]
                optimalMid = (min_value + max_value) / 2
                percentage = (value / optimalMid) * 100
                if percentage < lowestPercentage and percentage < 90:
                    lowestPercentage = percentage
                    limitingNutrient = {
                        "name": nutrient,
                        "value": value,
                        "optimal": optimalMid,
                        "percentage": percentage,
                        "type": "foliar",
                    }

        for nutrient, value in analysisData["soil"].items():
            if nutrient in optimalLevels["soil"] and nutrient != "ph":
                min_value = optimalLevels["soil"][nutrient]["min"]
                max_value = optimalLevels["soil"][nutrient]["max"]
                optimalMid = (min_value + max_value) / 2
                percentage = (value / optimalMid) * 100
                if percentage < lowestPercentage and percentage < 90:
                    lowestPercentage = percentage
                    limitingNutrient = {
                        "name": nutrient,
                        "value": value,
                        "optimal": optimalMid,
                        "percentage": percentage,
                        "type": "soil",
                    }

        return limitingNutrient

    def generateRecommendations():
        recommendations = []

        limitingNutrient = findLimitingNutrient()

        if limitingNutrient:
            nutrientName = nutrientNames[limitingNutrient["name"]] or limitingNutrient["name"]
            recommendations.append({
                "title": f"Corregir deficiencia de {nutrientName}",
                "description": f"El {nutrientName} es el nutriente limitante según la Ley de Liebig. Está al limitingNutrient['percentage']% del nivel óptimo.",
                "priority": "alta",
                "action": "Aplicar fertilizante foliar rico en {nutrientName}" if limitingNutrient["type"] == "foliar" else f"Incorporar {nutrientName} al suelo mediante fertilización",
            })

        phStatus = getNutrientStatus(analysisData["soil"]["ph"], optimalLevels["soil"]["ph"]["min"], optimalLevels["soil"]["ph"]["max"])
        if phStatus != "óptimo":
            recommendations.append({
                "title": "Corregir acidez del suelo" if phStatus == "deficiente" else "Reducir alcalinidad del suelo",
                "description": f"El pH actual ({analysisData['soil']['ph']}) está {'por debajo' if phStatus == 'deficiente' else 'por encima'} del rango óptimo.",
                "priority": "media",
                "action": "Aplicar cal agrícola para elevar el pH" if phStatus == "deficiente" else "Aplicar azufre elemental o materia orgánica para reducir el pH",
            })

        moStatus = getNutrientStatus(analysisData["soil"]["materiaOrganica"], optimalLevels["soil"]["materiaOrganica"]["min"], optimalLevels["soil"]["materiaOrganica"]["max"])
        if moStatus == "deficiente":
            recommendations.append({
                "title": "Aumentar materia orgánica",
                "description": f"El nivel de materia orgánica ({analysisData['soil']['materiaOrganica']}%) está por debajo del óptimo.",
                "priority": "media",
                "action": "Incorporar compost, estiércol bien descompuesto o abonos verdes",
            })

        return recommendations

    limitingNutrient = findLimitingNutrient()
    recommendations = generateRecommendations()

    return render_template('ver_reporte.j2', **context, 
            request=request,  analysisData=analysisData, optimalLevels=optimalLevels, foliarChartData=foliarChartData, soilChartData=soilChartData, historicalData=historicalData, nutrientNames=nutrientNames, limitingNutrient=limitingNutrient, recommendations=recommendations)



@web.route("/solicitar_informe")
def generar_informe():
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
    return render_template("solicitar_informe.j2", **context, request=request)

@web.route("listar_reportes")
def listar_reportes():
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
    total_informes = 10
    
    return render_template("listar_reportes.j2", **context, request=request, total_informes=total_informes)




@web.route("/cv_nutrientes")
def cv_nutrientes():
    """
    Página: Renderiza la vista de CV de nutrientes
    """
    # Calcular el CV para cada nutriente en el lote con ID 1
    coeficientes_variacion = determinar_coeficientes_variacion(1)
    productos_contribuciones = contribuciones_de_producto()
    objective_resource = ObjectiveResource()
    response = objective_resource.get_objective_list()
    
    # Obtener demandas ideales para el cultivo de papa
    crop_objectives = response.papa
    demandas_ideales = crop_objectives.get(index=0)
    demandas_ideales_dict = demandas_ideales.nutrient_data  # Already Decimal

    # Obtener análisis de hojas para el lote con ID 1
    leaf_analysis_resource = LeafAnalysisResource()
    response = leaf_analysis_resource.get_leaf_analysis_list()
    data_string = response.get_json()
    data = json.loads(data_string)  
    nutrientes_actuales_raw = data["4"][0]["nutrients"]

    # Convertir los valores de nutrientes_actuales a Decimal
    nutrientes_actuales = {
        nutriente: Decimal(str(valor))  # Convert string to Decimal
        for nutriente, valor in nutrientes_actuales_raw.items()
    }

    # Asegurar que demandas_ideales_dict es un diccionario
    if not isinstance(demandas_ideales_dict, dict):
        raise ValueError("demandas_ideales no es un diccionario")

    # Asegurar que nutrientes_actuales es un diccionario
    if not isinstance(nutrientes_actuales, dict):
        raise ValueError("nutrientes_actuales no es un diccionario")
    
    # Instanciar y usar la clase
    optimizador = NutrientOptimizer(nutrientes_actuales, demandas_ideales_dict, productos_contribuciones, coeficientes_variacion)
    limitante = optimizador.identificar_limitante()
    recomendacion = optimizador.generar_recomendacion(lot_id=1)
    return f"Nutriente limitante: {limitante}\n{recomendacion}"