from flask import request, Response
from flask_jwt_extended import jwt_required, get_jwt
from werkzeug.exceptions import BadRequest, Forbidden, NotFound
import json

from app.core.models import RoleEnum, ResellerPackage  
from app.extensions import db

class CRUDMixin:
    """Mixin genérico para operaciones CRUD con soporte para personalización."""
    decorators = [jwt_required()]

    def __init__(self, model, schema, service, required_roles=None):
        """
        Initialize CRUD operations with model, schema, service, and access control.

        :param model: SQLAlchemy model class for database operations.
        :param schema: Marshmallow schema for serialization/deserialization.
        :param service: Business logic service for model operations.
        :param required_roles: List of roles allowed to access resources (default: ['administrator']).
        """
        self.model = model
        self.schema = schema
        self.service = service
        self.required_roles = required_roles or ["administrator"]  # Roles por defecto

    def get(self, resource_id=None):
        """Retrieve single resource or list of resources."""
        if resource_id:
            return self._get_resource(resource_id)
        return self._get_resource_list()

    def post(self):
        """Create a new resource with validated input data."""
        data = request.get_json()
        if not data or not self._validate_required_fields(data):
            raise BadRequest("Missing required fields.")
        return self._create_resource(data)

    def put(self, resource_id):
        """Update an existing resource by ID."""
        data = request.get_json()
        if not data or not resource_id:
            raise BadRequest("Missing resource_id or data.")
        return self._update_resource(resource_id, data)

    def delete(self, resource_id=None):
        """Delete a single or multiple resources by ID(s)."""
        data = request.get_json()
        if data and "ids" in data:
            return self._delete_resources(data["ids"])
        if resource_id:
            return self._delete_resource(resource_id)
        raise BadRequest("Missing resource_id.")

    # Métodos base (pueden ser sobrescritos)
    def _get_resource_list(self):
        """Retrieve all resources filtered by user role with optional pagination."""
        claims = get_jwt()
        user_role = claims.get("rol")
        user_id = claims.get("id")

        # Obtener parámetros de paginación (opcionales)
        page = request.args.get('page', type=int)
        per_page = request.args.get('per_page', type=int)

        # Verificar si se solicitó paginación
        pagination_requested = page is not None or per_page is not None

        if pagination_requested:
            # Establecer valores por defecto si alguno falta
            page = page if page is not None else 1
            per_page = per_page if per_page is not None else 10

            # Validar parámetros de paginación
            if page < 1:
                raise BadRequest("Page number must be 1 or greater")
            if per_page < 1 or per_page > 100:
                raise BadRequest("Per_page must be between 1 and 100")

            # Obtener recursos paginados según el rol
            if user_role == RoleEnum.ADMINISTRATOR.value:
                pagination = self.service.get_all_paginated(page, per_page)
            elif user_role == RoleEnum.RESELLER.value:
                pagination = self.service.get_by_reseller_paginated(user_id, page, per_page)
            else:
                raise Forbidden(f"Only {', '.join(self.required_roles)} can list resources.")

            # Preparar respuesta paginada
            response_data = {
                "items": [self._serialize_resource(resource) for resource in pagination.items],
                "total": pagination.total,
                "pages": pagination.pages,
                "page": pagination.page,
                "per_page": pagination.per_page
            }
        else:
            # Comportamiento sin paginación
            if user_role == RoleEnum.ADMINISTRATOR.value:
                resources = self.service.get_all()
            elif user_role == RoleEnum.RESELLER.value:
                resources = self.service.get_by_reseller(user_id)
            else:
                raise Forbidden(f"Only {', '.join(self.required_roles)} can list resources.")
            
            response_data = [self._serialize_resource(resource) for resource in resources]

        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _get_resource(self, resource_id):
        """Retrieve a specific resource by ID with access control."""
        resource = self.service.get_by_id(resource_id)
        if not resource:
            raise NotFound(f"Resource {resource_id} not found.")
        claims = get_jwt()
        if not self._has_access(resource, claims):
            raise Forbidden("You do not have access to this resource.")
        response_data = self._serialize_resource(resource)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _create_resource(self, data):
        """Create and return new resource instance."""
        resource = self.service.create(data)
        response_data = self._serialize_resource(resource)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=201, mimetype="application/json")

    def _update_resource(self, resource_id, data):
        """Update existing resource with provided data."""
        resource = self.service.update(resource_id, data)
        response_data = self._serialize_resource(resource)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _delete_resource(self, resource_id):
        """Delete single resource by ID."""
        self.service.delete(resource_id)
        return {"message": "Resource deleted successfully"}, 200

    def _delete_resources(self, resource_ids):
        """Delete multiple resources by ID list."""
        deleted_resources = self.service.delete_multiple(resource_ids)
        if not deleted_resources:
            return {"error": "No resources were deleted due to permission restrictions"}, 403
        deleted_resources_str = ", ".join(map(str, deleted_resources))
        return {"message": f"Resources {deleted_resources_str} deleted successfully"}, 200

    # Métodos de personalización (hooks)
    def _validate_required_fields(self, data):
        """Validate presence of required fields in incoming data (override for custom checks)."""
        return True  # Default no validation - must be implemented by subclasses

    def _serialize_resource(self, resource):
        """Serialize resource using configured schema."""
        return self.schema.dump(resource)
    
    def _has_access(self, resource, claims):
        """Check user authorization to access specific resource."""
        user_role = claims.get("rol")
        
        # Caso del rol ADMINISTRATOR: acceso total
        if user_role == RoleEnum.ADMINISTRATOR.value:
            return True
        
        # Caso del rol RESELLER: acceso a recursos de organizaciones en su paquete
        if user_role == RoleEnum.RESELLER.value:
            from models import ResellerPackage
            reseller_package = ResellerPackage.query.filter_by(reseller_id=claims.get("org_id")).first()
            if not reseller_package:
                return False
            return any(org.id == getattr(resource, "org_id", None) for org in reseller_package.organizations)
        
        # Caso del rol ORG_ADMIN: acceso si el org_id del recurso coincide con una de sus organizaciones
        if user_role == RoleEnum.ORG_ADMIN.value or user_role == RoleEnum.ORG_EDITOR.value or user_role == RoleEnum.ORG_VIEWER.value:
            from models import User
            user_id = claims.get("user_id")  # Asumimos que claims incluye el ID del usuario
            if not user_id:
                return False
            user = User.query.get(user_id)
            if not user:
                return False
            resource_org_id = getattr(resource, "org_id", None)
            if resource_org_id is None:
                return False
            return any(org.id == resource_org_id for org in user.organizations)
        
        return False

