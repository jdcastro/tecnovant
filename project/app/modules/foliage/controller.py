# Python standard library imports
import json

# Third party imports
from flask_jwt_extended import jwt_required, get_jwt
from flask import request, jsonify, Response
from flask.views import MethodView
from werkzeug.exceptions import BadRequest, NotFound, Forbidden, Unauthorized
from sqlalchemy.orm import joinedload

# Local application imports
from app.extensions import db
from app.core.controller import check_permission
from app.core.models import RoleEnum, ResellerPackage
from .models import (
    Farm,
    Lot,
    Crop,
    LotCrop,
    CommonAnalysis,
    NutrientApplication,
    Nutrient,
    LeafAnalysis,
    Objective,
    objective_nutrients,
    SoilAnalysis,
    Production,
    Product,
    ProductContribution,
    ProductPrice,
    Recommendation,
)

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
        if not data or not all(k in data for k in ("name", "org_id")):
            raise BadRequest("Missing required fields.")
        return self._create_farm(data)

    @check_permission(resource_owner_check=True)
    def put(self, id: int):
        """
        Actualiza una granja existente.
        Args:
            farm_id (str): ID de la granja a actualizar.
        Returns:
            JSON: Detalles de la granja actualizada.
        """
        data = request.get_json()
        farm_id = data.get("id")
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
        org_id = claims.get("org_id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            if hasattr(Farm, "active"):
                farms = Farm.query.filter_by(active=True).all()
            else:
                farms = Farm.query.all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=org_id
            ).first()
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            farms = []
            for org in reseller_package.organizations:
                farms.extend(org.farms)
        else:
            raise Forbidden("Only administrators and resellers can list farms.")
        response_data = [self._serialize_farm(farm) for farm in farms]
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _get_farm(self, farm_id):
        """Obtiene los detalles de una granja específica."""
        farm = Farm.query.get_or_404(farm_id)
        claims = get_jwt()
        if not self._has_access(farm, claims):
            raise Forbidden("You do not have access to this farm.")
        response_data = self._serialize_farm(farm)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _create_farm(self, data):
        """Crea una nueva granja con los datos proporcionados."""
        if hasattr(Farm, "active"):
            if Farm.query.filter_by(
                name=data["name"], org_id=data["org_id"], active=True
            ).first():
                raise BadRequest("Name already exists.")
        else:
            if Farm.query.filter_by(name=data["name"], org_id=data["org_id"]).first():
                raise BadRequest("Name already exists.")
        farm = Farm(
            name=data["name"],
            org_id=data["org_id"],
        )
        db.session.add(farm)
        db.session.commit()
        response_data = self._serialize_farm(farm)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=201, mimetype="application/json")

    def _update_farm(self, farm_id, data):
        """Actualiza los datos de una granja existente."""
        farm = Farm.query.get_or_404(farm_id)
        if "name" in data and data["name"] != farm.name:
            if hasattr(Farm, "active"):
                if Farm.query.filter_by(
                    name=data["name"], org_id=farm.org_id, active=True
                ).first():
                    raise BadRequest("Name already exists.")
            else:
                if Farm.query.filter_by(name=data["name"], org_id=farm.org_id).first():
                    raise BadRequest("Name already exists.")
            farm.name = data["name"]
        if "org_id" in data:
            farm.org_id = data["org_id"]
        db.session.commit()
        response_data = self._serialize_farm(farm)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _delete_farm(self, farm_id=None, farm_ids=None):
        """Elimina una granja marcándola como inactiva."""
        claims = get_jwt()
        if farm_id and farm_ids:
            raise BadRequest("Solo se puede especificar farm_id o farm_ids, no ambos.")
        if farm_id:
            farm = Farm.query.get_or_404(farm_id)
            if hasattr(farm, "active"):
                farm.active = False
            else:
                db.session.delete(farm)
            db.session.commit()
            return jsonify({"message": "Farm deleted successfully"}), 200
        if farm_ids:
            deleted_farms = []
            for farm_id in farm_ids:
                farm = Farm.query.get(farm_id)
                if not farm:
                    continue
                if hasattr(farm, "active"):
                    farm.active = False
                else:
                    db.session.delete(farm)
                deleted_farms.append(farm.name)
                db.session.commit()
            deleted_farms_str = ", ".join(deleted_farms)
            return (
                jsonify({"message": f"Farms {deleted_farms_str} deleted successfully"}),
                200,
            )
        if not deleted_farms:
            return (
                jsonify(
                    {"error": "No farms were deleted due to permission restrictions"}
                ),
                403,
            )

    def _has_access(self, farm, claims):
        """Verifica si el usuario actual tiene acceso al recurso."""
        user_role = claims.get("rol")
        org_id = claims.get("org_id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        if user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=org_id
            ).first()
            return any(
                org.id in [o.id for o in reseller_package.organizations]
                for org in farm.organization
            )
        return farm.org_id == claims.get("org_id")

    def _serialize_farm(self, farm):
        """Serializa un objeto Farm a un diccionario."""
        return {
            "id": farm.id,
            "name": farm.name,
            "org_id": farm.org_id,
            "org_name": farm.organization.name if farm.organization else "",
            "lots": [lot.name for lot in farm.lots],
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
    def put(self, id=None):
        """
        Actualiza un lote existente.
        Args:
            lot_id (str): ID del lote a actualizar.
        Returns:
            JSON: Detalles del lote actualizado.
        """
        data = request.get_json()
        lot_id = data.get("id")
        if not data or not lot_id:
            raise BadRequest("Missing lot_id or data.")
        return self._update_lot(lot_id, data)

    @check_permission(resource_owner_check=True)
    def delete(self, id=None):
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
        if id:
            return self._delete_lot(lot_id=id)

        raise BadRequest("Missing lot_id.")

    # Métodos auxiliares
    def _get_lot_list(self, filter_by=None):
        """Obtiene una lista de lotes activos según el rol del usuario."""
        claims = get_jwt()
        user_role = claims.get("rol")
        user_id = claims.get("id")
        lots = []  # Lista de lotes que se devolverá
        if user_role == RoleEnum.ADMINISTRATOR.value:
            query = Lot.query
            if hasattr(Lot, "active"):
                query = query.filter_by(active=True)
            if filter_by:
                query = query.filter_by(farm_id=filter_by)
            lots = query.all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = (
                ResellerPackage.query.options(
                    joinedload(ResellerPackage.organizations).joinedload("lots")
                )
                .filter_by(reseller_id=user_id)
                .first()
            )
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            # Usamos un conjunto para evitar duplicados
            lots = {lot for org in reseller_package.organizations for lot in org.lots}
            # Convertimos a lista para la serialización final
            lots = list(lots)
        else:
            raise Forbidden("Only administrators and resellers can list lots.")
        # Serialización y respuesta
        response_data = [self._serialize_lot(lot) for lot in lots]
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _get_lot(self, lot_id):
        """Obtiene los detalles de un lote específico."""
        lot = Lot.query.get_or_404(lot_id)
        claims = get_jwt()
        if not self._has_access(lot, claims):
            raise Forbidden("You do not have access to this lot.")
        response_data = self._serialize_lot(lot)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _create_lot(self, data):
        """Crea un nuevo lote con los datos proporcionados."""
        if hasattr(Lot, "active"):
            if Lot.query.filter_by(name=data["name"], active=True).first():
                raise BadRequest("Name already exists.")
        else:
            if Lot.query.filter_by(name=data["name"]).first():
                raise BadRequest("Name already exists.")
        lot = Lot(
            name=data["name"],
            area=data["area"],
            farm_id=data["farm_id"],
        )
        db.session.add(lot)
        db.session.commit()
        response_data = self._serialize_lot(lot)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=201, mimetype="application/json")

    def _update_lot(self, lot_id, data):
        """Actualiza los datos de un lote existente."""
        lot = Lot.query.get_or_404(lot_id)
        if "name" in data and data["name"] != lot.name:
            if hasattr(Lot, "active"):
                if Lot.query.filter_by(name=data["name"], active=True).first():
                    raise BadRequest("Name already exists.")
            else:
                if Lot.query.filter_by(name=data["name"]).first():
                    raise BadRequest("Name already exists.")
            lot.name = data["name"]
        if "area" in data:
            lot.area = data["area"]
        if "farm_id" in data:
            lot.farm_id = data["farm_id"]
        db.session.commit()
        response_data = self._serialize_lot(lot)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _delete_lot(self, lot_id=None, lot_ids=None):
        """Elimina un lote marcándolo como inactivo."""
        claims = get_jwt()
        if lot_id and lot_ids:
            raise BadRequest("Solo se puede especificar lot_id o lot_ids, no ambos.")
        if lot_id:
            lot = Lot.query.get_or_404(lot_id)
            if hasattr(lot, "active"):
                lot.active = False
            else:
                db.session.delete(lot)
            db.session.commit()
            return jsonify({"message": "Lot deleted successfully"}), 200
        if lot_ids:
            deleted_lots = []
            for lot_id in lot_ids:
                lot = Lot.query.get(lot_id)
                if not lot:
                    continue
                if hasattr(lot, "active"):
                    lot.active = False
                else:
                    db.session.delete(lot)
                deleted_lots.append(lot.name)
                db.session.commit()
                deleted_lots_str = ", ".join(deleted_lots)
            return (
                jsonify({"message": f"Lots {deleted_lots_str} deleted successfully"}),
                200,
            )
        if not deleted_lots:
            return (
                jsonify(
                    {"error": "No lots were deleted due to permission restrictions"}
                ),
                403,
            )

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
            "farm_name": lot.farm.name if lot.farm else "",
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
    def put(self, id):
        """
        Actualiza un cultivo existente.
        Args:
            crop_id (str): ID del cultivo a actualizar.
        Returns:
            JSON: Detalles del cultivo actualizado.
        """
        data = request.get_json()
        crop_id = data.get("id")
        if not data or not crop_id:
            raise BadRequest("Missing crop_id or data.")
        return self._update_crop(crop_id, data)

    @check_permission(resource_owner_check=True)
    def delete(self, id=None):
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
        crop_id = id
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
            if hasattr(Crop, "active"):
                crops = Crop.query.filter_by(active=True).all()
            else:
                crops = Crop.query.all()
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
        response_data = [self._serialize_crop(crop) for crop in crops]
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _get_crop(self, crop_id):
        """Obtiene los detalles de un cultivo específico."""
        crop = Crop.query.get_or_404(crop_id)
        claims = get_jwt()
        if not self._has_access(crop, claims):
            raise Forbidden("You do not have access to this crop.")
        response_data = self._serialize_crop(crop)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _create_crop(self, data):
        """Crea un nuevo cultivo con los datos proporcionados."""
        if hasattr(Crop, "active"):
            if Crop.query.filter_by(name=data["name"], active=True).first():
                raise BadRequest("Name already exists.")
        else:
            if Crop.query.filter_by(name=data["name"]).first():
                raise BadRequest("Name already exists.")
        crop = Crop(
            name=data["name"],
        )
        db.session.add(crop)
        db.session.commit()
        response_data = self._serialize_crop(crop)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=201, mimetype="application/json")

    def _update_crop(self, crop_id, data):
        """Actualiza los datos de un cultivo existente."""
        crop = Crop.query.get_or_404(crop_id)
        if "name" in data and data["name"] != crop.name:
            if hasattr(Crop, "active"):
                if Crop.query.filter_by(name=data["name"], active=True).first():
                    raise BadRequest("Name already exists.")
            else:
                if Crop.query.filter_by(name=data["name"]).first():
                    raise BadRequest("Name already exists.")
            crop.name = data["name"]
        db.session.commit()
        response_data = self._serialize_crop(crop)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _delete_crop(self, crop_id=None, crop_ids=None):
        """Elimina un cultivo marcándolo como inactivo."""
        claims = get_jwt()
        if crop_id and crop_ids:
            raise BadRequest("Solo se puede especificar crop_id o crop_ids, no ambos.")
        if crop_id:
            crop = Crop.query.get_or_404(crop_id)
            if hasattr(crop, "active"):
                crop.active = False
            else:
                db.session.delete(crop)
            db.session.commit()
            return jsonify({"message": "Crop deleted successfully"}), 200
        if crop_ids:
            deleted_crops = []
            for crop_id in crop_ids:
                crop = Crop.query.get(crop_id)
                if not crop:
                    continue
                if hasattr(crop, "active"):
                    crop.active = False
                else:
                    db.session.delete(crop)
                deleted_crops.append(crop.name)
                db.session.commit()
                deleted_crops_str = ", ".join(deleted_crops)
            return (
                jsonify({"message": f"Crops {deleted_crops_str} deleted successfully"}),
                200,
            )
        if not deleted_crops:
            return (
                jsonify(
                    {"error": "No crops were deleted due to permission restrictions"}
                ),
                403,
            )

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
            if hasattr(LotCrop, "active"):
                lot_crops = LotCrop.query.filter_by(active=True).all()
            else:
                lot_crops = LotCrop.query.all()
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
        response_data = [self._serialize_lot_crop(lot_crop) for lot_crop in lot_crops]
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _get_lot_crop(self, lot_crop_id):
        """Obtiene los detalles de un lote de cultivo específico."""
        lot_crop = LotCrop.query.get_or_404(lot_crop_id)
        claims = get_jwt()
        if not self._has_access(lot_crop, claims):
            raise Forbidden("You do not have access to this lot_crop.")
        response_data = self._serialize_lot_crop(lot_crop)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _create_lot_crop(self, data):
        """Crea un nuevo lote de cultivo con los datos proporcionados."""
        if hasattr(LotCrop, "active"):
            if LotCrop.query.filter_by(
                lot_id=data["lot_id"], crop_id=data["crop_id"], active=True
            ).first():
                raise BadRequest("LotCrop already exists.")
        else:
            if LotCrop.query.filter_by(
                lot_id=data["lot_id"], crop_id=data["crop_id"]
            ).first():
                raise BadRequest("LotCrop already exists.")
        lot_crop = LotCrop(
            lot_id=data["lot_id"],
            crop_id=data["crop_id"],
            start_date=data["start_date"],
        )
        db.session.add(lot_crop)
        db.session.commit()
        response_data = self._serialize_lot_crop(lot_crop)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=201, mimetype="application/json")

    def _update_lot_crop(self, lot_crop_id, data):
        """Actualiza los datos de un lote de cultivo existente."""
        lot_crop = LotCrop.query.get_or_404(lot_crop_id)
        if "lot_id" in data and data["lot_id"] != lot_crop.lot_id:
            if hasattr(LotCrop, "active"):
                if LotCrop.query.filter_by(
                    lot_id=data["lot_id"], crop_id=lot_crop.crop_id, active=True
                ).first():
                    raise BadRequest("LotCrop already exists.")
            else:
                if LotCrop.query.filter_by(
                    lot_id=data["lot_id"], crop_id=lot_crop.crop_id
                ).first():
                    raise BadRequest("LotCrop already exists.")
            lot_crop.lot_id = data["lot_id"]
        if "crop_id" in data:
            lot_crop.crop_id = data["crop_id"]
        if "start_date" in data:
            lot_crop.start_date = data["start_date"]
        db.session.commit()
        response_data = self._serialize_lot_crop(lot_crop)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _delete_lot_crop(self, lot_crop_id=None, lot_crop_ids=None):
        """Elimina un lote de cultivo marcándolo como inactivo."""
        claims = get_jwt()
        if lot_crop_id and lot_crop_ids:
            raise BadRequest(
                "Solo se puede especificar lot_crop_id o lot_crop_ids, no ambos."
            )
        if lot_crop_id:
            lot_crop = LotCrop.query.get_or_404(lot_crop_id)
            if hasattr(lot_crop, "active"):
                lot_crop.active = False
            else:
                db.session.delete(lot_crop)
            db.session.commit()
            return jsonify({"message": "LotCrop deleted successfully"}), 200
        if lot_crop_ids:
            deleted_lot_crops = []
            for lot_crop_id in lot_crop_ids:
                lot_crop = LotCrop.query.get(lot_crop_id)
                if not lot_crop:
                    continue
                if hasattr(lot_crop, "active"):
                    lot_crop.active = False
                else:
                    db.session.delete(lot_crop)
                deleted_lot_crops.append(lot_crop.lot_id)
                db.session.commit()
                deleted_lot_crops_str = ", ".join(map(str, deleted_lot_crops))
            return (
                jsonify(
                    {
                        "message": f"LotCrops {deleted_lot_crops_str} deleted successfully"
                    }
                ),
                200,
            )
        if not deleted_lot_crops:
            return (
                jsonify(
                    {
                        "error": "No lot_crops were deleted due to permission restrictions"
                    }
                ),
                403,
            )

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
            if hasattr(CommonAnalysis, "active"):
                common_analyses = CommonAnalysis.query.filter_by(active=True).all()
            else:
                common_analyses = CommonAnalysis.query.all()
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
            raise Forbidden(
                "Only administrators and resellers can list common_analyses."
            )
        response_data = [
            self._serialize_common_analysis(common_analysis)
            for common_analysis in common_analyses
        ]
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _get_common_analysis(self, common_analysis_id):
        """Obtiene los detalles de un análisis común específico."""
        common_analysis = CommonAnalysis.query.get_or_404(common_analysis_id)
        claims = get_jwt()
        if not self._has_access(common_analysis, claims):
            raise Forbidden("You do not have access to this common_analysis.")
        response_data = self._serialize_common_analysis(common_analysis)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _create_common_analysis(self, data):
        """Crea un nuevo análisis común con los datos proporcionados."""
        if hasattr(CommonAnalysis, "active"):
            if CommonAnalysis.query.filter_by(
                date=data["date"], lot_id=data["lot_id"], active=True
            ).first():
                raise BadRequest("CommonAnalysis already exists.")
        else:
            if CommonAnalysis.query.filter_by(
                date=data["date"], lot_id=data["lot_id"]
            ).first():
                raise BadRequest("CommonAnalysis already exists.")
        common_analysis = CommonAnalysis(
            date=data["date"],
            lot_id=data["lot_id"],
        )
        db.session.add(common_analysis)
        db.session.commit()
        response_data = self._serialize_common_analysis(common_analysis)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=201, mimetype="application/json")

    def _update_common_analysis(self, common_analysis_id, data):
        """Actualiza los datos de un análisis común existente."""
        common_analysis = CommonAnalysis.query.get_or_404(common_analysis_id)
        if "date" in data:
            common_analysis.date = data["date"]
        if "lot_id" in data:
            common_analysis.lot_id = data["lot_id"]
        db.session.commit()
        response_data = self._serialize_common_analysis(common_analysis)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _delete_common_analysis(
        self, common_analysis_id=None, common_analysis_ids=None
    ):
        """Elimina un análisis común marcándolo como inactivo."""
        claims = get_jwt()
        if common_analysis_id and common_analysis_ids:
            raise BadRequest(
                "Solo se puede especificar common_analysis_id o common_analysis_ids, no ambos."
            )
        if common_analysis_id:
            common_analysis = CommonAnalysis.query.get_or_404(common_analysis_id)
            if hasattr(common_analysis, "active"):
                common_analysis.active = False
            else:
                db.session.delete(common_analysis)
            db.session.commit()
            return jsonify({"message": "CommonAnalysis deleted successfully"}), 200
        if common_analysis_ids:
            deleted_common_analyses = []
            for common_analysis_id in common_analysis_ids:
                common_analysis = CommonAnalysis.query.get(common_analysis_id)
                if not common_analysis:
                    continue
                if hasattr(common_analysis, "active"):
                    common_analysis.active = False
                else:
                    db.session.delete(common_analysis)
                deleted_common_analyses.append(common_analysis.lot_id)
                db.session.commit()
                deleted_common_analyses_str = ", ".join(
                    map(str, deleted_common_analyses)
                )
            return (
                jsonify(
                    {
                        "message": f"CommonAnalyses {deleted_common_analyses_str} deleted successfully"
                    }
                ),
                200,
            )
        if not deleted_common_analyses:
            return (
                jsonify(
                    {
                        "error": "No common_analyses were deleted due to permission restrictions"
                    }
                ),
                403,
            )

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
    def put(self, id: int):
        """
        Actualiza un nutriente existente.
        Args:
            nutrient_id (str): ID del nutriente a actualizar.
        Returns:
            JSON: Detalles del nutriente actualizado.
        """
        data = request.get_json()
        nutrient_id = id
        if not data or not nutrient_id:
            raise BadRequest("Missing nutrient_id or data.")
        return self._update_nutrient(nutrient_id, data)

    @check_permission(resource_owner_check=True)
    def delete(self, id=None):
        """
        Elimina un nutriente existente.
        Args:
            nutrient_id (str): ID del nutriente a eliminar.
        Returns:
            JSON: Mensaje de confirmación.
        """
        data = request.get_json()
        nutrient_id = id
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
            if hasattr(Nutrient, "active"):
                nutrients = Nutrient.query.filter_by(active=True).all()
            else:
                nutrients = Nutrient.query.all()
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
        response_data = [self._serialize_nutrient(nutrient) for nutrient in nutrients]
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _get_nutrient(self, nutrient_id):
        """Obtiene los detalles de un nutriente específico."""
        nutrient = Nutrient.query.get_or_404(nutrient_id)
        claims = get_jwt()
        if not self._has_access(nutrient, claims):
            raise Forbidden("You do not have access to this nutrient.")
        response_data = self._serialize_nutrient(nutrient)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _create_nutrient(self, data):
        """Crea un nuevo nutriente con los datos proporcionados."""
        if hasattr(Nutrient, "active"):
            if Nutrient.query.filter_by(name=data["name"], active=True).first():
                raise BadRequest("Name already exists.")
        else:
            if Nutrient.query.filter_by(name=data["name"]).first():
                raise BadRequest("Name already exists.")
        nutrient = Nutrient(
            name=data["name"],
            symbol=data["symbol"],
            unit=data["unit"],
        )
        db.session.add(nutrient)
        db.session.commit()
        response_data = self._serialize_nutrient(nutrient)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=201, mimetype="application/json")

    def _update_nutrient(self, nutrient_id, data):
        """Actualiza los datos de un nutriente existente."""
        nutrient = Nutrient.query.get_or_404(nutrient_id)
        if "name" in data and data["name"] != nutrient.name:
            if hasattr(Nutrient, "active"):
                if Nutrient.query.filter_by(name=data["name"], active=True).first():
                    raise BadRequest("Name already exists.")
            else:
                if Nutrient.query.filter_by(name=data["name"]).first():
                    raise BadRequest("Name already exists.")
            nutrient.name = data["name"]
        if "symbol" in data:
            nutrient.symbol = data["symbol"]
        if "unit" in data:
            nutrient.unit = data["unit"]
        db.session.commit()
        response_data = self._serialize_nutrient(nutrient)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _delete_nutrient(self, nutrient_id=None, nutrient_ids=None):
        """Elimina un nutriente marcándolo como inactivo."""
        claims = get_jwt()
        if nutrient_id and nutrient_ids:
            raise BadRequest(
                "Solo se puede especificar nutrient_id o nutrient_ids, no ambos."
            )
        if nutrient_id:
            nutrient = Nutrient.query.get_or_404(nutrient_id)
            if hasattr(nutrient, "active"):
                nutrient.active = False
            else:
                db.session.delete(nutrient)
            db.session.commit()
            return jsonify({"message": "Nutrient deleted successfully"}), 200
        if nutrient_ids:
            deleted_nutrients = []
            for nutrient_id in nutrient_ids:
                nutrient = Nutrient.query.get(nutrient_id)
                if not nutrient:
                    continue
                if hasattr(nutrient, "active"):
                    nutrient.active = False
                else:
                    db.session.delete(nutrient)
                deleted_nutrients.append(nutrient.name)
                db.session.commit()
                deleted_nutrients_str = ", ".join(deleted_nutrients)
            return (
                jsonify(
                    {
                        "message": f"Nutrients {deleted_nutrients_str} deleted successfully"
                    }
                ),
                200,
            )
        if not deleted_nutrients:
            return (
                jsonify(
                    {
                        "error": "No nutrients were deleted due to permission restrictions"
                    }
                ),
                403,
            )

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
            "description": nutrient.description,
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
            if hasattr(LeafAnalysis, "active"):
                leaf_analyses = LeafAnalysis.query.filter_by(active=True).all()
            else:
                leaf_analyses = LeafAnalysis.query.all()
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
        response_data = [
            self._serialize_leaf_analysis(leaf_analysis)
            for leaf_analysis in leaf_analyses
        ]
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _get_leaf_analysis(self, leaf_analysis_id):
        """Obtiene los detalles de un análisis de hoja específico."""
        leaf_analysis = LeafAnalysis.query.get_or_404(leaf_analysis_id)
        claims = get_jwt()
        if not self._has_access(leaf_analysis, claims):
            raise Forbidden("You do not have access to this leaf_analysis.")
        response_data = self._serialize_leaf_analysis(leaf_analysis)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _create_leaf_analysis(self, data):
        """Crea un nuevo análisis de hoja con los datos proporcionados."""
        if hasattr(LeafAnalysis, "active"):
            if LeafAnalysis.query.filter_by(
                common_analysis_id=data["common_analysis_id"], active=True
            ).first():
                raise BadRequest("LeafAnalysis already exists.")
        else:
            if LeafAnalysis.query.filter_by(
                common_analysis_id=data["common_analysis_id"]
            ).first():
                raise BadRequest("LeafAnalysis already exists.")
        leaf_analysis = LeafAnalysis(
            common_analysis_id=data["common_analysis_id"],
        )
        db.session.add(leaf_analysis)
        db.session.commit()
        response_data = self._serialize_leaf_analysis(leaf_analysis)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=201, mimetype="application/json")

    def _update_leaf_analysis(self, leaf_analysis_id, data):
        """Actualiza los datos de un análisis de hoja existente."""
        leaf_analysis = LeafAnalysis.query.get_or_404(leaf_analysis_id)
        if "common_analysis_id" in data:
            leaf_analysis.common_analysis_id = data["common_analysis_id"]
        db.session.commit()
        response_data = self._serialize_leaf_analysis(leaf_analysis)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _delete_leaf_analysis(self, leaf_analysis_id=None, leaf_analysis_ids=None):
        """Elimina un análisis de hoja marcándolo como inactivo."""
        claims = get_jwt()
        if leaf_analysis_id and leaf_analysis_ids:
            raise BadRequest(
                "Solo se puede especificar leaf_analysis_id o leaf_analysis_ids, no ambos."
            )
        if leaf_analysis_id:
            leaf_analysis = LeafAnalysis.query.get_or_404(leaf_analysis_id)
            if hasattr(leaf_analysis, "active"):
                leaf_analysis.active = False
            else:
                db.session.delete(leaf_analysis)
            db.session.commit()
            return jsonify({"message": "LeafAnalysis deleted successfully"}), 200
        if leaf_analysis_ids:
            deleted_leaf_analyses = []
            for leaf_analysis_id in leaf_analysis_ids:
                leaf_analysis = LeafAnalysis.query.get(leaf_analysis_id)
                if not leaf_analysis:
                    continue
                if hasattr(leaf_analysis, "active"):
                    leaf_analysis.active = False
                else:
                    db.session.delete(leaf_analysis)
                deleted_leaf_analyses.append(leaf_analysis.common_analysis_id)
                db.session.commit()
                deleted_leaf_analyses_str = ", ".join(map(str, deleted_leaf_analyses))
            return (
                jsonify(
                    {
                        "message": f"LeafAnalyses {deleted_leaf_analyses_str} deleted successfully"
                    }
                ),
                200,
            )
        if not deleted_leaf_analyses:
            return (
                jsonify(
                    {
                        "error": "No leaf_analyses were deleted due to permission restrictions"
                    }
                ),
                403,
            )

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
            return self._delete_nutrient_application(
                nutrient_application_ids=data["ids"]
            )
        if nutrient_application_id:
            return self._delete_nutrient_application(
                nutrient_application_id=nutrient_application_id
            )
        raise BadRequest("Missing nutrient_application_id.")

    # Métodos auxiliares
    def _get_nutrient_application_list(self):
        """Obtiene una lista de todos los nutrientes aplicados activos."""
        claims = get_jwt()
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            if hasattr(NutrientApplication, "active"):
                nutrient_applications = NutrientApplication.query.filter_by(
                    active=True
                ).all()
            else:
                nutrient_applications = NutrientApplication.query.all()
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
            raise Forbidden(
                "Only administrators and resellers can list nutrient_applications."
            )
        response_data = [
            self._serialize_nutrient_application(nutrient_application)
            for nutrient_application in nutrient_applications
        ]
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _get_nutrient_application(self, nutrient_application_id):
        """Obtiene los detalles de una aplicación de nutriente específico."""
        nutrient_application = NutrientApplication.query.get_or_404(
            nutrient_application_id
        )
        claims = get_jwt()
        if not self._has_access(nutrient_application, claims):
            raise Forbidden("You do not have access to this nutrient_application.")
        response_data = self._serialize_nutrient_application(nutrient_application)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _create_nutrient_application(self, data):
        """Crea una nueva aplicación de nutriente con los datos proporcionados."""
        if hasattr(NutrientApplication, "active"):
            if NutrientApplication.query.filter_by(
                date=data["date"], lot_id=data["lot_id"], active=True
            ).first():
                raise BadRequest("NutrientApplication already exists.")
        else:
            if NutrientApplication.query.filter_by(
                date=data["date"], lot_id=data["lot_id"]
            ).first():
                raise BadRequest("NutrientApplication already exists.")
        nutrient_application = NutrientApplication(
            date=data["date"],
            lot_id=data["lot_id"],
        )
        db.session.add(nutrient_application)
        db.session.commit()
        response_data = self._serialize_nutrient_application(nutrient_application)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=201, mimetype="application/json")

    def _update_nutrient_application(self, nutrient_application_id, data):
        """Actualiza los datos de una aplicación de nutriente existente."""
        nutrient_application = NutrientApplication.query.get_or_404(
            nutrient_application_id
        )
        if "date" in data:
            nutrient_application.date = data["date"]
        if "lot_id" in data:
            nutrient_application.lot_id = data["lot_id"]
        db.session.commit()
        response_data = self._serialize_nutrient_application(nutrient_application)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _delete_nutrient_application(
        self, nutrient_application_id=None, nutrient_application_ids=None
    ):
        """Elimina una aplicación de nutriente marcándolo como inactivo."""
        claims = get_jwt()
        if nutrient_application_id and nutrient_application_ids:
            raise BadRequest(
                "Solo se puede especificar nutrient_application_id o nutrient_application_ids, no ambos."
            )
        if nutrient_application_id:
            nutrient_application = NutrientApplication.query.get_or_404(
                nutrient_application_id
            )
            if hasattr(nutrient_application, "active"):
                nutrient_application.active = False
            else:
                db.session.delete(nutrient_application)
            db.session.commit()
            return jsonify({"message": "NutrientApplication deleted successfully"}), 200
        if nutrient_application_ids:
            deleted_nutrient_applications = []
            for nutrient_application_id in nutrient_application_ids:
                nutrient_application = NutrientApplication.query.get(
                    nutrient_application_id
                )
                if not nutrient_application:
                    continue
                if hasattr(nutrient_application, "active"):
                    nutrient_application.active = False
                else:
                    db.session.delete(nutrient_application)
                deleted_nutrient_applications.append(nutrient_application.lot_id)
                db.session.commit()
                deleted_nutrient_applications_str = ", ".join(
                    map(str, deleted_nutrient_applications)
                )
            return (
                jsonify(
                    {
                        "message": f"NutrientApplications {deleted_nutrient_applications_str} deleted successfully"
                    }
                ),
                200,
            )
        if not deleted_nutrient_applications:
            return (
                jsonify(
                    {
                        "error": "No nutrient_applications were deleted due to permission restrictions"
                    }
                ),
                403,
            )

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


