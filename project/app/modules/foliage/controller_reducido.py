from flask import request
from flask_jwt_extended import get_jwt
from flask.views import MethodView
from werkzeug.exceptions import BadRequest

from app.extensions import db
from app.core.models import ResellerPackage, RoleEnum
from .models import Farm, Lot, Crop, Nutrient
from .crud_pattern import BaseService, CRUDMixin
from .schemas import FarmSchema, LotSchema, CropSchema, NutrientSchema

class FarmService(BaseService):
    def __init__(self):
        super().__init__(Farm)

    def create(self, data):
        """Crea una granja verificando duplicados en nombre."""
        if self.model.query.filter_by(name=data["name"], org_id=data["org_id"]).first():
            raise BadRequest("Name already exists.")
        return super().create(data)

    def update(self, resource_id, data):
        """Actualiza una granja verificando duplicados en nombre si cambia."""
        farm = self.get_by_id(resource_id)
        if "name" in data and data["name"] != farm.name:
            if self.model.query.filter_by(name=data["name"], org_id=farm.org_id).first():
                raise BadRequest("Name already exists.")
        return super().update(resource_id, data)

    def delete(self, resource_id):
        """Elimina o desactiva una granja según el modelo."""
        farm = self.get_by_id(resource_id)
        if hasattr(farm, "active"):
            farm.active = False
            db.session.commit()
        else:
            super().delete(resource_id)

    def delete_multiple(self, resource_ids):
        """Elimina o desactiva múltiples granjas."""
        deleted_ids = []
        for resource_id in resource_ids:
            farm = self.model.query.get(resource_id)
            if farm:
                if hasattr(farm, "active"):
                    farm.active = False
                else:
                    db.session.delete(farm)
                deleted_ids.append(resource_id)
        db.session.commit()
        return deleted_ids

    def _prepare_create_data(self, data):
        """Prepara datos mínimos para crear una granja."""
        return {"name": data["name"], "org_id": data["org_id"]}

class FarmView(CRUDMixin, MethodView):
    def __init__(self):
        super().__init__(
            model=Farm,
            schema=FarmSchema(),
            service=FarmService(),
            required_roles=["administrator", "reseller"]
        )

    def delete(self, resource_id=None):
        """Maneja eliminación de granja individual o múltiples IDs."""
        data = request.get_json()
        if data and "ids" in data:
            deleted_ids = self.service.delete_multiple(data["ids"])
            if not deleted_ids:
                return {"error": "No farms were deleted"}, 403
            return {"message": f"Farms {', '.join(map(str, deleted_ids))} deleted"}, 200
        if resource_id:
            self.service.delete(resource_id)
            return {"message": "Farm deleted successfully"}, 200
        raise BadRequest("Missing farm_id or ids.")

class LotService(BaseService):
    def __init__(self):
        super().__init__(Lot)

    def create(self, data):
        existing = self.model.query.filter_by(name=data["name"])
        if hasattr(self.model, "active"):
            existing = existing.filter_by(active=True)
        if existing.first():
            raise BadRequest("Name already exists.")
        return super().create(data)

    def update(self, resource_id, data):
        lot = self.get_by_id(resource_id)
        if "name" in data and data["name"] != lot.name:
            existing = self.model.query.filter_by(name=data["name"])
            if hasattr(self.model, "active"):
                existing = existing.filter_by(active=True)
            if existing.first():
                raise BadRequest("Name already exists.")
        return super().update(resource_id, data)

    def delete(self, resource_id):
        lot = self.get_by_id(resource_id)
        if hasattr(lot, "active"):
            lot.active = False
            db.session.commit()
        else:
            super().delete(resource_id)
        return lot

    def get_by_reseller(self, reseller_id):
        reseller_package = ResellerPackage.query.filter_by(reseller_id=reseller_id).first()
        if not reseller_package:
            raise BadRequest("Reseller package not found.")
        org_ids = [org.id for org in reseller_package.organizations]
        return (self.model.query
                .join(Farm)
                .filter(Farm.org_id.in_(org_ids))
                .all())

    def get_by_reseller_paginated(self, reseller_id, page, per_page):
        reseller_package = ResellerPackage.query.filter_by(reseller_id=reseller_id).first()
        if not reseller_package:
            raise BadRequest("Reseller package not found.")
        org_ids = [org.id for org in reseller_package.organizations]
        query = (self.model.query
                .join(Farm)
                .filter(Farm.org_id.in_(org_ids)))
        return query.paginate(page=page, per_page=per_page, error_out=False)

