import json
# Third party imports
from flask_jwt_extended import jwt_required, get_jwt
from flask import request, jsonify, Response
from flask.views import MethodView
from werkzeug.exceptions import BadRequest, NotFound, Forbidden, Unauthorized

# Local application imports
from app.extensions import db
from app.core.controller import check_permission
from app.core.models import RoleEnum, ResellerPackage
from .models import Farm, Lot, Crop, LotCrop, CommonAnalysis, NutrientApplication, Nutrient, LeafAnalysis


# Vista para granjas (farms)
class FarmView(MethodView):
    """Clase para gestionar operaciones CRUD sobre granjas."""
    decorators = [jwt_required()]
    @check_permission(required_roles=["administrator", "reseller"])
    def get(self, farm_id=None):
        """
        Obtiene una lista de granjas o una granja específica.
        Args:
            farm_id (str, optional): ID de la granja a consultar.
        Returns:
            JSON: Lista de granjas o detalles de una granja específica.
        """
        if farm_id:
            return self._get_farm(farm_id)
        return self._get_farm_list()
    @check_permission(required_roles=["administrator", "reseller"])
    def post(self):
        """
        Crea una nueva granja.
        Returns:
            JSON: Detalles de la granja creada.
        """
        data = request.get_json()
        if not data or not all(k in data for k in ("name", "user_id")):
            raise BadRequest("Missing required fields.")
        return self._create_farm(data)
    @check_permission(resource_owner_check=True)
    def put(self, farm_id):
        """
        Actualiza una granja existente.
        Args:
            farm_id (str): ID de la granja a actualizar.
        Returns:
            JSON: Detalles de la granja actualizada.
        """
        data = request.get_json()
        if not data or not farm_id:
            raise BadRequest("Missing farm_id or data.")
        return self._update_farm(farm_id, data)
    @check_permission(resource_owner_check=True)
    def delete(self, farm_id=None):
        """
        Elimina una granja existente.
        Args:
            farm_id (str): ID de la granja a eliminar.
        Returns:
            JSON: Mensaje de confirmación.
        """
        data = request.get_json()
        if data and "ids" in data:
            return self._delete_farm(farm_ids=data["ids"])
        if farm_id:
            return self._delete_farm(farm_id=farm_id)
        raise BadRequest("Missing farm_id.")
    # Métodos auxiliares
    def _get_farm_list(self):
        """Obtiene una lista de todas las granjas activas."""
        claims = get_jwt()
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            farms = Farm.query.filter_by(active=True).all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=user_id
            ).first()
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            farms = []
            for org in reseller_package.organizations:
                farms.extend(org.farms)
        else:
            raise Forbidden("Only administrators and resellers can list farms.")
        return jsonify([self._serialize_farm(farm) for farm in farms]), 200
    def _get_farm(self, farm_id):
        """Obtiene los detalles de una granja específica."""
        farm = Farm.query.get_or_404(farm_id)
        claims = get_jwt()
        if not self._has_access(farm, claims):
            raise Forbidden("You do not have access to this farm.")
        return jsonify(self._serialize_farm(farm)), 200
    def _create_farm(self, data):
        """Crea una nueva granja con los datos proporcionados."""
        if Farm.query.filter_by(name=data["name"]).first():
            raise BadRequest("Name already exists.")
        farm = Farm(
            name=data["name"],
            user_id=data["user_id"],
        )
        db.session.add(farm)
        db.session.commit()
        return jsonify(self._serialize_farm(farm)), 201
    def _update_farm(self, farm_id, data):
        """Actualiza los datos de una granja existente."""
        farm = Farm.query.get_or_404(farm_id)
        if "name" in data and data["name"] != farm.name:
            if Farm.query.filter_by(name=data["name"]).first():
                raise BadRequest("Name already exists.")
            farm.name = data["name"]
        if "user_id" in data:
            farm.user_id = data["user_id"]
        db.session.commit()
        return jsonify(self._serialize_farm(farm)), 200
    def _delete_farm(self, farm_id=None, farm_ids=None):
        """Elimina una granja marcándola como inactiva."""
        claims = get_jwt()
        if farm_id and farm_ids:
            raise BadRequest("Solo se puede especificar farm_id o farm_ids, no ambos.")
        if farm_id:
            farm = Farm.query.get_or_404(farm_id)
            farm.active = False
            db.session.commit()
            return jsonify({"message": "Farm deleted successfully"}), 200
        if farm_ids:
            deleted_farms = []
            for farm_id in farm_ids:
                farm = Farm.query.get(farm_id)
                if not farm:
                    continue
                farm.active = False
                deleted_farms.append(farm.name)
                db.session.commit()
                deleted_farms_str = ", ".join(deleted_farms)
            return jsonify({"message": f"Farms {deleted_farms_str} deleted successfully"}), 200
        if not deleted_farms:
            return jsonify({"error": "No farms were deleted due to permission restrictions"}), 403
    def _has_access(self, farm, claims):
        """Verifica si el usuario actual tiene acceso al recurso."""
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        if user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=user_id
            ).first()
            return any(
                org.id in [o.id for o in reseller_package.organizations]
                for org in farm.user.organizations
            )
        return user_id == farm.user_id
    def _serialize_farm(self, farm):
        """Serializa un objeto Farm a un diccionario."""
        return {
            "id": farm.id,
            "name": farm.name,
            "user_id": farm.user_id,
            "created_at": farm.created_at.isoformat(),
            "updated_at": farm.updated_at.isoformat(),
        }

