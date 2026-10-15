"""The Teeter runner and command line.

The runner is the half of Teeter that lives on the customer's machines. It
holds the robot, the policy and the simulator, dials out to the control plane
for work, and sends back results. Nothing it is not told about in its own
config file can be run through it.
"""

__version__ = "0.1.0"
