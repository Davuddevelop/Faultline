"""Capture real simulation geometry for the site's replay.

Records body positions, the torso's orientation and the feet per control step,
which Trajectory does not carry, through ``runner.run(on_step=...)``: the same
loop that produced the campaign, not a copy of it. The minimal push is read
from the published record, so the replay cannot drift from the campaign it
illustrates. The Teeter site replays this as its opening. Run from harness/.

Sanity check when you run it: the minimal case must breach 35 deg at the first
mode's first_t in assets/data/campaign.json. tools/build_teeter_site.py also
checks this and refuses to build a page that disagrees.
"""
import json
from pathlib import Path

import mujoco

from faultline import Predicate, RunSpec, run
from faultline.config import load_policy
from faultline.model import load as load_model

MODEL = 'models/quadruped.xml'
RECORD = json.loads(Path('../assets/data/campaign.json').read_text())
MINIMAL_PUSH = RECORD['report']['modes'][0]['minimal']['push_impulse_ns']

robot = load_model(MODEL)
names = [mujoco.mj_id2name(robot.model, mujoco.mjtObj.mjOBJ_BODY, i)
         for i in range(robot.model.nbody)]
feet_ids = [mujoco.mj_name2id(robot.model, mujoco.mjtObj.mjOBJ_GEOM, f'{leg}_foot')
            for leg in ('fr', 'fl', 'hr', 'hl')]
policy = load_policy('stand', MODEL)
spec = RunSpec(model_path=MODEL, policy_id=policy.id, duration_s=5.0,
               predicates=(Predicate('tilt_limit', 'tilt_deg', '>', 35.0, grace_s=0.3),))


def capture(push_ns):
    xs, quat, feet = [], [], []

    def keep(t, m, d):
        xs.append([[round(float(v), 4) for v in d.xpos[i]] for i in range(m.nbody)])
        quat.append([round(float(v), 5) for v in d.xquat[robot.base_body_id]])
        feet.append([[round(float(v), 4) for v in d.geom_xpos[g]] for g in feet_ids])

    traj = run(spec.with_perturbation(push_impulse_ns=push_ns), policy, on_step=keep)
    return xs, [round(float(v), 2) for v in traj.tilt_deg], quat, feet


out = {'names': names, 'parents': [int(x) for x in robot.model.body_parentid],
       'hz': 50, 'runs': {}}
for label, push in (('nominal', 0.0), ('minimal', MINIMAL_PUSH)):
    xs, ti, q, ft = capture(push)
    breach = next((i / 50 for i, v in enumerate(ti) if v > 35), None)
    print(f'{label:8s} push={push:6.3f} N.s  peak tilt {max(ti):6.2f} deg  breach {breach}')
    out['runs'][label] = {'push_ns': push, 'xpos': xs, 'tilt': ti, 'quat': q, 'feet': ft}

json.dump(out, open('../media/sim.json', 'w'))
print('wrote media/sim.json')
