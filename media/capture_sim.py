"""Capture real simulation geometry for the ad.

Mirrors runner.py's loop — 50 Hz control over the model's 2 ms step, the push
spread over a 0.05 s window on the base body — but records body positions per
control step, which Trajectory does not carry. Run from harness/.

Sanity check when you run it: the minimal case must breach 35 deg at 1.26 s,
matching first_t for mode 1 in assets/data/campaign.json. If it does not, the
model, the policy or the perturbation has changed and the ad is out of date.
"""
import json, os, numpy as np, mujoco
from faultline.model import load as load_model
from faultline.policies import StandPolicy

robot = load_model('models/quadruped.xml')
names = [mujoco.mj_id2name(robot.model, mujoco.mjtObj.mjOBJ_BODY, i)
         for i in range(robot.model.nbody)]

def run(push_ns, dur=5.0, hz=50.0, push_t=1.0):
    m = mujoco.MjModel.from_xml_path('models/quadruped.xml')
    d = mujoco.MjData(m)
    mujoco.mj_resetDataKeyframe(m, d, 0) if m.nkey else mujoco.mj_resetData(m, d)
    pol = StandPolicy(d.qpos[robot.qpos_adr].copy()); pol.reset(0)
    sub = max(1, round((1.0 / hz) / m.opt.timestep))
    win, f = 0.05, np.zeros(6)
    if push_ns: f[:3] = [push_ns / win, 0.0, 0.0]
    xs, tilt = [], []
    for k in range(int(dur * hz)):
        t = k / hz
        d.ctrl[:] = pol.act(np.zeros(1), t)
        d.xfrc_applied[robot.base_body_id] = f if (push_ns and push_t <= t < push_t + win) else 0.0
        for _ in range(sub): mujoco.mj_step(m, d)
        R = d.xmat[robot.base_body_id].reshape(3, 3)
        tilt.append(float(np.degrees(np.arccos(np.clip(R[2, 2], -1, 1)))))
        xs.append([[round(float(v), 4) for v in d.xpos[i]] for i in range(m.nbody)])
    return xs, tilt

out = {'names': names, 'parents': [int(x) for x in robot.model.body_parentid],
       'hz': 50, 'runs': {}}
for label, push in (('nominal', 0.0), ('minimal', 7.875)):
    xs, ti = run(push)
    breach = next((i / 50 for i, v in enumerate(ti) if v > 35), None)
    print(f'{label:8s} push={push:6.3f} N.s  peak tilt {max(ti):6.2f} deg  breach {breach}')
    out['runs'][label] = {'push_ns': push, 'xpos': xs, 'tilt': [round(v, 2) for v in ti]}

json.dump(out, open('../media/sim.json', 'w'))
print('wrote media/sim.json')
