# Python standard library imports
import json
from datetime import datetime
from decimal import Decimal
from functools import wraps
import unicodedata

from flask import Response, current_app, jsonify, request
from flask.views import MethodView
from flask_jwt_extended import get_jwt, jwt_required

# Third party imports
from werkzeug.exceptions import BadRequest, Forbidden, InternalServerError, NotFound

from app.core.controller import check_permission, check_resource_access
from app.core.models import ResellerPackage, RoleEnum

# Local application imports
from app.extensions import db
from app.modules.foliage.models import (
    CommonAnalysis,
    Crop,
    Farm,
    LeafAnalysis,
    Lot,
    LotCrop,
    Nutrient,
    Objective,
    Recommendation,
    SoilAnalysis,
    leaf_analysis_nutrients,
    objective_nutrients,
)

from .helpers import (
    LeafAnalysisResource,
    NutrientOptimizer,
    ObjectiveResource,
    contribuciones_de_producto,
)


class ReportView(MethodView):
    """Clase para generar reportes integrados de análisis"""

    decorators = [jwt_required()]

    def get(self, id):
        recommendation = Recommendation.query.get_or_404(id)

        def safe_json_load(data):
            try:
                return json.loads(data) if data else {}
            except json.JSONDecodeError:
                return {}

        foliar_data = safe_json_load(recommendation.foliar_analysis_details)
        optimal_levels = safe_json_load(recommendation.optimal_comparison)
        def normalize_key(s):
            return ''.join(
                c for c in unicodedata.normalize('NFD', s.lower())
                if unicodedata.category(c) != 'Mn'
            )
        def build_foliar_chart(foliar, optimal):
            keys = {
                "N": "nitrógeno",
                "P": "fósforo",
                "K": "potasio",
                "Ca": "calcio",
                "Mg": "magnesio",
                "S": "azufre",
                "Fe": "hierro",
                "Mn": "manganeso",
                "Zn": "zinc",
                "Cu": "cobre",
                "B": "boro",
                "Mo": "molibdeno",
                "Si": "silicio"
            }
            # Ensure optimal_levels is a dictionary, specifically for foliar and soil keys
            # The structure for optimal_levels is expected to be:
            # {
            #   "foliar": {"nutrient_name": {"min": X, "max": Y, "unit": "Z"}, ...},
            #   "soil": {"nutrient_name": {"min": X, "max": Y, "unit": "Z"}, ...}
            # }
            # If optimal_comparison is a string, it's parsed from JSON.
            # If it's already a dict (e.g. from RecommendationGenerator), it's used directly.
            
            optimal_levels_data = {}
            if isinstance(recommendation.optimal_comparison, str):
                optimal_levels_data = safe_json_load(recommendation.optimal_comparison)
            elif isinstance(recommendation.optimal_comparison, dict):
                optimal_levels_data = recommendation.optimal_comparison

            # Fallback if optimal_levels_data is still not in the expected nested structure
            # This might happen if `optimal_comparison` stores a flat dict of nutrients
            # without the "foliar" or "soil" keys.
            # We'll assume all such nutrients are "foliar" for now if not nested.
            # And ensure "foliar" and "soil" keys exist.
            if not isinstance(optimal_levels_data.get("foliar"), dict) or \
               not isinstance(optimal_levels_data.get("soil"), dict):

                # Attempt to intelligently restructure if it's a flat dictionary of nutrients
                is_flat_nutrient_dict = all(
                    isinstance(v, dict) and ("min" in v or "max" in v or "ideal" in v)
                    for k, v in optimal_levels_data.items()
                    if k not in ["foliar", "soil"] # Avoid recursion if already partially structured
                )

                if is_flat_nutrient_dict and not ("foliar" in optimal_levels_data or "soil" in optimal_levels_data):
                    # Example: optimal_levels_data = {"nitrogeno": {"min": ...}, "fosforo": {"min": ...}}
                    # This heuristic assumes such flat structures primarily refer to foliar.
                    # A more robust solution might involve checking nutrient names against known soil/foliar types.
                    current_app.logger.info("Restructuring flat optimal_levels_data, assuming foliar for top-level nutrients.")
                    foliar_part = {k: v for k, v in optimal_levels_data.items()}
                    optimal_levels_data = {"foliar": foliar_part, "soil": {}}
                else:
                    # If it's not a flat dict or already partially structured but malformed, default safely.
                    current_app.logger.warning(
                        f"optimal_levels_data is not in the expected nested format. Original: {optimal_levels_data}. Defaulting foliar/soil to empty dicts."
                    )
                    if not isinstance(optimal_levels_data.get("foliar"), dict):
                        optimal_levels_data["foliar"] = {}
                    if not isinstance(optimal_levels_data.get("soil"), dict):
                        optimal_levels_data["soil"] = {}

            # Ensure foliar_data and soil_data are dictionaries
            foliar_analysis_data = safe_json_load(recommendation.foliar_analysis_details) \
                if isinstance(recommendation.foliar_analysis_details, str) \
                else (recommendation.foliar_analysis_details or {})

            soil_analysis_data = safe_json_load(recommendation.soil_analysis_details) \
                if isinstance(recommendation.soil_analysis_details, str) \
                else (recommendation.soil_analysis_details or {})


            # Build chart data for foliar and soil
            foliar_chart_data = self._build_chart_data(
                foliar_analysis_data,
                optimal_levels_data.get("foliar", {}), # Safe access
                is_soil=False
            )
            soil_chart_data = self._build_chart_data(
                soil_analysis_data,
                optimal_levels_data.get("soil", {}), # Safe access
                is_soil=True
            )

            # Nutrient names map
            nutrient_names = self._get_nutrient_name_map()

            # Limiting nutrient data
            # The limiting_nutrient_id stored in recommendation is just a name (string).
            # We need to reconstruct the structure expected by the template:
            # {"name": "nutrient_key", "value": X, "percentage": Y, "type": "foliar/soil"}
            limiting_nutrient_details = self._get_limiting_nutrient_data(
                recommendation.limiting_nutrient_id,
                {"foliar": foliar_analysis_data, "soil": soil_analysis_data},
                optimal_levels_data # Pass the entire optimal_levels_data structure
            )

            # Recommendations: automatic_recommendations is a text.
            # The template `vista_report` had a function `generateRecommendations`
            # which created a list of dicts. We need to adapt this.
            # For now, we'll pass the raw text and potentially parse it or
            # adjust the template if it expects a structured list.
            # The `automatic_recommendations` field in the DB seems to store the text output
            # from `NutrientOptimizer.generar_recomendacion`.
            # The template `ver_reporte2.j2` iterates over `recommendations` expecting a list of dicts.
            # This part needs careful adaptation.
            # Let's try to parse the automatic_recommendations if it's a JSON string
            # or simulate the structure if it's plain text.
            parsed_recommendations = []
            if recommendation.automatic_recommendations:
                try:
                    # If it's a JSON list of recommendations
                    parsed_recs = json.loads(recommendation.automatic_recommendations)
                    if isinstance(parsed_recs, list):
                        parsed_recommendations = parsed_recs
                    else: # If it's a single JSON object, wrap it in a list
                        parsed_recommendations = [parsed_recs]
                except json.JSONDecodeError:
                    # If it's plain text, create a basic recommendation structure
                    # This is a placeholder and might need more sophisticated parsing
                    # based on the actual content of `automatic_recommendations`.
                    parsed_recommendations.append({
                        "title": "Recomendación Automática",
                        "description": recommendation.automatic_recommendations,
                        "priority": "media", # Default priority
                        "action": "Revisar detalles en la descripción."
                    })

            # Add text_recommendations if any
            if recommendation.text_recommendations:
                 parsed_recommendations.append({
                        "title": "Recomendaciones Adicionales",
                        "description": recommendation.text_recommendations,
                        "priority": "media",
                        "action": "Considerar estas notas adicionales."
                    })


        response = {
            "id": recommendation.id,
            "date": recommendation.date.isoformat(),
            "title": recommendation.title,
            "author": recommendation.author,
            "analysisData": {
                "common": {
                    "id": recommendation.id, # or common_analysis.id if available
                    "fechaAnalisis": recommendation.date.isoformat(), # or common_analysis.date
                    "finca": recommendation.lot.farm.name if recommendation.lot and recommendation.lot.farm else "N/A",
                    "lote": recommendation.lot.name if recommendation.lot else "N/A",
                    # Add other common fields if they come from a CommonAnalysis record
                    # "proteinas": common_analysis.protein if common_analysis else None,
                    # "descanso": common_analysis.rest if common_analysis else None,
                },
                "foliar": foliar_analysis_data,
                "soil": soil_analysis_data,
            },
            "optimalLevels": optimal_levels_data, # Use the processed optimal_levels_data
            "foliarChartData": foliar_chart_data,
            "soilChartData": soil_chart_data,
            "historicalData": self._get_historical_data(recommendation.lot_id, recommendation.date),
            "nutrientNames": nutrient_names,
            "limitingNutrient": limiting_nutrient_details,
            "recommendations": parsed_recommendations, # Use parsed recommendations
            "crop": {
                "id": recommendation.crop.id,
                "name": recommendation.crop.name,
            } if recommendation.crop else None,
            "lot": {
                "id": recommendation.lot.id,
                "name": recommendation.lot.name,
                "farm": {
                    "id": recommendation.lot.farm.id,
                    "name": recommendation.lot.farm.name,
                } if recommendation.lot.farm else None,
            } if recommendation.lot else None,
            "limiting_nutrient_id": recommendation.limiting_nutrient_id,
            "automatic_recommendations": recommendation.automatic_recommendations or "",
            "text_recommendations": recommendation.text_recommendations or "",
            "minimum_law_analyses": safe_json_load(recommendation.minimum_law_analyses),
            "applied": recommendation.applied,
            "active": recommendation.active,
            "created_at": recommendation.created_at.isoformat(),
            "updated_at": recommendation.updated_at.isoformat(),
            "organization": {
                "id": recommendation.organization.id,
                "name": recommendation.organization.name,
            } if recommendation.organization else None
        }

        return jsonify(response)

    def _build_chart_data(self, analysis_details, optimal_levels, is_soil=False):
        """
        Helper function to build chart data for either foliar or soil analysis.
        analysis_details: dict of actual nutrient values (e.g., {"nitrogeno": 2.5, ...})
        optimal_levels: dict of optimal nutrient levels (e.g., {"nitrogeno": {"min": 2.8, "max": 3.5}, ...})
        is_soil: boolean, True if building for soil, False for foliar.
        """
        chart_data = []

        # Define nutrient keys relevant for charts.
        # These should match keys in analysis_details and optimal_levels.
        # Normalization of keys (e.g. 'Nitrógeno' vs 'nitrogeno') should be handled
        # before this function or by ensuring consistency in stored data.

        if is_soil:
            # Typical soil chart nutrients (adjust as needed)
            nutrient_keys_map = {
                "pH": "ph", # pH is a common one, often without min/max in same way
                "M.O.": "materiaOrganica", # Materia Orgánica
                "N": "nitrogeno",
                "P": "fosforo",
                "K": "potasio",
                "Ca": "calcio",
                "Mg": "magnesio",
                "S": "azufre",
                "CIC": "cic" # Capacidad de Intercambio Catiónico
            }
        else:
            # Typical foliar chart nutrients
            nutrient_keys_map = {
                "N": "nitrogeno", "P": "fosforo", "K": "potasio",
                "Ca": "calcio", "Mg": "magnesio", "S": "azufre",
                "Fe": "hierro", "Mn": "manganeso", "Zn": "zinc",
                "Cu": "cobre", "B": "boro", "Mo": "molibdeno"
                # "Si": "silicio" # Example, if used
            }

        for chart_label, data_key in nutrient_keys_map.items():
            actual_value = analysis_details.get(data_key)

            # Try normalized key for optimal_levels if direct key fails
            optimal_data_for_key = optimal_levels.get(data_key)
            if not optimal_data_for_key:
                 normalized_data_key = normalize_key(data_key)
                 optimal_data_for_key = optimal_levels.get(normalized_data_key)


            if actual_value is not None and optimal_data_for_key and \
               "min" in optimal_data_for_key and "max" in optimal_data_for_key:
                try:
                    chart_data.append({
                        "name": chart_label, # This is the display name like "N", "P", "pH"
                        "data_key": data_key, # This is the internal key like "nitrogeno", "ph"
                        "actual": float(actual_value),
                        "min": float(optimal_data_for_key["min"]),
                        "max": float(optimal_data_for_key["max"]),
                        "unit": optimal_data_for_key.get("unit", "") # Add unit if available
                    })
                except (ValueError, TypeError) as e:
                    current_app.logger.warning(
                        f"Could not parse chart values for nutrient '{data_key}' (label: {chart_label}): {e}. "
                        f"Actual: {actual_value}, Optimal: {optimal_data_for_key}"
                    )
            elif actual_value is not None and data_key == "ph": # Special handling for pH if it doesn't have min/max
                 chart_data.append({
                        "name": chart_label, # pH
                        "data_key": data_key, # ph
                        "actual": float(actual_value),
                        "min": None, # Or some default/expected value if applicable
                        "max": None,
                        "unit": optimal_data_for_key.get("unit", "") if optimal_data_for_key else ""
                    })


        return chart_data

    def _get_common_analysis(self, analysis_id):
        """Obtiene el análisis común con relaciones optimizadas"""
        return CommonAnalysis.query.options(
            db.joinedload(CommonAnalysis.lot).joinedload(Lot.farm),
            db.joinedload(CommonAnalysis.soil_analysis),
            db.joinedload(CommonAnalysis.leaf_analysis),
        ).get_or_404(analysis_id)

    def _check_access(self, common_analysis):
        """Valida permisos de acceso a la organización"""
        claims = get_jwt()
        user_role = claims.get("rol")

        if user_role == RoleEnum.ADMINISTRATOR.value:
            return

        if user_role == RoleEnum.RESELLER.value:
            org_id = (
                common_analysis.organization.id
                if common_analysis.organization
                else None
            )
            if not org_id:
                raise Forbidden("No se pudo determinar la organización del análisis")

            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=claims.get("org_id")
            ).first()

            if not reseller_package or org_id not in reseller_package.organization_ids:
                raise Forbidden("Acceso denegado al recurso")

    def _build_analysis_data(self, analysis):
        """Construye la estructura principal del reporte"""
        # This method seems to be used by RecommendationGenerator.
        # It might need adjustment if the source `analysis` (CommonAnalysis)
        # stores nutrient names differently than `foliar_analysis_details` JSON.
        # For ReportView.get, we are using foliar_analysis_details directly.
        return {
            "common": self._serialize_common(analysis),
            "foliar": self._get_foliar_data(analysis.leaf_analysis),
            "soil": self._get_soil_data(analysis.soil_analysis),
        }

    def _serialize_common(self, analysis):
        """Serializa datos del análisis común"""
        return {
            "id": analysis.id,
            "fechaAnalisis": analysis.date.isoformat(),
            "finca": (
                analysis.lot.farm.name if analysis.lot and analysis.lot.farm else "N/A"
            ), # Corrected to use navigation
            "lote": analysis.lot.name if analysis.lot else "N/A", # Corrected
            "proteinas": analysis.protein,
            "descanso": analysis.rest,
            "diasDescanso": analysis.rest_days,
            "mes": analysis.month,
            "aforo": analysis.yield_estimate,
        }

    def _get_foliar_data(self, leaf_analysis):
        """Obtiene y formatea datos foliares. Keys are normalized (lowercase, no spaces)."""
        if not leaf_analysis:
            return {} # Return empty dict instead of None

        foliar_data = {"id": leaf_analysis.id}
        # Assuming leaf_analysis.nutrients is a list of NutrientAssociation objects
        # where each object has .nutrient (Nutrient model) and .value
        # If leaf_analysis.nutrients is a direct link to Nutrient model through leaf_analysis_nutrients table,
        # the query to get values needs to be explicit.

        # Current implementation in controller uses a direct query on leaf_analysis_nutrients
        # Let's stick to that for consistency if this method is used by RecommendationGenerator.
        nutrient_entries = (
            db.session.query(Nutrient, leaf_analysis_nutrients.c.value)
            .join(
                leaf_analysis_nutrients,
                Nutrient.id == leaf_analysis_nutrients.c.nutrient_id,
            )
            .filter(leaf_analysis_nutrients.c.leaf_analysis_id == leaf_analysis.id)
            .all()
        )
        for nutrient, value in nutrient_entries:
            key = normalize_key(nutrient.name) # Use normalized key
            foliar_data[key] = float(value) if value is not None else None
        return foliar_data

    def _get_soil_data(self, soil_analysis):
        """Obtiene y formatea datos de suelo. Keys are property names from SoilAnalysis model."""
        if not soil_analysis:
            return {} # Return empty dict

        # Example: extract relevant soil properties. Adjust as per SoilAnalysis model.
        # This should ideally match the structure expected by `_build_chart_data` and the template.
        # For instance, if soil_analysis stores "materiaOrganica", "ph", etc.
        data = {"id": soil_analysis.id}
        # Assuming SoilAnalysis has attributes like ph, materiaOrganica, nitrogeno, etc.
        # These need to be explicitly listed or iterated if stored in a related table.

        # For now, let's assume direct attributes for common ones needed by charts.
        # The `soil_analysis_details` JSON in `Recommendation` model is the primary source for `ReportView.get`.
        # This helper is more for `RecommendationGenerator` if it builds this from scratch.

        attrs_to_get = ["ph", "materiaOrganica", "nitrogeno", "fosforo", "potasio", "calcio", "magnesio", "azufre", "cic", "energy", "grazing"]
        for attr in attrs_to_get:
            if hasattr(soil_analysis, attr):
                value = getattr(soil_analysis, attr)
                data[attr] = float(value) if isinstance(value, Decimal) else value
        return data


    def _lot_crop_data(self, common_analysis):
        """Obtiene el cultivo activo del lote en la fecha del análisis"""
        if not common_analysis or not common_analysis.lot_id:
            return None

        lot_crop = (
            LotCrop.query.filter(
                LotCrop.lot_id == common_analysis.lot_id,
                LotCrop.start_date <= common_analysis.date,
                db.or_(
                    LotCrop.end_date >= common_analysis.date, LotCrop.end_date.is_(None)
                ),
            )
            .options(db.joinedload(LotCrop.crop))
            .first()
        )

        return lot_crop

    def _get_optimal_levels(self, common_analysis):
        """Obtiene niveles óptimos del cultivo actual"""
        lot_crop = self._lot_crop_data(common_analysis)
        if not lot_crop or not lot_crop.crop:
            return None

        objective = Objective.query.filter_by(crop_id=lot_crop.crop.id).first()
        if not objective:
            return None

        return {
            "info": {
                "cultivo": lot_crop.crop.name,
                "valor_obj": objective.target_value,
                "proteina": objective.protein,
                "descanso": objective.rest,
            },
            "nutrientes": self._get_nutrient_targets(objective),
        }

    def _get_nutrient_targets(self, objective):
        """Obtiene y formatea los objetivos de nutrientes desde objective_nutrients"""
        targets = {}
        obj_nutrients = (
            db.session.query(objective_nutrients)
            .filter_by(objective_id=objective.id)
            .all()
        )

        for on in obj_nutrients:
            nutrient = Nutrient.query.get(on.nutrient_id)
            if nutrient:
                key = nutrient.name.lower().replace(" ", "")
                targets[key] = (
                    on.target_value
                )

        return targets

    def _get_historical_data(self, lot_id, current_date):
        """Obtiene datos históricos de análisis foliares para el lote."""

        # Permitir recibir un objeto Lot o simplemente su id
        if isinstance(lot_id, Lot):
            lot_id = lot_id.id

        historical_analyses = (
            LeafAnalysis.query.join(CommonAnalysis)
            .filter(
                CommonAnalysis.lot_id == lot_id,
                CommonAnalysis.date < current_date,
            )
            .order_by(CommonAnalysis.date.desc())
            .limit(5)
            .all()
        )

        data = []
        for analysis in reversed(historical_analyses):
            nutrients = (
                db.session.query(leaf_analysis_nutrients)
                .filter_by(leaf_analysis_id=analysis.id)
                .all()
            )
            entry = {
                "fecha": analysis.common_analysis.date.strftime("%b %Y")
            }
            for nv in nutrients:
                nutrient = Nutrient.query.get(nv.nutrient_id)
                if nutrient:
                    key = nutrient.name.lower().replace(" ", "")
                    entry[key] = nv.value
            data.append(entry)

        return data

    def _get_limiting_nutrient_data(self, limiting_name, analysisData, optimalLevels_data):
        """
        Intenta reconstruir los datos del nutriente limitante.
        analysisData: {"foliar": {...}, "soil": {...}}
        optimalLevels_data: {"foliar": {"nutrient": {"min": X, "max": Y, ...}}, "soil": {"nutrient": {"min": X, "max": Y, ...}}}
        """
        if not limiting_name or not analysisData:
            return None

        # Normalize limiting_name once
        normalized_limiting_name = normalize_key(limiting_name)

        # Check foliar nutrients
        foliar_analysis = analysisData.get("foliar", {})
        foliar_optimal = optimalLevels_data.get("foliar", {})
        for key, value in foliar_analysis.items():
            # Normalize key from analysis data for comparison
            normalized_key = normalize_key(key)
            if normalized_key == normalized_limiting_name:
                # Find corresponding optimal levels using original key or normalized one
                levels = foliar_optimal.get(key) or foliar_optimal.get(normalized_key)
                if levels and isinstance(levels, dict) and "min" in levels and "max" in levels:
                    # Ensure values are numeric for calculation
                    try:
                        actual_value = float(value)
                        min_val = float(levels["min"])
                        max_val = float(levels["max"])
                        optimal_mid = (min_val + max_val) / 2
                        percentage = (actual_value / optimal_mid * 100) if optimal_mid != 0 else 0
                        return {
                            "name": key, # Return original key
                            "value": actual_value,
                            "percentage": round(percentage, 2),
                            "type": "foliar",
                        }
                    except (ValueError, TypeError):
                        current_app.logger.warning(f"Could not parse values for nutrient {key} in foliar limiting nutrient calculation.")
                        continue # Skip if values are not numeric

        # Check soil nutrients
        soil_analysis = analysisData.get("soil", {})
        soil_optimal = optimalLevels_data.get("soil", {})
        for key, value in soil_analysis.items():
            normalized_key = normalize_key(key)
            if key.lower() != "ph" and normalized_key == normalized_limiting_name:
                levels = soil_optimal.get(key) or soil_optimal.get(normalized_key)
                if levels and isinstance(levels, dict) and "min" in levels and "max" in levels:
                    try:
                        actual_value = float(value)
                        min_val = float(levels["min"])
                        max_val = float(levels["max"])
                        optimal_mid = (min_val + max_val) / 2
                        percentage = (actual_value / optimal_mid * 100) if optimal_mid != 0 else 0
                        return {
                            "name": key, # Return original key
                            "value": actual_value,
                            "percentage": round(percentage, 2),
                            "type": "soil",
                        }
                    except (ValueError, TypeError):
                        current_app.logger.warning(f"Could not parse values for nutrient {key} in soil limiting nutrient calculation.")
                        continue # Skip if values are not numeric

        # Fallback if not found or error
        return {
            "name": limiting_name, # Original name passed
            "value": None,
            "percentage": None,
            "type": "unknown",
        }

    def _get_nutrient_name_map(self):
        """Genera un mapa de claves internas a nombres legibles."""
        return {
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
            # Añade mapeos para todas las claves que uses
        }


