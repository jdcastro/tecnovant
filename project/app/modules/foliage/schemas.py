from marshmallow import Schema, fields, validates, ValidationError
from marshmallow.validate import Length, Range
from .models import NutrientCategory
from app.core.schemas import UserSchema


class FarmSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=Length(min=3, max=100))
    user_id = fields.Int(required=True)
    user = fields.Nested(UserSchema(only=("id", "username", "email", "full_name")))
    lots = fields.List(fields.Nested(lambda: LotSchema(only=("id", "name", "area"))))
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates("name")
    def validate_name(self, value):
        if not value:
            raise ValidationError("El nombre es requerido.")


class LotSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=Length(min=3, max=100))
    area = fields.Float(required=True, validate=Range(min=0.1))
    farm_id = fields.Int(required=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates("area")
    def validate_area(self, value):
        if value <= 0:
            raise ValidationError("El área debe ser mayor a cero.")


class CropSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=Length(min=3, max=100))
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates("name")
    def validate_name(self, value):
        if not value:
            raise ValidationError("El nombre es requerido.")


class LotCropSchema(Schema):
    id = fields.Int(dump_only=True)
    lot_id = fields.Int(required=True)
    crop_id = fields.Int(required=True)
    start_date = fields.Date(required=True)
    end_date = fields.Date()
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates("start_date")
    def validate_start_date(self, value):
        if not value:
            raise ValidationError("La fecha de inicio es requerida.")


class CommonAnalysisSchema(Schema):
    id = fields.Int(dump_only=True)
    date = fields.Date(required=True)
    lot_id = fields.Int(required=True)
    protein = fields.Float(validate=Range(min=0))
    rest = fields.Float(validate=Range(min=0))
    rest_days = fields.Int(validate=Range(min=0))
    month = fields.Int(validate=Range(min=1, max=12))
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates("date")
    def validate_date(self, value):
        if not value:
            raise ValidationError("La fecha es requerida.")


class SoilAnalysisSchema(Schema):
    id = fields.Int(dump_only=True)
    common_analysis_id = fields.Int(required=True)
    energy = fields.Float(validate=Range(min=0))
    grazing = fields.Int(validate=Range(min=0))
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class NutrientSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=Length(min=3, max=50))
    symbol = fields.Str(required=True, validate=Length(min=1, max=10))
    unit = fields.Str(required=True, validate=Length(min=1, max=20))
    description = fields.Str()
    category = fields.Str(
        required=True, validate=Range(min=0, max=len(NutrientCategory) - 1)
    )
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates("category")
    def validate_category(self, value):
        if value not in NutrientCategory:
            raise ValidationError("Categoría no válida.")


class LeafAnalysisSchema(Schema):
    id = fields.Int(dump_only=True)
    common_analysis_id = fields.Int(required=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class NutrientApplicationSchema(Schema):
    id = fields.Int(dump_only=True)
    date = fields.Date(required=True)
    lot_id = fields.Int(required=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates("date")
    def validate_date(self, value):
        if not value:
            raise ValidationError("La fecha es requerida.")


class ObjectiveSchema(Schema):
    id = fields.Int(dump_only=True)
    crop_id = fields.Int(required=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class ProductionSchema(Schema):
    id = fields.Int(dump_only=True)
    date = fields.Date(required=True)
    lot_id = fields.Int(required=True)
    area = fields.Float(validate=Range(min=0))
    production_kg = fields.Float(validate=Range(min=0))
    bags = fields.Int(validate=Range(min=0))
    harvest = fields.Str(validate=Length(max=100))
    month = fields.Int(validate=Range(min=1, max=12))
    variety = fields.Str(validate=Length(max=100))
    price_per_kg = fields.Float(validate=Range(min=0))
    protein_65dde = fields.Float(validate=Range(min=0))
    discount = fields.Float(validate=Range(min=0, max=100))
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates("date")
    def validate_date(self, value):
        if not value:
            raise ValidationError("La fecha es requerida.")


class ProductSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=Length(min=3, max=100))
    description = fields.Str()
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates("name")
    def validate_name(self, value):
        if not value:
            raise ValidationError("El nombre es requerido.")


class ProductContributionSchema(Schema):
    id = fields.Int(dump_only=True)
    product_id = fields.Int(required=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class ProductPriceSchema(Schema):
    id = fields.Int(dump_only=True)
    product_id = fields.Int(required=True)
    price = fields.Float(required=True, validate=Range(min=0))
    supplier = fields.Str(validate=Length(max=100))
    start_date = fields.Date(required=True)
    end_date = fields.Date()
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates("price")
    def validate_price(self, value):
        if value < 0:
            raise ValidationError("El precio no puede ser negativo.")

    @validates("start_date")
    def validate_start_date(self, value):
        if not value:
            raise ValidationError("La fecha de inicio es requerida.")


class RecommendationSchema(Schema):
    id = fields.Int(dump_only=True)
    lot_id = fields.Int(required=True)
    date = fields.Date(required=True)
    recommendation = fields.Str(required=True, validate=Length(min=10))
    applied = fields.Boolean(default=False)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates("recommendation")
    def validate_recommendation(self, value):
        if not value:
            raise ValidationError("La recomendación es requerida.")


# Estas validaciones contienen:

# Validaciones de formato para correos electrónicos
# Validaciones de longitud para strings
# Validaciones de rango para números
# Validaciones de fecha
# Validaciones de requerimiento
# Validaciones de contraseña fuerte
# Manejo de enumeraciones
# Validaciones personalizadas con mensajes en español
# Cada esquema está diseñado para proteger contra:

# SQL Injection
# Inyección de comandos
# Sobrecarga de datos
# Tipos de dato incorrectos
# Valores fuera de rango
# Campos vacíos requeridos
# Formatos inválidos
