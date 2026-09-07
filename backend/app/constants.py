"""Shared constants and enumerations used across the backend."""

EVENT_TYPES = [
    "STATUS_CHANGE",
    "WORK_NOTE",
    "TEAM_TRANSFER",
    "APPROVAL_REQUESTED",
    "APPROVAL_COMPLETED",
    "VENDOR_UPDATE",
    "PROMISED_DATE_SET",
    "PROMISED_DATE_CHANGED",
    "DEPENDENCY_CREATED",
    "DEPENDENCY_COMPLETED",
    "ASSIGNMENT_CHANGE",
    "CUSTOMER_UPDATE",
    "RESOLUTION",
    "REOPENED",
]

TICKET_STATUSES = ["OPEN", "IN_PROGRESS", "PENDING", "ESCALATED", "RESOLVED", "REOPENED"]

PROGRESS_STATES = [
    "NEW",
    "INVESTIGATING",
    "IN_PROGRESS",
    "WAITING_FOR_APPROVAL",
    "WAITING_FOR_VENDOR",
    "WAITING_FOR_CUSTOMER",
    "WAITING_FOR_INTERNAL_TEAM",
    "BLOCKED",
    "TRANSFERRED",
    "SCHEDULED",
    "RESOLUTION_IN_PROGRESS",
    "RESOLVED",
    "REOPENED",
    "DELAYED",
]

DATE_STATUSES = ["ON_TRACK", "AT_RISK", "OVERDUE", "COMPLETED"]

EXPLANATION_STATUSES = ["DRAFT", "PENDING_REVIEW", "APPROVED", "PUBLISHED", "REJECTED"]

ROLES = ["CUSTOMER", "SUPPORT_AGENT", "REVIEWER", "ADMIN"]

REGIONS = [
    "North America",
    "Europe",
    "India",
    "Asia Pacific",
    "Middle East",
    "Latin America",
]

TEAMS = [
    "NA Support",
    "EU Support",
    "India Support",
    "APAC Support",
    "ME Support",
    "LATAM Support",
    "Finance Approval",
    "Security Review",
    "Vendor Operations",
    "Engineering Escalation",
]

VENDORS = [
    "Fabricon Global",
    "PartsUnited Express",
    "Northwind Components",
    "Quanta Electronics",
    "Cerule Systems",
    "Oceana Logistics",
    "Vertex Machinery",
]

CATEGORIES = [
    "Hardware",
    "Software",
    "Billing",
    "Account Management",
    "Networking",
    "Application Support",
]

PRIORITIES = ["P1", "P2", "P3", "P4"]

AUDIT_ACTIONS = [
    "EXPLANATION_GENERATED",
    "EVENT_IMPORTED",
    "STATUS_CHANGED",
    "DEPENDENCY_DETECTED",
    "APPROVAL_DETECTED",
    "VENDOR_UPDATE_DETECTED",
    "DATE_RISK_DETECTED",
    "EXPLANATION_REVIEWED",
    "EXPLANATION_APPROVED",
    "EXPLANATION_REJECTED",
    "ROLLBACK_EXECUTED",
    "EXPLANATION_PUBLISHED",
    "TICKET_IMPORTED",
    "EXPERIMENT_RUN",
]

DEFAULT_RULES_VERSION = "1.0.0"
DEFAULT_MODEL_VERSION = "1.0.0"

BASELINE_MODEL_VERSION = "baseline-1.0.0"