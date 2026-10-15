from . import auth_workos, campaigns, programs, public, runner, workspace

ROUTERS = (public.router, auth_workos.router, workspace.router, campaigns.router, programs.router, runner.router)
