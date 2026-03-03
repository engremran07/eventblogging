"""Backward-compat shim — User/Group admin moved to core.admin."""
# This module existed to register custom User and Group admins.
# Registration now lives in core/admin.py and is auto-discovered by Django.
# This shim exists only to prevent ImportError if anything still imports it.
