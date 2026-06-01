# -*- coding: utf-8 -*-
"""
optimizer.py — 예산 제약 스탯 배분 최적화 (Phase 9).
순수 모듈: 표준 라이브러리만 의존. 미분 없는 노이즈 내성 (μ,λ)-진화 전략.
"""
import random as _random

def _project_budget(x, weights, budget):
    """w·x == budget 초평면으로 직교 투영."""
    wdotx = sum(w * xi for w, xi in zip(weights, x))
    wdotw = sum(w * w for w in weights)
    if wdotw == 0:
        return list(x)
    k = (wdotx - budget) / wdotw
    return [xi - k * w for xi, w in zip(x, weights)]

def _feasible(x, weights, budget, bounds, passes=8):
    """경계 클립 + 예산 초평면 재투영 반복."""
    x = list(x)
    for _ in range(passes):
        x = _project_budget(x, weights, budget)
        hit = False
        for i, (lo, hi) in enumerate(bounds):
            if x[i] < lo:
                x[i] = lo; hit = True
            elif x[i] > hi:
                x[i] = hi; hit = True
        if not hit:
            break
    return x

def optimize_allocation(objective, x0, budget, weights=None, bounds=None,
                        iterations=40, population=14, elite=4, seed=0,
                        sigma=None, progress=None):
    n = len(x0)
    weights = list(weights) if weights else [1.0] * n
    if bounds is None:
        bounds = [(0.0, float(budget))] * n
    rng = _random.Random(seed)
    mean = _feasible(x0, weights, budget, bounds)
    if sigma is None:
        scale = sum(abs(v) for v in mean) / max(n, 1)
        sigma = max(1.0, 0.25 * scale)
    evals = [0]
    def ev(x):
        evals[0] += 1
        return objective(x)
    best_x, best_score = list(mean), ev(mean)
    history = [best_score]
    for it in range(iterations):
        cands = []
        for _ in range(population):
            c = [mean[i] + rng.gauss(0, sigma) for i in range(n)]
            c = _feasible(c, weights, budget, bounds)
            cands.append((c, ev(c)))
        cands.sort(key=lambda cs: -cs[1])
        el = cands[:elite]
        mean = _feasible([sum(e[0][i] for e in el) / elite for i in range(n)],
                         weights, budget, bounds)
        if el[0][1] > best_score:
            best_score, best_x = el[0][1], list(el[0][0])
        sigma *= 0.90
        history.append(el[0][1])
        if progress:
            progress(it + 1, iterations)
    return {"x": mean, "best_x": best_x, "score": best_score,
            "history": history, "evals": evals[0]}