class LotView(CRUDMixin, MethodView):
    def __init__(self):
        super().__init__(
            model=Lot,
            schema=LotSchema(),
            service=LotService(),
            required_roles=["administrator", "reseller"]
        )

    def _has_access(self, resource, claims):
        user_role = claims.get("rol")
        user_id = claims.get("id")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        if user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(reseller_id=user_id).first()
            if not reseller_package:
                return False
            farm_org_id = resource.farm.org_id
            return any(org.id == farm_org_id for org in reseller_package.organizations)
        return user_id == resource.farm.user_id
    

class CropService(BaseService):
    def __init__(self):
        super().__init__(model=Crop)

    def create(self, data):
        existing = self.model.query.filter_by(name=data['name']).first()
        if hasattr(self.model, 'active'):
            existing = self.model.query.filter_by(name=data['name'], active=True).first()
        if existing:
            raise BadRequest("Name already exists.")
        return super().create(data)

    def update(self, resource_id, data):
        crop = self.get_by_id(resource_id)
        if 'name' in data and data['name'] != crop.name:
            existing = self.model.query.filter_by(name=data['name'])
            if hasattr(self.model, 'active'):
                existing = existing.filter_by(active=True)
            existing = existing.first()
            if existing:
                raise BadRequest("Name already exists.")
        return super().update(resource_id, data)

    def delete(self, resource_id):
        crop = self.get_by_id(resource_id)
        if hasattr(crop, 'active'):
            crop.active = False
        else:
            db.session.delete(crop)
        db.session.commit()

    def delete_multiple(self, resource_ids):
        deleted = []
        for res_id in resource_ids:
            crop = self.model.query.get(res_id)
            if crop:
                if hasattr(crop, 'active'):
                    crop.active = False
                else:
                    db.session.delete(crop)
                deleted.append(res_id)
        db.session.commit()
        return deleted

class CropView(CRUDMixin, MethodView):
    def __init__(self):
        super().__init__(
            model=Crop,
            schema=CropSchema(),
            service=CropService(),
            required_roles=["administrator", "reseller"]
        )
        
class NutrientService(BaseService):
    def __init__(self):
        super().__init__(Nutrient)

    def create(self, data):
        org_id = data.get("org_id")
        query = self.model.query.filter_by(name=data["name"], org_id=org_id)
        if hasattr(self.model, "active"):
            query = query.filter_by(active=True)
        if query.first():
            raise BadRequest("Name already exists.")
        return super().create(data)

    def update(self, resource_id, data):
        nutrient = self.get_by_id(resource_id)
        if "name" in data and data["name"] != nutrient.name:
            query = self.model.query.filter_by(name=data["name"], org_id=nutrient.org_id)
            if hasattr(nutrient, "active"):
                query = query.filter_by(active=True)
            if query.first():
                raise BadRequest("Name already exists.")
        return super().update(resource_id, data)

    def delete(self, resource_id):
        nutrient = self.get_by_id(resource_id)
        if hasattr(nutrient, "active"):
            nutrient.active = False
        else:
            db.session.delete(nutrient)
        db.session.commit()

    def delete_multiple(self, resource_ids):
        deleted_ids = []
        for resource_id in resource_ids:
            nutrient = self.model.query.get(resource_id)
            if nutrient:
                if hasattr(nutrient, "active"):
                    nutrient.active = False
                else:
                    db.session.delete(nutrient)
                deleted_ids.append(resource_id)
        db.session.commit()
        return deleted_ids

    def _prepare_create_data(self, data):
        claims = get_jwt()
        data["org_id"] = claims.get("org_id")
        return data

class NutrientView(CRUDMixin, MethodView):
    def __init__(self):
        super().__init__(
            model=Nutrient,
            schema=NutrientSchema(),
            service=NutrientService(),
            required_roles=["administrator", "reseller"]
        )