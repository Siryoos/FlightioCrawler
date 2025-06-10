provider_insights = {
    "flights": {
        "AirlineA": {
            "market_share": 25.0,
            "on_time_performance": 92.1,
            "avg_price_deviation": -5.0,
            "customer_satisfaction": 4.2,
            "route_dominance": 0.7,
            "baggage_fee_transparency": 0.9,
            "cancellation_rate_trend": 1.2
        },
        "AirlineB": {
            "market_share": 15.0,
            "on_time_performance": 85.3,
            "avg_price_deviation": 3.0,
            "customer_satisfaction": 3.8,
            "route_dominance": 0.4,
            "baggage_fee_transparency": 0.7,
            "cancellation_rate_trend": 2.5
        }
    },
    "tours": {
        "TourCo": {
            "booking_conversion": 0.12,
            "avg_group_size": 15,
            "seasonal_demand": 0.8,
            "customer_repeat_rate": 0.3,
            "price_competitiveness": 0.9,
            "sustainability_rating": 0.6,
            "local_partnerships": 10,
            "avg_rating_by_category": 4.5
        }
    },
    "hotels": {
        "HotelChainX": {
            "occupancy_rate": 0.75,
            "revpar": 120.0,
            "review_sentiment": 0.85,
            "price_elasticity": 1.1,
            "booking_window_trend": 20,
            "competitor_pricing_position": -0.05,
            "amenity_value_score": 0.8,
            "repeat_guest_percentage": 0.4
        }
    }
}

def get_provider_insights(provider_type=None):
    if provider_type:
        return provider_insights.get(provider_type, {})
    return provider_insights
