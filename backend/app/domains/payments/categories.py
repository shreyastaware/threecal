"""Razorpay Route business categories offered to hosts.

A curated subset of Razorpay's "Business Category" / "Business Sub-Category"
lists (Route integration guide appendix) relevant to paid appointments.
"""

BUSINESS_CATEGORIES: dict[str, tuple[str, ...]] = {
    "healthcare": (
        "clinic",
        "doctors",
        "health_practitioners_medical_services",
        "dentists_and_orthodontists",
        "ophthalmologists",
        "osteopaths",
        "dietician",
        "fitness",
        "health_coaching",
        "lab",
    ),
    "education": (
        "coaching",
        "professional_courses",
        "elearning",
        "distance_learning",
    ),
    "services": (
        "consulting",
        "professional_services",
        "business_services",
        "legal",
        "debt_marriage_personal_counseling_service",
        "event_planning",
        "interior_design_and_architect",
        "photographic_studio",
        "ad_and_marketing",
    ),
    "it_and_software": (
        "consulting_and_outsourcing",
        "web_development",
        "technical_support",
        "saas",
    ),
}
