import json 
from decimal import Decimal

from flask import render_template, url_for, request, current_app
from flask_jwt_extended import get_jwt, jwt_required
from werkzeug.exceptions import Forbidden

from app.extensions import db
from . import foliage_report as web
from .helpers import calcular_cv_nutriente, determinar_coeficientes_variacion, contribuciones_de_producto, ObjectiveResource, LeafAnalysisResource, NutrientOptimizer, ReportView
from app.modules.foliage.models import Recommendation, Lot, Farm, Crop, CommonAnalysis
from app.core.controller import login_required, check_resource_access



def get_dashboard_menu():
    """Define el menu superior en los templates"""
    return {
        "menu": [
            {"name": "Home", "url": url_for("core.index")},
            {"name": "Logout", "url": url_for("core.logout")},
            {"name": "Profile", "url": url_for("core.profile")},
        ]
    }


@web.route("/listar_reportes/")
@login_required 
def listar_reportes():
    claims = get_jwt()
    user_role = claims.get("rol")
    
    # Obtener parámetros de filtro de la URL
    farm_id = request.args.get('farm_id', type=int)
    lot_id = request.args.get('lot_id', type=int)
    
    context = {
        "dashboard": True,
        "title": "Informes de Análisis",
        "description": "Listado de informes generados.",
        "author": "Johnny De Castro",
        "site_title": "Listado de Informes",
        "data_menu": get_dashboard_menu(),
        "entity_name": "Reportes",
        "entity_name_lower": "reporte",
        "selected_farm_id": farm_id,  # Para mantener la selección
        "selected_lot_id": lot_id     # Para mantener la selección
    }

    # Query base
    query = Recommendation.query.options(
        db.joinedload(Recommendation.lot).joinedload(Lot.farm).joinedload(Farm.organization),
        db.joinedload(Recommendation.crop)
    ).filter(Recommendation.active == True)
    
    # APLICAR FILTROS AQUÍ
    if lot_id:
        # Si se especifica un lote, filtrar por ese lote específico
        query = query.filter(Recommendation.lot_id == lot_id)
    elif farm_id:
        # Si solo se especifica finca, filtrar por todos los lotes de esa finca
        query = query.join(Lot).filter(Lot.farm_id == farm_id)

    accessible_recommendations = []
    all_recommendations = query.all()

    for rec in all_recommendations:
        if check_resource_access(rec.lot.farm, claims):
             accessible_recommendations.append(rec)

    # Serializar solo los datos necesarios para la tabla
    items_list = []
    for rec in accessible_recommendations:
        items_list.append({
            "id": rec.id,
            "title": rec.title,
            "finca_lote": f"{rec.lot.farm.name} / {rec.lot.name}" if rec.lot and rec.lot.farm else "N/A",
            "crop": rec.crop.name if rec.crop else "N/A",
            "date": rec.date.strftime('%Y-%m-%d') if rec.date else "N/A",
            "autor": rec.author or "Sistema"
        })

    total_informes = len(items_list)

    return render_template(
        "listar_reportes.j2",
        **context,
        request=request,
        total_informes=total_informes,
        items=items_list 
    )



