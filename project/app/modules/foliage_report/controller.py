# Python standard library imports
from functools import wraps
import json

# Third party imports
from werkzeug.exceptions import BadRequest, NotFound, Forbidden
from flask.views import MethodView
from flask_jwt_extended import get_jwt, jwt_required
from flask import request, jsonify, Response

# Local application imports
from app.extensions import db
from app.core.controller import check_permission, check_resource_access
from app.core.models import ResellerPackage, RoleEnum
from app.modules.foliage.models import Recommendation

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
