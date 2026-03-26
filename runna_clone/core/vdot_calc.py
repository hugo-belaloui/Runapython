import math

def calculate_vdot_from_race(distance_meters: float, time_seconds: float) -> float:
    """
    Calculates the VDOT value based on Jack Daniels' formula.
    VO2 = (0.182258 * v) + (0.000104 * v**2) - 4.60
    v = velocity in meters per minute (distance_meters / (time_seconds / 60))

    Percent_VO2max = 0.8 + 0.1894393 * math.exp(-0.012778 * time_minutes) + 0.2989558 * math.exp(-0.1932605 * time_minutes)
    VDOT = VO2 / Percent_VO2max
    """
    if distance_meters <= 0 or time_seconds <= 0:
        return 0.0

    time_minutes = time_seconds / 60.0
    velocity_m_per_min = distance_meters / time_minutes

    vo2 = (0.182258 * velocity_m_per_min) + (0.000104 * (velocity_m_per_min ** 2)) - 4.60

    percent_vo2max = 0.8 + 0.1894393 * math.exp(-0.012778 * time_minutes) + 0.2989558 * math.exp(-0.1932605 * time_minutes)

    vdot = vo2 / percent_vo2max
    return vdot

def get_paces_from_vdot(vdot: float) -> dict:
    """
    Calculates the training paces (E, M, T, I, R) in seconds per km
    based on the calculated VDOT.
    """
    if vdot <= 0:
        return {}

    # Approximation formulas for paces (min/km) from VDOT
    # These are simplified estimations matching typical VDOT tables.
    # E pace: ~55-65% VO2max or roughly VDOT-based formula
    # M pace: ~75-84% VO2max
    # T pace: ~83-88% VO2max
    # I pace: ~95-100% VO2max
    # R pace: ~105-110% VO2max

    # Simple approximations (in minutes per km)
    # The higher the VDOT, the faster the pace (lower time)
    # A more precise way is to reverse the VO2 formula for specific percentages

    # Using specific intensity factors relative to VDOT
    def pace_for_intensity(intensity: float) -> int:
        # VO2 = VDOT * intensity
        target_vo2 = vdot * intensity
        # Quadratic formula to solve for velocity: (0.000104)v^2 + (0.182258)v - (4.60 + target_vo2) = 0
        a = 0.000104
        b = 0.182258
        c = -(4.60 + target_vo2)

        discriminant = (b**2) - (4 * a * c)
        if discriminant < 0:
            return 0

        velocity_m_per_min = (-b + math.sqrt(discriminant)) / (2 * a)

        if velocity_m_per_min <= 0:
            return 0

        pace_min_per_km = 1000.0 / velocity_m_per_min
        return int(pace_min_per_km * 60) # returns seconds per km

    # Common intensities for Jack Daniels paces
    # Easy: ~0.65 to 0.75
    # Marathon: ~0.80
    # Threshold: ~0.88
    # Interval: ~0.98
    # Repetition: ~1.05

    return {
        'E': pace_for_intensity(0.70), # Easy (taking middle of range)
        'M': pace_for_intensity(0.80), # Marathon
        'T': pace_for_intensity(0.88), # Threshold
        'I': pace_for_intensity(0.98), # Interval
        'R': pace_for_intensity(1.05)  # Repetition
    }

def format_pace(seconds_per_km: int) -> str:
    """Formats pace in mm:ss/km."""
    if seconds_per_km <= 0:
        return "00:00"
    minutes = seconds_per_km // 60
    seconds = seconds_per_km % 60
    return f"{minutes:02d}:{seconds:02d}"

if __name__ == "__main__":
    # Test
    vdot = calculate_vdot_from_race(5000, 20*60) # 20 min 5k
    print(f"VDOT: {vdot:.1f}")
    paces = get_paces_from_vdot(vdot)
    for p_type, sec in paces.items():
        print(f"{p_type} Pace: {format_pace(sec)}/km")
