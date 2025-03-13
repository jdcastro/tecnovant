"""
Controller functions and class.
"""

# Python standard library imports
from functools import wraps

# Third party imports
from flask import current_app, redirect, url_for, jsonify, request
from flask.views import MethodView
from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
    get_jwt,
    verify_jwt_in_request,
)
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import SQLAlchemyError
from itsdangerous import URLSafeTimedSerializer

# Local application imports
from .models import (
    User,
    Client,
    ResellerPackage,
    RoleEnum,
    ActionEnum,
    PermissionEnum,
    ROLE_PERMISSIONS,
    PERMISSION_ACTIONS,
    verify_user_in_organization,
    check_permission,
    get_user_roles,
)
from .schemas import (
    UserSchema,
    ClientSchema,
    ResellerPackageSchema,
)
from app.helpers.validators import APIValidator
from app.extensions import db

"""1. Funciones y decoradores 
"""

"""1.1. Decoradores
"""


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return redirect(url_for("core.login"))
        return fn(*args, **kwargs)

    return wrapper


def role_required(*roles):
    """
    Decorador para verificar si un usuario tiene un rol específico
    Si el usuario es administrador, siempre tiene permiso
    :param roles: Lista de roles permitidos
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Verifica el token
            jwt_required()(fn)()
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            if user.is_admin() or user.role in roles:
                return fn(*args, **kwargs)
            return redirect(url_for("core.not_authorized"), 403)

        return wrapper

    return decorator


"""1.2. Reset password vía email
"""


def generate_reset_token(email):
    """Generates a password reset token for the given email."""
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return s.dumps(email, salt=current_app.config["SECURITY_SALT"])


def verify_reset_token(token, expiration=3600):
    """Verifies and returns the email from a password reset token."""
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        return s.loads(
            token, salt=current_app.config["SECURITY_SALT"], max_age=expiration
        )
    except Exception:
        return None


"""1.3. Validaciones
"""


def validate_login_data_email(data):
    """Validates email login data."""
    if not data:
        return False, "Datos de solicitud vacíos"
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return False, "Correo electrónico y contraseña son obligatorios"
    if not APIValidator.validate_email(email):
        return False, "Correo electrónico no válido"
    return True, None


def validate_login_data_username(data):
    """Validates username login data."""
    if not data:
        return False, "Datos de solicitud vacíos"
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return False, "Nombre de usuario y contraseña son obligatorios"
    return True, None


"""1.4. Funciones auxiliares
"""


def get_assigned_clients(user_id):
    """
    Obtiene los clientes asignados a un usuario.
    """
    user = User.query.get(user_id)
    if user.is_admin():
        return (
            Client.query.all()
        )  # Si el usuario es administrador, devuelve todos los clientes

    elif user.is_reseller() and hasattr(user, "reseller_info"):
        return (
            user.reseller_info.clients
        )  # Si el usuario es reseller, devuelve los clientes asociados a su cuenta
    else:
        if user.client:
            return [user.client]  # Se retorna solo el cliente
        else:
            return []


def create_reseller_package(user_id, max_clients=4):
    """
    Crea un paquete de reseller con un límite de clientes.
    """
    user = User.query.get(user_id)
    if not user or user.role != RoleEnum.RESELLER:
        raise ValueError("El usuario no existe o no tiene el rol de reseller.")

    # Crear el paquete de reseller
    new_package = ResellerPackage(
        user_id=user_id,
        max_clients=max_clients,  # por defecto máximo 4 clientes
        total_clients=0,
    )
    db.session.add(new_package)
    db.session.commit()
    return new_package


def assign_client_to_reseller(reseller_package_id, client_id):
    """
    Asigna un cliente a un reseller.
    """
    reseller_package = ResellerPackage.query.get(reseller_package_id)
    client = Client.query.get(client_id)

    if not reseller_package or not client:
        raise ValueError("El paquete de reseller o el cliente no existe.")

    if reseller_package.assign_client(client):
        db.session.commit()
        return True
    return False


def delete_client(client_id):
    """
    Deletes a client and its associated users, except for resellers.
    Prevents deletion of 'Primary' and 'Reseller ORG' clients.
    """
    client = Client.query.get(client_id)
    if not client:
        return False

    if client.name in ["Primary", "Reseller ORG"]:
        return False  # Prevent deletion of special clients

    # Delete associated users (excluding resellers)
    users_to_delete = (
        User.query.filter_by(client_id=client_id).filter(User.role != "reseller").all()
    )
    for user in users_to_delete:
        db.session.delete(user)

    if client.reseller_package_id:
        reseller_package = ResellerPackage.query.get(client.reseller_package_id)
        reseller_package.unassign_client(client)

    db.session.delete(client)
    db.session.commit()
    return True


def add_client(name, description=None):
    new_client = Client(name=name, description=description)
    db.session.add(new_client)
    db.session.commit()
    return new_client.id


def can_user_manage_client(user_id, client_id):
    user = User.query.get(user_id)
    if user:
        return verify_user_in_organization(user_id, client_id)
    return False


def create_primary_client():
    """
    Creates a 'Primary' client and assigns it to administrators.
    """
    primary_client = Client.query.filter_by(name="Primary").first()
    if not primary_client:
        primary_client = Client(
            name="Primary", description="Primary organization for administrators"
        )
        db.session.add(primary_client)
        db.session.commit()
    return primary_client.id


def create_reseller_org_client():
    """
    Creates a 'Reseller ORG' client and assigns it to resellers.
    """
    reseller_org_client = Client.query.filter_by(name="Reseller ORG").first()
    if not reseller_org_client:
        reseller_org_client = Client(
            name="Reseller ORG", description="Internal Organization for resellers"
        )
        db.session.add(reseller_org_client)
        db.session.commit()
    return reseller_org_client.id


def create_reseller(username, email, password):
    """
    Creates a reseller user and assigns them to the 'Reseller ORG' client.
    """
    reseller_org_client = get_or_create_client("Reseller ORG")
    reseller_user = User(
        username=username,
        email=email,
        full_name="Reseller",
        password_hash=generate_password_hash(password),
        role=RoleEnum.RESELLER,
        client_id=reseller_org_client.id,
    )
    db.session.add(reseller_user)
    db.session.commit()
    return reseller_user.id


def get_or_create_client(name):
    """
    Obtiene o crea un cliente con el nombre especificado.
    """
    client = Client.query.filter_by(name=name).first()
    if not client:
        client = Client(name=name)
        if name == "Primary":
            client.description = "Primary organization for administrators"
        elif name == "Reseller ORG":
            client.description = "Internal Organization for resellers"
        db.session.add(client)
        db.session.commit()
    return client


def create_administrator(username, email, password):
    """
    Creates an administrator user and assigns them to the 'Primary' client.
    """
    primary_client = get_or_create_client("Primary")
    admin_user = User(
        username=username,
        email=email,
        full_name="Administrator",
        password_hash=generate_password_hash(password),
        role=RoleEnum.ADMINISTRATOR,
        client_id=primary_client.id,
    )
    db.session.add(admin_user)
    db.session.commit()
    return admin_user.id


def create_user(username, email, full_name, password, role, client_id):
    """
    Creates a user with the specified role and client.
    """
    user = User(
        username=username,
        email=email,
        full_name=full_name,
        password_hash=generate_password_hash(password),
        role=role,
        client_id=client_id,
    )
    db.session.add(user)
    db.session.commit()
    return user


def initialize_system():
    create_primary_client()
    create_reseller_org_client()

    # Crear usuario administrador
    admin_user = User.query.filter_by(username="merlin").first()
    if not admin_user:
        create_administrator(
            username="merlin",
            email="webmaster@unwebparatodos.net",
            password="Strong_Pass123!",
        )


"""1. Clases 
"""


class UserView(MethodView):
    """Endpoint para gestionar usuarios. Permite realizar operaciones CRUD en la base de datos de usuarios."""

    decorators = [jwt_required()]

    def __init__(self):
        claims = get_jwt()
        self.user_id = claims.get("id", None)
        self.role = claims.get("rol", "")
        self.client_id = claims.get("client", {}).get("id", None)

    def get(self, user_id=None):
        """Obtiene información de un usuario o el listado de los usuarios asignados.

        :status 200: Operación exitosa
        :status 400: Error de validación
        :status 401: No autorizado
        :status 403: Prohibido
        :status 500: Error interno del servidor
        """

        if user_id:
            return self._get_single_user(user_id)
        return self._get_user_list()

    def _get_single_user(self, user_id):
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        if self._has_access(user):
            return jsonify(UserSchema().dump(user)), 200
        return jsonify({"error": "Forbidden"}), 403

    def _get_user_list(self):
        if self.role == RoleEnum.ADMINISTRATOR.value:
            query = User.query

        elif self.role == RoleEnum.RESELLER.value:
            reseller = User.query.get(self.user_id)
            if not reseller or not reseller.reseller_info:
                return jsonify({"error": "No reseller information found"}), 400
            client_ids = [client.id for client in reseller.reseller_info.clients]
            query = User.query.filter(User.client_id.in_(client_ids))

        elif self.role in [
            RoleEnum.ORG_ADMIN.value,
            RoleEnum.ORG_EDITOR.value,
            RoleEnum.ORG_VIEWER.value,
        ]:
            if not self.client_id:
                return jsonify({"error": "No client ID found in token"}), 400
            query = User.query.filter(User.client_id == self.client_id)
        else:
            return jsonify({"error": "Forbidden"}), 403

        users = query.all()
        return jsonify(UserSchema(many=True).dump(users)), 200

    def _has_access(self, user):
        return (
            user.id == self.user_id
            or self.role == RoleEnum.ADMINISTRATOR.value
            or (
                self.role == RoleEnum.RESELLER.value
                and verify_user_in_organization(user.id, user.client_id)
            )
        )

    def _has_delete_access(self, user):
        return (
            self.role == RoleEnum.ADMINISTRATOR.value
            or (
                self.role == RoleEnum.RESELLER.value
                and verify_user_in_organization(user.id, user.client_id)
            )
            or self.role == RoleEnum.ORG_ADMIN.value
            and verify_user_in_organization(user.id, user.client_id)
        )

    @APIValidator.validate_form(
        username=APIValidator.validate_username(),
        email=APIValidator.validate_email(),
        full_name=APIValidator.validate_textarea(max_length=128),
        password=APIValidator.validate_password_strength(),
        password_confirm=APIValidator.validate_password_strength(),
        client_name=APIValidator.validate_textarea(max_length=128),
        role=APIValidator.validate_radio([role.value for role in RoleEnum]),
    )
    def post(self):
        """Maneja los POST requests para crear un nuevo usuario.
        :param str username: Nombre de usuario
        :param str email: Correo electrónico
        :param str full_name: opcional. Nombre completo
        :param str password: Contraseña
        :param str password_confirm: Confirmación de contraseña
        :param str organization: Nombre de la organización
        :param str role: Rol del usuario
        :status 201: Operación exitosa
        :status 400: Error de validación
        :status 401: No autorizado
        :status 403: Prohibido
        :status 500: Error interno del servidor
        """

        data = request.get_json()
        client_name = data.get("client_name")
        role = data.get("role")
        client_id = Client.get_id_by_name(client_name)

        if data.get("password") != data.get("password_confirm"):
            return jsonify({"error": "Passwords do not match"}), 400

        """se cambia el id del cliente dependiendo del rol del usuario a crear"""
        if role == RoleEnum.ADMINISTRATOR.value:
            client_id = Client.get_id_by_name("Primary")
        elif role == RoleEnum.RESELLER.value:
            client_id = Client.get_id_by_name("Reseller ORG")
        if not client_id:
            return jsonify({"error": "Client not found"}), 404

        if not self._can_create_user(role, client_id):
            """se determina si el usuario puede crear usuarios con el rol indicado en el cliente"""
            return jsonify({"error": "Forbidden"}), 403

        username = data.get("username")
        email = data.get("email")
        full_name = data.get("full_name")
        password = data.get("password")

        new_user = create_user(username, email, full_name, password, role, client_id)

        if new_user:
            return jsonify({"message": f"User {new_user} created successfully"}), 201
        else:
            return jsonify({"error": "Failed to create user"}), 500

    def _can_create_user(self, role, client_id):
        permissions = {
            RoleEnum.ADMINISTRATOR: True,
            RoleEnum.RESELLER: role
            in [RoleEnum.ORG_ADMIN, RoleEnum.ORG_EDITOR, RoleEnum.ORG_VIEWER],
            RoleEnum.ORG_ADMIN: role in [RoleEnum.ORG_EDITOR, RoleEnum.ORG_VIEWER],
        }

        user = User.query.get(self.user_id)
        if user.is_admin():
            return True
        if user.is_reseller() and permissions[RoleEnum.RESELLER]:
            return verify_user_in_organization(self.user_id, client_id)
        if user.is_org_manager() and permissions[RoleEnum.ORG_ADMIN]:
            return verify_user_in_organization(self.user_id, client_id)
        return False

    def create_user(self, username, email, full_name, password, role, client_id):

        user = User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=generate_password_hash(password),
            role=role,
            client_id=client_id,
        )
        db.session.add(user)
        try:
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

        return jsonify(UserSchema().dump(user)), 201

    def put(self, user_id):
        aut_user_id = get_jwt_identity()
        json_data = request.json
        if not check_permission(
            aut_user_id,
            PermissionEnum.ORG_MANAGEMENT.value,
            ActionEnum.UPDATE.value,
            json_data.get("client_id"),
        ):
            return jsonify({"error": "Forbidden"}), 403

        target_user = User.query.get(user_id)
        if not target_user:
            return jsonify({"error": "User not found"}), 404

        for key, value in json_data.items():
            if key == "password":
                target_user.set_password(value)
            else:
                setattr(target_user, key, value)

        try:
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

        return jsonify(UserSchema().dump(target_user)), 200

    def delete(self, user_id):
        aut_user_id = self.user_id
        target_user = User.query.get(user_id)
        if not target_user:
            return jsonify({"error": "User not found"}), 404
        if not self._has_delete_access(target_user):
            return jsonify({"error": "Forbidden"}), 403

        if target_user.id == aut_user_id:
            return jsonify({"error": "Cannot delete yourself"}), 400

        try:
            db.session.delete(target_user)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

        return (
            jsonify({"message": f"User {target_user.username} deleted successfully"}),
            200,
        )

    def _process_client(self, client_name):
        if self.role == RoleEnum.ADMINISTRATOR.value:
            return self._get_or_create_admin_client(client_name)
        if self.role == RoleEnum.RESELLER.value:
            return self._validate_reseller_client(client_name)

        return jsonify({"error": "Forbidden"}), 403

    def _get_or_create_admin_client(self, client_name):
        client = Client.query.filter_by(name=client_name).first()
        if not client:
            client = Client(name=client_name)
            db.session.add(client)
            db.session.commit()
        return client.id

    def _validate_reseller_client(self, client_name):
        reseller = User.query.get(self.user_id)
        valid_clients = reseller.reseller_info.clients if reseller.reseller_info else []
        client = next((c for c in valid_clients if c.name == client_name), None)
        if not client:
            return jsonify({"error": "Cliente inválido para este reseller"}), 403
        return client.id


class ClientView(MethodView):
    decorators = [jwt_required()]

    def __init__(self):
        claims = get_jwt()
        self.user_id = claims.get("id", None)
        self.role = claims.get("rol", "")
        self.client_id = claims.get("client", {}).get("id", None)

    def get(self, client_id=None, client_name=None):
        if self.role == "administrator":
            if client_id:
                client = Client.query.get(client_id)
                if client:
                    return jsonify(ClientSchema().dump(client)), 200
                else:
                    return jsonify({"message": "Cliente no encontrado"}), 404
            elif client_name:
                client = Client.query.filter_by(name=client_name).first()
                if client:
                    return jsonify(ClientSchema().dump(client)), 200
                else:
                    return jsonify({"message": "Cliente no encontrado"}), 404
            else:
                clients = Client.query.all()
                return jsonify([ClientSchema().dump(client) for client in clients]), 200
        elif self.role == "reseller":
            if client_id:
                client = Client.query.get(client_id)
                if client and client.reseller_package_id == self.client_id:
                    return jsonify(ClientSchema().dump(client)), 200
                else:
                    return (
                        jsonify(
                            {
                                "message": "Cliente no encontrado o no pertenece al reseller"
                            }
                        ),
                        404,
                    )
            elif client_name:
                client = Client.query.filter_by(name=client_name).first()
                if client and client.reseller_package_id == self.client_id:
                    return jsonify(ClientSchema().dump(client)), 200
                else:
                    return (
                        jsonify(
                            {
                                "message": "Cliente no encontrado o no pertenece al reseller"
                            }
                        ),
                        404,
                    )
            else:
                clients = Client.query.filter_by(
                    reseller_package_id=self.client_id
                ).all()
                return jsonify([ClientSchema().dump(client) for client in clients]), 200
        else:
            return jsonify({"message": "No tiene permiso para obtener clientes"}), 403

    def post(self):
        if self.role == "administrator":
            json_data = request.json
            new_client = Client(**json_data)
            db.session.add(new_client)
            db.session.commit()
            return jsonify(ClientSchema().dump(new_client)), 201
        elif self.role == "reseller":
            json_data = request.json
            reseller_package = ResellerPackage.query.get(self.client_id)
            if (
                reseller_package
                and reseller_package.total_clients < reseller_package.max_clients
            ):
                new_client = Client(**json_data)
                new_client.reseller_package_id = self.client_id
                db.session.add(new_client)
                reseller_package.total_clients += 1
                db.session.commit()
                return jsonify(ClientSchema().dump(new_client)), 201
            else:
                return jsonify({"message": "No puede crear más clientes"}), 403
        else:
            return jsonify({"message": "No tiene permiso para crear clientes"}), 403

    def put(self, client_id=None, client_name=None):
        if self.role == "administrator":
            if client_id:
                client = Client.query.get(client_id)
                if client:
                    json_data = request.json
                    client.name = json_data.get("name", client.name)
                    client.description = json_data.get(
                        "description", client.description
                    )
                    db.session.commit()
                    return jsonify(ClientSchema().dump(client)), 200
                else:
                    return jsonify({"message": "Cliente no encontrado"}), 404
            elif client_name:
                client = Client.query.filter_by(name=client_name).first()
                if client:
                    json_data = request.json
                    client.name = json_data.get("name", client.name)
                    client.description = json_data.get(
                        "description", client.description
                    )
                    db.session.commit()
                    return jsonify(ClientSchema().dump(client)), 200
                else:
                    return jsonify({"message": "Cliente no encontrado"}), 404
            else:
                return (
                    jsonify(
                        {"message": "Debe proporcionar el ID o nombre del cliente"}
                    ),
                    400,
                )
        elif self.role == "reseller":
            if client_id:
                client = Client.query.get(client_id)
                if client and client.reseller_package_id == self.client_id:
                    json_data = request.json
                    client.name = json_data.get("name", client.name)
                    client.description = json_data.get(
                        "description", client.description
                    )
                    db.session.commit()
                    return jsonify(ClientSchema().dump(client)), 200
                else:
                    return (
                        jsonify(
                            {
                                "message": "Cliente no encontrado o no pertenece al reseller"
                            }
                        ),
                        404,
                    )
            elif client_name:
                client = Client.query.filter_by(name=client_name).first()
                if client and client.reseller_package_id == self.client_id:
                    json_data = request.json
                    client.name = json_data.get("name", client.name)
                    client.description = json_data.get(
                        "description", client.description
                    )
                    db.session.commit()
                    return jsonify(ClientSchema().dump(client)), 200
                else:
                    return (
                        jsonify(
                            {
                                "message": "Cliente no encontrado o no pertenece al reseller"
                            }
                        ),
                        404,
                    )
            else:
                return (
                    jsonify(
                        {"message": "Debe proporcionar el ID o nombre del cliente"}
                    ),
                    400,
                )
        else:
            return jsonify({"message": "No tiene permiso para editar clientes"}), 403

    def delete(self, client_id=None, client_name=None):
        if self.role == "administrator":
            if client_id:
                client = Client.query.get(client_id)
                if client:
                    db.session.delete(client)
                    db.session.commit()
                    return jsonify({"message": "Cliente eliminado"}), 200
                else:
                    return jsonify({"message": "Cliente no encontrado"}), 404
            elif client_name:
                client = Client.query.filter_by(name=client_name).first()
                if client:
                    db.session.delete(client)
                    db.session.commit()
                    return jsonify({"message": "Cliente eliminado"}), 200
                else:
                    return jsonify({"message": "Cliente no encontrado"}), 404
            else:
                return (
                    jsonify(
                        {"message": "Debe proporcionar el ID o nombre del cliente"}
                    ),
                    400,
                )
        elif self.role == "reseller":
            if client_id:
                client = Client.query.get(client_id)
                if client and client.reseller_package_id == self.client_id:
                    db.session.delete(client)
                    reseller_package = ResellerPackage.query.get(self.client_id)
                    reseller_package.total_clients -= 1
                    db.session.commit()
                    return jsonify({"message": "Cliente eliminado"}), 200
                else:
                    return (
                        jsonify(
                            {
                                "message": "Cliente no encontrado o no pertenece al reseller"
                            }
                        ),
                        404,
                    )
            elif client_name:
                client = Client.query.filter_by(name=client_name).first()
                if client and client.reseller_package_id == self.client_id:
                    db.session.delete(client)
                    reseller_package = ResellerPackage.query.get(self.client_id)
                    reseller_package.total_clients -= 1
                    db.session.commit()
                    return jsonify({"message": "Cliente eliminado"}), 200
                else:
                    return (
                        jsonify(
                            {
                                "message": "Cliente no encontrado o no pertenece al reseller"
                            }
                        ),
                        404,
                    )
            else:
                return (
                    jsonify(
                        {"message": "Debe proporcionar el ID o nombre del cliente"}
                    ),
                    400,
                )
        else:
            return jsonify({"message": "No tiene permiso para eliminar clientes"}), 403


class ResellerView(MethodView):
    @APIValidator.validate_form(
        user_id=APIValidator.validate_number(min_value=1),
        max_clients=APIValidator.validate_number(min_value=1),
    )
    def post(self):
        json_data = request.json
        new_reseller_package = ResellerPackage(**json_data)
        db.session.add(new_reseller_package)
        db.session.commit()
        return jsonify(ResellerPackageSchema().dump(new_reseller_package)), 201

    def assign_client(self, reseller_id, client_id):
        reseller = User.query.get(reseller_id)
        client = Client.query.get(client_id)
        if reseller and client and reseller.is_reseller():
            if client.assign_to_reseller(reseller):
                db.session.commit()
                return jsonify({"message": "Client assigned successfully"}), 200
            return jsonify({"error": "Reseller has no available slots"}), 400
        return jsonify({"error": "Invalid reseller or client"}), 404

    def unassign_client(self, reseller_id, client_id):
        reseller = User.query.get(reseller_id)
        client = Client.query.get(client_id)
        if reseller and client and reseller.is_reseller():
            if client.unassign_from_reseller():
                db.session.commit()
                return jsonify({"message": "Client unassigned successfully"}), 200
            return jsonify({"error": "Client not assigned to this reseller"}), 400
        return jsonify({"error": "Invalid reseller or client"}), 404


# # Registro de rutas
# app.add_url_rule('/users/', view_func=UserView.as_view('users'))
# app.add_url_rule('/clients/', view_func=ClientView.as_view('clients'))
# app.add_url_rule('/resellers/', view_func=ResellerView.as_view('resellers'))
# app.add_url_rule('/resellers/<int:reseller_id>/assign_client/<int:client_id>', view_func=ResellerView.as_view('assign_client'))
# app.add_url_rule('/resellers/<int:reseller_id>/unassign_client/<int:client_id>', view_func=ResellerView.as_view('unassign_client'))