class BaseService:
    """Base service class for business logic operations (CRUD operations)."""

    def __init__(self, model):
        """
        Initialize service with associated SQLAlchemy model.
        :param model: SQLAlchemy model class for database operations.
        """
        self.model = model
    
    def get_all(self):
        """Retrieve all resources."""
        return self.model.query.all()
    
    def get_all_paginated(self, page, per_page):
        """Retrieve all resources with pagination."""
        return self.model.query.paginate(page=page, per_page=per_page, error_out=False)

    def get_by_id(self, resource_id):
        """Retrieve single resource by primary key."""
        return self.model.query.get_or_404(resource_id)
    
    def get_by_filter(self, filter_data):
        """Retrive a list of resource by a filter."""
        return self.model.query.filter_by(**filter_data).all()
        
    def get_by_reseller(self, reseller_id):
        """Retrieve resources linked to reseller account."""
        reseller_package = ResellerPackage.query.filter_by(reseller_id=reseller_id).first()
        if not reseller_package:
            raise NotFound("Reseller package not found.")
        resources = []
        for organization in reseller_package.organizations:
            resources.extend(self.model.query.filter_by(org_id=organization.id).all())
        return resources
    
    def get_by_reseller_paginated(self, reseller_id, page, per_page):
        """Retrieve paginated resources linked to reseller account."""
        reseller_package = ResellerPackage.query.filter_by(reseller_id=reseller_id).first()
        if not reseller_package:
            raise NotFound("Reseller package not found.")
        
        query = self.model.query.filter(
            self.model.org_id.in_([org.id for org in reseller_package.organizations])
        )
        return query.paginate(page=page, per_page=per_page, error_out=False)
    
    def create(self, data):
        """Create new resource instance."""
        resource = self.model(**self._prepare_create_data(data))
        db.session.add(resource)
        db.session.commit()
        return resource

    def update(self, resource_id, data):
        """Update existing resource with provided data."""
        resource = self.get_by_id(resource_id)
        self._update_resource(resource, data)
        db.session.commit()
        return resource

    def delete(self, resource_id):
        """Delete single resource."""
        resource = self.get_by_id(resource_id)
        db.session.delete(resource)
        db.session.commit()

    def delete_multiple(self, resource_ids):
        """Batch delete resources by ID list."""
        deleted_ids = []
        for resource_id in resource_ids:
            resource = self.model.query.get(resource_id)
            if resource:
                db.session.delete(resource)
                deleted_ids.append(resource_id)
        db.session.commit()
        return deleted_ids

    # Métodos de personalización (hooks)
    def _prepare_create_data(self, data):
        """Prepare data before resource creation (override for validation)."""
        return data

    def _update_resource(self, resource, data):
        """Update resource attributes (override to restrict/edit fields)."""           
        allowed_fields = self.model._sa_class_manager.mapper.column_attrs.keys()  # Get table columns
        for key, value in data.items():
            if key in allowed_fields:
                setattr(resource, key, value)