# Vista para lotes (lots)
class LotView(MethodView):
    """Clase para gestionar operaciones CRUD sobre lotes."""
    decorators = [jwt_required()]
    @check_permission(required_roles=["administrator", "reseller"])
    def get(self, lot_id=None):
        """
        Obtiene una lista de lotes o un lote específico.
        Args:
            lot_id (str, optional): ID del lote a consultar.
        Returns:
            JSON: Lista de lotes o detalles de un lote específico.
        """
        if lot_id:
            return self._get_lot(lot_id)
        return self._get_lot_list()
    @check_permission(required_roles=["administrator", "reseller"])
    def post(self):
        """
        Crea un nuevo lote.
        Returns:
            JSON: Detalles del lote creado.
        """
        data = request.get_json()
        if not data or not all(k in data for k in ("name", "area", "farm_id")):
            raise BadRequest("Missing required fields.")
        return self._create_lot(data)
    @check_permission(resource_owner_check=True)
    def put(self, lot_id):
        """
        Actualiza un lote existente.
        Args:
            lot_id (str): ID del lote a actualizar.
        Returns:
            JSON: Detalles del lote actualizado.
        """
        data = request.get_json()
        if not data or not lot_id:
            raise BadRequest("Missing lot_id or data.")
        return self._update_lot(lot_id, data)
    @check_permission(resource_owner_check=True)
    def delete(self, lot_id=None):
        """
        Elimina un lote existente.
        Args:
            lot_id (str): ID del lote a eliminar.
        Returns:
            JSON: Mensaje de confirmación.
        """
        data = request.get_json()
        if data and "ids" in data:
            return self._delete_lot(lot_ids=data["ids"])
        if lot_id:
            return self._delete_lot(lot_id=lot_id)
        raise BadRequest("Missing lot_id.")
    # Métodos auxiliares
    def _get_lot_list(self):
        """Obtiene una lista de todos los lotes activos."""
        claims = get_jwt()
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            lots = Lot.query.filter_by(active=True).all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=user_id
            ).first()
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            lots = []
            for org in reseller_package.organizations:
                lots.extend(org.lots)
        else:
            raise Forbidden("Only administrators and resellers can list lots.")
        return jsonify([self._serialize_lot(lot) for lot in lots]), 200
    def _get_lot(self, lot_id):
        """Obtiene los detalles de un lote específico."""
        lot = Lot.query.get_or_404(lot_id)
        claims = get_jwt()
        if not self._has_access(lot, claims):
            raise Forbidden("You do not have access to this lot.")
        return jsonify(self._serialize_lot(lot)), 200
    def _create_lot(self, data):
        """Crea un nuevo lote con los datos proporcionados."""
        if Lot.query.filter_by(name=data["name"]).first():
            raise BadRequest("Name already exists.")
        lot = Lot(
            name=data["name"],
            area=data["area"],
            farm_id=data["farm_id"],
        )
        db.session.add(lot)
        db.session.commit()
        return jsonify(self._serialize_lot(lot)), 201
    def _update_lot(self, lot_id, data):
        """Actualiza los datos de un lote existente."""
        lot = Lot.query.get_or_404(lot_id)
        if "name" in data and data["name"] != lot.name:
            if Lot.query.filter_by(name=data["name"]).first():
                raise BadRequest("Name already exists.")
            lot.name = data["name"]
        if "area" in data:
            lot.area = data["area"]
        if "farm_id" in data:
            lot.farm_id = data["farm_id"]
        db.session.commit()
        return jsonify(self._serialize_lot(lot)), 200
    def _delete_lot(self, lot_id=None, lot_ids=None):
        """Elimina un lote marcándolo como inactivo."""
        claims = get_jwt()
        if lot_id and lot_ids:
            raise BadRequest("Solo se puede especificar lot_id o lot_ids, no ambos.")
        if lot_id:
            lot = Lot.query.get_or_404(lot_id)
            lot.active = False
            db.session.commit()
            return jsonify({"message": "Lot deleted successfully"}), 200
        if lot_ids:
            deleted_lots = []
            for lot_id in lot_ids:
                lot = Lot.query.get(lot_id)
                if not lot:
                    continue
                lot.active = False
                deleted_lots.append(lot.name)
                db.session.commit()
                deleted_lots_str = ", ".join(deleted_lots)
            return jsonify({"message": f"Lots {deleted_lots_str} deleted successfully"}), 200
        if not deleted_lots:
            return jsonify({"error": "No lots were deleted due to permission restrictions"}), 403
    def _has_access(self, lot, claims):
        """Verifica si el usuario actual tiene acceso al recurso."""
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        if user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=user_id
            ).first()
            return any(
                org.id in [o.id for o in reseller_package.organizations]
                for org in lot.farm.user.organizations
            )
        return user_id == lot.farm.user_id
    def _serialize_lot(self, lot):
        """Serializa un objeto Lot a un diccionario."""
        return {
            "id": lot.id,
            "name": lot.name,
            "area": lot.area,
            "farm_id": lot.farm_id,
            "created_at": lot.created_at.isoformat(),
            "updated_at": lot.updated_at.isoformat(),
        }

