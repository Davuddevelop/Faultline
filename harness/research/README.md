# research/: training tooling for the A / B / C experiment

Research tooling only. It does not change what Teeter measures, and nothing here is experiment data.

- `env.py`: a training environment for `models/quadruped.xml`, using the harness's own model loader, observation layout, push model and fall rule.
- `ppo.py`: a small PPO trainer with parallel CPU rollouts that exports an ONNX brain Teeter can load. The ONNX graph holds the stance and action scale.

```
python research/ppo.py --out brainA.onnx --push-max 0 --steps 400000 --seed 0
```

Status (2026-11-24): the loop was smoke-tested end to end on a short run: train, export, load in Teeter, run. The smoke brain is not a result. Not yet built: perturbation sampling for B and C, and the failure-to-training-start export for C.
