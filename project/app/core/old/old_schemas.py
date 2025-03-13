# Third party imports
from marshmallow import Schema, fields, validate, pre_load, ValidationError

# Local application imports
from app.helpers.validators import APIValidator
from app.core.models import RoleEnum, User, ResellerPackage


class UserSchema(Schema):
    """
    Esquema de Marshmallow para el modelo User.
    """

    id = fields.Int(dump_only=True)
    username = fields.Str(
        required=True,
        validate=[
            validate.Length(min=3, max=20),
            validate.Regexp(
                r"^[a-zA-Z0-9_]+$",
                error="Username must contain only letters, numbers, and underscores.",
            ),
        ],
    )
    email = fields.Email(required=True)
    full_name = fields.Str(required=True, validate=validate.Length(min=1, max=128))
    password = fields.Str(
        load_only=True,
        required=True,
        validate=[APIValidator.validate_password_strength()],
    )
    password_confirm = fields.Str(required=False, load_only=True)
    profile_data = fields.Dict(required=False, default=dict)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    active = fields.Bool(dump_only=True)
    role = fields.Str(required=False)
    role_value = fields.Method("get_role_value", dump_only=True)
    client_id = fields.Int(dump_only=False, required=False)
    client_name = fields.Str(required=True)
    role_name = fields.Method("get_role_name", dump_only=True)
    all_clients = fields.Method("get_all_clients", dump_only=True)

    def get_client_name(self, obj):
        return obj.client.name if obj.client else None

    def get_all_clients(self, obj):
        if obj.is_admin():
            # Si el usuario es administrador, devuelve todos los clientes
            return [client.name for client in Client.query.all()]
        elif obj.is_reseller() and hasattr(obj, "reseller_info"):
            # Si el usuario es reseller, devuelve los clientes asociados a su cuenta
            # Si no tiene clientes está vacío y no verifica. OJO
            return "[client.name for client in obj.reseller_info.clients]"
        else:
            # Si el usuario tiene otro rol, devuelve el cliente asignado
            if obj.client:
                return [obj.client.name]
            else:
                return []

    def get_role_name(self, obj):
        return obj.role_name()

    def get_role_value(self, obj):
        return obj.role.value

    def load_password(self, data, **kwargs):
        if "password" in data:
            user = kwargs.get("obj")
            password = data["password"]
            if user and user.check_password(password):
                pass  # Si el usuario y la contraseña son correctos, no hagas nada (o actualiza la contraseña si es necesario)
            else:
                user.set_password(password)
        return data

    @pre_load
    def process_input(self, data, **kwargs):
        if "role" in data:
            # Asegúrate de que el valor del rol sea válido
            if data["role"] not in [role.value for role in RoleEnum]:
                raise ValidationError("Rol inválido")
        return data


class ClientSchema(Schema):
    """
    Esquema de Marshmallow para el modelo Client.
    """

    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    description = fields.Str(required=False, validate=validate.Length(max=255))
    profile_data = fields.Dict(required=False, default=dict)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    reseller_package_id = fields.Int(dump_only=False, required=False)


class ResellerPackageSchema(Schema):
    """
    Esquema de Marshmallow para el modelo ResellerPackage.
    """

    id = fields.Int(dump_only=True)
    user_id = fields.Int(required=True)
    max_clients = fields.Int(required=True, validate=validate.Range(min=1))
    total_clients = fields.Int(dump_only=True)


# Ejemplos de uso en rutas Flask con el decorador validate_form

# Ejemplo de ruteo Flask
# from flask import Flask
# from flask.views import MethodView

# app = Flask(__name__)

# class UserView(MethodView):
#     @APIValidator.validate_form(
#         username=APIValidator.validate_username(),
#         email=APIValidator.validate_email(),
#         full_name=APIValidator.validate_textarea(max_length=128),
#         password=APIValidator.validate_password_strength(),
#         role=APIValidator.validate_radio([role.value for role in RoleEnum])
#     )
#     def post(self):
#         json_data = request.json
#         new_user = User(**json_data)
#         db.session.add(new_user)
#         db.session.commit()
#         return jsonify(UserSchema().dump(new_user)), 201

# app.add_url_rule('/users/', view_func=UserView.as_view('users'))