# Vista para cultivos (crops)
class CropView(MethodView):
    """Clase para gestionar operaciones CRUD sobre cultivos."""
    decorators = [jwt_required()]
    @check_permission(required_roles=["administrator", "reseller"])
    def get(self, crop_id=None):
        """
        Obtiene una lista de cultivos o un cultivo específico.
        Args:
            crop_id (str, optional): ID del cultivo a consultar.
        Returns:
            JSON: Lista de cultivos o detalles de un cultivo específico.
        """
        if crop_id:
            return self._get_crop(crop_id)
        return self._get_crop_list()
    @check_permission(required_roles=["administrator", "reseller"])
    def post(self):
        """
        Crea un nuevo cultivo.
        Returns:
            JSON: Detalles del cultivo creado.
        """
        data = request.get_json()
        if not data or not all(k in data for k in ("name",)):
            raise BadRequest("Missing required fields.")
        return self._create_crop(data)
    @check_permission(resource_owner_check=True)
    def put(self, crop_id):
        """
        Actualiza un cultivo existente.
        Args:
            crop_id (str): ID del cultivo a actualizar.
        Returns:
            JSON: Detalles del cultivo actualizado.
        """
        data = request.get_json()
        if not data or not crop_id:
            raise BadRequest("Missing crop_id or data.")
        return self._update_crop(crop_id, data)
    @check_permission(resource_owner_check=True)
    def delete(self, crop_id=None):
        """
        Elimina un cultivo existente.
        Args:
            crop_id (str): ID del cultivo a eliminar.
        Returns:
            JSON: Mensaje de confirmación.
        """
        data = request.get_json()
        if data and "ids" in data:
            return self._delete_crop(crop_ids=data["ids"])
        if crop_id:
            return self._delete_crop(crop_id=crop_id)
        raise BadRequest("Missing crop_id.")
    # Métodos auxiliares
    def _get_crop_list(self):
        """Obtiene una lista de todos los cultivos activos."""
        claims = get_jwt()
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            crops = Crop.query.filter_by(active=True).all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=user_id
            ).first()
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            crops = []
            for org in reseller_package.organizations:
                crops.extend(org.crops)
        else:
            raise Forbidden("Only administrators and resellers can list crops.")
        return jsonify([self._serialize_crop(crop) for crop in crops]), 200
    def _get_crop(self, crop_id):
        """Obtiene los detalles de un cultivo específico."""
        crop = Crop.query.get_or_404(crop_id)
        claims = get_jwt()
        if not self._has_access(crop, claims):
            raise Forbidden("You do not have access to this crop.")
        return jsonify(self._serialize_crop(crop)), 200
    def _create_crop(self, data):
        """Crea un nuevo cultivo con los datos proporcionados."""
        if Crop.query.filter_by(name=data["name"]).first():
            raise BadRequest("Name already exists.")
        crop = Crop(
            name=data["name"],
        )
        db.session.add(crop)
        db.session.commit()
        return jsonify(self._serialize_crop(crop)), 201
    def _update_crop(self, crop_id, data):
        """Actualiza los datos de un cultivo existente."""
        crop = Crop.query.get_or_404(crop_id)
        if "name" in data and data["name"] != crop.name:
            if Crop.query.filter_by(name=data["name"]).first():
                raise BadRequest("Name already exists.")
            crop.name = data["name"]
        db.session.commit()
        return jsonify(self._serialize_crop(crop)), 200
    def _delete_crop(self, crop_id=None, crop_ids=None):
        """Elimina un cultivo marcándolo como inactivo."""
        claims = get_jwt()
        if crop_id and crop_ids:
            raise BadRequest("Solo se puede especificar crop_id o crop_ids, no ambos.")
        if crop_id:
            crop = Crop.query.get_or_404(crop_id)
            crop.active = False
            db.session.commit()
            return jsonify({"message": "Crop deleted successfully"}), 200
        if crop_ids:
            deleted_crops = []
            for crop_id in crop_ids:
                crop = Crop.query.get(crop_id)
                if not crop:
                    continue
                crop.active = False
                deleted_crops.append(crop.name)
                db.session.commit()
                deleted_crops_str = ", ".join(deleted_crops)
            return jsonify({"message": f"Crops {deleted_crops_str} deleted successfully"}), 200
        if not deleted_crops:
            return jsonify({"error": "No crops were deleted due to permission restrictions"}), 403
    def _has_access(self, crop, claims):
        """Verifica si el usuario actual tiene acceso al recurso."""
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        if user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=user_id
            ).first()
            return any(
                org.id in [o.id for o in reseller_package.organizations]
                for org in crop.user.organizations
            )
        return user_id == crop.user_id
    def _serialize_crop(self, crop):
        """Serializa un objeto Crop a un diccionario."""
        return {
            "id": crop.id,
            "name": crop.name,
            "created_at": crop.created_at.isoformat(),
            "updated_at": crop.updated_at.isoformat(),
        }

