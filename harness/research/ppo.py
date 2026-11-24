"""A small PPO trainer (CPU, parallel rollouts) that exports an ONNX brain.

    python research/ppo.py --out brainA.onnx --push-max 0   --steps 400000 --seed 0
    python research/ppo.py --out brainB.onnx --push-max 4.5 --steps 400000 --seed 0 --init brainA.pt

Rollouts run in worker processes with a numpy copy of the network; updates run
in torch. The ONNX graph contains the stance and action scale, so Teeter's
loader needs nothing else. Research tooling only.
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env import ACTION_SCALE, StandEnv  # noqa: E402

H = 64
_env = None


def _init(push_max, seed):
    global _env
    _env = StandEnv(push_max, seed)


def _mlp(x, W):  # numpy forward: returns actor mean and value
    h = np.tanh(x @ W["a1"] + W["ab1"]); h = np.tanh(h @ W["a2"] + W["ab2"])
    mean = h @ W["a3"] + W["ab3"]
    g = np.tanh(x @ W["c1"] + W["cb1"]); g = np.tanh(g @ W["c2"] + W["cb2"])
    return mean, float((g @ W["c3"] + W["cb3"])[0])


def _rollout(W, log_std, n, seed):
    rng = np.random.default_rng(seed)
    std = np.exp(log_std)
    O, A, LP, R, V, D, T = [], [], [], [], [], [], []
    obs = _env.reset()
    for _ in range(n):
        mean, v = _mlp(obs, W)
        a = mean + std * rng.standard_normal(mean.shape)
        lp = float(-0.5 * np.sum(((a - mean) / std) ** 2 + 2 * log_std + np.log(2 * np.pi)))
        nxt, r, done, timeout = _env.step(a)
        O.append(obs); A.append(a); LP.append(lp); R.append(r); V.append(v); D.append(done)
        T.append(timeout)
        obs = _env.reset() if (done or timeout) else nxt
        if timeout and not done:
            T[-1] = True
    # bootstrap value for the unfinished tail
    _, last_v = _mlp(obs, W)
    falls = int(sum(D))
    return (np.array(O, np.float32), np.array(A, np.float32), np.array(LP, np.float32),
            np.array(R, np.float32), np.array(V, np.float32), np.array(D), np.array(T), last_v, falls)


def build(n_obs, n_act):
    import torch.nn as nn
    actor = nn.Sequential(nn.Linear(n_obs, H), nn.Tanh(), nn.Linear(H, H), nn.Tanh(), nn.Linear(H, n_act))
    critic = nn.Sequential(nn.Linear(n_obs, H), nn.Tanh(), nn.Linear(H, H), nn.Tanh(), nn.Linear(H, 1))
    return actor, critic


def weights(actor, critic):
    a = [p.detach().numpy().astype(np.float64) for p in actor.parameters()]
    c = [p.detach().numpy().astype(np.float64) for p in critic.parameters()]
    return {"a1": a[0].T, "ab1": a[1], "a2": a[2].T, "ab2": a[3], "a3": a[4].T, "ab3": a[5],
            "c1": c[0].T, "cb1": c[1], "c2": c[2].T, "cb2": c[3], "c3": c[4].T, "cb3": c[5]}


def export_onnx(actor, stance, path):
    import onnx
    from onnx import TensorProto, helper
    p = [x.detach().numpy().astype(np.float32) for x in actor.parameters()]
    init = [helper.make_tensor(n, TensorProto.FLOAT, v.shape, v.ravel()) for n, v in [
        ("W1", p[0].T.copy()), ("b1", p[1]), ("W2", p[2].T.copy()), ("b2", p[3]),
        ("W3", p[4].T.copy()), ("b3", p[5]),
        ("lo", np.array(-1, np.float32)), ("hi", np.array(1, np.float32)),
        ("scale", np.full(12, ACTION_SCALE, np.float32)), ("stance", stance.astype(np.float32))]]
    nodes = [helper.make_node("MatMul", ["obs", "W1"], ["m1"]), helper.make_node("Add", ["m1", "b1"], ["z1"]),
             helper.make_node("Tanh", ["z1"], ["h1"]),
             helper.make_node("MatMul", ["h1", "W2"], ["m2"]), helper.make_node("Add", ["m2", "b2"], ["z2"]),
             helper.make_node("Tanh", ["z2"], ["h2"]),
             helper.make_node("MatMul", ["h2", "W3"], ["m3"]), helper.make_node("Add", ["m3", "b3"], ["mean"]),
             helper.make_node("Clip", ["mean", "lo", "hi"], ["a"]),
             helper.make_node("Mul", ["a", "scale"], ["as"]), helper.make_node("Add", ["as", "stance"], ["action"])]
    g = helper.make_graph(nodes, "brain", [helper.make_tensor_value_info("obs", TensorProto.FLOAT, ["batch", 30])],
                          [helper.make_tensor_value_info("action", TensorProto.FLOAT, ["batch", 12])], init)
    m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)]); m.ir_version = 10
    onnx.save(m, path)


def main():
    import torch
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--push-max", type=float, default=0.0)
    ap.add_argument("--steps", type=int, default=400_000); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--init", help="start from a saved .pt (brain A) instead of from scratch")
    ap.add_argument("--workers", type=int, default=4); ap.add_argument("--batch", type=int, default=8192)
    a = ap.parse_args()
    torch.manual_seed(a.seed); torch.set_num_threads(1)
    probe = StandEnv(0.0, 0)
    actor, critic = build(probe.n_obs, probe.n_act)
    log_std = torch.nn.Parameter(torch.full((probe.n_act,), -1.0))
    if a.init:
        ck = torch.load(a.init)
        actor.load_state_dict(ck["actor"]); critic.load_state_dict(ck["critic"]); log_std.data = ck["log_std"]
    opt = torch.optim.Adam(list(actor.parameters()) + list(critic.parameters()) + [log_std], lr=3e-4)
    per = a.batch // a.workers
    done_steps = 0; it = 0
    with ProcessPoolExecutor(a.workers, initializer=_init, initargs=(a.push_max, a.seed * 1000)) as ex:
        while done_steps < a.steps:
            W = weights(actor, critic); ls = log_std.detach().numpy().astype(np.float64)
            futs = [ex.submit(_rollout, W, ls, per, a.seed * 100000 + it * 10 + i) for i in range(a.workers)]
            outs = [f.result() for f in futs]
            obs_l, act_l, lp_l, adv_l, ret_l = [], [], [], [], []
            falls = 0
            for O, A, LP, R, V, D, T, lastv, f in outs:
                falls += f
                adv = np.zeros(len(R), np.float32); last = 0.0; nv = lastv
                for t in reversed(range(len(R))):
                    end = D[t] or T[t]
                    nextv = 0.0 if D[t] else (V[t + 1] if (t + 1 < len(R) and not T[t]) else (nv if not T[t] else V[t]))
                    delta = R[t] + 0.99 * nextv - V[t]
                    last = delta + 0.99 * 0.95 * (0.0 if end else last)
                    adv[t] = last
                obs_l.append(O); act_l.append(A); lp_l.append(LP); adv_l.append(adv); ret_l.append(adv + V)
            O = torch.tensor(np.concatenate(obs_l)); A = torch.tensor(np.concatenate(act_l))
            LP0 = torch.tensor(np.concatenate(lp_l)); ADV = torch.tensor(np.concatenate(adv_l))
            RET = torch.tensor(np.concatenate(ret_l)); ADV = (ADV - ADV.mean()) / (ADV.std() + 1e-8)
            n = len(O)
            for _ in range(8):
                perm = torch.randperm(n)
                for s in range(0, n, 2048):
                    ix = perm[s:s + 2048]
                    mean = actor(O[ix]); std = log_std.exp()
                    lp = (-0.5 * (((A[ix] - mean) / std) ** 2 + 2 * log_std + np.log(2 * np.pi))).sum(1)
                    ratio = (lp - LP0[ix]).exp()
                    pl = -torch.min(ratio * ADV[ix], ratio.clamp(0.8, 1.2) * ADV[ix]).mean()
                    vl = ((critic(O[ix]).squeeze(1) - RET[ix]) ** 2).mean()
                    loss = pl + 0.5 * vl
                    opt.zero_grad(); loss.backward(); opt.step()
            done_steps += n; it += 1
            mean_r = float(np.mean(np.concatenate([o[3] for o in outs])))
            print(f"it {it:3d}  steps {done_steps:8d}  mean reward/step {mean_r:6.3f}  falls in batch {falls}", flush=True)
    out = Path(a.out)
    torch.save({"actor": actor.state_dict(), "critic": critic.state_dict(), "log_std": log_std.data}, out.with_suffix(".pt"))
    export_onnx(actor, probe.stance, str(out))
    print("wrote", out, "and", out.with_suffix(".pt"))


if __name__ == "__main__":
    main()