class ObjectiveView(MethodView):
    """Class to manage CRUD operations for nutrient objectives tied to crops"""

    decorators = [jwt_required()]

    @check_permission(required_roles=["administrator", "reseller"])
    def get(self, objective_id=None):
        """
        Retrieve a list of objectives or a specific objective.
        Args:
            objective_id (int, optional): ID of the objective to retrieve.
        Returns:
            JSON: List of objectives or details of a specific objective.
        """
        if objective_id:
            return self._get_objective(objective_id)
        return self._get_objective_list()

    @check_permission(required_roles=["administrator", "reseller"])
    def post(self):
        """
        Create a new objective with nutrient targets, protein, rest, and target value.
        Expected JSON data:
            {
                "crop_id": int,
                "target_value": float,
                "protein": float (optional),
                "rest": float (optional),
                "nutrient_targets": {"nutrient_<id>": float, ...} (e.g., "nutrient_1": 10.5)
            }
        Returns:
            JSON: Details of the created objective.
        """
        data = request.get_json()
        required_fields = ["crop_id", "target_value"]
        if not data or not all(k in data for k in required_fields):
            raise BadRequest("Missing required fields: crop_id and target_value.")
        return self._create_objective(data)

    @check_permission(resource_owner_check=True)
    def put(self, id: int):
        """
        Update an existing objective.
        Args:
            objective_id (int): ID of the objective to update.
        Expected JSON data: Same as POST, with optional fields.
        Returns:
            JSON: Details of the updated objective.
        """
        data = request.get_json()
        objective_id = id

        if not data or not objective_id:
            raise BadRequest("Missing objective_id or data.")
        return self._update_objective(objective_id, data)

    @check_permission(resource_owner_check=True)
    def delete(self, id=None):
        """
        Delete an existing objective.
        Args:
            objective_id (int): ID of the objective to delete.
        Returns:
            JSON: Confirmation message.
        """
        objective_id = id

        if not objective_id:
            raise BadRequest("Missing objective_id.")
        return self._delete_objective(objective_id)

    # Helper Methods
    def _get_objective_list(self):
        """Retrieve a list of all objectives based on user role"""
        claims = get_jwt()
        user_role = claims.get("rol")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            objectives = Objective.query.all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=claims.get("org_id")
            ).first()
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            objectives = []
            for organization in reseller_package.organizations:
                for crop in organization.crops:
                    objectives.extend(crop.objectives)
        else:
            raise Forbidden("Only administrators and resellers can list objectives.")
        response_data = [self._serialize_objective(obj) for obj in objectives]
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _get_objective(self, objective_id):
        """Retrieve details of a specific objective"""
        objective = Objective.query.get_or_404(objective_id)
        claims = get_jwt()
        if not self._has_access(objective, claims):
            raise Forbidden("You do not have access to this objective.")
        response_data = self._serialize_objective(objective)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _create_objective(self, data):
        """Create a new objective with nutrient targets"""
        crop_id = data["crop_id"]
        target_value = float(data["target_value"])  # Convert to float
        protein = data.get("protein")  # Optional
        rest = data.get("rest")  # Optional

        # Validate crop exists
        crop = Crop.query.get(crop_id)
        if not crop:
            raise BadRequest("Invalid crop ID.")

        # Convert optional fields to float if provided
        protein = float(protein) if protein is not None else None
        rest = float(rest) if rest is not None else None

        # Create new objective
        new_objective = Objective(
            crop_id=crop_id, target_value=target_value, protein=protein, rest=rest
        )
        db.session.add(new_objective)
        db.session.flush()  # Ensure new_objective.id is available

        # Handle nutrient targets
        nutrient_targets = {k: v for k, v in data.items() if k.startswith("nutrient_")}
        for key, value in nutrient_targets.items():
            nutrient_id = int(key.split("_")[1])
            nutrient = Nutrient.query.get(nutrient_id)
            if not nutrient:
                raise BadRequest(f"Invalid nutrient ID: {nutrient_id}")
            try:
                target_value_float = float(value)  # Convert to float
                if target_value_float <= 0:
                    raise BadRequest(
                        f"Target value for {nutrient.name} must be positive."
                    )
                insert_stmt = objective_nutrients.insert().values(
                    objective_id=new_objective.id,
                    nutrient_id=nutrient_id,
                    target_value=target_value_float,
                )
                db.session.execute(insert_stmt)
            except ValueError:
                raise BadRequest(
                    f"Invalid numeric value for {nutrient.name}: '{value}'"
                )

        db.session.commit()
        response_data = self._serialize_objective(new_objective)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=201, mimetype="application/json")

    def _update_objective(self, objective_id, data):
        """Update an existing objective"""
        objective = Objective.query.get_or_404(objective_id)

        # Update main fields if provided
        if "crop_id" in data:
            crop = Crop.query.get(data["crop_id"])
            if not crop:
                raise BadRequest("Invalid crop ID.")
            objective.crop_id = data["crop_id"]
        if "target_value" in data:
            objective.target_value = data["target_value"]
        if "protein" in data:
            objective.protein = data["protein"]
        if "rest" in data:
            objective.rest = data["rest"]

        # Handle nutrient targets if provided
        nutrient_targets = {k: v for k, v in data.items() if k.startswith("nutrient_")}
        if nutrient_targets:
            # Delete existing nutrient targets
            db.session.query(objective_nutrients).filter_by(
                objective_id=objective.id
            ).delete()
            # Add new nutrient targets
            for key, value in nutrient_targets.items():
                nutrient_id = int(key.split("_")[1])
                nutrient = Nutrient.query.get(nutrient_id)
                if not nutrient:
                    raise BadRequest(f"Invalid nutrient ID: {nutrient_id}")
                # Convert value to float (or int) and validate
                try:
                    target_value = float(
                        value
                    )  # Use float to handle decimal values; use int if only integers are expected
                    if target_value <= 0:
                        raise BadRequest(
                            f"Target value for {nutrient.name} must be positive."
                        )
                    insert_stmt = objective_nutrients.insert().values(
                        objective_id=objective.id,
                        nutrient_id=nutrient_id,
                        target_value=target_value,
                    )
                    db.session.execute(insert_stmt)
                except ValueError:
                    raise BadRequest(
                        f"Target value for {nutrient.name} must be a valid number."
                    )

        db.session.commit()
        response_data = self._serialize_objective(objective)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _delete_objective(self, objective_id):
        """Delete an existing objective"""
        objective = Objective.query.get_or_404(objective_id)
        db.session.delete(objective)
        db.session.commit()
        return jsonify({"message": "Objective deleted successfully"}), 200

    def _has_access(self, objective, claims):
        """Check if the current user has access to the objective"""
        user_role = claims.get("rol")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        if user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=claims.get("org_id")
            ).first()
            if not reseller_package:
                return False
            return any(
                org.id == objective.crop.organization.id
                for org in reseller_package.organizations
            )
        return False

    def _serialize_objective(self, objective):
        """Serialize an Objective object to a dictionary"""
        nutrient_targets = (
            db.session.query(objective_nutrients)
            .filter_by(objective_id=objective.id)
            .all()
        )
        nutrient_targets_dict = [
            {
                "nutrient_id": target.nutrient_id,
                "target_value": target.target_value,
                "nutrient_name": Nutrient.query.get(target.nutrient_id).name,
                "nutrient_symbol": Nutrient.query.get(target.nutrient_id).symbol,
                "nutrient_unit": Nutrient.query.get(target.nutrient_id).unit,
            }
            for target in nutrient_targets
        ]
        return {
            "id": objective.id,
            "crop_id": objective.crop_id,
            "crop_name": objective.crop.name,
            "target_value": objective.target_value,
            "protein": objective.protein,
            "rest": objective.rest,
            "created_at": objective.created_at.isoformat(),
            "updated_at": objective.updated_at.isoformat(),
            "nutrient_targets": nutrient_targets_dict,
        }