# Vista para lotes de cultivos (lot_crops)
class LotCropView(MethodView):
    """Clase para gestionar operaciones CRUD sobre lotes de cultivos."""
    decorators = [jwt_required()]
    @check_permission(required_roles=["administrator", "reseller"])
    def get(self, lot_crop_id=None):
        """
        Obtiene una lista de lotes de cultivos o un lote de cultivo específico.
        Args:
            lot_crop_id (str, optional): ID del lote de cultivo a consultar.
        Returns:
            JSON: Lista de lotes de cultivos o detalles de un lote de cultivo específico.
        """
        if lot_crop_id:
            return self._get_lot_crop(lot_crop_id)
        return self._get_lot_crop_list()
    @check_permission(required_roles=["administrator", "reseller"])
    def post(self):
        """
        Crea un nuevo lote de cultivo.
        Returns:
            JSON: Detalles del lote de cultivo creado.
        """
        data = request.get_json()
        if not data or not all(k in data for k in ("lot_id", "crop_id", "start_date")):
            raise BadRequest("Missing required fields.")
        return self._create_lot_crop(data)
    @check_permission(resource_owner_check=True)
    def put(self, lot_crop_id):
        """
        Actualiza un lote de cultivo existente.
        Args:
            lot_crop_id (str): ID del lote de cultivo a actualizar.
        Returns:
            JSON: Detalles del lote de cultivo actualizado.
        """
        data = request.get_json()
        if not data or not lot_crop_id:
            raise BadRequest("Missing lot_crop_id or data.")
        return self._update_lot_crop(lot_crop_id, data)
    @check_permission(resource_owner_check=True)
    def delete(self, lot_crop_id=None):
        """
        Elimina un lote de cultivo existente.
        Args:
            lot_crop_id (str): ID del lote de cultivo a eliminar.
        Returns:
            JSON: Mensaje de confirmación.
        """
        data = request.get_json()
        if data and "ids" in data:
            return self._delete_lot_crop(lot_crop_ids=data["ids"])
        if lot_crop_id:
            return self._delete_lot_crop(lot_crop_id=lot_crop_id)
        raise BadRequest("Missing lot_crop_id.")
    # Métodos auxiliares
    def _get_lot_crop_list(self):
        """Obtiene una lista de todos los lotes de cultivos activos."""
        claims = get_jwt()
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            lot_crops = LotCrop.query.filter_by(active=True).all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=user_id
            ).first()
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            lot_crops = []
            for org in reseller_package.organizations:
                lot_crops.extend(org.lot_crops)
        else:
            raise Forbidden("Only administrators and resellers can list lot_crops.")
        return jsonify([self._serialize_lot_crop(lot_crop) for lot_crop in lot_crops]), 200
    def _get_lot_crop(self, lot_crop_id):
        """Obtiene los detalles de un lote de cultivo específico."""
        lot_crop = LotCrop.query.get_or_404(lot_crop_id)
        claims = get_jwt()
        if not self._has_access(lot_crop, claims):
            raise Forbidden("You do not have access to this lot_crop.")
        return jsonify(self._serialize_lot_crop(lot_crop)), 200
    def _create_lot_crop(self, data):
        """Crea un nuevo lote de cultivo con los datos proporcionados."""
        if LotCrop.query.filter_by(lot_id=data["lot_id"], crop_id=data["crop_id"]).first():
            raise BadRequest("LotCrop already exists.")
        lot_crop = LotCrop(
            lot_id=data["lot_id"],
            crop_id=data["crop_id"],
            start_date=data["start_date"],
        )
        db.session.add(lot_crop)
        db.session.commit()
        return jsonify(self._serialize_lot_crop(lot_crop)), 201
    def _update_lot_crop(self, lot_crop_id, data):
        """Actualiza los datos de un lote de cultivo existente."""
        lot_crop = LotCrop.query.get_or_404(lot_crop_id)
        if "lot_id" in data and data["lot_id"] != lot_crop.lot_id:
            if LotCrop.query.filter_by(lot_id=data["lot_id"], crop_id=lot_crop.crop_id).first():
                raise BadRequest("LotCrop already exists.")
            lot_crop.lot_id = data["lot_id"]
        if "crop_id" in data:
            lot_crop.crop_id = data["crop_id"]
        if "start_date" in data:
            lot_crop.start_date = data["start_date"]
        db.session.commit()
        return jsonify(self._serialize_lot_crop(lot_crop)), 200
    def _delete_lot_crop(self, lot_crop_id=None, lot_crop_ids=None):
        """Elimina un lote de cultivo marcándolo como inactivo."""
        claims = get_jwt()
        if lot_crop_id and lot_crop_ids:
            raise BadRequest("Solo se puede especificar lot_crop_id o lot_crop_ids, no ambos.")
        if lot_crop_id:
            lot_crop = LotCrop.query.get_or_404(lot_crop_id)
            lot_crop.active = False
            db.session.commit()
            return jsonify({"message": "LotCrop deleted successfully"}), 200
        if lot_crop_ids:
            deleted_lot_crops = []
            for lot_crop_id in lot_crop_ids:
                lot_crop = LotCrop.query.get(lot_crop_id)
                if not lot_crop:
                    continue
                lot_crop.active = False
                deleted_lot_crops.append(lot_crop.lot_id)
                db.session.commit()
                deleted_lot_crops_str = ", ".join(map(str, deleted_lot_crops))
            return jsonify({"message": f"LotCrops {deleted_lot_crops_str} deleted successfully"}), 200
        if not deleted_lot_crops:
            return jsonify({"error": "No lot_crops were deleted due to permission restrictions"}), 403
    def _has_access(self, lot_crop, claims):
        """Verifica si el usuario actual tiene acceso al recurso."""
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        if user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=user_id
            ).first()
            return any(
                org.id in [o.id for o in reseller_package.organizations]
                for org in lot_crop.lot.farm.user.organizations
            )
        return user_id == lot_crop.lot.farm.user_id
    def _serialize_lot_crop(self, lot_crop):
        """Serializa un objeto LotCrop a un diccionario."""
        return {
            "id": lot_crop.id,
            "lot_id": lot_crop.lot_id,
            "crop_id": lot_crop.crop_id,
            "start_date": lot_crop.start_date,
            "created_at": lot_crop.created_at.isoformat(),
            "updated_at": lot_crop.updated_at.isoformat(),
        }

