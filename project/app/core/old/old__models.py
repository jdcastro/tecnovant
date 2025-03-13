"""
User model roles, permissions and actions
module for Yet Another Flask Survival Kit (YAFSK)
Author: Johnny De Castro
Email: j@jdcastro.co
Copyright (c) 2024 - 2025 Johnny De Castro.
All rights reserved.

Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

# Python standard library imports
from datetime import datetime
from enum import Enum
from functools import lru_cache
from threading import Timer
import time
import weakref

# Third party imports
from werkzeug.security import check_password_hash, generate_password_hash

# Local application imports
from app.extensions import db

__doc__ = """
Documentación del modelo: 

Este modelo SQLAlchemy implementa un sistema de control de acceso basado en roles y permisos, diseñado para gestionar usuarios, sus roles, permisos y acciones asociadas dentro de un esquema de reseller. Incluye también modelos para clientes (organizaciones), límites para reseller y módulos del sistema.

Gestión de permisos:
El modelo de roles, acciones y permisos es manejado de manera estática con enumeraciones
La definición de roles, acciones y permisos se hace mediante enums para que la estructura sea muy clara y fácil de mantener.
Los cambios en los permisos o roles se pueden gestionar de manera centralizada en los enums y diccionarios asociados.

"""


# 1. Enumeraciones (Enums):


class RoleEnum(Enum):
    """RoleEnum: Define los roles predefinidos en el sistema
    (administrador, reseller, administrador de organización, editor de organización, visor de organización).
    """

    ADMINISTRATOR = ("administrator", "Administrador")
    RESELLER = ("reseller", "Revendedor")
    ORG_ADMIN = ("org_admin", "Administrador de Organización")
    ORG_EDITOR = ("org_editor", "Editor de Organización")
    ORG_VIEWER = ("org_viewer", "Visor de Organización")

    def __init__(self, id, description):
        self.id = id
        self.description = description

    @property
    def value(self):
        """
        Devuelve el valor del rol.
        """
        return self.id


class ActionEnum(Enum):
    """ActionEnum: Define las acciones posibles
    (crear, leer, actualizar, eliminar, administrar)."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    MANAGE = "manage"


class PermissionEnum(Enum):
    """PermissionEnum: Define los permisos disponibles
    (gestión completa, gestión de organización, gestión de contenido, informes, ajustes del sistema, informes limitados).
    """

    FULL_MANAGEMENT = "full_management"
    ORG_MANAGEMENT = "org_management"
    CONTENT_MANAGEMENT = "content_management"
    REPORTING = "reporting"
    SYSTEM_SETTINGS = "system_settings"
    LIMITED_REPORTS = "limited_reports"


# Definir permisos por rol
ROLE_PERMISSIONS = {
    RoleEnum.ADMINISTRATOR: [PermissionEnum.FULL_MANAGEMENT],
    RoleEnum.RESELLER: [PermissionEnum.ORG_MANAGEMENT],
    RoleEnum.ORG_ADMIN: [PermissionEnum.CONTENT_MANAGEMENT, PermissionEnum.REPORTING],
    RoleEnum.ORG_EDITOR: [PermissionEnum.REPORTING],
    RoleEnum.ORG_VIEWER: [PermissionEnum.REPORTING],
}
# Definir acciones permitidas por permiso
PERMISSION_ACTIONS = {
    PermissionEnum.FULL_MANAGEMENT: [action for action in ActionEnum],
    PermissionEnum.ORG_MANAGEMENT: [
        ActionEnum.CREATE,
        ActionEnum.READ,
        ActionEnum.UPDATE,
        ActionEnum.DELETE,
    ],
    PermissionEnum.CONTENT_MANAGEMENT: [
        ActionEnum.CREATE,
        ActionEnum.READ,
        ActionEnum.UPDATE,
    ],
    PermissionEnum.REPORTING: [ActionEnum.READ],
}

"""2. Tablas de asociación 
Estas tablas se utilizan para implementar relaciones de muchos a muchos entre las entidades principales:
"""
# Tablas de asociación
client_user = db.Table(
    "client_user",
    db.Column(
        "client_id",
        db.Integer,
        db.ForeignKey("clients.id", ondelete="CASCADE"),
        index=True,
    ),
    db.Column(
        "user_id",
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    ),
    db.Index(
        "ix_client_user_client",
        "client_id",
    ),
    db.Index(
        "ix_client_user_user",
        "user_id",
    ),
    # Tabla de asociación entre clientes y usuarios (Many-to-Many).
)

"""3. Modelo de datos
Estas clases representan los modelos de datos del sistema
"""


