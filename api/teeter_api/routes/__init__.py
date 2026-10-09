from . import campaigns, programs, public, runner, workspace

ROUTERS = (public.router, workspace.router, campaigns.router, programs.router, runner.router)