# Vista para análisis comunes (common_analyses)
class CommonAnalysisView(MethodView):
    """Clase para gestionar operaciones CRUD sobre análisis comunes."""
    decorators = [jwt_required()]
    @check_permission(required_roles=["administrator", "reseller"])
    def get(self, common_analysis_id=None):
        """
        Obtiene una lista de análisis comunes o un análisis común específico.
        Args:
            common_analysis_id (str, optional): ID del análisis común a consultar.
        Returns:
            JSON: Lista de análisis comunes o detalles de un análisis común específico.
        """
        if common_analysis_id:
            return self._get_common_analysis(common_analysis_id)
        return self._get_common_analysis_list()
    @check_permission(required_roles=["administrator", "reseller"])
    def post(self):
        """
        Crea un nuevo análisis común.
        Returns:
            JSON: Detalles del análisis común creado.
        """
        data = request.get_json()
        if not data or not all(k in data for k in ("date", "lot_id")):
            raise BadRequest("Missing required fields.")
        return self._create_common_analysis(data)
    @check_permission(resource_owner_check=True)
    def put(self, common_analysis_id):
        """
        Actualiza un análisis común existente.
        Args:
            common_analysis_id (str): ID del análisis común a actualizar.
        Returns:
            JSON: Detalles del análisis común actualizado.
        """
        data = request.get_json()
        if not data or not common_analysis_id:
            raise BadRequest("Missing common_analysis_id or data.")
        return self._update_common_analysis(common_analysis_id, data)
    @check_permission(resource_owner_check=True)
    def delete(self, common_analysis_id=None):
        """
        Elimina un análisis común existente.
        Args:
            common_analysis_id (str): ID del análisis común a eliminar.
        Returns:
            JSON: Mensaje de confirmación.
        """
        data = request.get_json()
        if data and "ids" in data:
            return self._delete_common_analysis(common_analysis_ids=data["ids"])
        if common_analysis_id:
            return self._delete_common_analysis(common_analysis_id=common_analysis_id)
        raise BadRequest("Missing common_analysis_id.")
    # Métodos auxiliares
    def _get_common_analysis_list(self):
        """Obtiene una lista de todos los análisis comunes activos."""
        claims = get_jwt()
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            common_analyses = CommonAnalysis.query.filter_by(active=True).all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=user_id
            ).first()
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            common_analyses = []
            for org in reseller_package.organizations:
                common_analyses.extend(org.common_analyses)
        else:
            raise Forbidden("Only administrators and resellers can list common_analyses.")
        return jsonify([self._serialize_common_analysis(common_analysis) for common_analysis in common_analyses]), 200
    def _get_common_analysis(self, common_analysis_id):
        """Obtiene los detalles de un análisis común específico."""
        common_analysis = CommonAnalysis.query.get_or_404(common_analysis_id)
        claims = get_jwt()
        if not self._has_access(common_analysis, claims):
            raise Forbidden("You do not have access to this common_analysis.")
        return jsonify(self._serialize_common_analysis(common_analysis)), 200
    def _create_common_analysis(self, data):
        """Crea un nuevo análisis común con los datos proporcionados."""
        if CommonAnalysis.query.filter_by(date=data["date"], lot_id=data["lot_id"]).first():
            raise BadRequest("CommonAnalysis already exists.")
        common_analysis = CommonAnalysis(
            date=data["date"],
            lot_id=data["lot_id"],
        )
        db.session.add(common_analysis)
        db.session.commit()
        return jsonify(self._serialize_common_analysis(common_analysis)), 201
    def _update_common_analysis(self, common_analysis_id, data):
        """Actualiza los datos de un análisis común existente."""
        common_analysis = CommonAnalysis.query.get_or_404(common_analysis_id)
        if "date" in data:
            common_analysis.date = data["date"]
        if "lot_id" in data:
            common_analysis.lot_id = data["lot_id"]
        db.session.commit()
        return jsonify(self._serialize_common_analysis(common_analysis)), 200
    def _delete_common_analysis(self, common_analysis_id=None, common_analysis_ids=None):
        """Elimina un análisis común marcándolo como inactivo."""
        claims = get_jwt()
        if common_analysis_id and common_analysis_ids:
            raise BadRequest("Solo se puede especificar common_analysis_id o common_analysis_ids, no ambos.")
        if common_analysis_id:
            common_analysis = CommonAnalysis.query.get_or_404(common_analysis_id)
            common_analysis.active = False
            db.session.commit()
            return jsonify({"message": "CommonAnalysis deleted successfully"}), 200
        if common_analysis_ids:
            deleted_common_analyses = []
            for common_analysis_id in common_analysis_ids:
                common_analysis = CommonAnalysis.query.get(common_analysis_id)
                if not common_analysis:
                    continue
                common_analysis.active = False
                deleted_common_analyses.append(common_analysis.lot_id)
                db.session.commit()
                deleted_common_analyses_str = ", ".join(map(str, deleted_common_analyses))
            return jsonify({"message": f"CommonAnalyses {deleted_common_analyses_str} deleted successfully"}), 200
        if not deleted_common_analyses:
            return jsonify({"error": "No common_analyses were deleted due to permission restrictions"}), 403
    def _has_access(self, common_analysis, claims):
        """Verifica si el usuario actual tiene acceso al recurso."""
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        if user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=user_id
            ).first()
            return any(
                org.id in [o.id for o in reseller_package.organizations]
                for org in common_analysis.lot.farm.user.organizations
            )
        return user_id == common_analysis.lot.farm.user_id
    def _serialize_common_analysis(self, common_analysis):
        """Serializa un objeto CommonAnalysis a un diccionario."""
        return {
            "id": common_analysis.id,
            "date": common_analysis.date,
            "lot_id": common_analysis.lot_id,
            "created_at": common_analysis.created_at.isoformat(),
            "updated_at": common_analysis.updated_at.isoformat(),
        }

