# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "receivables_recovery"
app_title = "Receivables & Collections"
app_publisher = "Receivables Recovery"
app_description = "Multi-channel collections automation for ERPNext — WhatsApp/SMS reminders, escalation cadence, and dispute tracking built on top of Dunning."
app_email = "support@example.com"
app_license = "MIT"

# Apps
app_include_js = []
app_include_css = []

# Fixtures
# Custom fields, roles, workspace, and notifications are imported via
# the after_install hook (see install.py) for immediate availability.
# The fixtures below are for bench export-fixtures / bench import-fixtures.
fixtures = [
    {"dt": "Custom Field", "filters": [["dt", "in", ["Dunning", "Customer"]]]},
    {"dt": "Role", "filters": [["role_name", "in", ["Collections Manager", "Sales Rep"]]]},
    {"dt": "Report", "filters": [["module", "=", "receivables_and_collections"]]},
]

# Website
website_context = {}

# Scheduler Events
scheduler_events = {
    "daily": [
        "receivables_recovery.tasks.run_collections_cadence",
        "receivables_recovery.tasks.check_broken_promises",
    ],
    "hourly": [
        "receivables_recovery.tasks.retry_failed_messages",
    ],
}

# After Install
after_install = "receivables_recovery.install.after_install"

# Before Uninstall
before_uninstall = "receivables_recovery.install.before_uninstall"

# Page JS
doc_events = {
    "Dunning": {
        "validate": "receivables_recovery.api.validate_dunning",
    }
}

# Permissions
permission_query_conditions = {
    "Dunning": "receivables_recovery.api.get_permission_query_conditions_for_dunning",
}

has_permission = {
    "Dunning": "receivables_recovery.api.has_dunning_permission",
}
