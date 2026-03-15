"""
Recommendation layer configuration.

Weights for recommendation signals (MVP: favorites only).
Future: WEIGHT_ML_SIMILARITY, WEIGHT_PROMOTED.
"""

# User favorited this plate
WEIGHT_PLATE_FAVORITED = 10

# User favorited this restaurant (all plates from that restaurant get this)
WEIGHT_RESTAURANT_FAVORITED = 5

# score >= threshold => is_recommended
RECOMMENDATION_THRESHOLD = 5