# Vista para nutrientes (nutrients)
class NutrientView(MethodView):
    """Clase para gestionar operaciones CRUD sobre nutrientes."""
    decorators = [jwt_required()]
    @check_permission(required_roles=["administrator", "reseller"])
    def get(self, nutrient_id=None):
        """
        Obtiene una lista de nutrientes o un nutriente específico.
        Args:
            nutrient_id (str, optional): ID del nutriente a consultar.
        Returns:
            JSON: Lista de nutrientes o detalles de un nutriente específico.
        """
        if nutrient_id:
            return self._get_nutrient(nutrient_id)
        return self._get_nutrient_list()
    @check_permission(required_roles=["administrator", "reseller"])
    def post(self):
        """
        Crea un nuevo nutriente.
        Returns:
            JSON: Detalles del nutriente creado.
        """
        data = request.get_json()
        if not data or not all(k in data for k in ("name", "symbol", "unit")):
            raise BadRequest("Missing required fields.")
        return self._create_nutrient(data)
    @check_permission(resource_owner_check=True)
    def put(self, nutrient_id):
        """
        Actualiza un nutriente existente.
        Args:
            nutrient_id (str): ID del nutriente a actualizar.
        Returns:
            JSON: Detalles del nutriente actualizado.
        """
        data = request.get_json()
        if not data or not nutrient_id:
            raise BadRequest("Missing nutrient_id or data.")
        return self._update_nutrient(nutrient_id, data)
    @check_permission(resource_owner_check=True)
    def delete(self, nutrient_id=None):
        """
        Elimina un nutriente existente.
        Args:
            nutrient_id (str): ID del nutriente a eliminar.
        Returns:
            JSON: Mensaje de confirmación.
        """
        data = request.get_json()
        if data and "ids" in data:
            return self._delete_nutrient(nutrient_ids=data["ids"])
        if nutrient_id:
            return self._delete_nutrient(nutrient_id=nutrient_id)
        raise BadRequest("Missing nutrient_id.")
    # Métodos auxiliares
    def _get_nutrient_list(self):
        """Obtiene una lista de todos los nutrientes activos."""
        claims = get_jwt()
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            nutrients = Nutrient.query.all() # Nutrient.query.filter_by(active=True).all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=user_id
            ).first()
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            nutrients = []
            for org in reseller_package.organizations:
                nutrients.extend(org.nutrients)
        else:
            raise Forbidden("Only administrators and resellers can list nutrients.")
        
        # JDC
        response_data = [self._serialize_nutrient(nutrient) for nutrient in nutrients]
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)  # Evita problemas con tildes

        return Response(json_data, status=200, mimetype="application/json")

    def _get_nutrient(self, nutrient_id):
        """Obtiene los detalles de un nutriente específico."""
        nutrient = Nutrient.query.get_or_404(nutrient_id)
        claims = get_jwt()
        if not self._has_access(nutrient, claims):
            raise Forbidden("You do not have access to this nutrient.")
        return jsonify(self._serialize_nutrient(nutrient)), 200
    def _create_nutrient(self, data):
        """Crea un nuevo nutriente con los datos proporcionados."""
        if Nutrient.query.filter_by(name=data["name"]).first():
            raise BadRequest("Name already exists.")
        nutrient = Nutrient(
            name=data["name"],
            symbol=data["symbol"],
            unit=data["unit"],
        )
        db.session.add(nutrient)
        db.session.commit()
        return jsonify(self._serialize_nutrient(nutrient)), 201
    def _update_nutrient(self, nutrient_id, data):
        """Actualiza los datos de un nutriente existente."""
        nutrient = Nutrient.query.get_or_404(nutrient_id)
        if "name" in data and data["name"] != nutrient.name:
            if Nutrient.query.filter_by(name=data["name"]).first():
                raise BadRequest("Name already exists.")
            nutrient.name = data["name"]
        if "symbol" in data:
            nutrient.symbol = data["symbol"]
        if "unit" in data:
            nutrient.unit = data["unit"]
        db.session.commit()
        return jsonify(self._serialize_nutrient(nutrient)), 200
    def _delete_nutrient(self, nutrient_id=None, nutrient_ids=None):
        """Elimina un nutriente marcándolo como inactivo."""
        claims = get_jwt()
        if nutrient_id and nutrient_ids:
            raise BadRequest("Solo se puede especificar nutrient_id o nutrient_ids, no ambos.")
        if nutrient_id:
            nutrient = Nutrient.query.get_or_404(nutrient_id)
            nutrient.active = False
            db.session.commit()
            return jsonify({"message": "Nutrient deleted successfully"}), 200
        if nutrient_ids:
            deleted_nutrients = []
            for nutrient_id in nutrient_ids:
                nutrient = Nutrient.query.get(nutrient_id)
                if not nutrient:
                    continue
                nutrient.active = False
                deleted_nutrients.append(nutrient.name)
                db.session.commit()
                deleted_nutrients_str = ", ".join(deleted_nutrients)
            return jsonify({"message": f"Nutrients {deleted_nutrients_str} deleted successfully"}), 200
        if not deleted_nutrients:
            return jsonify({"error": "No nutrients were deleted due to permission restrictions"}), 403
    def _has_access(self, nutrient, claims):
        """Verifica si el usuario actual tiene acceso al recurso."""
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        if user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=user_id
            ).first()
            return any(
                org.id in [o.id for o in reseller_package.organizations]
                for org in nutrient.user.organizations
            )
        return user_id == nutrient.user_id
    def _serialize_nutrient(self, nutrient):
        """Serializa un objeto Nutrient a un diccionario."""
        return {
            "id": nutrient.id,
            "name": nutrient.name,
            "symbol": nutrient.symbol,
            "unit": nutrient.unit,
            "created_at": nutrient.created_at.isoformat(),
            "updated_at": nutrient.updated_at.isoformat(),
        }

