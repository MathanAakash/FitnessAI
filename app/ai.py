from .config import GEMINI_API_KEY, GEMINI_TIP_MODEL, GEMINI_WORKOUT_MODEL

_client = None


def ai_enabled() -> bool:
    return bool(GEMINI_API_KEY)

def _client_or_none():
    global _client
    if not GEMINI_API_KEY:
        return None
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client

def generate(prompt: str, model: str) -> str:
    client = _client_or_none()
    if client is None:
        return ""
    try:
        response = client.models.generate_content(model=model, contents=prompt)
        return (response.text or "").strip()
    except Exception:
        return ""

def demo_workout(name, age, weight, goal, intensity):
    return f"""FITBUDDY 7-DAY WORKOUT PLAN\n\n{name} | Age {age} | {weight} kg | Goal: {goal} | Intensity: {intensity}\n\nDay 1 - Full Body\nWarm-up: 5-10 minutes walking and mobility.\nWorkout: Squats 3x10, wall/incline push-ups 3x10, glute bridges 3x12, plank 3x20 seconds.\nCooldown: 5 minutes easy walking and stretching.\n\nDay 2 - Cardio + Core\nWarm-up: 5-10 minutes.\nWorkout: Brisk walk or cycling 20-30 minutes, dead bug 3x10, bird dog 3x10/side.\nCooldown: Gentle stretching.\n\nDay 3 - Recovery\nEasy walk 15-20 minutes plus light mobility.\n\nDay 4 - Strength\nWarm-up: 5-10 minutes.\nWorkout: Reverse lunges 3x8/side, rows 3x10, hip hinge 3x10, side plank 2x20 seconds/side.\nCooldown: 5 minutes.\n\nDay 5 - Cardio\nWarm-up: 5-10 minutes.\nWorkout: Moderate cardio 20-30 minutes at a comfortable effort.\nCooldown: Easy walking and stretching.\n\nDay 6 - Full Body + Core\nWarm-up: 5-10 minutes.\nWorkout: Sit-to-stand 3x12, push-ups against wall 3x12, calf raises 3x15, plank 3x20 seconds.\nCooldown: 5 minutes.\n\nDay 7 - Rest / Active Recovery\nEasy movement, mobility, hydration and recovery.\n\nSafety: This is general wellness information, not medical advice. Stop for sharp pain or unusual symptoms and seek professional advice when appropriate."""

def workout_plan(name, age, weight, goal, intensity):
    prompt = f"""You are FitBuddy, a general fitness planning assistant. Create a personalized 7-day workout plan.\nName: {name}\nAge: {age}\nWeight: {weight} kg\nGoal: {goal}\nIntensity: {intensity}\n\nReturn Day 1 through Day 7. For every day include Focus, Warm-up, Main workout with exercises and sets/reps or duration, and Cooldown/Recovery. Include at least one recovery/rest day. Keep it conservative and suitable for a general wellness app. Do not diagnose conditions, prescribe treatment, or guarantee results. Add a brief safety note."""
    return generate(prompt, GEMINI_WORKOUT_MODEL) or demo_workout(name, age, weight, goal, intensity)

def nutrition_tip(goal):
    prompt = f"Give one concise, practical nutrition or recovery tip for a general fitness user whose goal is {goal}. Keep it 2-4 sentences. Avoid extreme dieting, medical claims, or diagnosis."
    return generate(prompt, GEMINI_TIP_MODEL) or {
        "weight loss": "Build meals around vegetables, protein, whole-food carbohydrates and adequate water. Focus on sustainable habits rather than extreme restriction.",
        "muscle gain": "Include a protein-rich food in each main meal and eat enough overall to support training and recovery.",
        "general wellness": "Stay hydrated, include a variety of minimally processed foods, and aim for regular meals and consistent sleep.",
        "flexibility": "Support mobility work with adequate hydration and balanced meals containing protein and a variety of fruits and vegetables."
    }.get(goal, "Stay hydrated and choose balanced meals with protein, vegetables and whole-food carbohydrates.")

def revise_plan(original, feedback):
    prompt = f"""Revise this general wellness 7-day workout plan using the user's feedback.\n\nORIGINAL:\n{original}\n\nFEEDBACK:\n{feedback}\n\nReturn a complete Day 1-Day 7 plan, not a patch. Keep recovery days and avoid medical diagnosis or treatment advice."""
    result = generate(prompt, GEMINI_WORKOUT_MODEL)
    return result or f"UPDATED PLAN\n\nFeedback applied: {feedback}\n\n{original}"