class User(db.Model):
    """
    Modelo que representa a los usuarios del sistema.
    Gestiona la información personal, credenciales de acceso, roles,
    y la pertenencia a organizaciones (clientes).
    """

    __tablename__ = "users"

    id = db.Column(
        db.Integer, primary_key=True, doc="Clave primaria única del usuario."
    )
    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False,
        index=True,
        doc="Nombre de usuario (String, único, no nulo, indexado). Utilizado para el login.",
    )
    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False,
        index=True,
        doc="Correo electrónico (String, único, no nulo, indexado). Utilizado para la recuperación de contraseña y notificaciones.",
    )
    full_name = db.Column(
        db.String(128),
        nullable=False,
        doc="Nombre completo del usuario (String, no nulo).",
    )
    password_hash = db.Column(
        db.String(255),
        doc="Hash de la contraseña (String). Almacena la contraseña de forma segura.",
    )
    profile_data = db.Column(
        db.JSON,
        nullable=False,
        default=dict,
        doc="Datos adicionales del perfil (JSON, valor por defecto: diccionario vacío). Permite almacenar información extra específica del usuario.",
    )
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        doc="Fecha de creación del usuario (DateTime).",
    )
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        doc="Fecha de última actualización del usuario (DateTime). Se actualiza automáticamente.",
    )
    active = db.Column(
        db.Boolean,
        default=True,
        doc="Estado de la cuenta (Boolean, valor por defecto: True). Indica si la cuenta está activa o inactiva.",
    )
    role = db.Column(
        db.Enum(RoleEnum),
        nullable=False,
        default=RoleEnum.ORG_VIEWER,
        doc="Rol del usuario (Enum, no nulo, valor por defecto: ORG_VIEWER). Define el rol del usuario en el sistema.",
    )
    client_id = db.Column(
        db.Integer,
        db.ForeignKey("clients.id"),
        doc="Clave foránea a la tabla clients (Client.id). Indica el cliente al que pertenece el usuario.",
    )
    client = db.relationship(
        "Client",
        foreign_keys=[client_id],
        backref=db.backref("assigned_users", lazy="dynamic"),
        doc="Relación One-to-Many con la tabla Client. Permite acceder a la información del cliente al que pertenece el usuario.",
    )

    def __repr__(self):
        """
        Representación en cadena del objeto User.
        Returns:
            str: Representación en cadena del usuario.
        """
        return f"<User {self.username}>"

    def set_password(self, password):
        """
        Establece un hash seguro para la contraseña del usuario.
        Args:
            password (str): La contraseña en texto plano.
        Raises:
            ValueError: Si la contraseña no cumple con los requisitos de seguridad.
        """
        if not validate_password_strength(password):
            raise ValueError("La contraseña no cumple con los requisitos de seguridad.")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """
        Verifica si la contraseña proporcionada coincide con el hash almacenado.
        Args:
            password (str): La contraseña en texto plano a verificar.
        Returns:
            bool: True si la contraseña coincide, False en caso contrario.
        """
        return check_password_hash(self.password_hash, password)

    def is_client_user(self, client_id):
        """
        Verifica si el usuario pertenece a un cliente específico.
        Args:
            client_id (int): El ID del cliente a verificar.
        Returns:
            bool: True si el usuario pertenece al cliente, False en caso contrario.
        """
        return self.client_id == client_id

    def role_name(self):
        """Mostrar el nombre descriptivo del rol"""
        return self.role.description
        # or return self.role.name

    def has_permission(self, permission_name, action_name, client_id=None):
        """
        Verifica si el usuario tiene un permiso específico y opcionalmente dentro de un cliente específico.
        Args:
            permission_name (str): Nombre del permiso a verificar (ej: 'full_management').
            action_name (str): Nombre de la acción a verificar (ej: 'create').
            client_id (int, optional): ID del cliente para verificar el permiso dentro de ese cliente. Defaults to None.
        Returns:
            bool: True si el usuario tiene el permiso y la acción especificados, False en caso contrario.
        """
        try:
            perm_enum = PermissionEnum(permission_name)
            action_enum = ActionEnum(action_name)

            # Verificar si el permiso está asignado al rol del usuario
            if perm_enum in ROLE_PERMISSIONS.get(self.role, []):
                # Verificar si la acción está permitida para ese permiso
                if action_enum in PERMISSION_ACTIONS.get(perm_enum, []):
                    if client_id:
                        return self.client_id == client_id or self.is_admin()
                    return True
        except ValueError:
            # Si alguno de los valores no está en las enumeraciones, retornar False
            return False
        return False

    def is_admin(self):
        """
        Verifica si el usuario tiene el rol de administrador.
        Returns:
            bool: True si el usuario tiene el rol de administrador, False en caso contrario.
        """
        return self.role == RoleEnum.ADMINISTRATOR

    def is_reseller(self):
        """
        Verifica si el usuario tiene el rol de reseller.
        Returns:
            bool: True si el usuario tiene el rol de reseller, False en caso contrario.
        """
        return self.role == RoleEnum.RESELLER

    def is_org_manager(self):
        """
        Verifica si es un administrador de organización.
        Returns:
            bool: True si es un administrador de organización, False en caso contrario.
        """
        return self.role == RoleEnum.ORG_ADMIN

    @classmethod
    @lru_cache(maxsize=32)
    def get_by_username(self, username):
        """
        Obtiene un usuario por su nombre de usuario (cacheado).
        Args:
            username (str): Nombre de usuario.
        Returns:
            User or None: El usuario si existe, None en caso contrario.
        """
        return self.query.filter_by(username=username).first()

    @classmethod
    @lru_cache(maxsize=32)
    def get_by_email(self, email):
        """
        Obtiene un usuario por su correo electrónico (cacheado).
        Args:
            email (str): Correo electrónico.
        Returns:
            User or None: El usuario si existe, None en caso contrario.
        """
        return self.query.filter_by(email=email).first()