# Vista para análisis de hojas (leaf_analyses)
class LeafAnalysisView(MethodView):
    """Clase para gestionar operaciones CRUD sobre análisis de hojas."""
    decorators = [jwt_required()]
    @check_permission(required_roles=["administrator", "reseller"])
    def get(self, leaf_analysis_id=None):
        """
        Obtiene una lista de análisis de hojas o un análisis de hoja específico.
        Args:
            leaf_analysis_id (str, optional): ID del análisis de hoja a consultar.
        Returns:
            JSON: Lista de análisis de hojas o detalles de un análisis de hoja específico.
        """
        if leaf_analysis_id:
            return self._get_leaf_analysis(leaf_analysis_id)
        return self._get_leaf_analysis_list()
    @check_permission(required_roles=["administrator", "reseller"])
    def post(self):
        """
        Crea un nuevo análisis de hoja.
        Returns:
            JSON: Detalles del análisis de hoja creado.
        """
        data = request.get_json()
        if not data or not all(k in data for k in ("common_analysis_id",)):
            raise BadRequest("Missing required fields.")
        return self._create_leaf_analysis(data)
    @check_permission(resource_owner_check=True)
    def put(self, leaf_analysis_id):
        """
        Actualiza un análisis de hoja existente.
        Args:
            leaf_analysis_id (str): ID del análisis de hoja a actualizar.
        Returns:
            JSON: Detalles del análisis de hoja actualizado.
        """
        data = request.get_json()
        if not data or not leaf_analysis_id:
            raise BadRequest("Missing leaf_analysis_id or data.")
        return self._update_leaf_analysis(leaf_analysis_id, data)
    @check_permission(resource_owner_check=True)
    def delete(self, leaf_analysis_id=None):
        """
        Elimina un análisis de hoja existente.
        Args:
            leaf_analysis_id (str): ID del análisis de hoja a eliminar.
        Returns:
            JSON: Mensaje de confirmación.
        """
        data = request.get_json()
        if data and "ids" in data:
            return self._delete_leaf_analysis(leaf_analysis_ids=data["ids"])
        if leaf_analysis_id:
            return self._delete_leaf_analysis(leaf_analysis_id=leaf_analysis_id)
        raise BadRequest("Missing leaf_analysis_id.")
    # Métodos auxiliares
    def _get_leaf_analysis_list(self):
        """Obtiene una lista de todos los análisis de hojas activos."""
        claims = get_jwt()
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            leaf_analyses = LeafAnalysis.query.filter_by(active=True).all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=user_id
            ).first()
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            leaf_analyses = []
            for org in reseller_package.organizations:
                leaf_analyses.extend(org.leaf_analyses)
        else:
            raise Forbidden("Only administrators and resellers can list leaf_analyses.")
        return jsonify([self._serialize_leaf_analysis(leaf_analysis) for leaf_analysis in leaf_analyses]), 200
    def _get_leaf_analysis(self, leaf_analysis_id):
        """Obtiene los detalles de un análisis de hoja específico."""
        leaf_analysis = LeafAnalysis.query.get_or_404(leaf_analysis_id)
        claims = get_jwt()
        if not self._has_access(leaf_analysis, claims):
            raise Forbidden("You do not have access to this leaf_analysis.")
        return jsonify(self._serialize_leaf_analysis(leaf_analysis)), 200
    def _create_leaf_analysis(self, data):
        """Crea un nuevo análisis de hoja con los datos proporcionados."""
        if LeafAnalysis.query.filter_by(common_analysis_id=data["common_analysis_id"]).first():
            raise BadRequest("LeafAnalysis already exists.")
        leaf_analysis = LeafAnalysis(
            common_analysis_id=data["common_analysis_id"],
        )
        db.session.add(leaf_analysis)
        db.session.commit()
        return jsonify(self._serialize_leaf_analysis(leaf_analysis)), 201
    def _update_leaf_analysis(self, leaf_analysis_id, data):
        """Actualiza los datos de un análisis de hoja existente."""
        leaf_analysis = LeafAnalysis.query.get_or_404(leaf_analysis_id)
        if "common_analysis_id" in data:
            leaf_analysis.common_analysis_id = data["common_analysis_id"]
        db.session.commit()
        return jsonify(self._serialize_leaf_analysis(leaf_analysis)), 200
    def _delete_leaf_analysis(self, leaf_analysis_id=None, leaf_analysis_ids=None):
        """Elimina un análisis de hoja marcándolo como inactivo."""
        claims = get_jwt()
        if leaf_analysis_id and leaf_analysis_ids:
            raise BadRequest("Solo se puede especificar leaf_analysis_id o leaf_analysis_ids, no ambos.")
        if leaf_analysis_id:
            leaf_analysis = LeafAnalysis.query.get_or_404(leaf_analysis_id)
            leaf_analysis.active = False
            db.session.commit()
            return jsonify({"message": "LeafAnalysis deleted successfully"}), 200
        if leaf_analysis_ids:
            deleted_leaf_analyses = []
            for leaf_analysis_id in leaf_analysis_ids:
                leaf_analysis = LeafAnalysis.query.get(leaf_analysis_id)
                if not leaf_analysis:
                    continue
                leaf_analysis.active = False
                deleted_leaf_analyses.append(leaf_analysis.common_analysis_id)
                db.session.commit()
                deleted_leaf_analyses_str = ", ".join(map(str, deleted_leaf_analyses))
            return jsonify({"message": f"LeafAnalyses {deleted_leaf_analyses_str} deleted successfully"}), 200
        if not deleted_leaf_analyses:
            return jsonify({"error": "No leaf_analyses were deleted due to permission restrictions"}), 403
    def _has_access(self, leaf_analysis, claims):
        """Verifica si el usuario actual tiene acceso al recurso."""
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        if user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=user_id
            ).first()
            return any(
                org.id in [o.id for o in reseller_package.organizations]
                for org in leaf_analysis.common_analysis.lot.farm.user.organizations
            )
        return user_id == leaf_analysis.common_analysis.lot.farm.user_id
    def _serialize_leaf_analysis(self, leaf_analysis):
        """Serializa un objeto LeafAnalysis a un diccionario."""
        return {
            "id": leaf_analysis.id,
            "common_analysis_id": leaf_analysis.common_analysis_id,
            "created_at": leaf_analysis.created_at.isoformat(),
            "updated_at": leaf_analysis.updated_at.isoformat(),
        }