@web.route("/vista_reporte/<int:report_id>")
@jwt_required() 
# @login_required
def vista_reporte(report_id):
    
    claims = get_jwt()
    context = {
        "dashboard": True,
        "title": "Ver Informe de Análisis",
        "description": "Detalles del informe.",
        "author": "Johnny De Castro",
        "site_title": "Ver Informe",
        "data_menu": get_dashboard_menu(),
    }

    # # Obtener la recomendación/reporte
    # report = Recommendation.query.get_or_404(report_id)
    # report_creator = ReportView() 
    # # Verificar acceso
    # if not check_resource_access(report.lot.farm, claims):
    #      raise Forbidden("No tienes acceso a este reporte.")

    # # --- Deserializar los datos guardados ---
    # # Es crucial que la estructura coincida con lo que espera 'ver_reporte.j2'
    # try:
    #     # Asume que estos campos guardan JSON strings
    #     foliar_details = json.loads(report.foliar_analysis_details or '{}')
    #     soil_details = json.loads(report.soil_analysis_details or '{}')
    #     optimal_levels_json = json.loads(report.optimal_comparison or '{}')

    #     # Reconstruir analysisData (necesitarás el common_analysis asociado)
    #     common_analysis = CommonAnalysis.query.get(foliar_details.get('common_analysis_id') or soil_details.get('common_analysis_id')) # O buscarlo de otra forma si no está en los detalles
    #     if not common_analysis:
    #         raise ValueError("No se encontró el CommonAnalysis asociado.")

        
    #     analysisData = {
    #         "common": {
    #             "id": common_analysis.id,
    #             "fechaAnalisis": common_analysis.date.isoformat(),
    #             "finca": common_analysis.lot.farm.name if common_analysis.lot and common_analysis.lot.farm else 'N/A',
    #             "lote": common_analysis.lot.name if common_analysis.lot else 'N/A',
    #             "proteinas": common_analysis.protein,
    #             "descanso": common_analysis.rest,
    #             "diasDescanso": common_analysis.rest_days,
    #             "mes": common_analysis.month
    #         },
    #         "foliar": foliar_details, # Usar directamente si la estructura coincide
    #         "soil": soil_details # Usar directamente si la estructura coincide
    #     }

    #     # Reconstruir optimalLevels
    #     optimalLevels = optimal_levels_json # Asume que la estructura ya es correcta

    #     # Reconstruir datos para los gráficos (si no están ya en el formato adecuado)
    #     # Ejemplo para foliarChartData (ajusta según tu serialización)
    #     foliarChartData = []
    #     if optimalLevels and 'nutrientes' in optimalLevels and analysisData.get('foliar'):
    #         for nutrient_key, levels in optimalLevels['nutrientes'].items():
    #             # Necesitas mapear nutrient_key (ej. 'nitrogeno') al nombre corto (ej. 'N')
    #             # y obtener el valor actual de analysisData.foliar
    #             # Esto requiere un mapeo o una lógica más robusta
    #             # Ejemplo simplificado:
    #             nutrient_name_map = {"nitrogeno": "N", "fosforo": "P", "potasio": "K", "calcio": "Ca", "magnesio": "Mg", "azufre": "S"} # etc.
    #             short_name = nutrient_name_map.get(nutrient_key)
    #             actual_value = analysisData['foliar'].get(nutrient_key)
    #             if short_name is not None and actual_value is not None and isinstance(levels, dict) and 'min' in levels and 'max' in levels:
    #                  foliarChartData.append({
    #                      "name": short_name,
    #                      "actual": actual_value,
    #                      "min": levels['min'],
    #                      "max": levels['max']
    #                  })

    #     # Ejemplo para soilChartData (similar a foliar)
    #     soilChartData = []
    #     if optimalLevels and 'nutrientes' in optimalLevels and analysisData.get('soil'):
    #          # ... lógica similar para soil ...
    #          pass # Implementar lógica de mapeo y extracción

    #     # Datos históricos (esto requeriría una consulta separada o estar almacenado)
    #     historicalData = [] # Obtener o generar estos datos dinámicamente si es necesario

    #     # Recomendaciones automáticas (del campo del modelo)
    #     recommendations_list = []
    #     if report.automatic_recommendations:
    #         # Si guardaste una lista JSON, deserialízala. Si es texto, procésalo.
    #         try:
    #             # Intenta cargar como JSON si guardaste una estructura
    #             recommendations_list = json.loads(report.automatic_recommendations)
    #             if not isinstance(recommendations_list, list): # Asegurar que sea una lista
    #                  # Si es texto simple, crea una estructura básica
    #                  recommendations_list = [{"title": "Recomendación Automática", "description": report.automatic_recommendations, "priority": "media", "action": "Revisar"}]
    #         except json.JSONDecodeError:
    #             # Si es solo texto, crea una estructura básica
    #              recommendations_list = [{"title": "Recomendación Automática", "description": report.automatic_recommendations, "priority": "media", "action": "Revisar"}]


    #     # Nutriente limitante (si lo guardaste)
    #     limitingNutrientData = None
    #     if report.limiting_nutrient_id:
    #         # Necesitarías recuperar los valores asociados a este nutriente
    #         # para reconstruir la estructura que espera la plantilla.
    #         # Esto es un placeholder, ajusta según cómo guardes la info.
    #          limitingNutrientData = {"name": report.limiting_nutrient_id, "percentage": 50, "type": "foliar/soil"} # Datos ficticios


    # except (json.JSONDecodeError, ValueError, AttributeError) as e:
    #     current_app.logger.error(f"Error al procesar datos del reporte {report_id}: {e}", exc_info=True)
    #     # Manejar el error, quizás mostrar un mensaje en la plantilla
    #     analysisData = {}
    #     optimalLevels = {}
    #     foliarChartData = []
    #     soilChartData = []
    #     historicalData = []
    #     recommendations_list = []
    #     limitingNutrientData = None
    #     # Podrías añadir un mensaje de error al contexto



    # # Pasar los datos dinámicos a la plantilla
    # analysisData = {}
    # optimalLevels = {}
    # foliarChartData = []
    # soilChartData = []
    # historicalData = []
    # recommendations_list = []
    # limitingNutrientData = None
    # # report_creator = ReportView() 
    # return render_template(
    #     'ver_reporte.j2',
    #     report_id=report_id,
        
    #     **context,
    #     request=request,
    #     analysisData=analysisData,
    #     optimalLevels=optimalLevels,
    #     foliarChartData=foliarChartData,
    #     soilChartData=soilChartData,
    #     historicalData=historicalData,
    #   #   nutrientNames=report_creator._get_nutrient_name_map(), # Reutilizar o definir mapeo
    #     limitingNutrient=limitingNutrientData,
    #     recommendations=recommendations_list
    # )


    report = Recommendation.query.options(
        db.joinedload(Recommendation.lot).joinedload(Lot.farm),
        db.joinedload(Recommendation.crop)
    ).get_or_404(report_id)

    if not check_resource_access(report.lot.farm, claims):
        raise Forbidden("No tienes acceso a este reporte.")

    # Initialize variables with default values
    analysisData = {"common": {}, "foliar": {}, "soil": {}}
    optimalLevels = {"foliar": {}, "soil": {}}

    foliarChartData = []
    soilChartData = []
    historicalData = [] # Per requirement, leave as empty list
    recommendations_list = []
    limitingNutrientData = None

    nutrient_name_map_full_to_short = {
        "nitrogeno": "N", "fosforo": "P", "potasio": "K", "calcio": "Ca", "magnesio": "Mg", "azufre": "S",
        "hierro": "Fe", "manganeso": "Mn", "zinc": "Zn", "cobre": "Cu", "boro": "B"
        # Add other mappings if necessary, especially for soil nutrients like pH, M.O., CIC
    }
    nutrient_name_map_key_to_display = {
        "nitrogeno": "Nitrógeno", "fosforo": "Fósforo", "potasio": "Potasio", "calcio": "Calcio",
        "magnesio": "Magnesio", "azufre": "Azufre", "hierro": "Hierro", "manganeso": "Manganeso",
        "zinc": "Zinc", "cobre": "Cobre", "boro": "Boro",
        "ph": "pH", "materiaOrganica": "Materia Orgánica", "cic": "CIC"
        # Add other mappings as they appear in foliar_details or soil_details keys
    }

    try:
        foliar_details = json.loads(report.foliar_analysis_details or '{}')
        soil_details = json.loads(report.soil_analysis_details or '{}')
        optimal_levels_json = json.loads(report.optimal_comparison or '{}') # This is optimalLevels

        # Reconstruct analysisData
        analysisData['foliar'] = foliar_details
        analysisData['soil'] = soil_details
        analysisData['common'] = {
            # 'id': foliar_details.get('common_analysis_id'), # Assuming common_analysis_id was stored
            'fechaAnalisis': report.date.isoformat(), # Use report date as analysis date
            'finca': report.lot.farm.name if report.lot and report.lot.farm else 'N/A',
            'lote': report.lot.name if report.lot else 'N/A',
            'cultivo': report.crop.name if report.crop else 'N/A',
            # Other common fields like proteinas, descanso can be added if they are in foliar_details
        }
        # Update nutrient_name_map_key_to_display with keys from actual data
        for key in foliar_details.keys():
            if key not in nutrient_name_map_key_to_display:
                nutrient_name_map_key_to_display[key] = key.replace("_", " ").title()
        for key in soil_details.keys():
            if key not in nutrient_name_map_key_to_display:
                nutrient_name_map_key_to_display[key] = key.replace("_", " ").title()


        # Reconstruct optimalLevels (already done by optimal_levels_json)
        # The structure from Recommendation.optimal_comparison should be:
        # {'NutrientName': {'min': X, 'max': Y, 'ideal': Z, 'unit': 'unit'}, ...}
        # The template expects optimalLevels.foliar and optimalLevels.soil,
        # but our optimal_comparison is flat. We need to adapt or assume template changes.
        # For now, assume optimal_levels_json can be directly used if it matches template's needs,
        # or we might need to restructure it if it's flat.
        # Based on ver_reporte2.j2, it expects optimalLevels.foliar and optimalLevels.soil.
        # The optimal_comparison from previous step is flat: {'NutrientName': {'min': X, ...}}
        # We need to segregate this into foliar and soil based on known nutrient types or by inspecting analysisData.
        
        optimalLevels = {"foliar": {}, "soil": {}}
        for nutrient_key, levels_data in optimal_levels_json.items():
            if nutrient_key in analysisData['foliar']:
                optimalLevels['foliar'][nutrient_key] = levels_data
            elif nutrient_key in analysisData['soil']:
                optimalLevels['soil'][nutrient_key] = levels_data
            else: # Fallback if nutrient not in foliar or soil data, put in foliar by default or log
                optimalLevels['foliar'][nutrient_key] = levels_data 
                current_app.logger.warning(f"Nutrient {nutrient_key} from optimal_comparison not found in foliar or soil analysisData. Added to foliar optimalLevels by default.")


        # Reconstruct foliarChartData
        if analysisData.get('foliar') and optimalLevels.get('foliar'):
            for nutrient_key, actual_value in analysisData['foliar'].items():
                if isinstance(actual_value, (int, float)): # Ensure it's a plottable value
                    levels = optimalLevels['foliar'].get(nutrient_key)
                    short_name = nutrient_name_map_full_to_short.get(nutrient_key.lower(), nutrient_key[:3].upper())
                    if levels and 'min' in levels and 'max' in levels:
                        foliarChartData.append({
                            "name": short_name,
                            "actual": float(actual_value),
                            "min": float(levels['min']),
                            "max": float(levels['max'])
                        })
        
        # Reconstruct soilChartData
        if analysisData.get('soil') and optimalLevels.get('soil'):
            for nutrient_key, actual_value in analysisData['soil'].items():
                if isinstance(actual_value, (int, float)): # Ensure it's a plottable value
                    levels = optimalLevels['soil'].get(nutrient_key)
                    # Soil chart names might be direct keys like 'pH', 'M.O.'
                    short_name = nutrient_name_map_full_to_short.get(nutrient_key.lower(), nutrient_key.replace("_", " ").title()[:4])
                    if levels and 'min' in levels and 'max' in levels:
                        soilChartData.append({
                            "name": short_name, # Or nutrient_key.title() if more appropriate
                            "actual": float(actual_value),
                            "min": float(levels['min']),
                            "max": float(levels['max']),
                            "unit": levels.get('unit', '') 
                        })
        
        # Reconstruct recommendations_list
        if report.automatic_recommendations:
            try:
                # Attempt to load as JSON if it's a structured list
                parsed_recs = json.loads(report.automatic_recommendations)
                if isinstance(parsed_recs, list):
                    recommendations_list = parsed_recs
                elif isinstance(parsed_recs, dict): # If it's a single recommendation dict
                    recommendations_list = [parsed_recs]
                else: # If it's simple text after JSON load (unlikely but possible)
                    recommendations_list = [{"title": "Recomendación Automática", "description": str(parsed_recs), "priority": "media", "action": "Revisar"}]
            except json.JSONDecodeError:
                # If it's just plain text
                recommendations_list = [{"title": "Recomendación Automática", "description": report.automatic_recommendations, "priority": "media", "action": "Revisar"}]
        
        # Reconstruct limitingNutrientData
        if report.limiting_nutrient_id:
            nutrient_name = report.limiting_nutrient_id
            actual_value = None
            nutrient_type = None
            optimal_val_for_limiting = None

            if nutrient_name in analysisData['foliar']:
                actual_value = analysisData['foliar'][nutrient_name]
                nutrient_type = 'foliar'
                if optimalLevels['foliar'] and nutrient_name in optimalLevels['foliar']:
                    optimal_val_for_limiting = optimalLevels['foliar'][nutrient_name].get('ideal', (optimalLevels['foliar'][nutrient_name].get('min', 0) + optimalLevels['foliar'][nutrient_name].get('max', 0)) / 2)
            elif nutrient_name in analysisData['soil']:
                actual_value = analysisData['soil'][nutrient_name]
                nutrient_type = 'soil'
                if optimalLevels['soil'] and nutrient_name in optimalLevels['soil']:
                    optimal_val_for_limiting = optimalLevels['soil'][nutrient_name].get('ideal', (optimalLevels['soil'][nutrient_name].get('min', 0) + optimalLevels['soil'][nutrient_name].get('max', 0)) / 2)
            
            if actual_value is not None and optimal_val_for_limiting is not None and optimal_val_for_limiting != 0:
                percentage = (Decimal(str(actual_value)) / Decimal(str(optimal_val_for_limiting))) * 100
                limitingNutrientData = {
                    "name": nutrient_name,
                    "value": float(actual_value),
                    "optimal": float(optimal_val_for_limiting),
                    "percentage": float(percentage),
                    "type": nutrient_type
                }
            elif actual_value is not None: # Optimal not found, but actual is
                limitingNutrientData = { "name": nutrient_name, "value": float(actual_value), "optimal": "N/A", "percentage": "N/A", "type": nutrient_type}


    except json.JSONDecodeError as e:
        current_app.logger.error(f"Error deserializando JSON para reporte {report_id}: {e}")
        # context["error_message"] = "Error al cargar detalles del reporte. Algunos datos pueden estar corruptos."
    except Exception as e:
        current_app.logger.error(f"Error procesando datos del reporte {report_id}: {e}", exc_info=True)
        # context["error_message"] = "Error inesperado al procesar datos del reporte."


    return render_template(
        'ver_reporte2.j2', # Changed template
        **context,
        # Pass reconstructed data
        analysisData=analysisData,
        optimalLevels=optimalLevels,
        foliarChartData=foliarChartData,
        soilChartData=soilChartData,
        historicalData=historicalData, # Empty as per instructions
        nutrientNames=nutrient_name_map_key_to_display, # Pass the map
        limitingNutrient=limitingNutrientData,
        recommendations=recommendations_list
    )