class Client(db.Model):
    """Modelo que representa a los clientes u organizaciones en el sistema."""

    __tablename__ = "clients"
    id = db.Column(
        db.Integer, primary_key=True, doc="Clave primaria única del cliente."
    )
    name = db.Column(
        db.String(100), nullable=False, doc="Nombre del cliente (String, no nulo)."
    )
    description = db.Column(
        db.String(255),
        doc="Descripción del cliente. Proporciona información adicional sobre el cliente u organización.",
    )
    profile_data = db.Column(
        db.JSON,
        nullable=False,
        default=dict,
        doc="Datos adicionales del cliente (JSON, valor por defecto: diccionario vacío). Permite almacenar información extra específica del cliente.",
    )
    created_at = db.Column(
        db.DateTime, default=datetime.utcnow, doc="Fecha de creación del cliente."
    )
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        doc="Fecha de última actualización del cliente.",
    )
    reseller_package_id = db.Column(
        db.Integer,
        db.ForeignKey("reseller_packages.id"),
        nullable=True,
        doc="ID del paquete de reseller al que pertenece este cliente, si aplica.",
    )

    def __repr__(self):
        return f"<Client {self.name}>"

    def get_reseller_user(self):
        """
        Obtiene el usuario reseller asociado a este cliente, si existe.
        Returns:
            User or None: El usuario reseller si existe, None en caso contrario
        """
        if self.reseller_package:
            return self.reseller_package.user
        return None

    def get_users(self):
        """
        Devuelve los ID de los usuarios asociados a este cliente.
        Returns:
            list: Lista de IDs de usuarios.
        """
        return [user.id for user in self.assigned_users]

    @classmethod
    def get_id_by_name(self, name):
        """
        Busca el ID de un cliente por su nombre.

        Args:
            name (str): Nombre del cliente a buscar

        Returns:
            int or None: ID del cliente si existe, None en caso contrario
        """
        client = self.query.filter_by(name=name).first()
        return client.id if client else None

    def __repr__(self):
        return f"Client(id={self.id})"


