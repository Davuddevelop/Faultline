"""Teeter control plane.

Holds workspaces, campaigns and results, and hands work to runners on the
customer's machines through a job queue in Postgres. Holds no robot, no policy
and no simulator: those stay with the runner.
"""

__version__ = "0.1.0"