# Example Usage
# Create an Objective (POST)
# json

# {
#     "crop_id": 1,
#     "target_value": 100.0,
#     "protein": 20.5,
#     "rest": 15.0,
#     "nutrient_1": 10.5,  // Nitrogen target
#     "nutrient_2": 5.0    // Phosphorus target
# }

# Response
# json

# {
#     "id": 1,
#     "crop_id": 1,
#     "target_value": 100.0,
#     "protein": 20.5,
#     "rest": 15.0,
#     "created_at": "2025-03-13T12:00:00",
#     "updated_at": "2025-03-13T12:00:00",
#     "nutrient_targets": [
#         {
#             "nutrient_id": 1,
#             "target_value": 10.5,
#             "nutrient_name": "Nitrogen",
#             "nutrient_symbol": "N",
#             "nutrient_unit": "mg/L"
#         },
#         {
#             "nutrient_id": 2,
#             "target_value": 5.0,
#             "nutrient_name": "Phosphorus",
#             "nutrient_symbol": "P",
#             "nutrient_unit": "mg/L"
#         }
#     ]
# }

# Update an Objective (PUT)
# json

# {
#     "target_value": 120.0,
#     "nutrient_1": 12.0
# }


class SoilAnalysisView(MethodView):
    """Class to manage CRUD operations for soil analyses"""

    decorators = [jwt_required()]

    @check_permission(required_roles=["administrator", "reseller"])
    def get(self, soil_analysis_id=None):
        """
        Retrieve a list of soil analyses or a specific soil analysis
        Args:
            soil_analysis_id (int, optional): ID of the soil analysis to retrieve
        Returns:
            JSON: List of soil analyses or details of a specific soil analysis
        """
        if soil_analysis_id:
            return self._get_soil_analysis(soil_analysis_id)
        return self._get_soil_analysis_list()

    @check_permission(required_roles=["administrator", "reseller"])
    def post(self):
        """
        Create a new soil analysis
        Returns:
            JSON: Details of the created soil analysis
        """
        data = request.get_json()
        required_fields = ["common_analysis_id", "energy", "grazing"]
        if not data or not all(k in data for k in required_fields):
            raise BadRequest("Missing required fields")
        return self._create_soil_analysis(data)

    @check_permission(resource_owner_check=True)
    def put(self, id: int):
        """
        Update an existing soil analysis
        Args:
            soil_analysis_id (int): ID of the soil analysis to update
        Returns:
            JSON: Details of the updated soil analysis
        """
        data = request.get_json()
        soil_analysis_id = id
        if not data or not soil_analysis_id:
            raise BadRequest("Missing soil_analysis_id or data")
        return self._update_soil_analysis(soil_analysis_id, data)

    @check_permission(resource_owner_check=True)
    def delete(self, id=None):
        """
        Delete an existing soil analysis
        Args:
            soil_analysis_id (int): ID of the soil analysis to delete
        Returns:
            JSON: Confirmation message
        """
        soil_analysis_id = id
        if not soil_analysis_id:
            raise BadRequest("Missing soil_analysis_id")
        return self._delete_soil_analysis(soil_analysis_id)

    # Helper Methods
    def _get_soil_analysis_list(self):
        """Retrieve a list of all soil analyses"""
        claims = get_jwt()
        user_role = claims.get("rol")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            soil_analyses = SoilAnalysis.query.all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=claims.get("org_id")
            ).first()
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            soil_analyses = []
            for organization in reseller_package.organizations:
                for common_analysis in organization.common_analyses:
                    soil_analyses.extend / common_analysis.soil_analysis
        else:
            raise Forbidden("Only administrators and resellers can list soil analyses")
        response_data = [self._serialize_soil_analysis(sa) for sa in soil_analyses]
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _get_soil_analysis(self, soil_analysis_id):
        """Retrieve details of a specific soil analysis"""
        soil_analysis = SoilAnalysis.query.get_or_404(soil_analysis_id)
        claims = get_jwt()
        if not self._has_access(soil_analysis, claims):
            raise Forbidden("You do not have access to this soil analysis")
        response_data = self._serialize_soil_analysis(soil_analysis)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _create_soil_analysis(self, data):
        """Create a new soil analysis"""
        common_analysis_id = data["common_analysis_id"]
        energy = data["energy"]
        grazing = data["grazing"]
        soil_analysis = SoilAnalysis(
            common_analysis_id=common_analysis_id, energy=energy, grazing=grazing
        )
        db.session.add(soil_analysis)
        db.session.commit()
        response_data = self._serialize_soil_analysis(soil_analysis)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=201, mimetype="application/json")

    def _update_soil_analysis(self, soil_analysis_id, data):
        """Update an existing soil analysis"""
        soil_analysis = SoilAnalysis.query.get_or_404(soil_analysis_id)
        if "energy" in data:
            soil_analysis.energy = data["energy"]
        if "grazing" in data:
            soil_analysis.grazing = data["grazing"]
        db.session.commit()
        response_data = self._serialize_soil_analysis(soil_analysis)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _delete_soil_analysis(self, soil_analysis_id):
        """Delete an existing soil analysis"""
        soil_analysis = SoilAnalysis.query.get_or_404(soil_analysis_id)
        db.session.delete(soil_analysis)
        db.session.commit()
        return jsonify({"message": "Soil analysis deleted successfully"}), 200

    def _has_access(self, soil_analysis, claims):
        """Check if the current user has access to the soil analysis"""
        user_role = claims.get("rol")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        if user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=claims.get("org_id")
            ).first()
            if not reseller_package:
                return False
            return any(
                org.id == soil_analysis.common_analysis.organization.id
                for org in reseller_package.organizations
            )
        return False

    def _serialize_soil_analysis(self, soil_analysis):
        """Serialize a SoilAnalysis object to a dictionary"""
        return {
            "id": soil_analysis.id,
            "common_analysis_id": soil_analysis.common_analysis_id,
            "energy": soil_analysis.energy,
            "grazing": soil_analysis.grazing,
            "created_at": soil_analysis.created_at.isoformat(),
            "updated_at": soil_analysis.updated_at.isoformat(),
        }