nutrient_names_map = ReportView()._get_nutrient_name_map()


class RecommendationView(MethodView):
    """Class to manage CRUD operations for recommendations"""

    decorators = [jwt_required()]

    @check_permission(required_roles=["administrator", "reseller"])
    def get(self, recommendation_id=None):
        """
        Retrieve a list of recommendations or a specific recommendation
        Args:
            recommendation_id (int, optional): ID of the recommendation to retrieve
        Returns:
            JSON: List of recommendations or details of a specific recommendation
        """
        if recommendation_id:
            return self._get_recommendation(recommendation_id)
        return self._get_recommendation_list()

    @check_permission(required_roles=["administrator", "reseller"])
    def post(self):
        """
        Create a new recommendation
        Returns:
            JSON: Details of the created recommendation
        """
        data = request.get_json()
        required_fields = ["lot_id", "date", "recommendation"]
        if not data or not all(k in data for k in required_fields):
            raise BadRequest("Missing required fields")
        return self._create_recommendation(data)

    @check_permission(resource_owner_check=True)
    def put(self, id: int):
        """
        Update an existing recommendation
        Args:
            recommendation_id (int): ID of the recommendation to update
        Returns:
            JSON: Details of the updated recommendation
        """
        data = request.get_json()
        recommendation_id = id
        if not data or not recommendation_id:
            raise BadRequest("Missing recommendation_id or data")
        return self._update_recommendation(recommendation_id, data)

    @check_permission(resource_owner_check=True)
    def delete(self, id=None):
        """
        Delete an existing recommendation
        Args:
            recommendation_id (int): ID of the recommendation to delete
        Returns:
            JSON: Confirmation message
        """
        recommendation_id = id
        if not recommendation_id:
            raise BadRequest("Missing recommendation_id")
        return self._delete_recommendation(recommendation_id)

    # Helper Methods
    def _get_recommendation_list(self):
        """Retrieve a list of all recommendations"""
        claims = get_jwt()
        user_role = claims.get("rol")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            recommendations = Recommendation.query.all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=claims.get("org_id")
            ).first()
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            recommendations = []
            for organization in reseller_package.organizations:
                for lot in organization.lots:
                    recommendations.extend(lot.recommendations)
        else:
            raise Forbidden(
                "Only administrators and resellers can list recommendations"
            )
        response_data = [self._serialize_recommendation(r) for r in recommendations]
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _get_recommendation(self, recommendation_id):
        """Retrieve details of a specific recommendation"""
        recommendation = Recommendation.query.get_or_404(recommendation_id)
        claims = get_jwt()
        if not self._has_access(recommendation, claims):
            raise Forbidden("You do not have access to this recommendation")
        response_data = self._serialize_recommendation(recommendation)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _create_recommendation(self, data):
        """Create a new recommendation"""
        lot_id = data["lot_id"]
        date = data["date"]
        recommendation = data["recommendation"]
        rec = Recommendation(lot_id=lot_id, date=date, recommendation=recommendation)
        db.session.add(rec)
        db.session.commit()
        response_data = self._serialize_recommendation(rec)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=201, mimetype="application/json")

    def _update_recommendation(self, recommendation_id, data):
        """Update an existing recommendation"""
        recommendation = Recommendation.query.get_or_404(recommendation_id)
        if "date" in data:
            recommendation.date = data["date"]
        if "recommendation" in data:
            recommendation.recommendation = data["recommendation"]
        db.session.commit()
        response_data = self._serialize_recommendation(recommendation)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _delete_recommendation(self, recommendation_id):
        """Delete an existing recommendation"""
        recommendation = Recommendation.query.get_or_404(recommendation_id)
        db.session.delete(recommendation)
        db.session.commit()
        return jsonify({"message": "Recommendation deleted successfully"}), 200

    def _has_access(self, recommendation, claims):
        """Check if the current user has access to the recommendation"""
        return check_resource_access(recommendation, claims)

    def _serialize_recommendation(self, recommendation):
        """Serialize a Recommendation object to a dictionary"""
        return {
            "id": recommendation.id,
            "lot_id": recommendation.lot_id,
            "date": recommendation.date,
            "recommendation": recommendation.recommendation,
            "created_at": recommendation.created_at.isoformat(),
            "updated_at": recommendation.updated_at.isoformat(),
        }