class ResellerPackage(db.Model):
    """Modelo que representa las asignaciones a un usuario reseller. Define los límites y características a los que tiene acceso."""

    __tablename__ = "reseller_packages"
    id = db.Column(
        db.Integer,
        primary_key=True,
        doc="Clave primaria única del paquete de reseller.",
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        doc="Relación con el usuario base reseller (user.id)",
    )
    user = db.relationship(
        "User",
        backref=db.backref("reseller_info", uselist=False),
        doc="Relación con el usuario base reseller",
    )
    max_clients = db.Column(
        db.Integer,
        default=5,
        nullable=False,
        doc="Número máximo de clientes permitidos en este paquete de reseller.",
    )
    total_clients = db.Column(
        db.Integer,
        default=0,
        nullable=False,
        doc="Total de clientes asignados hasta el momento a ese reseller.",
    )
    clients = db.relationship(
        "Client",
        backref="reseller_package",
        lazy="dynamic",
        doc="Clientes asignados a este reseller",
    )

    def add_client(self):
        """
        Verifica si el reseller puede crear más clientes.
        Returns:
            bool: True si puede crear más clientes, False en caso contrario.
        """
        return self.total_clients < self.max_clients

    def increase_client(self):
        """
        Incrementa el contador de clientes.
        """
        self.total_clients += 1
        db.session.commit()

    def decrease_client(self):
        """
        Decrementa el contador de clientes.
        """
        if self.total_clients > 0:
            self.total_clients -= 1
            db.session.commit()

    def is_reseller_client(self, client_id):
        """
        Verifica si un cliente pertenece a este reseller.
        Args:
            client_id (int): ID del cliente a verificar
        Returns:
            bool: True si el cliente pertenece a este reseller, False en caso contrario
        """
        return self.clients.filter_by(id=client_id).first() is not None

    def get_available_slots(self):
        """
        Obtiene el número de espacios disponibles para nuevos clientes.
        Returns:
            int: Número de espacios disponibles
        """
        return max(0, self.max_clients - self.total_clients)

    def assign_client(self, client):
        """
        Asigna un cliente a este reseller si hay espacios disponibles.
        Args:
            client (Client): Cliente a asignar
        Returns:
            bool: True si se asignó correctamente, False en caso contrario
        """
        if not self.add_client():
            return False

        client.reseller_package_id = self.id
        self.increase_client()
        return True

    def unassign_client(self, client):
        """
        Desasigna un cliente de este reseller.
        Args:
            client (Client): Cliente a desasignar
        Returns:
            bool: True si se desasignó correctamente, False en caso contrario
        """
        if not self.is_reseller_client(client.id):
            return False

        client.reseller_package_id = None
        self.decrease_client()
        return True

    def get_all_users_clients(self):
        """
        Obtiene el listado de todos los usuarios que son parte de los clientes de este reseller.

        Returns:
            list: Lista de usuarios asociados a los clientes del reseller.
        """
        users = []
        for client in self.clients:
            for user in client.assigned_users:
                users.append(user)
        return users


# Funciones de utilidad adicionales


@lru_cache(maxsize=128)
def check_permission(user_id, permission_name, action_name, client_id=None):
    """
    Verifica permisos de forma centralizada y cacheada.
    Args:
        user_id: (int): ID del usuario
        permission_name (str): Nombre del permiso a verificar (ej: 'full_management')
        action_name (str): Nombre de la acción a verificar (ej: 'create')
        client_id (int): ID de la organización (opcional)

    Returns:
        bool: True si el usuario tiene el permiso, False en caso contrario

    """
    user = User.query.get(user_id)
    if not user:
        return False

    return user.has_permission(permission_name, action_name, client_id)


def verify_user_credentials(username, password):
    """
    Verifica las credenciales de un usuario de forma segura.

    Args:
        username (str): Nombre de usuario
        password (str): Contraseña en texto plano

    Returns:
        User or None: El usuario si las credenciales son correctas, None en caso contrario
    """
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password) and user.active:
        return user
    return None


def verify_user_in_organization(user_id, client_id):
    """
    Verifica si un usuario pertenece a un cliente específico.
    Args:
        user_id (int): ID del usuario
        client_id (int): ID del cliente
    Returns:
        bool: True si el usuario pertenece al cliente, False en caso contrario
    """
    # si no existe
    user = User.query.get(user_id)
    if not user:
        return False

    # Si el usuario es administrador, tiene acceso a todos los clientes
    if user.is_admin():
        return True

    # Si el usuario pertenece directamente al cliente
    if user.client_id == client_id:
        return True

    # Si el usuario es reseller y el cliente está en su paquete
    if user.is_reseller() and hasattr(user, "reseller_info"):
        return user.reseller_info.is_reseller_client(client_id)

    return False


@lru_cache(maxsize=64)
def get_user_roles(user_id):
    """
    Obtiene el rol de un usuario.

    Args:
        user_id (int): ID del usuario

    Returns:
        rol del usuario
    """
    user = User.query.get(user_id)
    return user.role if user else None


def validate_password_strength(password):
    """
    Valida la fortaleza de una contraseña.

    Args:
        password (str): Contraseña a validar

    Returns:
        bool: True si la contraseña cumple con los requisitos, False en caso contrario
    """
    if len(password) < 8:
        return False

    # Verificar si contiene al menos un número
    if not any(c.isdigit() for c in password):
        return False

    # Verificar si contiene al menos una letra mayúscula
    if not any(c.isupper() for c in password):
        return False

    # Verificar si contiene al menos una letra minúscula
    if not any(c.islower() for c in password):
        return False

    # Verificar si contiene al menos un carácter especial
    if not any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?/" for c in password):
        return False

    return True


# gestión de cache para el modelo


