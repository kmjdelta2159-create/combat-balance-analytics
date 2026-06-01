"""Spatial System — 격자 좌표 + 거리/사거리 계산. (Phase 4a)

캐릭터 위치는 char['position'] = {'x': int, 'y': int} 또는 None.
순수 데이터 속성(int/str)만 가지므로 pickle/deepcopy 안전 (멀티프로세싱 호환).
4a는 좌표 + 사거리만. 이동/경계 클램프는 4b에서 추가.
"""


class SpatialModule:
    def __init__(self, width=None, height=None, distance_metric="manhattan"):
        # width/height: 격자 크기. 4a 엔진은 미사용 (4a-UI 격자 선언 / 4b 이동 경계용).
        self.width = width
        self.height = height
        # "manhattan" (4방향 거리) | "chebyshev" (8방향 거리)
        self.distance_metric = distance_metric

    def distance(self, pos_a, pos_b):
        """두 위치 dict 간 격자 거리."""
        dx = abs(int(pos_a['x']) - int(pos_b['x']))
        dy = abs(int(pos_a['y']) - int(pos_b['y']))
        if self.distance_metric == "chebyshev":
            return max(dx, dy)
        return dx + dy  # manhattan (기본)

    def in_range(self, attacker, target, attack_range):
        """attacker가 target을 attack_range 내에서 칠 수 있는지 판정.
        attack_range가 None이거나 둘 중 한쪽이라도 위치 미지정이면 True
        (사거리 무제한 = 현행 동작 보존)."""
        if attack_range is None:
            return True
        pa = attacker.get('position')
        pt = target.get('position')
        if not pa or not pt:
            return True
        return self.distance(pa, pt) <= attack_range

    def clamp(self, pos):
        """위치를 격자 경계 [0, width-1] x [0, height-1] 안으로 클램프.
        width/height가 None이면 해당 축은 무제한."""
        x, y = int(pos['x']), int(pos['y'])
        if self.width is not None:
            x = max(0, min(self.width - 1, x))
        if self.height is not None:
            y = max(0, min(self.height - 1, y))
        return {'x': x, 'y': y}

    def step_toward(self, src, dst, steps):
        """src에서 dst 방향으로 정확히 steps 타일 이동한 새 위치를 반환한다.
        장애물 없음 가정. distance_metric에 따라 이동 방식이 다르다:
        - manhattan: 한 스텝에 한 축만 1칸
        - chebyshev: 한 스텝에 x,y 동시 1칸씩(대각 허용)
        결과는 격자 경계로 클램프된다."""
        x, y = int(src['x']), int(src['y'])
        tx, ty = int(dst['x']), int(dst['y'])
        for _ in range(max(0, int(steps))):
            if x == tx and y == ty:
                break
            if self.distance_metric == "chebyshev":
                if x < tx: x += 1
                elif x > tx: x -= 1
                if y < ty: y += 1
                elif y > ty: y -= 1
            else:  # manhattan
                if x != tx:
                    x += 1 if x < tx else -1
                elif y != ty:
                    y += 1 if y < ty else -1
        return self.clamp({'x': x, 'y': y})