class RecommendationGenerator(MethodView):
    """Genera y guarda un nuevo reporte de recomendación."""

    decorators = [jwt_required()]

    @check_permission(
        required_roles=["administrator", "reseller", "org_admin", "org_editor"]
    )
    def post(self):
        """
        Genera un reporte basado en los parámetros recibidos.
        Expected JSON: {"lot_id": int, "common_analysis_ids": list[int], "objective_id": int, "title": str}
        """
        claims = get_jwt()
        author_name = claims.get("username", "Sistema")

        data = request.get_json()
        if not data or not all(
            k in data
            for k in ["lot_id", "common_analysis_ids", "objective_id", "title"]
        ):
            raise BadRequest(
                "Faltan parámetros: lot_id, common_analysis_ids, objective_id, title"
            )

        lot_id = data.get("lot_id")
        common_analysis_ids = data.get("common_analysis_ids")
        objective_id = data.get("objective_id")
        report_title = data.get("title")

        if not isinstance(lot_id, int):
            raise BadRequest("lot_id debe ser un entero.")
        if not isinstance(common_analysis_ids, list) or not all(
            isinstance(id, int) for id in common_analysis_ids
        ):
            raise BadRequest("common_analysis_ids debe ser una lista de enteros.")
        if not common_analysis_ids:
            raise BadRequest("common_analysis_ids no puede estar vacía.")
        if not isinstance(objective_id, int):
            raise BadRequest("objective_id debe ser un entero.")
        if not isinstance(report_title, str) or not report_title.strip():
            raise BadRequest("El título no puede estar vacío.")

        # --- Procesar CommonAnalysis ---
        # Estrategia: Procesar solo el primer common_analysis_id de la lista.
        if len(common_analysis_ids) > 1:
            current_app.logger.warning(
                f"Múltiples common_analysis_ids recibidos: {common_analysis_ids}. "
                f"Solo se procesará el primero: {common_analysis_ids[0]}."
            )
        selected_common_analysis_id = common_analysis_ids[0]

        common_analysis = CommonAnalysis.query.options(
            db.joinedload(CommonAnalysis.leaf_analysis)
            .joinedload(LeafAnalysis.nutrients)
            .joinedload(Nutrient.objectives),  # Preload Nutrient for objectives
            db.joinedload(CommonAnalysis.soil_analysis),
            db.joinedload(CommonAnalysis.lot),  # Para crop_id y farm access check
        ).get(selected_common_analysis_id)

        if not common_analysis:
            raise NotFound(
                f"No se encontró CommonAnalysis con ID {selected_common_analysis_id}."
            )

        if not common_analysis.leaf_analysis:
            raise NotFound(
                f"CommonAnalysis ID {selected_common_analysis_id} no tiene un LeafAnalysis asociado."
            )

        # Verificar acceso al lote/finca
        lot = common_analysis.lot
        if not lot or not check_resource_access(lot.farm, claims):
            raise Forbidden("No tienes acceso a este lote/finca.")

        # 1. Niveles actuales (del LeafAnalysis)
        nutrientes_actuales_raw = {}
        # Acceder a los nutrientes a través de la relación cargada en common_analysis.leaf_analysis
        for nutrient_assoc in common_analysis.leaf_analysis.nutrients:
            # nutrient_assoc es una instancia de Nutrient, el valor está en la tabla de asociación
            # Necesitamos una forma de obtener el 'value' de la tabla leaf_analysis_nutrients
            # Esto requiere que el modelo LeafAnalysis.nutrients devuelva objetos que contengan el valor.
            # Asumimos que la relación está configurada para esto o se hace una subconsulta.
            # Por ahora, vamos a buscarlo directamente si no está en el objeto `nutrient_assoc`.
            # Esto es ineficiente y debería mejorarse con una carga adecuada en el modelo.

            stmt = db.select(db.column("value")).where(
                db.and_(
                    leaf_analysis_nutrients.c.leaf_analysis_id
                    == common_analysis.leaf_analysis.id,
                    leaf_analysis_nutrients.c.nutrient_id == nutrient_assoc.id,
                )
            )
            result = db.session.execute(stmt).scalar_one_or_none()
            if result is not None:
                nutrientes_actuales_raw[nutrient_assoc.name] = result
            else:
                current_app.logger.warning(
                    f"No se encontró valor para el nutriente {nutrient_assoc.name} en LeafAnalysis {common_analysis.leaf_analysis.id}"
                )

        if not nutrientes_actuales_raw:
            raise NotFound(
                f"LeafAnalysis ID {common_analysis.leaf_analysis.id} no tiene valores de nutrientes."
            )
        nutrientes_actuales = {
            k: Decimal(str(v)) for k, v in nutrientes_actuales_raw.items()
        }

        # --- Procesar Objective ---
        objective = Objective.query.options(
            db.joinedload(
                Objective.nutrients
            )  # Asegura que los nutrientes del objetivo están cargados
        ).get(objective_id)
        if not objective:
            raise NotFound(f"No se encontró Objective con ID {objective_id}.")

        crop_id = objective.crop_id  # Usar el crop_id del objetivo

        # 2. Demandas ideales (del Objective)
        demandas_ideales = {}
        # Los nutrientes y sus target_value están en la tabla de asociación objective_nutrients
        for nutrient_target in objective.nutrients:
            # Similar al caso anterior, necesitamos el target_value de la tabla de asociación
            stmt = db.select(db.column("target_value")).where(
                db.and_(
                    objective_nutrients.c.objective_id == objective.id,
                    objective_nutrients.c.nutrient_id == nutrient_target.id,
                )
            )
            target_value = db.session.execute(stmt).scalar_one_or_none()
            if target_value is not None:
                demandas_ideales[nutrient_target.name] = Decimal(str(target_value))
            else:
                current_app.logger.warning(
                    f"No se encontró target_value para el nutriente {nutrient_target.name} en Objective {objective.id}"
                )

        if not demandas_ideales:
            raise NotFound(
                f"El objetivo ID {objective_id} no tiene metas de nutrientes definidas."
            )

        # 3. Contribuciones de producto
        productos_contribuciones_data = contribuciones_de_producto()

        # 4. Coeficientes de variación obtenidos desde el modelo Nutrient
        coeficientes_variacion = {
            n.name: Decimal(str(n.cv)) if n.cv is not None else Decimal("0")
            for n in Nutrient.query.all()
        }

        # --- Instanciar y usar NutrientOptimizer ---
        try:
            optimizer = NutrientOptimizer(
                nutrientes_actuales,
                demandas_ideales,
                productos_contribuciones_data,
                coeficientes_variacion,
            )
            recomendacion_texto = optimizer.generar_recomendacion(lot_id=lot_id)
            limitante_nombre = optimizer.identificar_limitante()
        except ValueError as ve:
            if "No products available for optimization" in str(ve):
                current_app.logger.error(
                    f"ValueError en optimización para lote {lot_id} con objetivo {objective_id}: {str(ve)}",
                    exc_info=True,
                )
                raise BadRequest(
                    "No hay productos de fertilización configurados o disponibles que coincidan con los nutrientes requeridos. No se puede generar una recomendación."
                )
            # Re-raise other ValueErrors to be caught by the generic Exception handler or handled differently if needed
            raise

        except Exception as e:
            current_app.logger.error(
                f"Error en optimización para lote {lot_id} con objetivo {objective_id}: {str(e)}",
                exc_info=True,
            )
            raise BadRequest(
                f"Error al generar recomendación con optimizador: {str(e)}"
            )

        # --- Preparar datos para guardar en Recommendation ---
        report_creator = ReportView()

        # Foliar details from the chosen common_analysis
        # _build_analysis_data espera un common_analysis completo
        analysis_data_for_report = report_creator._build_analysis_data(common_analysis)
        foliar_details_json = json.dumps(
            analysis_data_for_report.get("foliar"), default=str
        )
        soil_details_json = json.dumps(
            analysis_data_for_report.get("soil"), default=str
        )

        # Optimal comparison from the objective
        # Necesitamos un método para formatear los datos del objetivo como optimal_levels
        # Formato esperado: {'Nutriente': {'min': X, 'max': Y, 'ideal': Z, 'unit': 'unidad'}}
        optimal_comparison_data = {}
        for nutrient_name, ideal_value in demandas_ideales.items():
            # Encontrar el objeto Nutrient para obtener la unidad
            nutrient_obj = next(
                (n for n in objective.nutrients if n.name == nutrient_name), None
            )
            unit = nutrient_obj.unit if nutrient_obj else "%"  # Default unit
            optimal_comparison_data[nutrient_name] = {
                "min": float(ideal_value),  # O un rango si el objetivo lo define
                "max": float(ideal_value),
                "ideal": float(ideal_value),
                "unit": unit,
            }
        optimal_comparison_json = json.dumps(optimal_comparison_data, default=str)

        # --- Crear y guardar la Recommendation ---
        try:
            new_recommendation = Recommendation(
                lot_id=lot_id,
                crop_id=crop_id,
                date=datetime.now().date(),
                author=author_name,
                title=report_title,
                limiting_nutrient_id=limitante_nombre,
                automatic_recommendations=recomendacion_texto,
                text_recommendations="",
                optimal_comparison=optimal_comparison_json,
                soil_analysis_details=soil_details_json,
                foliar_analysis_details=foliar_details_json,
                # Considerar añadir objective_id y common_analysis_ids_used si se modifica el modelo
                applied=False,
                active=True,
            )
            db.session.add(new_recommendation)
            db.session.commit()

            return (
                jsonify(
                    {
                        "message": "Reporte generado con éxito",
                        "report_id": new_recommendation.id,
                    }
                ),
                201,
            )

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error guardando recomendación: {str(e)}", exc_info=True
            )
            raise InternalServerError("No se pudo guardar el reporte.")