# Singleton para la gestión de caché de permisos
class PermissionCache:
    _instance = None
    _timer = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PermissionCache, cls).__new__(cls)
            cls._instance.cache = {}
            cls._instance.user_refs = (
                weakref.WeakValueDictionary()
            )  # Inicializar user_refs
            cls._instance.last_cleanup = time.time()
            cls._instance._schedule_cleanup()
        return cls._instance

    def update_user(self, user):
        self.clear_user_cache(user.id)
        # Actualizar caché con nuevos datos
        permissions = self.get_user_permissions(user.id)
        self.cache[user.id] = {
            "data": permissions,
            "timestamp": time.time(),
            "version": user.updated_at.timestamp(),
        }

    def _schedule_cleanup(self):
        # Cancelar timer existente si hay uno
        if self._timer:
            self._timer.cancel()

        # Programar limpieza cada 30 minutos
        self._timer = Timer(1800, self._cleanup_expired)
        self._timer.daemon = (
            True  # Asegurar que el timer no impida la terminación del programa
        )
        self._timer.start()

    def __del__(self):
        # Asegurar que el timer se cancele cuando se destruye la instancia
        if hasattr(self, "_timer") and self._timer:
            self._timer.cancel()

    def _cleanup_expired(self):
        """Limpia entradas expiradas de la caché (más de 1 hora)"""
        current_time = time.time()
        expired_keys = []

        for user_id, entry in self.cache.items():
            if current_time - entry["timestamp"] > 3600:  # 1 hora
                expired_keys.append(user_id)

        for key in expired_keys:
            del self.cache[key]

        self.last_cleanup = current_time
        self._schedule_cleanup()

    # Método para limpiar recursos al finalizar la aplicación
    @classmethod
    def cleanup_resources(cls):
        if cls._instance and cls._instance._timer:
            cls._instance._timer.cancel()
            cls._instance._timer = None
        if cls._instance:
            cls._instance.cache.clear()
            cls._instance = None

    def clear_user_cache(self, user_id):
        """Limpia la caché de un usuario específico"""
        if user_id in self.cache:
            del self.cache[user_id]

    def clear_all(self):
        """Limpia toda la caché"""
        self.cache.clear()

    def get_user_permissions(self, user_id):
        """Obtiene permisos de usuario con caché y definiciones estáticas"""
        current_time = time.time()
        if (
            user_id in self.cache
            and current_time - self.cache[user_id]["timestamp"] < 300
        ):  # 5 minutos
            return self.cache[user_id]["data"]

        user = User.query.get(user_id)
        if not user:
            return set()

        permissions = set()
        for role in user.roles:
            # Usar definiciones estáticas
            role_enum = RoleEnum(role.name)
            if role_enum in ROLE_PERMISSIONS:
                for perm_enum in ROLE_PERMISSIONS[role_enum]:
                    if perm_enum in PERMISSION_ACTIONS:
                        actions = tuple(
                            action.value for action in PERMISSION_ACTIONS[perm_enum]
                        )
                        permissions.add((perm_enum.value, actions))

        # Almacena en caché y mantiene una referencia débil al usuario
        self.cache[user_id] = {"data": permissions, "timestamp": current_time}
        self.user_refs[user_id] = user
        return permissions


class CacheManager:
    """Gestor centralizado de cachés para la aplicación"""

    _instance = None
    _timer = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CacheManager, cls).__new__(cls)
            cls._instance.last_cleanup = time.time()
            cls._instance._schedule_cleanup()
        return cls._instance

    def _schedule_cleanup(self):
        # Cancelar timer existente si hay uno
        if self._timer:
            self._timer.cancel()

        # Programar limpieza cada 6 horas
        self._timer = Timer(21600, self._cleanup_all_caches)
        self._timer.daemon = True
        self._timer.start()

    def _cleanup_all_caches(self):
        """Limpia todas las cachés de la aplicación"""
        current_time = time.time()

        # Limpiar caché de permisos
        perm_cache = PermissionCache()
        perm_cache._cleanup_expired()

        # Limpiar cachés de funciones con lru_cache
        check_permission.cache_clear()
        get_user_roles.cache_clear()
        User.get_by_username.cache_clear()
        User.get_by_email.cache_clear()

        self.last_cleanup = current_time
        self._schedule_cleanup()

    def __del__(self):
        if hasattr(self, "_timer") and self._timer:
            self._timer.cancel()


# Inicializar el gestor de caché al inicio de la aplicación
def init_cache_manager():
    """Inicializa el gestor de caché de la aplicación"""
    return CacheManager()