@web.route("/vista_report")
@login_required
def vista_report():
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

    return render_template('ver_reporte2.j2', **context, 
            request=request,  analysisData=analysisData, optimalLevels=optimalLevels, foliarChartData=foliarChartData, soilChartData=soilChartData, historicalData=historicalData, nutrientNames=nutrientNames, limitingNutrient=limitingNutrient, recommendations=recommendations)



@web.route("/solicitar_informe")
@login_required
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
    return render_template("solicitar_informe2.j2", **context, request=request)
# return render_template("solicitar_informe.j2", **context, request=request)





@web.route("/cv_nutrientes")
@login_required
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


###########################
# example
@web.route("/reportes_demo")
def reports_dashboard():
    context = {
        "role": "ORG_ADMIN",  # Cambia a ORG_EDITOR o ORG_VIEWER para testear
        "farms": [
            {"id": 1, "name": "Finca El Sol"},
            {"id": 2, "name": "Finca La Esperanza"},
        ],
        "lots": [
            {"id": 1, "name": "Lote 1"},
            {"id": 2, "name": "Lote 2"},
        ],
        "reports": [
            {
                "id": 101,
                "date": "2025-05-20",
                "farm": "Finca El Sol",
                "lot": "Lote 1",
                "type": "foliar",
                "crop": "Café",
                "status": "Listo"
            },
            {
                "id": 102,
                "date": "2025-05-22",
                "farm": "Finca La Esperanza",
                "lot": "Lote 2",
                "type": "suelo",
                "crop": "Cacao",
                "status": "En análisis"
            }
        ]
    }
    return render_template("reports.j2", **context)
