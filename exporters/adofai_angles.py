from __future__ import annotations


def clean_angle(x: float) -> int | float:
    x %= 360.0
    if abs(x - round(x)) < 1e-9:
        return int(round(x)) % 360
    return round(x, 9)


def clean_relative_angle(x: float) -> float:
    """
    Relative angle for generated ADOFAI tiles.
    Avoid exact 0 because it can create awkward/ambiguous U-turn-like geometry.
    """
    v = float(x) % 360.0
    if abs(v) < 1e-9:
        v = 360.0
    return round(v, 9)


def nearest_cardinal_angle(abs_angle: float, step: float = 90.0) -> float:
    step = max(1e-6, float(step))
    return clean_angle(round(float(abs_angle) / step) * step)


def abs_angle_diff(a: float, b: float) -> float:
    return abs((float(a) - float(b) + 180.0) % 360.0 - 180.0)


def final_visual_angle(
    *,
    mode: str,
    prev_abs: float,
    scaled_final_angle: float,
    custom_final_angle: float,
    cardinal_step: float = 90.0,
) -> float:
    """
    Choose the visual final-tile relative angle.

    scaled:
        current mathematically scaled fractional angle.
    straight:
        legacy alias for custom 180. Not exposed in the UI.
    cardinal:
        choose a relative angle that makes the final absolute tile direction snap
        to the nearest cardinal/grid direction.
    horizontal:
        choose a relative angle that makes the final absolute tile direction snap
        to 0° or 180° only.
    custom:
        use user-specified relative angle.
    """
    mode = (mode or "scaled").lower().replace(" ", "_").replace("-", "_")

    if mode in ("straight", "straight_relative"):
        return 180.0

    if mode in ("custom", "custom_relative"):
        return clean_relative_angle(custom_final_angle)

    if mode in ("cardinal", "snap_cardinal", "snap_to_cardinal"):
        scaled_abs = clean_angle(prev_abs + 180.0 - scaled_final_angle)
        desired_abs = nearest_cardinal_angle(scaled_abs, cardinal_step)
        return clean_relative_angle(prev_abs + 180.0 - desired_abs)

    if mode in ("horizontal", "snap_horizontal", "sideways"):
        scaled_abs = clean_angle(prev_abs + 180.0 - scaled_final_angle)
        # Snap only to horizontal directions. 0° = right, 180° = left.
        desired_abs = 0.0 if abs_angle_diff(scaled_abs, 0.0) <= abs_angle_diff(scaled_abs, 180.0) else 180.0
        return clean_relative_angle(prev_abs + 180.0 - desired_abs)

    return float(scaled_final_angle)