class ProductionView(MethodView):
    """Class to manage CRUD operations for productions"""

    decorators = [jwt_required()]

    @check_permission(required_roles=["administrator", "reseller"])
    def get(self, production_id=None):
        """
        Retrieve a list of productions or a specific production
        Args:
            production_id (int, optional): ID of the production to retrieve
        Returns:
            JSON: List of productions or details of a specific production
        """
        if production_id:
            return self._get_production(production_id)
        return self._get_production_list()

    @check_permission(required_roles=["administrator", "reseller"])
    def post(self):
        """
        Create a new production
        Returns:
            JSON: Details of the created production
        """
        data = request.get_json()
        required_fields = ["lot_id", "date", "area", "production_kg"]
        if not data or not all(k in data for k in required_fields):
            raise BadRequest("Missing required fields")
        return self._create_production(data)

    @check_permission(resource_owner_check=True)
    def put(self, id: int):
        """
        Update an existing production
        Args:
            production_id (int): ID of the production to update
        Returns:
            JSON: Details of the updated production
        """
        data = request.get_json()
        production_id = id
        if not data or not production_id:
            raise BadRequest("Missing production_id or data")
        return self._update_production(production_id, data)

    @check_permission(resource_owner_check=True)
    def delete(self, id=None):
        """
        Delete an existing production
        Args:
            production_id (int): ID of the production to delete
        Returns:
            JSON: Confirmation message
        """
        production_id = id
        if not production_id:
            raise BadRequest("Missing production_id")
        return self._delete_production(production_id)

    # Helper Methods
    def _get_production_list(self):
        """Retrieve a list of all productions"""
        claims = get_jwt()
        user_role = claims.get("rol")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            productions = Production.query.all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=claims.get("org_id")
            ).first()
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            productions = []
            for organization in reseller_package.organizations:
                for lot in organization.lots:
                    productions.extend(lot.productions)
        else:
            raise Forbidden("Only administrators and resellers can list productions")
        response_data = [self._serialize_production(p) for p in productions]
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _get_production(self, production_id):
        """Retrieve details of a specific production"""
        production = Production.query.get_or_404(production_id)
        claims = get_jwt()
        if not self._has_access(production, claims):
            raise Forbidden("You do not have access to this production")
        response_data = self._serialize_production(production)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _create_production(self, data):
        """Create a new production"""
        lot_id = data["lot_id"]
        date = data["date"]
        area = data["area"]
        production_kg = data["production_kg"]
        production = Production(
            lot_id=lot_id, date=date, area=area, production_kg=production_kg
        )
        db.session.add(production)
        db.session.commit()
        response_data = self._serialize_production(production)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=201, mimetype="application/json")

    def _update_production(self, production_id, data):
        """Update an existing production"""
        production = Production.query.get_or_404(production_id)
        if "date" in data:
            production.date = data["date"]
        if "area" in data:
            production.area = data["area"]
        if "production_kg" in data:
            production.production_kg = data["production_kg"]
        db.session.commit()
        response_data = self._serialize_production(production)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _delete_production(self, production_id):
        """Delete an existing production"""
        production = Production.query.get_or_404(production_id)
        db.session.delete(production)
        db.session.commit()
        return jsonify({"message": "Production deleted successfully"}), 200

    def _has_access(self, production, claims):
        """Check if the current user has access to the production"""
        user_role = claims.get("rol")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        if user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=claims.get("org_id")
            ).first()
            if not reseller_package:
                return False
            return any(
                org.id == production.lot.farm.organization.id
                for org in reseller_package.organizations
            )
        return False

    def _serialize_production(self, production):
        """Serialize a Production object to a dictionary"""
        return {
            "id": production.id,
            "lot_id": production.lot_id,
            "date": production.date,
            "area": production.area,
            "production_kg": production.production_kg,
            "created_at": production.created_at.isoformat(),
            "updated_at": production.updated_at.isoformat(),
        }