class RecommendationFilterView(MethodView):
    def get(self):
        try:
            farm_id = int(request.args.get("farm_id", 0))
            lot_id = int(request.args.get("lot_id", 0))

            # Query para filtrar las recomendaciones
            query = Recommendation.query.options(
                db.joinedload(Recommendation.lot), db.joinedload(Recommendation.crop)
            ).filter(
                Recommendation.lot_id == lot_id
                if lot_id
                else Recommendation.lot.has(farm_id=farm_id)
            )

            recommendations = query.all()

            # Convertir a lista para serializar
            recommendations_list = list(recommendations)

            return jsonify(
                [
                    {
                        "id": rec.id,
                        "lot_id": rec.lot_id,
                        "crop_id": rec.crop_id,
                        "date": rec.date.isoformat(),
                        "author": rec.author,
                        "title": rec.title,
                        "limiting_nutrient_id": rec.limiting_nutrient_id,
                        "automatic_recommendations": rec.automatic_recommendations,
                        "text_recommendations": rec.text_recommendations,
                        "optimal_comparison": rec.optimal_comparison,
                        "minimum_law_analyses": rec.minimum_law_analyses,
                        "soil_analysis_details": rec.soil_analysis_details,
                        "foliar_analysis_details": rec.foliar_analysis_details,
                        "applied": rec.applied,
                        "active": rec.active,
                        "created_at": rec.created_at.isoformat(),
                        "updated_at": rec.updated_at.isoformat(),
                        "lot": {
                            "id": rec.lot.id,
                            "name": rec.lot.name,
                            "farm_id": rec.lot.farm_id,
                        },
                        "crop": {"id": rec.crop.id, "name": rec.crop.name},
                    }
                    for rec in recommendations_list
                ]
            )

        except ValueError:
            return jsonify({"error": "Invalid farm_id or lot_id"}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500


class DeleteRecommendationView(MethodView):
    @jwt_required()
    def delete(self, report_id):
        # Verificar autenticación y permisos (ajusta según tu lógica)
        claims = get_jwt()  # Asume que tienes una función get_jwt() para obtener claims
        if not claims or not claims.get("rol") in [
            "administrator",
            "reseller",
            "org_admin",
            "org_editor",
        ]:
            return jsonify({"error": "No autorizado"}), 403

        # Buscar el reporte
        report = Recommendation.query.get(report_id)
        if not report:
            return jsonify({"error": "Reporte no encontrado"}), 404

        # Verificar acceso al recurso
        if not check_resource_access(report.lot.farm, claims):
            return jsonify({"error": "No tienes acceso a este reporte"}), 403

        try:
            # Eliminación lógica (soft delete)
            report.active = False
            db.session.commit()
            return jsonify({"message": "Reporte eliminado exitosamente"}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500