# Vista para aplicaciones de nutrientes (nutrient_applications)
class NutrientApplicationView(MethodView):
    """Clase para gestionar operaciones CRUD sobre aplicaciones de nutrientes."""
    decorators = [jwt_required()]
    @check_permission(required_roles=["administrator", "reseller"])
    def get(self, nutrient_application_id=None):
        """
        Obtiene una lista de aplicaciones de nutrientes o una aplicación de nutriente específico.
        Args:
            nutrient_application_id (str, optional): ID de la aplicación de nutriente a consultar.
        Returns:
            JSON: Lista de aplicaciones de nutrientes o detalles de una aplicación de nutriente específico.
        """
        if nutrient_application_id:
            return self._get_nutrient_application(nutrient_application_id)
        return self._get_nutrient_application_list()
    @check_permission(required_roles=["administrator", "reseller"])
    def post(self):
        """
        Crea una nueva aplicación de nutriente.
        Returns:
            JSON: Detalles de la aplicación de nutriente creada.
        """
        data = request.get_json()
        if not data or not all(k in data for k in ("date", "lot_id")):
            raise BadRequest("Missing required fields.")
        return self._create_nutrient_application(data)
    @check_permission(resource_owner_check=True)
    def put(self, nutrient_application_id):
        """
        Actualiza una aplicación de nutriente existente.
        Args:
            nutrient_application_id (str): ID de la aplicación de nutriente a actualizar.
        Returns:
            JSON: Detalles de la aplicación de nutriente actualizada.
        """
        data = request.get_json()
        if not data or not nutrient_application_id:
            raise BadRequest("Missing nutrient_application_id or data.")
        return self._update_nutrient_application(nutrient_application_id, data)
    @check_permission(resource_owner_check=True)
    def delete(self, nutrient_application_id=None):
        """
        Elimina una aplicación de nutriente existente.
        Args:
            nutrient_application_id (str): ID de la aplicación de nutriente a eliminar.
        Returns:
            JSON: Mensaje de confirmación.
        """
        data = request.get_json()
        if data and "ids" in data:
            return self._delete_nutrient_application(nutrient_application_ids=data["ids"])
        if nutrient_application_id:
            return self._delete_nutrient_application(nutrient_application_id=nutrient_application_id)
        raise BadRequest("Missing nutrient_application_id.")
    # Métodos auxiliares
    def _get_nutrient_application_list(self):
        """Obtiene una lista de todos los nutrientes aplicados activos."""
        claims = get_jwt()
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            nutrient_applications = NutrientApplication.query.filter_by(active=True).all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=user_id
            ).first()
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            nutrient_applications = []
            for org in reseller_package.organizations:
                nutrient_applications.extend(org.nutrient_applications)
        else:
            raise Forbidden("Only administrators and resellers can list nutrient_applications.")
        return jsonify([self._serialize_nutrient_application(nutrient_application) for nutrient_application in nutrient_applications]), 200
    def _get_nutrient_application(self, nutrient_application_id):
        """Obtiene los detalles de una aplicación de nutriente específico."""
        nutrient_application = NutrientApplication.query.get_or_404(nutrient_application_id)
        claims = get_jwt()
        if not self._has_access(nutrient_application, claims):
            raise Forbidden("You do not have access to this nutrient_application.")
        return jsonify(self._serialize_nutrient_application(nutrient_application)), 200
    def _create_nutrient_application(self, data):
        """Crea una nueva aplicación de nutriente con los datos proporcionados."""
        if NutrientApplication.query.filter_by(date=data["date"], lot_id=data["lot_id"]).first():
            raise BadRequest("NutrientApplication already exists.")
        nutrient_application = NutrientApplication(
            date=data["date"],
            lot_id=data["lot_id"],
        )
        db.session.add(nutrient_application)
        db.session.commit()
        return jsonify(self._serialize_nutrient_application(nutrient_application)), 201
    def _update_nutrient_application(self, nutrient_application_id, data):
        """Actualiza los datos de una aplicación de nutriente existente."""
        nutrient_application = NutrientApplication.query.get_or_404(nutrient_application_id)
        if "date" in data:
            nutrient_application.date = data["date"]
        if "lot_id" in data:
            nutrient_application.lot_id = data["lot_id"]
        db.session.commit()
        return jsonify(self._serialize_nutrient_application(nutrient_application)), 200
    def _delete_nutrient_application(self, nutrient_application_id=None, nutrient_application_ids=None):
        """Elimina una aplicación de nutriente marcándolo como inactivo."""
        claims = get_jwt()
        if nutrient_application_id and nutrient_application_ids:
            raise BadRequest("Solo se puede especificar nutrient_application_id o nutrient_application_ids, no ambos.")
        if nutrient_application_id:
            nutrient_application = NutrientApplication.query.get_or_404(nutrient_application_id)
            nutrient_application.active = False
            db.session.commit()
            return jsonify({"message": "NutrientApplication deleted successfully"}), 200
        if nutrient_application_ids:
            deleted_nutrient_applications = []
            for nutrient_application_id in nutrient_application_ids:
                nutrient_application = NutrientApplication.query.get(nutrient_application_id)
                if not nutrient_application:
                    continue
                nutrient_application.active = False
                deleted_nutrient_applications.append(nutrient_application.lot_id)
                db.session.commit()
                deleted_nutrient_applications_str = ", ".join(map(str, deleted_nutrient_applications))
            return jsonify({"message": f"NutrientApplications {deleted_nutrient_applications_str} deleted successfully"}), 200
        if not deleted_nutrient_applications:
            return jsonify({"error": "No nutrient_applications were deleted due to permission restrictions"}), 403
    def _has_access(self, nutrient_application, claims):
        """Verifica si el usuario actual tiene acceso al recurso."""
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        if user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=user_id
            ).first()
            return any(
                org.id in [o.id for o in reseller_package.organizations]
                for org in nutrient_application.lot.farm.user.organizations
            )
        return user_id == nutrient_application.lot.farm.user_id
    def _serialize_nutrient_application(self, nutrient_application):
        """Serializa un objeto NutrientApplication a un diccionario."""
        return {
            "id": nutrient_application.id,
            "date": nutrient_application.date,
            "lot_id": nutrient_application.lot_id,
            "created_at": nutrient_application.created_at.isoformat(),
            "updated_at": nutrient_application.updated_at.isoformat(),
        }