class ProductView(MethodView):
    """Class to manage CRUD operations for products"""

    decorators = [jwt_required()]

    @check_permission(required_roles=["administrator", "reseller"])
    def get(self, product_id=None):
        """
        Retrieve a list of products or a specific product
        Args:
            product_id (int, optional): ID of the product to retrieve
        Returns:
            JSON: List of products or details of a specific product
        """
        if product_id:
            return self._get_product(product_id)
        return self._get_product_list()

    @check_permission(required_roles=["administrator", "reseller"])
    def post(self):
        """
        Create a new product
        Returns:
            JSON: Details of the created product
        """
        data = request.get_json()
        required_fields = ["name", "description"]
        if not data or not all(k in data for k in required_fields):
            raise BadRequest("Missing required fields")
        return self._create_product(data)

    @check_permission(resource_owner_check=True)
    def put(self, id: int):
        """
        Update an existing product
        Args:
            product_id (int): ID of the product to update
        Returns:
            JSON: Details of the updated product
        """
        data = request.get_json()
        product_id = id
        if not data or not product_id:
            raise BadRequest("Missing product_id or data")
        return self._update_product(product_id, data)

    @check_permission(resource_owner_check=True)
    def delete(self, id=None):
        """
        Delete an existing product
        Args:
            product_id (int): ID of the product to delete
        Returns:
            JSON: Confirmation message
        """
        product_id = id
        if not product_id:
            raise BadRequest("Missing product_id")
        return self._delete_product(product_id)

    # Helper Methods
    def _get_product_list(self):
        """Retrieve a list of all products"""
        claims = get_jwt()
        user_role = claims.get("rol")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            products = Product.query.all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=claims.get("org_id")
            ).first()
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            products = []
            for organization in reseller_package.organizations:
                products.extend(organization.products)
        else:
            raise Forbidden("Only administrators and resellers can list products")
        response_data = [self._serialize_product(p) for p in products]
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _get_product(self, product_id):
        """Retrieve details of a specific product"""
        product = Product.query.get_or_404(product_id)
        claims = get_jwt()
        if not self._has_access(product, claims):
            raise Forbidden("You do not have access to this product")
        response_data = self._serialize_product(product)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _create_product(self, data):
        """Create a new product"""
        name = data["name"]
        description = data["description"]
        product = Product(name=name, description=description)
        db.session.add(product)
        db.session.commit()
        response_data = self._serialize_product(product)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=201, mimetype="application/json")

    def _update_product(self, product_id, data):
        """Update an existing product"""
        product = Product.query.get_or_404(product_id)
        if "name" in data:
            product.name = data["name"]
        if "description" in data:
            product.description = data["description"]
        db.session.commit()
        response_data = self._serialize_product(product)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _delete_product(self, product_id):
        """Delete an existing product"""
        product = Product.query.get_or_404(product_id)
        db.session.delete(product)
        db.session.commit()
        return jsonify({"message": "Product deleted successfully"}), 200

    def _has_access(self, product, claims):
        """Check if the current user has access to the product"""
        user_role = claims.get("rol")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        if user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=claims.get("org_id")
            ).first()
            if not reseller_package:
                return False
            return any(
                org.id == product.organization.id
                for org in reseller_package.organizations
            )
        return False

    def _serialize_product(self, product):
        """Serialize a Product object to a dictionary"""
        return {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "created_at": product.created_at.isoformat(),
            "updated_at": product.updated_at.isoformat(),
        }


class ProductContributionView(MethodView):
    """Class to manage CRUD operations for product contributions"""

    decorators = [jwt_required()]

    @check_permission(required_roles=["administrator", "reseller"])
    def get(self, product_contribution_id=None):
        """
        Retrieve a list of product contributions or a specific product contribution
        Args:
            product_contribution_id (int, optional): ID of the product contribution to retrieve
        Returns:
            JSON: List of product contributions or details of a specific product contribution
        """
        if product_contribution_id:
            return self._get_product_contribution(product_contribution_id)
        return self._get_product_contribution_list()

    @check_permission(required_roles=["administrator", "reseller"])
    def post(self):
        """
        Create a new product contribution
        Returns:
            JSON: Details of the created product contribution
        """
        data = request.get_json()
        required_fields = ["product_id"]
        if not data or not all(k in data for k in required_fields):
            raise BadRequest("Missing required fields")
        return self._create_product_contribution(data)

    @check_permission(resource_owner_check=True)
    def put(self, id: int):
        """
        Update an existing product contribution
        Args:
            product_contribution_id (int): ID of the product contribution to update
        Returns:
            JSON: Details of the updated product contribution
        """
        data = request.get_json()
        product_contribution_id = id
        if not data or not product_contribution_id:
            raise BadRequest("Missing product_contribution_id or data")
        return self._update_product_contribution(product_contribution_id, data)

    @check_permission(resource_owner_check=True)
    def delete(self, id=None):
        """
        Delete an existing product contribution
        Args:
            product_contribution_id (int): ID of the product contribution to delete
        Returns:
            JSON: Confirmation message
        """
        product_contribution_id = id
        if not product_contribution_id:
            raise BadRequest("Missing product_contribution_id")
        return self._delete_product_contribution(product_contribution_id)

    # Helper Methods
    def _get_product_contribution_list(self):
        """Retrieve a list of all product contributions"""
        claims = get_jwt()
        user_role = claims.get("rol")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            product_contributions = ProductContribution.query.all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=claims.get("org_id")
            ).first()
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            product_contributions = []
            for organization in reseller_package.organizations:
                for product in organization.products:
                    product_contributions.extend(product.product_contributions)
        else:
            raise Forbidden(
                "Only administrators and resellers can list product contributions"
            )
        response_data = [
            self._serialize_product_contribution(pc) for pc in product_contributions
        ]
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _get_product_contribution(self, product_contribution_id):
        """Retrieve details of a specific product contribution"""
        product_contribution = ProductContribution.query.get_or_404(
            product_contribution_id
        )
        claims = get_jwt()
        if not self._has_access(product_contribution, claims):
            raise Forbidden("You do not have access to this product contribution")
        response_data = self._serialize_product_contribution(product_contribution)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _create_product_contribution(self, data):
        """Create a new product contribution"""
        product_id = data["product_id"]
        product = Product.query.get(product_id)
        if not product:
            raise BadRequest("Invalid product ID")
        product_contribution = ProductContribution(product_id=product_id)
        db.session.add(product_contribution)
        db.session.commit()
        response_data = self._serialize_product_contribution(product_contribution)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=201, mimetype="application/json")

    def _update_product_contribution(self, product_contribution_id, data):
        """Update an existing product contribution"""
        product_contribution = ProductContribution.query.get_or_404(
            product_contribution_id
        )
        if "product_id" in data:
            product_id = data["product_id"]
            product = Product.query.get(product_id)
            if not product:
                raise BadRequest("Invalid product ID")
            product_contribution.product_id = product_id
        db.session.commit()
        response_data = self._serialize_product_contribution(product_contribution)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _delete_product_contribution(self, product_contribution_id):
        """Delete an existing product contribution"""
        product_contribution = ProductContribution.query.get_or_404(
            product_contribution_id
        )
        db.session.delete(product_contribution)
        db.session.commit()
        return jsonify({"message": "Product contribution deleted successfully"}), 200

    def _has_access(self, product_contribution, claims):
        """Check if the current user has access to the product contribution"""
        user_role = claims.get("rol")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        if user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=claims.get("org_id")
            ).first()
            if not reseller_package:
                return False
            return any(
                org.id == product_contribution.product.organization.id
                for org in reseller_package.organizations
            )
        return False

    def _serialize_product_contribution(self, product_contribution):
        """Serialize a ProductContribution object to a dictionary"""
        return {
            "id": product_contribution.id,
            "product_id": product_contribution.product_id,
            "product_name": product_contribution.product.name,
            "created_at": product_contribution.created_at.isoformat(),
            "updated_at": product_contribution.updated_at.isoformat(),
        }


class ProductPriceView(MethodView):
    """Class to manage CRUD operations for product prices"""

    decorators = [jwt_required()]

    @check_permission(required_roles=["administrator", "reseller"])
    def get(self, product_price_id=None):
        """
        Retrieve a list of product prices or a specific product price
        Args:
            product_price_id (int, optional): ID of the product price to retrieve
        Returns:
            JSON: List of product prices or details of a specific product price
        """
        if product_price_id:
            return self._get_product_price(product_price_id)
        return self._get_product_price_list()

    @check_permission(required_roles=["administrator", "reseller"])
    def post(self):
        """
        Create a new product price
        Returns:
            JSON: Details of the created product price
        """
        data = request.get_json()
        required_fields = ["product_id", "price", "start_date"]
        if not data or not all(k in data for k in required_fields):
            raise BadRequest("Missing required fields")
        return self._create_product_price(data)

    @check_permission(resource_owner_check=True)
    def put(self, id: int):
        """
        Update an existing product price
        Args:
            product_price_id (int): ID of the product price to update
        Returns:
            JSON: Details of the updated product price
        """
        data = request.get_json()
        product_price_id = id
        if not data or not product_price_id:
            raise BadRequest("Missing product_price_id or data")
        return self._update_product_price(product_price_id, data)

    @check_permission(resource_owner_check=True)
    def delete(self, id=None):
        """
        Delete an existing product price
        Args:
            product_price_id (int): ID of the product price to delete
        Returns:
            JSON: Confirmation message
        """
        product_price_id = id
        if not product_price_id:
            raise BadRequest("Missing product_price_id")
        return self._delete_product_price(product_price_id)

    # Helper Methods
    def _get_product_price_list(self):
        """Retrieve a list of all product prices"""
        claims = get_jwt()
        user_role = claims.get("rol")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            product_prices = ProductPrice.query.all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=claims.get("org_id")
            ).first()
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            product_prices = []
            for organization in reseller_package.organizations:
                for product in organization.products:
                    product_prices.extend(product.product_prices)
        else:
            raise Forbidden("Only administrators and resellers can list product prices")
        response_data = [self._serialize_product_price(pp) for pp in product_prices]
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _get_product_price(self, product_price_id):
        """Retrieve details of a specific product price"""
        product_price = ProductPrice.query.get_or_404(product_price_id)
        claims = get_jwt()
        if not self._has_access(product_price, claims):
            raise Forbidden("You do not have access to this product price")
        response_data = self._serialize_product_price(product_price)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _create_product_price(self, data):
        """Create a new product price"""
        product_id = data["product_id"]
        price = data["price"]
        start_date = data["start_date"]
        product_price = ProductPrice(
            product_id=product_id, price=price, start_date=start_date
        )
        db.session.add(product_price)
        db.session.commit()
        response_data = self._serialize_product_price(product_price)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=201, mimetype="application/json")

    def _update_product_price(self, product_price_id, data):
        """Update an existing product price"""
        product_price = ProductPrice.query.get_or_404(product_price_id)
        if "price" in data:
            product_price.price = data["price"]
        if "start_date" in data:
            product_price.start_date = data["start_date"]
        if "end_date" in data:
            product_price.end_date = data["end_date"]
        db.session.commit()
        response_data = self._serialize_product_price(product_price)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _delete_product_price(self, product_price_id):
        """Delete an existing product price"""
        product_price = ProductPrice.query.get_or_404(product_price_id)
        db.session.delete(product_price)
        db.session.commit()
        return jsonify({"message": "Product price deleted successfully"}), 200

    def _has_access(self, product_price, claims):
        """Check if the current user has access to the product price"""
        user_role = claims.get("rol")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        if user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=claims.get("org_id")
            ).first()
            if not reseller_package:
                return False
            return any(
                org.id == product_price.product.organization.id
                for org in reseller_package.organizations
            )
        return False

    def _serialize_product_price(self, product_price):
        """Serialize a ProductPrice object to a dictionary"""
        return {
            "id": product_price.id,
            "product_id": product_price.product_id,
            "product_name": product_price.product.name,
            "price": product_price.price,
            "start_date": product_price.start_date,
            "end_date": product_price.end_date,
            "created_at": product_price.created_at.isoformat(),
            "updated_at": product_price.updated_at.isoformat(),
        }


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
        user_role = claims.get("rol")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        if user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=claims.get("org_id")
            ).first()
            if not reseller_package:
                return False
            return any(
                org.id == recommendation.lot.farm.organization.id
                for org in reseller_package.organizations
            )
        return False

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